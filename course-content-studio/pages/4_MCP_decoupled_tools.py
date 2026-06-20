"""Lab · MCP — decouple the tools.

The same two capabilities from the previous labs (vector search + structured
lookup), now behind ONE MCP server. The app no longer imports ``pinecone`` or
``psycopg`` — it calls named tools over a standard protocol via
``lib.mcp_client.call_tool(...)``. An agent could call these exact same tools.

The MCP server runs locally in Docker for now; if it's unreachable the page
shows the exact build/run commands and stays informative.
"""
import json

import streamlit as st

st.set_page_config(
    page_title="MCP — decouple the tools", page_icon="🔌", layout="wide"
)

from lib.config import gate
gate()

from lib import config
from lib.ui import render_deck
from lib import mcp_client


st.title("Lab · MCP — decouple the tools")
st.caption(
    "Same two capabilities — vector search + structured lookup — but now behind "
    "ONE MCP server, reached over one standard protocol. The app calls named "
    "tools; it no longer imports the SDKs or holds their credentials."
)

render_deck("mcp-real")


# --- The before/after framing ---------------------------------------------
left, right = st.columns(2)
with left:
    st.markdown(
        "#### Before — direct SDK imports\n"
        "- `from lib import vectors` → Pinecone SDK + key\n"
        "- `from lib import db` → psycopg + PG creds\n"
        "- Two SDKs, two cred sets, two shapes **in the app**."
    )
with right:
    st.markdown(
        "#### After — one MCP server\n"
        "- `mcp_client.call_tool('vector_search', …)`\n"
        "- `mcp_client.call_tool('course_lookup', …)`\n"
        "- One protocol; creds + SDKs live **on the server**."
    )

st.markdown(
    f"App is configured to reach the MCP server at "
    f"`{config.MCP_SERVER_URL}` (set via the `mcp_server_url` secret)."
)

st.divider()


# --- Reusable instructions panel (used when the server is unreachable) -----
def _docker_help() -> None:
    st.info(
        "The MCP server isn't reachable yet. It runs **locally in Docker** for "
        "now — build and run it, then this page can call the tools.",
        icon="🐳",
    )
    st.markdown("**1. Build** (run from `course-content-studio/`):")
    st.code(
        "docker build -f mcp-server/Dockerfile -t genai-course-mcp .",
        language="bash",
    )
    st.markdown("**2. Run** (pass the same credentials the labs use):")
    st.code(
        "docker run -p 8000:8000 \\\n"
        "  -e openai_api_key=... \\\n"
        "  -e pinecone_api_key=... \\\n"
        "  -e pinecone_index=course-content \\\n"
        "  -e PG_HOST=... -e PG_PORT=5432 -e PG_DB=course \\\n"
        "  -e PG_USER=... -e PG_PASSWORD=... -e PG_SSLMODE=require \\\n"
        "  genai-course-mcp",
        language="bash",
    )
    st.markdown(
        "**3. Point the app at it** — set the Streamlit secret "
        "`mcp_server_url = \"http://localhost:8000/mcp\"`, then rerun. "
        "Full details are in **`mcp-server/README.md`**."
    )


# --- The server's advertised tool catalog ----------------------------------
st.subheader("🧰 The server's tool catalog")
st.caption(
    "`list_tools()` over MCP — the same catalog a model would see. The app "
    "discovers tools; it doesn't hard-code SDK calls."
)
try:
    tools = mcp_client.list_tools()
    if not tools:
        st.warning("Connected, but the server advertised no tools.")
    for t in tools:
        with st.expander(f"🔧 {t['name']} — {t.get('description', '')[:80]}"):
            st.markdown(t.get("description") or "_(no description)_")
            if t.get("input_schema"):
                st.markdown("**Input schema** (typed parameters):")
                st.json(t["input_schema"])
    server_up = True
except mcp_client.MCPUnavailable:
    server_up = False
    _docker_help()

st.divider()


# --- Call a tool via MCP ---------------------------------------------------
st.subheader("📡 Call a tool via MCP")
st.caption(
    "Pick a tool, fill the arguments, and the app sends an MCP "
    "`call_tool` request — no `import pinecone`, no `import psycopg`."
)

tool = st.radio(
    "Tool",
    ["vector_search", "course_lookup"],
    horizontal=True,
)

if tool == "vector_search":
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        query = st.text_input(
            "query", value="What are the learning objectives about normalization?"
        )
    with c2:
        top_k = st.number_input("top_k", min_value=1, max_value=20, value=5)
    with c3:
        namespace = st.text_input("namespace", value="lab")
    args = {"query": query, "top_k": int(top_k), "namespace": namespace}
else:
    c1, c2, c3 = st.columns(3)
    with c1:
        kind = st.selectbox("kind", ["courses", "objectives", "rubric", "bank"])
    with c2:
        course_id_raw = st.text_input("course_id (int, optional)", value="")
    with c3:
        objective_id_raw = st.text_input("objective_id (int, optional)", value="")
    args = {"kind": kind}
    if course_id_raw.strip():
        try:
            args["course_id"] = int(course_id_raw)
        except ValueError:
            st.warning("course_id must be an integer — ignoring it.")
    if objective_id_raw.strip():
        try:
            args["objective_id"] = int(objective_id_raw)
        except ValueError:
            st.warning("objective_id must be an integer — ignoring it.")

# Show the exact MCP request the app will send.
st.markdown("**➡️ MCP REQUEST** (client → server: `call_tool`)")
st.code(
    "session.call_tool(\n"
    f"    {tool!r},\n"
    f"    {json.dumps(args, indent=4)},\n"
    ")",
    language="python",
)

if st.button("Call tool via MCP", type="primary"):
    try:
        with st.spinner(f"Calling {tool} over MCP at {config.MCP_SERVER_URL}…"):
            result = mcp_client.call_tool(tool, args)
        st.markdown("**⬅️ MCP RESPONSE** (server → client: parsed result)")
        st.json(result)
    except mcp_client.MCPUnavailable as e:
        st.error(str(e))
        _docker_help()
    except Exception as e:  # tool ran but errored (bad args, DB not seeded, …)
        st.error(
            "The MCP call reached the server but the tool failed. Check the "
            "arguments and that the server's credentials/data are set.\n\n"
            f"```\n{e}\n```"
        )

st.divider()


# --- Teaching note ---------------------------------------------------------
with st.expander("What just happened? (and why an agent could do the same)"):
    st.markdown(
        "1. **One protocol** — the app opened an MCP session to "
        f"`{config.MCP_SERVER_URL}` and called a **named tool**. No `pinecone` "
        "or `psycopg` import lives in the app anymore.\n"
        "2. **The server owns the tools** — `vector_search` still uses "
        "`lib.vectors` and `course_lookup` still uses `lib.db`, but that code "
        "(and its credentials) now lives behind the server.\n"
        "3. **Decoupled** — swap a tool's implementation, rotate a credential, "
        "or add a third app, and the **contract is unchanged**.\n"
        "4. **An agent could call these same tools.** `list_tools` advertises "
        "names + typed schemas — exactly what a model needs to call them. The "
        "next step is to **assemble a real app on top of these tools**."
    )
