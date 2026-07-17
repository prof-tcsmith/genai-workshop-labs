# Live demos — the building blocks of GenAI

Companion live demos to the *Enterprise AI for IS Faculty* deck. One Streamlit app
that assembles a GenAI system from a handful of core components — grouped into five
labs, each one breaking the one before it. Participants pick a **provider (OpenAI or
Anthropic/Claude)** and paste the workshop key in the sidebar, then watch.

| Lab | Demo | Shows |
|---|---|---|
| **1 · A model becomes an app** | Chatbot | system prompt + one message; no memory, no guardrails |
| | Memory | session history replayed each turn — see what the model "remembers" |
| **2 · It will answer anything** | Guardrails | a narrow support bot with a fail-closed scope check you can watch fire |
| **3 · Ground it — then break it** | Grounding & RAG | model-alone vs. grounded + cited over a small corpus |
| | Build & break a RAG | sabotage chunking / staleness / permissions and watch quality collapse |
| **4 · It knows, but can't act** | Tools & the agent loop | a real plan→call→observe loop over an MCP-style server (real protocol: `../mcp-lab/`) |
| **5 · Agents over MCP + A2A** | Multi-agent & governance | specialist agents collaborate under RBAC, an approval gate, and an audit log |
| Take-home | Red-team & govern | run injection / exfiltration / unauthorized-write attacks, then enable controls |

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
- Retrieval (the Grounding & RAG demos in Lab 3) uses an in-memory index over OpenAI embeddings — no external DB.
- See `../live-demos-guide.md` for facilitation notes (what to point out at each lab)
  and `../DEPLOY.md` for the broader hosting picture.
