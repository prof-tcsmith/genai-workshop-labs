"""RAG store for Labs 4-5: a REAL managed vector DB (Pinecone) when configured,
in-memory NumPy otherwise.

Same corpus, same cosine ranking either way — the only thing that changes is
WHERE the vectors live. With a Pinecone key set, the labs upsert into and query
a real, persistent, serverless vector database you can watch in the Pinecone
console. With no key (e.g. the Docker/local run, which has only an OpenAI key),
it transparently falls back to the in-RAM store so the labs always run.

Isolation: each browser SESSION gets its own namespace prefix, and each LAB has
its own bookkeeping (via `scope`), so concurrent participants, the two hosted
instances, AND the two RAG labs within one session never delete each other's
data. One person's "break it" experiment (a stale doc, a RESTRICTED-doc leak)
stays inside their own namespace.

Robustness: anything that goes wrong on the Pinecone side (missing key, plan
limit, network, a create-race, a read-after-write freshness timeout, a query
error mid-session) degrades gracefully to in-RAM — either for the whole session
or, for a mid-session query error, by self-healing the live handle in place.
Labs 6-9 and the Case are untouched; they use shared.store / their own store.
"""
from __future__ import annotations

import os
import time
import uuid

import numpy as np
import streamlit as st

from . import store  # reuse load_corpus, chunk, embed, render_doc_viewer

EMBED_DIM = 1536                 # text-embedding-3-small
DEFAULT_INDEX = "genai-labs"     # dedicated index, separate from course-content-studio
FRESH_TIMEOUT = 15.0             # seconds to wait for read-after-write query freshness
SWEEP_MAX_AGE = 3 * 60 * 60      # reap namespaces older than 3h (workshop hygiene)


def _secret(name: str):
    try:
        return st.secrets.get(name)  # type: ignore[attr-defined]
    except Exception:
        return None


def pinecone_key() -> str | None:
    return _secret("pinecone_api_key") or os.environ.get("PINECONE_API_KEY")


def index_name() -> str:
    return _secret("pinecone_index_labs") or os.environ.get("PINECONE_INDEX_LABS") or DEFAULT_INDEX


def configured() -> bool:
    """A Pinecone key is present AND Pinecone hasn't failed for this session."""
    return bool(pinecone_key()) and not st.session_state.get("_rag_pc_broke")


def _flag_broke(reason: str) -> None:
    st.session_state["_rag_pc_broke"] = reason


def _session_prefix() -> str:
    """Per-session namespace prefix, timestamped so a janitor can reap old ones."""
    p = st.session_state.get("_rag_prefix")
    if not p:
        p = f"labs-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        st.session_state["_rag_prefix"] = p
    return p


# ---- version-robust SDK helpers (pinecone v5 dict-ish / v9 objects) -----------
def _index_names(pc) -> set[str]:
    lst = pc.list_indexes()
    names = getattr(lst, "names", None)
    if callable(names):
        return set(names())
    out = set()
    for ix in lst:
        out.add(ix["name"] if isinstance(ix, dict) else getattr(ix, "name", None))
    return {n for n in out if n}


def _index_ready(desc) -> bool:
    status = desc["status"] if isinstance(desc, dict) else getattr(desc, "status", None)
    if status is None:
        return True
    if isinstance(status, dict):
        return bool(status.get("ready"))
    return bool(getattr(status, "ready", True))


