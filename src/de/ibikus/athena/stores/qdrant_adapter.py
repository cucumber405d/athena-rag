"""Qdrant vector store adapter — the production-like backend.

qdrant_client is imported lazily so the rest of Athena can be used/tested
without it installed when the configured backend is Chroma.
"""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from de.ibikus.athena.core.models.chunk import Chunk
from de.ibikus.athena.core.models.retrieval import ScoredChunk
from de.ibikus.athena.stores.vector_gateway import CollectionStats, SearchFilters, VectorStoreGateway

_POINT_ID_NAMESPACE = uuid.UUID("6f6a6b1e-6e4a-4c0a-9a2f-8f5f7a8b0e01")


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, chunk_id))


def _build_filter(filters: SearchFilters | None):
    from qdrant_client.http import models as qm

    if filters is None:
        return None

    must: list[Any] = []

    def _match(field: str, value: Any) -> None:
        must.append(qm.FieldCondition(key=field, match=qm.MatchValue(value=value)))

    if filters.domain_id is not None:
        _match("domain_id", filters.domain_id)
    if filters.document_id is not None:
        _match("document_id", filters.document_id)
    if filters.document_type is not None:
        _match("document_type", filters.document_type)
    if filters.language is not None:
        _match("language", filters.language)
    if filters.access_level is not None:
        _match("access_level", filters.access_level)
    if filters.deleted is not None:
        _match("deleted", filters.deleted)
    if filters.source_id is not None:
        _match("source_id", filters.source_id)
    if filters.file_type is not None:
        _match("file_type", filters.file_type)
    if filters.page_number is not None:
        _match("page_number", filters.page_number)
    if filters.tags:
        must.append(qm.FieldCondition(key="tags", match=qm.MatchAny(any=filters.tags)))
    if filters.created_after or filters.created_before:
        must.append(
            qm.FieldCondition(
                key="created_at",
                range=qm.DatetimeRange(gte=filters.created_after, lte=filters.created_before),
            )
        )
    if filters.updated_after or filters.updated_before:
        must.append(
            qm.FieldCondition(
                key="updated_at",
                range=qm.DatetimeRange(gte=filters.updated_after, lte=filters.updated_before),
            )
        )

    if not must:
        return None
    return qm.Filter(must=must)


def _payload_to_scored_chunk(chunk_id: str, payload: dict[str, Any], score: float) -> ScoredChunk:
    from de.ibikus.athena.core.models.chunk import ChunkMetadata

    text = payload.pop("_text", "")
    metadata = ChunkMetadata(**payload)
    return ScoredChunk(chunk_id=chunk_id, text=text, metadata=metadata, score=score, source="vector")


