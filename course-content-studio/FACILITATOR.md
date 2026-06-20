# Course Content Studio — Facilitator Guide

The build-to-application track: foundations → **RAG (Pinecone)** → **structured lookup (Postgres)** →
**the coupling problem** → **decouple with MCP** → **Capstone: Course Content Studio** → **bridge to
Session 2 (agents)**. Everything is Cloud-runnable; the MCP server runs in Docker (local or Cloud Run).

This guide is the pre-flight checklist plus per-lab talking points. The participant-facing version is
**PARTICIPANT.md**.

---

## 1. Setup checklist (do this before the session)

Real values live **only** in Streamlit Secrets (or local `.streamlit/secrets.toml`) — never in the repo.
Use `.streamlit/secrets.toml.example` as your template.

### 1a. OpenAI
- [ ] Have the workshop OpenAI API key → set Secret `openai_api_key`.
- Models are fixed in `lib/config.py`: chat `gpt-4o-mini`, embeddings `text-embedding-3-small` (dim 1536).

### 1b. Pinecone (vector DB) — **public SaaS, works on Cloud**
- [ ] Create a free Pinecone account → **API Keys** → create a key.
- [ ] Set Secret `pinecone_api_key`.
- [ ] (Optional) set `pinecone_index` (default `course-content`). The index is **auto-created** on first
      use as `cosine`, dim `1536`; one namespace per course.

### 1c. Postgres (Neon or Supabase) — **cloud, free tier**
- [ ] Create a free **Neon** (recommended) or **Supabase** Postgres project.
- [ ] Open the provider's **SQL editor** and run, in order:
      1. `postgres-setup/01_schema.sql`  (courses, objectives, rubrics, question_bank, sources)
      2. `postgres-setup/02_seed.sql`    (realistic seed data)
      (See `postgres-setup/README.md` for the psql alternative.)
- [ ] Create a least-privilege app role (read-mostly) and put the connection into Secrets:
      `PG_HOST`, `PG_PORT` (5432), `PG_DB`, `PG_USER`, `PG_PASSWORD`, `PG_SSLMODE = "require"`.
- A managed cloud Postgres means no LAN host and no tunneling — the Cloud app connects directly over SSL.

### 1d. MCP server (decoupled tools)
- [ ] Build/run `mcp-server/` (FastMCP) — locally via Docker, or deploy to **Cloud Run** for a public
      HTTPS endpoint the Cloud app can reach.
- [ ] Set Secret `mcp_server_url` (local example `http://localhost:8000/mcp`; Cloud Run gives an HTTPS URL).
- It wraps the same `vector_search` + `course_lookup` tools used in Labs 3–6.

### 1e. Participant-code gate
- [ ] Pick a participant code; store **only its SHA-256 hash** as Secret `workshop_passphrase_sha256`:
      ```bash
      printf '%s' 'your-code' | shasum -a 256
      ```
- Hand attendees the **plain** code; the app only ever sees the hash. If the Secret is unset, the gate is
  open (handy for local dev).

### 1f. Verify the status panel
- [ ] Open the home page (`app.py`) → **What's configured** shows ✅ for OpenAI / Pinecone / Postgres /
      MCP server. Anything ⬜ means that Secret is missing.

---

## 2. Run order of the labs

The story is cumulative — run them in order. Each page embeds its own concept deck.

| # | Page | Needs |
|---|------|-------|
| 1 | `pages/1_RAG_with_Pinecone.py` | OpenAI + Pinecone |
| 2 | `pages/2_Structured_lookup_PG.py` | Postgres |
| 3 | `pages/3_The_coupling_problem.py` | (framing; reads from 1+2) |
| 4 | `pages/4_MCP_decoupled_tools.py` | MCP server (+ what it wraps) |
| 5 | `pages/5_Course_Content_Studio.py` | OpenAI + Pinecone + Postgres + MCP |
| 6 | `pages/6_Whats_next_agents.py` | (teaser — no services) |

Home (`app.py`) sets the story up front; open it first and walk the **overview-ccs** deck.

---

## 3. Talking points per lab

**Home — the story.** "Today we don't show *a* capability — we build *one tool*, one real piece at a
time, on the same 7-layer stack as the demos. The payoff is a Canvas-importable quiz from your own slides."

**Lab 1 — RAG with Pinecone.** A model alone *guesses*; grounding makes it cite **your** documents.
Contrast with the earlier in-memory toy: this is persistent, scalable, real ANN with cosine scores.
*Aha:* great for unstructured meaning — but it can't return exact, authoritative facts.

**Lab 2 — Structured lookup (Postgres).** Authoritative facts live in a database: objectives, rubrics, a
reusable question bank. *Aha:* now we have both kinds of grounding — but the app is hard-wired to *both*
Pinecone and Postgres.

**Lab 3 — The coupling problem.** Show the app's direct dependence on each tool's SDK, creds, and data
shape. *Aha:* brittle, unshareable, every app reinvents it — we need a standard contract.

**Lab 4 — MCP, decouple the tools.** Re-expose vector search + Postgres lookup as **MCP tools** the app
(or any agent) calls over one protocol. Same power, now decoupled, reusable, governable.

**Lab 5 — Capstone: Course Content Studio.** Upload PDF/PPTX/HTML/MD → retrieve grounding (vector tool) +
structured context (Postgres tool) → draft items (each cited + objective-aligned) → review/approve →
export **Canvas QTI 1.2 .zip**. Emphasize human-in-the-loop: nothing exports until approved.

**Lab 6 — What's next.** "We built this pipeline **by hand** — chose the tools, wrote the calls, sequenced
the steps. Next session: agents + **harnesses** that plan and assemble pipelines like this themselves." Keep
named frameworks (Hermes, OpenClaw, peers) generic — they're upcoming topics, not endorsements.

---

## 4. Deploy to Streamlit Community Cloud

1. Push the repo (public; **no keys inside**) to GitHub.
2. https://share.streamlit.io → **New app** → select the repo, branch `main`.
3. **Main file path:** `course-content-studio/app.py`.
4. **Settings → Secrets** — paste the full block (values only in Cloud, never git):
   ```toml
   openai_api_key = "sk-..."
   pinecone_api_key = "pcsk_..."
   pinecone_index = "course-content"
   PG_HOST = "ep-xxxx.us-east-2.aws.neon.tech"
   PG_PORT = "5432"
   PG_DB   = "course"
   PG_USER = "course_app"
   PG_PASSWORD = "..."
   PG_SSLMODE = "require"
   mcp_server_url = "https://<your-cloud-run-url>/mcp"
   workshop_passphrase_sha256 = "<64-char hash>"
   ```
5. Deploy, then **pre-warm** the app right before the session (free Cloud apps sleep when idle).
6. MCP server: deploy `mcp-server/` to Cloud Run for the public URL, or run it locally via Docker if the
   whole session is local.

**Local Docker dev:** copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`, fill it in
(`secrets.toml` is gitignored), then `streamlit run app.py`.

---

## 5. Pre-session smoke test
- [ ] Home status panel all ✅.
- [ ] Lab 1: ingest a sample doc, run a query, see cosine scores + a grounded answer.
- [ ] Lab 2: list courses/objectives from Postgres.
- [ ] Lab 4: an MCP tool call round-trips.
- [ ] Lab 5: generate a small quiz and **export a QTI .zip**; (optionally) do one real Canvas import.
- [ ] Both teaser/overview decks render (open them full-screen from the page links).
