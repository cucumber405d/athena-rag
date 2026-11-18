"""ALTERNATIVE / EXPERIMENTAL — NOT WIRED IN.

A parallel implementation of ingestion + retrieval built on top of
LlamaIndex, kept side by side with Athena's hand-rolled pipeline
(`de.ibikus.athena.ingestion`, `de.ibikus.athena.retrieval`).

Why this exists: the original spec for Athena named LlamaIndex as the
preferred RAG engine. The active implementation went a different way (direct
loaders/chunkers/BM25/RRF-fusion — see the "Known limitations" section of the
README) to keep full control over the metadata schema and the pluggable
Qdrant/Chroma gateway. This package is a possible future replacement or
point of comparison, not a requirement to use it.

Status: **not imported by** `de.ibikus.athena.ingestion.pipeline`,
`de.ibikus.athena.retrieval.context_builder`, `de.ibikus.athena.cli`, or
`de.ibikus.athena.web`. Nothing here runs unless you call it explicitly.

To try it:
    pip install -e ".[llamaindex]"

Collections created here are written to `<collection_name>_llamaindex` —
a distinct namespace — so they can never collide with or corrupt the
collections used by the production ChunkMetadata-based gateway (LlamaIndex's
own node/document metadata layout is not compatible with
`de.ibikus.athena.core.models.chunk.ChunkMetadata`).
"""
