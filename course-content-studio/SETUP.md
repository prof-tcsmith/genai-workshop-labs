# Setup — Course Content Studio (Pinecone + Neon)

Course Content Studio is the **applied** track: it grounds answers in a real
**vector database (Pinecone)** and joins authoritative facts from a real
**database (Neon Postgres)**. MCP tools run **in-process** — there's no separate
server to host. So you need three credentials: an **LLM key** (OpenAI, or
Anthropic for chat), a **Pinecone key**, and a **Neon connection string**.

> **Secrets never go in the repo.** You provide them at runtime. Pick whichever
> path fits how you're running the app (below). Embeddings always use OpenAI
> (Anthropic has no embeddings API), so an OpenAI key is needed even if you run
> chat on Claude.

---

## Three ways to provide the secrets

| Where you're running | How to supply secrets |
|---|---|
| **Locally — easiest** | Open the app, then **paste keys into the 🔌 Connections sidebar.** Held in your browser session only; never written to disk or committed. |
| **Locally — set once** | Copy the template and fill it in (it's gitignored): `cp .streamlit/secrets.toml.example .streamlit/secrets.toml` |
| **Streamlit Cloud** | Paste the same values into the app's **Settings → Secrets** (never the repo). |

You can also export them as environment variables (`OPENAI_API_KEY`,
`PINECONE_API_KEY`, `DATABASE_URL`, optional `ANTHROPIC_API_KEY`, `LLM_PROVIDER`).

---

## 1. Pinecone (vector database — free tier)

1. Create a free account at **https://www.pinecone.io/** (the "Starter" tier is free).
2. In the console, open **API Keys** and **create / copy** a key (it looks like `pcsk_...`).
3. That's it — the app **creates the index automatically** on first ingest
   (serverless, cosine, dimension 1536). Default index name: `course-content`.

Provide it as `pinecone_api_key` (sidebar field "Pinecone API key", or the
`pinecone_api_key` secret / `PINECONE_API_KEY` env var).

## 2. Neon (Postgres — free tier)

1. Create a free account at **https://neon.tech/** and a new **Project**.
2. On the project dashboard, copy the **connection string** (Connection Details →
   "Connection string"). It looks like:
   ```
   postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
   ```
   Use the **pooled** ("-pooler") host and keep `?sslmode=require`.
3. **Seed the schema once** so the courses / objectives / rubrics / question-bank
   tables exist. From this folder, with `DATABASE_URL` set to your Neon string:
   ```bash
   psql "$DATABASE_URL" -f postgres-setup/01_schema.sql
   psql "$DATABASE_URL" -f postgres-setup/02_seed.sql
   ```
   (No local `psql`? Paste the contents of those two files into Neon's **SQL
   Editor** in the dashboard and run them. See `postgres-setup/README.md`.)

Provide it as the **Neon Postgres URL** sidebar field (or the `DATABASE_URL`
secret / env var).

## 3. The LLM key (OpenAI, and optionally Anthropic)

- **OpenAI** (required — powers embeddings, and chat by default): `openai_api_key`.
- **Anthropic / Claude** (optional — chat only): set the **Chat provider** to
  *Anthropic (Claude)* and provide `anthropic_api_key`. Embeddings still use OpenAI.

---

## Verify it's wired up

Open the app's home page — **"What's configured"** and the **🔌 Connections**
sidebar show a live ✅ / ⬜ for Chat, OpenAI embeddings, Pinecone, and Postgres.
When all four are ✅, run the labs in order (RAG → Structured lookup → Coupling →
MCP → Capstone). MCP shows as in-process automatically — nothing to configure.

## Cost & safety notes

- All three services have **free tiers** that comfortably cover the workshop.
- Keys pasted in the sidebar live in your browser session only — close the tab and
  they're gone. Nothing is logged or committed.
- Don't paste sensitive/real student data — this is a teaching environment.
