# Course Content Studio — MCP server (the "decoupling" unit)

This server re-exposes the app's two existing capabilities as **MCP tools**, so
the app (and, later, an agent) calls them over **one standard protocol** instead
of importing each SDK directly:

| Tool | What it does | Was (direct import) |
| --- | --- | --- |
| `vector_search(query, top_k=5, namespace="lab")` | Semantic (cosine) search over ingested course content | `lib.vectors` → OpenAI embeddings + Pinecone |
| `course_lookup(kind, course_id=None, objective_id=None)` | Exact, structured rows (`kind` ∈ `{courses, objectives, rubric, bank}`) | `lib.db` → psycopg / Postgres |

No LLM key or orchestration lives here — the server owns only the **tools** and
the **data** behind them. Swap a tool, add a third app, or rotate a credential
in **one place**, behind **one contract**.

Transport is **streamable-http**, served on `0.0.0.0:$PORT` (default `8000`) at
the endpoint path `/mcp`. The MCP server runs **locally via Docker** for now.

## Environment variables (credentials)

The server reads its credentials from the environment (`lib.config` falls back
to env vars when Streamlit is absent — which is the case in this container):

| Var | Purpose | Default |
| --- | --- | --- |
| `openai_api_key` | OpenAI key (for embeddings) | — |
| `pinecone_api_key` | Pinecone API key | — |
| `pinecone_index` | Pinecone index name | `course-content` |
| `PG_HOST` | Postgres host | — |
| `PG_PORT` | Postgres port | `5432` |
| `PG_DB` | Postgres database name | `course` |
| `PG_USER` | Postgres user | `course_app` |
| `PG_PASSWORD` | Postgres password | — |
| `PG_SSLMODE` | Postgres sslmode | `require` |

## Build (run from `course-content-studio/`)

The build context is the **parent** `course-content-studio/` directory so the
image can include the shared `lib/` package:

```bash
docker build -f mcp-server/Dockerfile -t genai-course-mcp .
```

## Run

```bash
docker run -p 8000:8000 \
  -e openai_api_key=...   \
  -e pinecone_api_key=... \
  -e pinecone_index=course-content \
  -e PG_HOST=...   \
  -e PG_PORT=5432  \
  -e PG_DB=course  \
  -e PG_USER=...   \
  -e PG_PASSWORD=... \
  -e PG_SSLMODE=require \
  genai-course-mcp
```

On startup the server prints a `(c) Dr. Tim Smith, 2026` banner and serves at
`http://localhost:8000/mcp`.

## Point the app at it

In the app's Streamlit Secrets (or environment), set:

```toml
mcp_server_url = "http://localhost:8000/mcp"
```

The pages **MCP — decouple the tools** and **The coupling problem** then call
these tools via `lib.mcp_client.call_tool(...)`.
