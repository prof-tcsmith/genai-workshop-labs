"""What's next — the bridge from this hand-built pipeline to Session 2 (autonomy & agents)."""
import streamlit as st

st.set_page_config(page_title="What's next — agents", page_icon="🤖", layout="wide")

from lib.config import gate  # noqa: E402  (must come after set_page_config)

gate()

from lib.ui import render_deck  # noqa: E402

st.title("🤖 What's next — autonomy & agentic systems")
st.caption("We just built this whole pipeline by hand. Next session: systems that build pipelines like this themselves.")

render_deck("whats-next", label="📊 Concept slides — autonomy & agents", expanded=True)

st.subheader("We built it by hand")
st.markdown(
    "Across labs 1–5 we assembled a real pipeline — but **we** did the assembling:\n\n"
    "- **We chose the tools** for each step (Pinecone for meaning, Postgres for facts, the LLM to draft).\n"
    "- **We wrote the calls** and wired up the credentials and data shapes ourselves.\n"
    "- **We sequenced the steps**: retrieve → look up → draft → review → export.\n\n"
    "It works — but every new task means a human re-planning the pipeline."
)

st.subheader("What an agent + harness does instead")
st.markdown(
    "Next session we look at **agentic frameworks** and the **harnesses** that run them — software that "
    "wraps a model with the ability to:\n\n"
    "1. **Plan** — break a goal into steps on its own.\n"
    "2. **Select tools** — pick which tool fits each step.\n"
    "3. **Execute** — call tools, pass results forward, multi-step.\n"
    "4. **Check** — verify the result, then retry or escalate if it's wrong.\n\n"
    "Crucially, an agent can call the **same MCP tools** we built in Lab 4 — so the work we just did is "
    "exactly what an autonomous system would orchestrate. This capstone is the *before* picture."
)

with st.expander("ℹ️ A note on frameworks & harnesses"):
    st.markdown(
        "A growing ecosystem of agentic **frameworks and harnesses** exists — both open-source and "
        "commercial (for example, Hermes, OpenClaw, and peers). These are **upcoming-session topics for "
        "comparison, not endorsements**; capabilities and maturity vary widely. What they share is the "
        "**plan → act → observe** loop and a reliance on standard tool contracts like MCP.\n\n"
        "The harder, more important half is **the guardrails that make autonomy safe**: scoped tool "
        "permissions, human-in-the-loop checkpoints, and an activity trail — the same Layer-7 governance "
        "ideas we've used throughout, now applied to a system that acts on its own."
    )
