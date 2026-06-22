"""Shared LLM access, key handling, and the passphrase gate for all labs.

Provider-configurable: chat runs on **OpenAI** or **Anthropic (Claude)**, chosen
in the sidebar (or via the ``LLM_PROVIDER`` secret/env var). Embeddings always use
OpenAI — Anthropic has no embeddings API (a real lock-in lesson: chat and
embeddings can be different vendors).

Design goals:
- One key per provider, held in session memory only (never logged or persisted).
- Optional passphrase gate so the public URL is attendee-only.
- Cheap defaults + caps so a shared key can't run up a big bill.
- Pages stay provider-agnostic: ``chat()`` returns the same OpenAI-shaped object
  for both providers (the Anthropic backend translates to/from that shape using
  the official ``anthropic`` SDK).
"""
from __future__ import annotations

import hashlib
import json
import os

import streamlit as st

CHAT_MODEL_DEFAULT = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
ANTHROPIC_CHAT_MODEL = "claude-haiku-4-5"  # cheap/fast peer of gpt-4o-mini
MAX_OUTPUT_TOKENS = 700
SESSION_REQUEST_CAP = 80  # soft per-session cap to protect the shared key

PROVIDERS = {"openai": "OpenAI", "anthropic": "Anthropic (Claude)"}


def _secret(name: str):
    try:
        return st.secrets.get(name)  # type: ignore[attr-defined]
    except Exception:
        return None


# --------------------------------------------------------------- provider choice
def provider() -> str:
    sess = st.session_state.get("llm_provider")
    if sess in PROVIDERS:
        return sess
    cfg = (_secret("llm_provider") or os.environ.get("LLM_PROVIDER") or "openai").lower()
    return cfg if cfg in PROVIDERS else "openai"


def chat_model() -> str:
    return ANTHROPIC_CHAT_MODEL if provider() == "anthropic" else CHAT_MODEL_DEFAULT


# ---------------------------------------------------------------- access gate
def ensure_access() -> None:
    """Require the workshop passphrase before anything else.

    The passphrase is NEVER stored in plaintext. Configure the SHA-256 hash in
    `workshop_passphrase_sha256` (preferred). A plaintext `workshop_passphrase`
    secret is still honored as a fallback for local dev, but don't commit it.
    """
    expected_hash = _secret("workshop_passphrase_sha256")
    expected_plain = _secret("workshop_passphrase")  # local-dev fallback only
    if not expected_hash and not expected_plain:
        return  # gate disabled (no secret set)
    if st.session_state.get("_pass_ok"):
        return
    st.title("🔒 Workshop labs")
    st.write("Enter the workshop passphrase to continue.")
    pw = st.text_input("Passphrase", type="password")
    if st.button("Enter"):
        if expected_hash:
            ok = hashlib.sha256(pw.encode("utf-8")).hexdigest() == str(expected_hash).strip().lower()
        else:
            ok = pw == expected_plain
        if ok:
            st.session_state["_pass_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect passphrase.")
    st.stop()


