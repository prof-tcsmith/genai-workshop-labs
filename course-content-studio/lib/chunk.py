"""Token-aware text chunking for the RAG lab.

We split long text into overlapping windows so each chunk is small enough to
embed and retrieve cleanly, while the overlap keeps ideas that straddle a
boundary from being lost. Chunking is done by *tokens* (not characters) via
``tiktoken`` so the sizes line up with what the embedding model actually sees.
If ``tiktoken`` isn't installed we fall back to an approximate ~4-chars/token
slice so the lab still runs offline.
"""
from __future__ import annotations


def chunk(text: str, size_tokens: int = 400, overlap: int = 60) -> list[str]:
    """Split ``text`` into overlapping chunks of roughly ``size_tokens`` tokens.

    Args:
        text: the raw document text.
        size_tokens: target window size, in tokens.
        overlap: how many tokens of the previous window to repeat at the start
            of the next one (keeps context across boundaries).

    Returns:
        A list of non-empty chunk strings. Empty/whitespace-only input -> ``[]``.
    """
    if not text or not text.strip():
        return []

    size_tokens = max(1, int(size_tokens))
    overlap = max(0, min(int(overlap), size_tokens - 1))
    step = size_tokens - overlap  # always >= 1 because overlap < size_tokens

    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        toks = enc.encode(text)
        out: list[str] = []
        for start in range(0, len(toks), step):
            piece = enc.decode(toks[start:start + size_tokens]).strip()
            if piece:
                out.append(piece)
            if start + size_tokens >= len(toks):
                break
        return [c for c in out if c.strip()]
    except Exception:
        # Fallback: approximate tokens as ~4 characters each.
        char_size = size_tokens * 4
        char_step = step * 4
        out = []
        for start in range(0, len(text), char_step):
            piece = text[start:start + char_size].strip()
            if piece:
                out.append(piece)
            if start + char_size >= len(text):
                break
        return [c for c in out if c.strip()]
