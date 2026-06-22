"""Central config, secrets, connections sidebar, and the participant gate.

Real secret VALUES come only from (in priority order):
  1. **Runtime overrides** pasted into the "🔌 Connections" sidebar — held in this
     browser session only, never stored or committed. This is the zero-setup path
     for running locally: paste your keys, go.
  2. **Streamlit Secrets** — ``.streamlit/secrets.toml`` locally (gitignored) or the
     Cloud "Secrets" UI when deployed.
  3. **Environment variables**.

Nothing sensitive is hard-coded here, and none of it lives in the repo. Secret
values are resolved *dynamically* on each access (see ``__getattr__``) so a key
pasted in the sidebar takes effect immediately, app-wide.
"""
from __future__ import annotations

import hashlib
import os

# --- Static, non-secret config (safe to keep as plain constants) ----------
CHAT_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"   # embeddings are ALWAYS OpenAI (Anthropic has none)
EMBED_DIM = 1536
ANTHROPIC_CHAT_MODEL = "claude-haiku-4-5"


def _secret(name: str, default=None):
    """Resolve a secret: session override → Streamlit Secrets → env var.

    Each source is tried in its own guarded block so a missing script context
    (e.g. the standalone MCP server importing this module) simply falls through
    to Secrets/env instead of erroring.
    """
    # 1) runtime override pasted in the sidebar (only when a session is active)
    try:
        import streamlit as st
        ov = st.session_state.get("_secret_overrides")
        if ov:
            v = ov.get(name)
            if v not in (None, ""):
                return v
    except Exception:
        pass
    # 2) Streamlit Secrets (works without a running script context)
    try:
        import streamlit as st
        v = st.secrets.get(name)  # type: ignore[attr-defined]
        if v is not None:
            return v
    except Exception:
        pass
    # 3) environment — accept the secret name as-is OR its conventional
    #    UPPERCASE form (so `OPENAI_API_KEY` / `PINECONE_API_KEY` / `LLM_PROVIDER`
    #    work as env vars, matching the live-demos/labs convention).
    v = os.environ.get(name)
    if v is None and name != name.upper():
        v = os.environ.get(name.upper())
    return v if v is not None else default


# --- Dynamic secret resolution -------------------------------------------
# These are resolved on every access so a sidebar-pasted value applies at once.
# External code keeps using `config.PINECONE_API_KEY` etc.; `__getattr__` makes
# each such access re-read from _secret().
_DYNAMIC = {
    "OPENAI_API_KEY": lambda: _secret("openai_api_key"),
    "ANTHROPIC_API_KEY": lambda: _secret("anthropic_api_key"),
    "LLM_PROVIDER": lambda: (_secret("llm_provider") or "openai").lower(),
    "PINECONE_API_KEY": lambda: _secret("pinecone_api_key"),
    "PINECONE_INDEX": lambda: _secret("pinecone_index", "course-content"),
    "PG_HOST": lambda: _secret("PG_HOST", "CHANGE-ME.neon.tech"),
    "PG_PORT": lambda: int(_secret("PG_PORT", "5432")),
    "PG_DB": lambda: _secret("PG_DB", "course"),
    "PG_USER": lambda: _secret("PG_USER", "course_app"),
    "PG_PASSWORD": lambda: _secret("PG_PASSWORD", ""),
    "PG_SSLMODE": lambda: _secret("PG_SSLMODE", "require"),
    "DATABASE_URL": lambda: _secret("DATABASE_URL") or _secret("database_url"),
    "MCP_SERVER_URL": lambda: _secret("mcp_server_url", "http://localhost:8000/mcp"),
    "WORKSHOP_PASSPHRASE_SHA256": lambda: _secret("workshop_passphrase_sha256"),
}


def __getattr__(name: str):  # PEP 562 — module-level dynamic attributes
    fn = _DYNAMIC.get(name)
    if fn is not None:
        return fn()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --- Provider selection ---------------------------------------------------
def chat_provider() -> str:
    return "anthropic" if _DYNAMIC["LLM_PROVIDER"]() == "anthropic" else "openai"


def chat_model() -> str:
    return ANTHROPIC_CHAT_MODEL if chat_provider() == "anthropic" else CHAT_MODEL


# --- Postgres -------------------------------------------------------------
def pg_dsn() -> str:
    """A psycopg-compatible connection string (a URL, or libpq keywords)."""
    url = _DYNAMIC["DATABASE_URL"]()
    if url:
        return url
    return (f"host={_DYNAMIC['PG_HOST']()} port={_DYNAMIC['PG_PORT']()} "
            f"dbname={_DYNAMIC['PG_DB']()} user={_DYNAMIC['PG_USER']()} "
            f"password={_DYNAMIC['PG_PASSWORD']()} sslmode={_DYNAMIC['PG_SSLMODE']()}")


def pg_configured() -> bool:
    if _DYNAMIC["DATABASE_URL"]():
        return True
    host = _DYNAMIC["PG_HOST"]()
    return bool(host) and not str(host).startswith("CHANGE-ME")


def configured() -> dict:
    """Quick status used by the home page + sidebar to show what's wired up."""
    chat_ok = bool(_DYNAMIC["ANTHROPIC_API_KEY"]()) if chat_provider() == "anthropic" \
        else bool(_DYNAMIC["OPENAI_API_KEY"]())
    return {
        f"Chat ({chat_provider()})": chat_ok,
        "OpenAI embeddings": bool(_DYNAMIC["OPENAI_API_KEY"]()),
        "Pinecone": bool(_DYNAMIC["PINECONE_API_KEY"]()),
        "Postgres (Neon)": pg_configured(),
    }


