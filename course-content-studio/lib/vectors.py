"""Embeddings + Pinecone vector store helpers for the RAG lab.

This is the thin layer that turns text into vectors (OpenAI embeddings) and
stores / searches them in a real, persistent vector database (Pinecone v5,
serverless). The page and other units import these functions; keep the
signatures stable.

Flow:
    text  --embed-->  vector  --upsert-->  Pinecone (namespace)
    query --embed-->  vector  --query-->   cosine top-k matches
"""
from __future__ import annotations

from lib import config


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings into vectors using the configured OpenAI model.

    Returns a list of vectors aligned with ``texts`` (same order).
    """
    if not texts:
        return []
    client = config.openai_client()
    if client is None:
        raise RuntimeError(
            "OpenAI is not configured. Set 'openai_api_key' in Streamlit "
            "Secrets (or the OPENAI_API_KEY env var)."
        )
    resp = client.embeddings.create(model=config.EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def ensure_index(
    name: str | None = None,
    dim: int = config.EMBED_DIM,
    metric: str = "cosine",
):
    """Return a handle to the Pinecone index ``name``, creating it if missing.

    Uses the modern Pinecone v5 serverless API. Raises a clear ``RuntimeError``
    if no Pinecone API key is configured. ``name`` resolves at call time so a
    sidebar-pasted ``pinecone_index`` takes effect.
    """
    name = name or config.PINECONE_INDEX
    if not config.PINECONE_API_KEY:
        raise RuntimeError(
            "Pinecone is not configured. Set 'pinecone_api_key' in Streamlit "
            "Secrets (or the PINECONE_API_KEY env var)."
        )

    from pinecone import Pinecone, ServerlessSpec

    pc = Pinecone(api_key=config.PINECONE_API_KEY)

    existing = {ix["name"] for ix in pc.list_indexes()}
    if name not in existing:
        pc.create_index(
            name=name,
            dimension=dim,
            metric=metric,
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    return pc.Index(name)


def upsert_chunks(namespace: str, chunks: list[dict]) -> int:
    """Embed and upsert chunks into ``namespace``.

    Each chunk is ``{"id", "text", "metadata"}``. The chunk text is copied into
    the stored vector's metadata as ``text`` so retrieval returns it directly.

    Returns the number of vectors upserted.
    """
    if not chunks:
        return 0

    index = ensure_index()
    vectors = embed([c["text"] for c in chunks])

    payload = []
    for c, values in zip(chunks, vectors):
        meta = dict(c.get("metadata") or {})
        meta["text"] = c["text"]
        payload.append({"id": c["id"], "values": values, "metadata": meta})

    index.upsert(vectors=payload, namespace=namespace)
    return len(payload)


def query(namespace: str, text: str, top_k: int = 5) -> list[dict]:
    """Embed ``text`` and return the top-k nearest chunks (cosine similarity).

    Returns ``[{"id", "score", "text", "metadata"}, ...]`` ordered best-first.
    """
    if not text or not text.strip():
        return []

    index = ensure_index()
    vector = embed([text])[0]
    res = index.query(
        namespace=namespace,
        vector=vector,
        top_k=top_k,
        include_metadata=True,
    )

    matches = res.get("matches", []) if isinstance(res, dict) else res.matches
    out: list[dict] = []
    for m in matches:
        meta = (m.get("metadata") if isinstance(m, dict) else m.metadata) or {}
        out.append({
            "id": m["id"] if isinstance(m, dict) else m.id,
            "score": m["score"] if isinstance(m, dict) else m.score,
            "text": meta.get("text", ""),
            "metadata": meta,
        })
    return out