@st.cache_resource(show_spinner=False)
def _get_index(name: str):
    """Create-if-missing + wait-until-ready, ONCE per index name (cached across
    reruns and sessions in this process). A create-race is benign: the loser
    swallows the 409 and everyone waits for readiness before returning."""
    from pinecone import Pinecone, ServerlessSpec

    pc = Pinecone(api_key=pinecone_key())
    if name not in _index_names(pc):
        try:
            pc.create_index(
                name=name, dimension=EMBED_DIM, metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        except Exception:
            pass  # a concurrent session created it first — fine
    # ALWAYS wait for ready, whether we created it or merely found it.
    for _ in range(60):
        try:
            if _index_ready(pc.describe_index(name)):
                break
        except Exception:
            pass
        time.sleep(1.0)
    return pc.Index(name)


def _pc_index():
    return _get_index(index_name())


def _wait_queryable(idx, ns: str, probe_id: str, probe_vec: list[float],
                    timeout: float = FRESH_TIMEOUT) -> bool:
    """Poll the QUERY path until a just-upserted id is actually returned.

    Query-level freshness (not describe_index_stats' count, which lags and does
    not imply queryability). Returns True when fresh, False on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            res = idx.query(namespace=ns, vector=probe_vec, top_k=1, include_metadata=False)
            matches = res["matches"] if isinstance(res, dict) else res.matches
            ids = {(m["id"] if isinstance(m, dict) else m.id) for m in matches}
            if probe_id in ids:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def _sweep_old_namespaces(idx) -> None:
    """Once per session, best-effort: delete namespaces older than SWEEP_MAX_AGE
    (age read from the epoch embedded in the 'labs-<epoch>-...' prefix). Reaps
    orphans from closed tabs / crashed sessions that no Clear button can catch."""
    if st.session_state.get("_rag_swept"):
        return
    st.session_state["_rag_swept"] = True
    try:
        stats = idx.describe_index_stats()
        spaces = stats["namespaces"] if isinstance(stats, dict) else stats.namespaces
        now = int(time.time())
        for ns in list(spaces.keys()):
            parts = ns.split("-")
            if len(parts) >= 2 and parts[0] == "labs" and parts[1].isdigit():
                if now - int(parts[1]) > SWEEP_MAX_AGE:
                    try:
                        idx.delete(delete_all=True, namespace=ns)
                    except Exception:
                        pass
    except Exception:
        pass  # never let hygiene break the lab


def _chunks(docs: dict[str, str], size: int, overlap: int) -> list[dict]:
    items = []
    for name, text in docs.items():
        for c in store.chunk(text, size, overlap):
            items.append({"doc": name, "text": c})
    return items


def rebuild(client, docs: dict[str, str], size: int = 600, overlap: int = 100,
            *, scope: str = "rag") -> dict:
    """Chunk + embed + store THIS session's docs for THIS lab (`scope`). Returns
    an opaque handle. Embeds once and reuses the vectors for either backend.

    Pinecone path: upsert into a fresh per-(session,lab,build) namespace, wait for
    query freshness, then retire this lab's PREVIOUS namespace. A create-race,
    freshness timeout, or any Pinecone error degrades this build to in-RAM.
    """
    items = _chunks(docs, size, overlap)
    vecs = store.embed(client, [it["text"] for it in items]) if items \
        else np.zeros((0, EMBED_DIM), np.float32)

    if configured():
        try:
            idx = _pc_index()
            _sweep_old_namespaces(idx)
            bkey, nkey = f"_rag_build_{scope}", f"_rag_ns_{scope}"
            n = st.session_state.get(bkey, 0) + 1
            ns = f"{_session_prefix()}-{scope}-{n}"
            prev = st.session_state.get(nkey)

            if items:
                payload = [
                    {"id": f"{ns}-{i}", "values": vecs[i].tolist(),
                     "metadata": {"doc": items[i]["doc"], "text": items[i]["text"]}}
                    for i in range(len(items))
                ]
                idx.upsert(vectors=payload, namespace=ns)
                if not _wait_queryable(idx, ns, f"{ns}-0", vecs[0].tolist()):
                    raise RuntimeError("pinecone read-after-write freshness timeout")

            # committed — record and retire this lab's previous namespace
            st.session_state[bkey] = n
            st.session_state[nkey] = ns
            if prev:
                try:
                    idx.delete(delete_all=True, namespace=prev)
                except Exception:
                    pass  # best-effort; never fatal
            return {"backend": "pinecone", "namespace": ns, "index": index_name(), "items": items}
        except Exception as e:  # any Pinecone trouble → degrade THIS build to RAM
            _flag_broke(str(e)[:200])

    return {"backend": "ram", "items": items, "matrix": vecs}


def search(client, handle: dict, query: str, k: int = 4) -> list[tuple[dict, float]]:
    """Top-k nearest chunks — uniform [(item, score)] shape for both backends.

    A Pinecone query error self-heals: the live handle is degraded to RAM in
    place (it already carries the chunk texts), so this search AND every later
    one on the same cached handle serve results instead of hanging at zero.
    """
    if not handle or not handle.get("items"):
        return []
    if handle.get("backend") == "pinecone":
        try:
            qv = store.embed(client, [query])[0]
            idx = _pc_index()
            res = idx.query(namespace=handle["namespace"], vector=qv.tolist(),
                            top_k=k, include_metadata=True)
            matches = res["matches"] if isinstance(res, dict) else res.matches
            out = []
            for m in matches:
                meta = (m["metadata"] if isinstance(m, dict) else m.metadata) or {}
                score = m["score"] if isinstance(m, dict) else m.score
                out.append(({"doc": meta.get("doc", ""), "text": meta.get("text", "")}, float(score)))
            return out
        except Exception as e:
            _flag_broke(str(e)[:200])
            # self-heal: turn this handle into a RAM handle so it recovers now
            handle["matrix"] = store.embed(client, [it["text"] for it in handle["items"]])
            handle["backend"] = "ram"
            # fall through to the RAM path below

    v = store.embed(client, [query])[0]
    scores = handle["matrix"] @ v
    order = np.argsort(-scores)[:k]
    return [(handle["items"][i], float(scores[i])) for i in order]


def render_backend_badge(handle: dict | None = None) -> None:
    """One-line status — truthful about which backend actually served the result.
    The session-failure flag is checked FIRST so a stale pinecone handle can't
    keep claiming Pinecone after a fallback."""
    if st.session_state.get("_rag_pc_broke"):
        st.caption(
            "🧠 **In-memory (NumPy)** — a Pinecone key is set but Pinecone was unavailable, "
            "so this session fell back to RAM. The lab still works identically."
        )
    elif handle and handle.get("backend") == "pinecone":
        st.caption(
            f"🌲 **Real vector DB — Pinecone** · index `{handle['index']}` · your namespace "
            f"`{handle['namespace']}` (persistent & isolated to your session)."
        )
    else:
        st.caption(
            "🧠 **In-memory (NumPy)** — vectors held in RAM for this session. Set a "
            "`pinecone_api_key` to use a real, persistent Pinecone vector DB instead."
        )
