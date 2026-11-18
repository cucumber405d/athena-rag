"""ChromaDB vector store adapter — the local/dev backend.

chromadb is imported lazily so the rest of Athena can be used/tested without
it installed when the configured backend is Qdrant.

Chroma metadata values must be scalar (str/int/float/bool), so list fields
(``tags``) are stored as a comma-joined string (``tags_csv``) and tag filters
are applied client-side after the Chroma ``where`` pushdown for everything
else — this is the "as far as the backend supports it" pushdown mentioned
in the spec.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from de.ibikus.athena.core.models.chunk import Chunk, ChunkMetadata
from de.ibikus.athena.core.models.retrieval import ScoredChunk
from de.ibikus.athena.stores.vector_gateway import CollectionStats, SearchFilters, VectorStoreGateway

_TAGS_SEP = "|"


def _encode_metadata(metadata: ChunkMetadata) -> dict[str, Any]:
    payload = metadata.model_dump(mode="json")
    tags = payload.pop("tags", [])
    payload["tags_csv"] = _TAGS_SEP.join(tags)
    return payload


def _decode_metadata(payload: dict[str, Any]) -> ChunkMetadata:
    payload = dict(payload)
    tags_csv = payload.pop("tags_csv", "")
    payload["tags"] = [t for t in tags_csv.split(_TAGS_SEP) if t]
    return ChunkMetadata(**payload)


def _build_where(filters: SearchFilters | None) -> dict[str, Any] | None:
    if filters is None:
        return None
    clauses: list[dict[str, Any]] = []
    if filters.domain_id is not None:
        clauses.append({"domain_id": filters.domain_id})
    if filters.document_id is not None:
        clauses.append({"document_id": filters.document_id})
    if filters.document_type is not None:
        clauses.append({"document_type": filters.document_type})
    if filters.language is not None:
        clauses.append({"language": filters.language})
    if filters.access_level is not None:
        clauses.append({"access_level": filters.access_level})
    if filters.deleted is not None:
        clauses.append({"deleted": filters.deleted})
    if filters.source_id is not None:
        clauses.append({"source_id": filters.source_id})
    if filters.file_type is not None:
        clauses.append({"file_type": filters.file_type})
    if filters.page_number is not None:
        clauses.append({"page_number": filters.page_number})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _matches_tags(payload: dict[str, Any], tags: list[str]) -> bool:
    if not tags:
        return True
    existing = set((payload.get("tags_csv") or "").split(_TAGS_SEP))
    return any(tag in existing for tag in tags)


class ChromaVectorStoreAdapter(VectorStoreGateway):
    backend_name = "chroma"

    def __init__(self, persist_dir: str):
        import chromadb

        self._client = chromadb.PersistentClient(path=persist_dir)

    def _collection(self, collection_name: str):
        return self._client.get_or_create_collection(collection_name)

    def create_collection(self, collection_name: str, embedding_dimension: int, distance: str = "cosine") -> None:
        self._client.get_or_create_collection(
            collection_name, metadata={"embedding_dimension": embedding_dimension, "distance": distance}
        )

    def upsert_chunks(self, collection_name: str, chunks: list[Chunk]) -> None:
        collection = self._collection(collection_name)
        collection.upsert(
            ids=[c.metadata.chunk_id for c in chunks],
            embeddings=[c.vector for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[_encode_metadata(c.metadata) for c in chunks],
        )

    def delete_by_document_id(self, collection_name: str, document_id: str, hard: bool = False) -> int:
        collection = self._collection(collection_name)
        matches = collection.get(where={"document_id": document_id}, include=[])
        ids = matches["ids"]
        if not ids:
            return 0
        if hard:
            collection.delete(ids=ids)
        else:
            collection.update(ids=ids, metadatas=[{"deleted": True}] * len(ids))
        return len(ids)

    def delete_by_filter(self, collection_name: str, filters: SearchFilters, hard: bool = False) -> int:
        collection = self._collection(collection_name)
        where = _build_where(filters)
        matches = collection.get(where=where, include=["metadatas"])
        ids = matches["ids"]
        if filters.tags:
            keep = [i for i, meta in zip(ids, matches["metadatas"]) if _matches_tags(meta, filters.tags)]
            ids = keep
        if not ids:
            return 0
        if hard:
            collection.delete(ids=ids)
        else:
            collection.update(ids=ids, metadatas=[{"deleted": True}] * len(ids))
        return len(ids)

    def search_vector(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[ScoredChunk]:
        collection = self._collection(collection_name)
        # Over-fetch when tag filtering must happen client-side.
        fetch_k = top_k * 5 if filters and filters.tags else top_k
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=fetch_k,
            where=_build_where(filters),
            include=["documents", "metadatas", "distances"],
        )
        scored: list[ScoredChunk] = []
        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]
        for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
            if filters and filters.tags and not _matches_tags(meta, filters.tags):
                continue
            score = 1.0 - dist  # cosine distance -> similarity
            scored.append(ScoredChunk(chunk_id=chunk_id, text=doc, metadata=_decode_metadata(meta), score=score))
            if len(scored) >= top_k:
                break
        return scored

    def update_payload(self, collection_name: str, chunk_id: str, payload: dict[str, Any]) -> None:
        collection = self._collection(collection_name)
        if "tags" in payload:
            payload = dict(payload)
            payload["tags_csv"] = _TAGS_SEP.join(payload.pop("tags"))
        collection.update(ids=[chunk_id], metadatas=[payload])

    def get_collection_stats(self, collection_name: str) -> CollectionStats:
        collection = self._collection(collection_name)
        count = collection.count()
        domains, file_types, languages, document_ids = self._aggregate_payload_stats(collection_name)
        dimension = (collection.metadata or {}).get("embedding_dimension")
        return CollectionStats(
            collection_name=collection_name,
            backend=self.backend_name,
            document_count=len(document_ids),
            chunk_count=count,
            vector_dimension=dimension,
            domains=domains,
            file_types=file_types,
            languages=languages,
        )

    def get_domains(self, collection_name: str) -> dict[str, int]:
        domains, _, _, _ = self._aggregate_payload_stats(collection_name)
        return domains

    def _aggregate_payload_stats(
        self, collection_name: str
    ) -> tuple[dict[str, int], dict[str, int], dict[str, int], set[str]]:
        collection = self._collection(collection_name)
        matches = collection.get(include=["metadatas"])
        domains: Counter[str] = Counter()
        file_types: Counter[str] = Counter()
        languages: Counter[str] = Counter()
        document_ids: set[str] = set()
        for meta in matches["metadatas"]:
            if meta.get("domain_id"):
                domains[meta["domain_id"]] += 1
            if meta.get("file_type"):
                file_types[meta["file_type"]] += 1
            if meta.get("language"):
                languages[meta["language"]] += 1
            if meta.get("document_id"):
                document_ids.add(meta["document_id"])
        return dict(domains), dict(file_types), dict(languages), document_ids

    def sample_points(
        self, collection_name: str, limit: int = 20, filters: SearchFilters | None = None
    ) -> list[ScoredChunk]:
        collection = self._collection(collection_name)
        fetch_limit = limit * 5 if filters and filters.tags else limit
        matches = collection.get(where=_build_where(filters), limit=fetch_limit, include=["documents", "metadatas"])
        results = []
        for chunk_id, doc, meta in zip(matches["ids"], matches["documents"], matches["metadatas"]):
            if filters and filters.tags and not _matches_tags(meta, filters.tags):
                continue
            results.append(ScoredChunk(chunk_id=chunk_id, text=doc, metadata=_decode_metadata(meta), score=1.0))
            if len(results) >= limit:
                break
        return results

    def list_collections(self) -> list[str]:
        return [c.name for c in self._client.list_collections()]