# --- Connections sidebar (runtime secret entry for local use) -------------
_CONN_FIELDS = [
    ("openai_api_key", "OpenAI API key", True, "sk-..."),
    ("anthropic_api_key", "Anthropic API key (only for Claude)", True, "sk-ant-..."),
    ("pinecone_api_key", "Pinecone API key", True, "pcsk_..."),
    ("DATABASE_URL", "Neon Postgres URL", True,
     "postgresql://USER:PASS@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require"),
]


def connections_sidebar() -> None:
    """Render the 🔌 Connections panel: paste keys to run locally.

    Values go into ``st.session_state['_secret_overrides']`` and are read by
    :func:`_secret` ahead of Streamlit Secrets / env. Held in this browser session
    only — never written to disk, logged, or committed.
    """
    import streamlit as st

    ov = st.session_state.setdefault("_secret_overrides", {})
    with st.sidebar:
        st.header("🔌 Connections")
        opts = ["openai", "anthropic"]
        cur = _DYNAMIC["LLM_PROVIDER"]()
        prov = st.radio(
            "Chat provider", opts,
            index=opts.index(cur) if cur in opts else 0,
            format_func=lambda p: {"openai": "OpenAI", "anthropic": "Anthropic (Claude)"}[p],
            key="conn_provider",
        )
        ov["llm_provider"] = prov
        st.caption(
            "Running locally? Paste your keys below. Held in this session only — "
            "never stored or committed. On Streamlit Cloud, set these in **Secrets** instead. "
            "Embeddings always use OpenAI (Anthropic has no embeddings API)."
        )
        for key, label, secret, ph in _CONN_FIELDS:
            val = st.text_input(label, type=("password" if secret else "default"),
                                placeholder=ph, key=f"conn_{key}")
            if val and val.strip():
                ov[key] = val.strip()
            else:
                ov.pop(key, None)

        st.divider()
        st.caption("**Status**")
        for label, ok in configured().items():
            st.caption(("✅ " if ok else "⚪️ ") + label)
        st.caption("Need keys? See **SETUP.md** (Pinecone + Neon, free tiers).")


# --- Participant code gate ------------------------------------------------
def gate() -> None:
    """Boot every page: render the Connections sidebar, then enforce the
    participant-code gate **iff** ``workshop_passphrase_sha256`` is configured.

    Call once at the top of every page, AFTER ``st.set_page_config(...)``.
    """
    import streamlit as st
    connections_sidebar()

    h = _DYNAMIC["WORKSHOP_PASSPHRASE_SHA256"]()
    if not h:
        return
    if st.session_state.get("_pass_ok"):
        return
    st.title("🔒 Course Content Studio")
    st.caption("Enter the participant code from the workshop to continue.")
    pw = st.text_input("Participant code", type="password")
    if st.button("Enter"):
        if hashlib.sha256(pw.encode("utf-8")).hexdigest() == str(h).strip().lower():
            st.session_state["_pass_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect code.")
    st.stop()


# --- LLM clients + provider-neutral chat ----------------------------------
def openai_client():
    """A ready OpenAI client, or None if no key is configured.

    Used for **embeddings** (always OpenAI) and for chat when the provider is
    OpenAI. Anthropic chat goes through :func:`chat_text` / :func:`chat_json`.
    """
    key = _DYNAMIC["OPENAI_API_KEY"]()
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key)


def _anthropic_client():
    key = _DYNAMIC["ANTHROPIC_API_KEY"]()
    if not key:
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=key)


def chat_text(system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1000) -> str:
    """Provider-neutral single-turn chat → returns the assistant's text.

    Raises RuntimeError if the active provider isn't configured.
    """
    if chat_provider() == "anthropic":
        client = _anthropic_client()
        if client is None:
            raise RuntimeError("Anthropic is not configured. Paste an Anthropic key (🔌 Connections) or set 'anthropic_api_key' in Secrets.")
        # Anthropic Opus-tier models reject `temperature`; omit it for safety.
        resp = client.messages.create(
            model=ANTHROPIC_CHAT_MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")
    client = openai_client()
    if client is None:
        raise RuntimeError("OpenAI is not configured. Paste an OpenAI key (🔌 Connections) or set 'openai_api_key' in Secrets.")
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def chat_json(system: str, user: str, schema: dict, schema_name: str, *,
              temperature: float = 0.2, max_tokens: int = 4000) -> str:
    """Provider-neutral structured-output chat → returns a raw JSON string.

    Uses OpenAI ``response_format`` (strict json_schema) or Anthropic
    ``output_config.format`` (json_schema). The caller parses + re-validates.
    """
    if chat_provider() == "anthropic":
        client = _anthropic_client()
        if client is None:
            raise RuntimeError("Anthropic is not configured. Paste an Anthropic key (🔌 Connections) or set 'anthropic_api_key' in Secrets.")
        resp = client.messages.create(
            model=ANTHROPIC_CHAT_MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        return "".join(b.text for b in resp.content if b.type == "text") or "{}"
    client = openai_client()
    if client is None:
        raise RuntimeError("OpenAI is not configured. Paste an OpenAI key (🔌 Connections) or set 'openai_api_key' in Secrets.")
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        temperature=temperature,
    )
    return resp.choices[0].message.content or "{}"
