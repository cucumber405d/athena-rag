"""ALTERNATIVE / EXPERIMENTAL — NOT WIRED IN.

A LlamaIndex-based stand-in for `de.ibikus.athena.retrieval.context_builder.RetrievalEngine`.
Loads an existing LlamaIndex-built collection (see `ingestion.py` in this
package) and retrieves nodes through LlamaIndex's own retriever, bypassing
Athena's vector/BM25/hybrid/rerank machinery entirely.
"""

from __future__ import annotations

from de.ibikus.athena.core.config.loader import Config
from de.ibikus.athena.experimental.llamaindex.common import (
    build_embed_model,
    build_vector_store,
    llamaindex_collection_name,
)


def load_llamaindex_index(config: Config, collection_name: str, backend: str, embedding_profile_id: str, embed_model=None):
    from llama_index.core import VectorStoreIndex

    embedding_profile = config.embedding_profiles.get(embedding_profile_id)
    embed_model = embed_model or build_embed_model(embedding_profile)
    vector_store = build_vector_store(config, backend, llamaindex_collection_name(collection_name))
    return VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)


def query_with_llamaindex(
    config: Config,
    collection_name: str,
    backend: str,
    embedding_profile_id: str,
    query: str,
    top_k: int = 10,
    embed_model=None,
) -> list[dict]:
    """Runs a plain dense-vector similarity query and returns lightweight result dicts
    (text/score/metadata) — no fusion, reranking or filter pushdown, unlike the
    production RetrievalEngine."""
    index = load_llamaindex_index(config, collection_name, backend, embedding_profile_id, embed_model=embed_model)
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    return [
        {"text": node.node.get_content(), "score": node.score, "metadata": dict(node.node.metadata)}
        for node in nodes
    ]
