"""Lab · The coupling problem.

Illustrative only — no external calls. The previous two labs wired the app
*directly* to two SDKs (Pinecone via ``lib.vectors``, Postgres via ``lib.db``),
each with its own credentials and its own result shape baked into the app code.
This page makes that coupling visible, shows what breaks as the system grows,
and frames MCP as the fix (built out in the next lab).
"""
import streamlit as st

st.set_page_config(
    page_title="The coupling problem", page_icon="🔗", layout="wide"
)

from lib.config import gate
gate()

from lib.ui import render_deck


st.title("Lab · The coupling problem")
st.caption(
    "Two great labs — but the app is now welded to two SDKs, two credential "
    "sets, and two bespoke result shapes. That tight coupling is what MCP exists "
    "to undo. (This page is illustrative — no external calls.)"
)

render_deck("coupling")


# --- The two hard-wired dependencies --------------------------------------
st.subheader("How the app reaches its capabilities today")
st.markdown(
    "Each capability is imported **directly** into the app. The SDK, the "
    "credentials, and the exact return shape all live *inside* the app process."
)

left, right = st.columns(2)
with left:
    st.markdown("#### 🔎 Vector search → `lib.vectors`")
    st.code(
        "# pages/1_RAG_with_Pinecone.py\n"
        "from lib import vectors          # imports the Pinecone SDK\n"
        "\n"
        "# lib/vectors.py\n"
        "from pinecone import Pinecone, ServerlessSpec\n"
        "pc = Pinecone(api_key=config.PINECONE_API_KEY)   # cred #1\n"
        "hits = vectors.query('lab', text, top_k=5)\n"
        "#   -> [{'id','score','text','metadata'}, ...]   # shape #1",
        language="python",
    )
    st.caption("SDK: `pinecone` · creds: `openai_api_key`, `pinecone_api_key`, `pinecone_index`")
with right:
    st.markdown("#### 🗄️ Structured lookup → `lib.db`")
    st.code(
        "# pages/2_Structured_lookup_PG.py\n"
        "from lib import db               # imports psycopg\n"
        "\n"
        "# lib/db.py\n"
        "import psycopg\n"
        "conn = psycopg.connect(config.pg_dsn())          # cred #2\n"
        "rows = db.list_objectives(course_id)\n"
        "#   -> [{'id','course_id','text','bloom_level'}] # shape #2",
        language="python",
    )
    st.caption("SDK: `psycopg` · creds: `PG_HOST/PG_PORT/PG_DB/PG_USER/PG_PASSWORD/PG_SSLMODE`")

st.markdown(
    "> **Two SDKs, two credential sets, two result shapes — all baked into the "
    "app.** Add a third system and you add a third of everything. The app has to "
    "*know how* to talk to each one."
)

st.divider()


# --- What breaks when... ---------------------------------------------------
st.subheader("What breaks when…")

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.markdown(
            "**➕ You add a 3rd app**\n\n"
            "Another Streamlit app (or a script, or a notebook) needs the same "
            "search + lookup. You re-import both SDKs, copy the glue, and "
            "duplicate **both credential sets** into the new app. Two apps now "
            "drift apart."
        )
    with st.container(border=True):
        st.markdown(
            "**🔁 You swap a tool**\n\n"
            "Move from Pinecone to a different vector DB (or Postgres to a data "
            "warehouse). The SDK, the call signature, and the result shape all "
            "change — so **every app that imported it** has to change too."
        )
with c2:
    with st.container(border=True):
        st.markdown(
            "**🔑 You rotate a credential**\n\n"
            "A key leaks and must be rotated. The secret is embedded in **every "
            "app** that imported the SDK, so you hunt it down in each one. Miss "
            "one and it breaks (or stays exposed)."
        )
    with st.container(border=True):
        st.markdown(
            "**🤖 You let an agent use them**\n\n"
            "An LLM agent can't `import lib.vectors`. It needs a **described, "
            "callable contract** — tool names, typed parameters, predictable "
            "results — over a protocol. Direct SDK imports give it none of that."
        )

st.divider()


# --- The fix: MCP ----------------------------------------------------------
st.subheader("The fix → MCP")
st.markdown(
    "**MCP (Model Context Protocol)** puts both capabilities behind **one "
    "server** that the app talks to over **one standard protocol**:"
)
st.markdown(
    "- The app calls **named tools** (`vector_search`, `course_lookup`) — it no "
    "longer imports `pinecone` or `psycopg`.\n"
    "- **Credentials live in one place** (the server), not scattered across apps.\n"
    "- **Swap a tool** behind the server and every client keeps working — the "
    "contract is unchanged.\n"
    "- **Agents can call the same tools** — MCP is a contract a model already "
    "understands."
)

st.info(
    "Next lab → **MCP — decouple the tools**: the same two capabilities, now "
    "behind one MCP server, called via `lib.mcp_client.call_tool(...)`.",
    icon="▶️",
)
