# Live demos — eight progressive levels

Companion live demos to the *Enterprise AI for IS Faculty* deck. One Streamlit app,
eight levels, each adding one capability and lighting up more of the 7-layer stack.
Participants pick a **provider (OpenAI or Anthropic/Claude)** and paste the workshop
key in the sidebar, then watch.

| Level | Shows | Layers |
|---|---|---|
| 1 · Chatbot | system prompt + one message; no memory, no guardrails | 1, 3 |
| 2 · Memory | session history replayed each turn — see what the model "remembers" | 1, 3 |
| 3 · Guardrails | a narrow support bot with a fail-closed scope check you can watch fire | 1, 7 |
| 4 · Grounding & RAG | model-alone vs. grounded + cited over a small corpus | 4, 6 |
| 5 · Build & break a RAG | sabotage chunking / staleness / permissions and watch quality collapse | 4, 6 |
| 6 · Tools & the agent loop | a real plan→call→observe loop over an MCP-style server (real protocol: `../mcp-lab/`) | 2, 5 |
| 7 · Multi-agent & governance | specialist agents collaborate under RBAC, an approval gate, and an audit log | 2, 7 |
| 8 · Red-team | run injection / exfiltration / unauthorized-write attacks, then enable controls | 7 |

## Provider: OpenAI or Claude
Chat runs on either vendor — choose it in the sidebar, or set `LLM_PROVIDER`
(`openai` | `anthropic`) in `.env`/Secrets. **Embeddings always use OpenAI**
(Anthropic has no embeddings API), so the RAG demos need `OPENAI_API_KEY` set even
when chat runs on Claude — itself a useful "avoid lock-in" lesson.

## Run it (Docker — one command)
```bash
cd live-demos
docker compose up --build
# open http://localhost:8501, pick a provider, and paste the key in the sidebar
```

Stop with `Ctrl-C`; `docker compose down` to remove the container.

## Run it (without Docker)
```bash
cd live-demos
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- The key stays in the browser session only; demos use a cheap model
  (`gpt-4o-mini` or `claude-haiku-4-5`) with capped output and a per-session request limit.
- Retrieval (Levels 4–5) uses an in-memory index over OpenAI embeddings — no external DB.
- See `../live-demos-guide.md` for facilitation notes (what to point out at each level)
  and `../DEPLOY.md` for the broader hosting picture.