# ------------------------------------------------------------------- key entry
def default_key(prov: str | None = None) -> str | None:
    """A workshop default key for ``prov``, from Streamlit secrets or env."""
    prov = prov or provider()
    if prov == "anthropic":
        return _secret("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
    return _secret("openai_api_key") or os.environ.get("OPENAI_API_KEY")


def _openai_embed_key() -> str | None:
    pasted = st.session_state.get("user_key_openai")
    return pasted or _secret("openai_api_key") or os.environ.get("OPENAI_API_KEY")


def render_sidebar_key() -> str | None:
    """Render the provider chooser + key field; effective key = entered, else default."""
    st.sidebar.header("🔑 Model provider")
    prov = st.sidebar.radio(
        "Chat provider", list(PROVIDERS), index=list(PROVIDERS).index(provider()),
        format_func=lambda p: PROVIDERS[p],
        help="Switch the chat model between vendors — same lab, no code change. "
             "Embeddings (RAG labs) always use OpenAI; Anthropic has no embeddings API.",
    )
    st.session_state["llm_provider"] = prov

    dflt = default_key(prov)
    label = "Your Anthropic key (optional)" if prov == "anthropic" else "Your OpenAI key (optional)"
    placeholder = "workshop default active — paste to override" if dflt else (
        "sk-ant-..." if prov == "anthropic" else "sk-...")
    sess_key = f"user_key_{prov}"
    entered = st.sidebar.text_input(
        label, type="password", value=st.session_state.get(sess_key, ""),
        placeholder=placeholder,
        help="A workshop default may be configured. Paste your own to use it instead. "
             "Held in this browser session only — never stored or logged.",
    ).strip()
    st.session_state[sess_key] = entered
    eff = entered if entered else dflt
    st.session_state["key"] = eff
    if entered:
        st.sidebar.caption(f"✅ Using **your** {PROVIDERS[prov]} key (entered).")
    elif dflt:
        st.sidebar.caption(f"Using the **workshop default** {PROVIDERS[prov]} key.")
    else:
        st.sidebar.caption("No key yet — paste one above.")
    st.sidebar.caption("Model `%s` · shared key — please be gentle." % chat_model())
    return eff


def api_guard(e: Exception) -> None:
    """Turn an API exception into a friendly message and stop — never a raw traceback."""
    msg = str(e)
    low = msg.lower()
    if any(s in low for s in ("invalid_api_key", "incorrect api key", "authentication", "no api key", "x-api-key")) or "401" in msg:
        st.error("🔑 The API key was rejected (invalid or expired). Paste a valid key in the sidebar.")
    elif any(s in low for s in ("rate limit", "quota", "insufficient_quota", "overloaded")) or "429" in msg:
        st.error("⏳ The key hit a rate or quota limit. Wait a moment, or paste a different key.")
    else:
        st.error(f"Model request failed: {e}")
    st.stop()


openai_guard = api_guard  # back-compat alias (rag.py imported this name)


# --------------------------------------------------------------- client wrapper
class LLMClient:
    def __init__(self, prov, raw, chat_model, embed_raw, embed_model):
        self.provider = prov
        self.raw = raw
        self.chat_model = chat_model
        self.embed_raw = embed_raw
        self.embed_model = embed_model


def _build_chat_raw(prov: str, key: str):
    if prov == "anthropic":
        try:
            from anthropic import Anthropic
        except Exception:
            st.error("The `anthropic` package is not installed. Add `anthropic` to requirements.txt.")
            st.stop()
        return Anthropic(api_key=key)
    try:
        from openai import OpenAI
    except Exception:
        st.error("The `openai` package is not installed in this environment.")
        st.stop()
    return OpenAI(api_key=key)


def _build_embed_raw():
    key = _openai_embed_key()
    if not key:
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None
    return OpenAI(api_key=key)


def get_client():
    key = st.session_state.get("key")
    if not key:
        return None
    prov = provider()
    return LLMClient(prov, _build_chat_raw(prov, key), chat_model(), _build_embed_raw(), EMBED_MODEL)


def boot(page_title: str):
    """Call at the top of every lab page. Returns a ready provider-neutral client.

    Sets page config, enforces the gate, renders the key field, and stops with a
    friendly message until a key is present.
    """
    st.set_page_config(page_title=page_title, page_icon="🧪", layout="wide")
    ensure_access()
    render_sidebar_key()
    client = get_client()
    if client is None:
        st.title(page_title)
        st.info(f"⬅️ Paste the workshop {PROVIDERS[provider()]} key in the sidebar to begin.")
        st.stop()
    return client


def home_setup(page_title: str) -> None:
    st.set_page_config(page_title=page_title, page_icon="🧪", layout="wide")
    ensure_access()
    render_sidebar_key()


# ----------------------------------------------------------------- chat helper
def _bump() -> None:
    n = st.session_state.get("_reqs", 0) + 1
    st.session_state["_reqs"] = n
    if n > SESSION_REQUEST_CAP:
        st.error("Per-session request limit reached (protects the shared key). Refresh the page to reset.")
        st.stop()


# ----------------------------------------------- OpenAI <-> Anthropic shims
class _FnCall:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.type = "function"
        self.function = _FnCall(name, arguments)

    def model_dump(self):
        return {"id": self.id, "type": "function",
                "function": {"name": self.function.name, "arguments": self.function.arguments}}


class _Msg:
    def __init__(self, content, tool_calls):
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls or None


class _Choice:
    def __init__(self, message):
        self.message = message


class _Resp:
    def __init__(self, message):
        self.choices = [_Choice(message)]


def _to_anthropic_messages(messages):
    system_parts, out = [], []
    for m in messages:
        role = m.get("role")
        if role == "system":
            if m.get("content"):
                system_parts.append(m["content"])
        elif role == "tool":
            content = m.get("content")
            out.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id"),
                "content": content if isinstance(content, str) else json.dumps(content),
            }]})
        elif role == "assistant":
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in (m.get("tool_calls") or []):
                fn = tc["function"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                blocks.append({"type": "tool_use", "id": tc["id"], "name": fn["name"], "input": args})
            out.append({"role": "assistant", "content": blocks if blocks else ""})
        else:
            out.append({"role": "user", "content": m.get("content", "")})
    system = "\n\n".join(p for p in system_parts if p) or None
    return system, out


def _tools_to_anthropic(tools):
    out = []
    for t in tools or []:
        fn = t["function"]
        out.append({"name": fn["name"], "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}})})
    return out


def _tool_choice_to_anthropic(tc):
    if tc in (None, "auto"):
        return None
    if tc in ("required", "any"):
        return {"type": "any"}
    if isinstance(tc, dict) and tc.get("type") == "function":
        return {"type": "tool", "name": tc["function"]["name"]}
    return None


def chat(client, messages, model: str | None = None, tools=None, tool_choice=None,
         max_tokens: int = MAX_OUTPUT_TOKENS, temperature: float = 0.2):
    """Non-streaming completion. Returns an OpenAI-shaped response for both providers."""
    _bump()
    if client.provider == "anthropic":
        system, msgs = _to_anthropic_messages(messages)
        kw = dict(model=model or client.chat_model, max_tokens=max_tokens, messages=msgs)
        if system:
            kw["system"] = system
        if tools:
            kw["tools"] = _tools_to_anthropic(tools)
        ac = _tool_choice_to_anthropic(tool_choice)
        if ac:
            kw["tool_choice"] = ac
        try:
            resp = client.raw.messages.create(**kw)
        except Exception as e:
            api_guard(e)
        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [_ToolCall(b.id, b.name, json.dumps(b.input)) for b in resp.content if b.type == "tool_use"]
        return _Resp(_Msg(text, calls))

    kwargs = dict(model=model or client.chat_model, messages=messages,
                  max_tokens=max_tokens, temperature=temperature)
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    try:
        return client.raw.chat.completions.create(**kwargs)
    except Exception as e:  # surface auth/rate errors cleanly to attendees
        api_guard(e)