class QdrantVectorStoreAdapter(VectorStoreGateway):
    backend_name = "qdrant"

    def __init__(self, url: str, api_key: str | None = None):
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=url, api_key=api_key or None)

    def create_collection(self, collection_name: str, embedding_dimension: int, distance: str = "cosine") -> None:
        from qdrant_client.http import models as qm

        distance_map = {
            "cosine": qm.Distance.COSINE,
            "dot": qm.Distance.DOT,
            "euclid": qm.Distance.EUCLID,
        }
        if self._client.collection_exists(collection_name):
            return
        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=qm.VectorParams(size=embedding_dimension, distance=distance_map[distance]),
        )

    def upsert_chunks(self, collection_name: str, chunks: list[Chunk]) -> None:
        from qdrant_client.http import models as qm

        points = []
        for chunk in chunks:
            payload = chunk.metadata.model_dump(mode="json")
            payload["_text"] = chunk.text
            points.append(
                qm.PointStruct(id=_point_id(chunk.metadata.chunk_id), vector=chunk.vector, payload=payload)
            )
        self._client.upsert(collection_name=collection_name, points=points)

    def delete_by_document_id(self, collection_name: str, document_id: str, hard: bool = False) -> int:
        from qdrant_client.http import models as qm

        query_filter = qm.Filter(
            must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
        )
        count_result = self._client.count(collection_name, count_filter=query_filter, exact=True)
        if hard:
            self._client.delete(collection_name=collection_name, points_selector=qm.FilterSelector(filter=query_filter))
        else:
            self._client.set_payload(
                collection_name=collection_name, payload={"deleted": True}, points=query_filter
            )
        return count_result.count

    def delete_by_filter(self, collection_name: str, filters: SearchFilters, hard: bool = False) -> int:
        from qdrant_client.http import models as qm

        query_filter = _build_filter(filters) or qm.Filter()
        count_result = self._client.count(collection_name, count_filter=query_filter, exact=True)
        if hard:
            self._client.delete(collection_name=collection_name, points_selector=qm.FilterSelector(filter=query_filter))
        else:
            self._client.set_payload(
                collection_name=collection_name, payload={"deleted": True}, points=query_filter
            )
        return count_result.count

    def search_vector(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[ScoredChunk]:
        results = self._client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=_build_filter(filters),
            with_payload=True,
        )
        return [
            _payload_to_scored_chunk(str(point.id), dict(point.payload or {}), point.score) for point in results
        ]

    def update_payload(self, collection_name: str, chunk_id: str, payload: dict[str, Any]) -> None:
        self._client.set_payload(
            collection_name=collection_name, payload=payload, points=[_point_id(chunk_id)]
        )

    def get_collection_stats(self, collection_name: str) -> CollectionStats:
        info = self._client.get_collection(collection_name)
        domains, file_types, languages, document_ids = self._aggregate_payload_stats(collection_name)
        vector_size = None
        try:
            vector_size = info.config.params.vectors.size  # type: ignore[union-attr]
        except AttributeError:
            pass
        return CollectionStats(
            collection_name=collection_name,
            backend=self.backend_name,
            document_count=len(document_ids),
            chunk_count=info.points_count or 0,
            vector_dimension=vector_size,
            domains=domains,
            file_types=file_types,
            languages=languages,
        )

    def get_domains(self, collection_name: str) -> dict[str, int]:
        domains, _, _, _ = self._aggregate_payload_stats(collection_name)
        return domains

    def _aggregate_payload_stats(
        self, collection_name: str, sample_limit: int = 10_000
    ) -> tuple[dict[str, int], dict[str, int], dict[str, int], set[str]]:
        """Approximate aggregation via scroll — good enough for dashboard purposes."""
        domains: Counter[str] = Counter()
        file_types: Counter[str] = Counter()
        languages: Counter[str] = Counter()
        document_ids: set[str] = set()

        next_offset = None
        scanned = 0
        while scanned < sample_limit:
            points, next_offset = self._client.scroll(
                collection_name=collection_name,
                limit=min(1000, sample_limit - scanned),
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )
            if not points:
                break
            for point in points:
                payload = point.payload or {}
                if payload.get("domain_id"):
                    domains[payload["domain_id"]] += 1
                if payload.get("file_type"):
                    file_types[payload["file_type"]] += 1
                if payload.get("language"):
                    languages[payload["language"]] += 1
                if payload.get("document_id"):
                    document_ids.add(payload["document_id"])
            scanned += len(points)
            if next_offset is None:
                break
        return dict(domains), dict(file_types), dict(languages), document_ids

    def sample_points(
        self, collection_name: str, limit: int = 20, filters: SearchFilters | None = None
    ) -> list[ScoredChunk]:
        points, _ = self._client.scroll(
            collection_name=collection_name,
            limit=limit,
            scroll_filter=_build_filter(filters),
            with_payload=True,
            with_vectors=False,
        )
        return [_payload_to_scored_chunk(str(p.id), dict(p.payload or {}), 1.0) for p in points]

    def list_collections(self) -> list[str]:
        return [c.name for c in self._client.get_collections().collections]
