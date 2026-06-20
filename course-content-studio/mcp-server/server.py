"""MCP server for Course Content Studio — the *decoupling* unit.

This re-exposes the app's two existing capabilities as MCP tools so callers
reach them over one standard protocol instead of importing each SDK directly:

  - ``vector_search``  → semantic (cosine) search over ingested course content
                          (was: ``lib.vectors`` → OpenAI embeddings + Pinecone).
  - ``course_lookup``  → exact, structured rows from cloud Postgres
                          (was: ``lib.db`` → psycopg).

No LLM *orchestration* lives here — the server only owns the tools and the
data behind them. The app (or, later, an agent) is the MCP *client*. That clean
client/server split is the whole point: swap a tool, add a third app, or rotate
a credential in ONE place, behind ONE contract.

Credentials are read from environment variables. ``lib.config`` falls back to
env vars whenever Streamlit isn't present (which is the case inside this
container), so the same code that powers the app powers the tools:

  openai_api_key   - OpenAI key (for embeddings)
  pinecone_api_key - Pinecone API key
  pinecone_index   - Pinecone index name (default: course-content)
  PG_HOST          - Postgres host
  PG_PORT          - Postgres port (default: 5432)
  PG_DB            - Postgres database name
  PG_USER          - Postgres user
  PG_PASSWORD      - Postgres password
  PG_SSLMODE       - Postgres sslmode (default: require)

Transport is streamable-http (a long-running service for Docker / Cloud Run),
served on 0.0.0.0:$PORT (default 8000) at the path ``/mcp`` — matching the
existing ``mcp-lab/`` server pattern.

(c) Dr. Tim Smith, 2026
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

PORT = int(os.environ.get("PORT", "8000"))

# host/port for the streamable-http server; "/mcp" endpoint matches mcp-lab.
mcp = FastMCP("course-tools", host="0.0.0.0", port=PORT)


@mcp.tool()
def vector_search(query: str, top_k: int = 5, namespace: str = "lab") -> list:
    """Semantic (cosine) search over ingested course content.

    Returns the top-k nearest chunks as ``[{id, score, text, metadata}, ...]``.
    """
    from lib import vectors
    return vectors.query(namespace, query, top_k)


@mcp.tool()
def course_lookup(
    kind: str,
    course_id: int | None = None,
    objective_id: int | None = None,
):
    """Structured lookup against Postgres.

    ``kind`` is one of:
      - ``courses``    → all courses
      - ``objectives`` → learning objectives for ``course_id``
      - ``rubric``     → the rubric (with criteria) for ``course_id``
      - ``bank``       → question-bank items for ``course_id`` (filter by ``objective_id``)
    """
    from lib import db
    if kind == "courses":
        return db.list_courses()
    if kind == "objectives":
        return db.list_objectives(course_id)
    if kind == "rubric":
        return db.get_rubric(course_id)
    if kind == "bank":
        return db.list_bank(course_id, objective_id)
    return {"error": f"unknown kind {kind!r}"}


if __name__ == "__main__":
    print("(c) Dr. Tim Smith, 2026")
    print(f"course-tools MCP server (streamable-http) on http://0.0.0.0:{PORT}/mcp")
    mcp.run(transport="streamable-http")
