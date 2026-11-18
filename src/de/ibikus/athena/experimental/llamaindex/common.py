"""ALTERNATIVE / EXPERIMENTAL — NOT WIRED IN. Shared helpers for the LlamaIndex pipeline."""

from __future__ import annotations

from de.ibikus.athena.core.config.loader import Config, EmbeddingProfile

_SUFFIX = "_llamaindex"

# Athena file types that llama-index-readers-file can extract out of the box.
# Images/audio/video/pptx/xlsx/archives are TODOs here too, mirroring the
# main pipeline's MVP scope (de.ibikus.athena.ingestion.pipeline._REGISTRY).
SUPPORTED_FILE_TYPES = {"text", "markdown", "pdf", "docx"}


def llamaindex_collection_name(base_collection_name: str) -> str:
    """Namespaces LlamaIndex-built collections away from the production ones."""
    return base_collection_name if base_collection_name.endswith(_SUFFIX) else base_collection_name + _SUFFIX


def build_embed_model(profile: EmbeddingProfile):
    """Real HuggingFace embedding model. Tests should inject
    `llama_index.core.embeddings.MockEmbedding(embed_dim=...)` instead to avoid
    a torch/sentence-transformers dependency."""
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    return HuggingFaceEmbedding(model_name=profile.model_name, device=profile.device)


def build_vector_store(config: Config, backend: str, collection_name: str):
    if backend == "chroma":
        import chromadb
        from llama_index.vector_stores.chroma import ChromaVectorStore

        client = chromadb.PersistentClient(path=config.vector_store.chroma.persist_dir)
        chroma_collection = client.get_or_create_collection(collection_name)
        return ChromaVectorStore(chroma_collection=chroma_collection)

    if backend == "qdrant":
        import qdrant_client
        from llama_index.vector_stores.qdrant import QdrantVectorStore

        client = qdrant_client.QdrantClient(url=config.vector_store.qdrant.url)
        return QdrantVectorStore(client=client, collection_name=collection_name)

    raise ValueError(f"Unsupported backend for the LlamaIndex experimental pipeline: {backend}")
