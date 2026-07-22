"""Order store for Lab 6 (Tools & the agent loop): a REAL cloud Postgres (Neon)
when configured, in-memory otherwise.

The agent's tools read and write an order system. With a DATABASE_URL set, that
system is a real Neon Postgres you can watch in the console: get_order SELECTs a
seeded order, and the human-gated issue_refund INSERTs a real refund row. With no
URL (e.g. the Docker/local run, which has only an OpenAI key) it falls back to
the in-memory seed so the lab always runs.

Isolation: the `orders` table is a shared, read-only seed (everyone reads the
same 4471 / 5012). Writes go to a `refunds` table tagged with a per-SESSION id,
so concurrent participants — and the two hosted instances — only ever see their
OWN refunds, and nobody's approved write mutates shared state.

Robustness (hardened after an adversarial review):
  * every DB call tries Neon and, on ANY failure, falls back to in-memory for
    THAT call only — no permanent session latch, so a transient blip (Neon's
    scale-to-zero cold start, a pooler hiccup) self-heals on the next call;
  * `_connect` retries a few times to absorb Neon's cold-start wake;
  * schema creation is serialized with a transaction advisory lock, because
    `CREATE TABLE IF NOT EXISTS` is idempotent for sequential re-runs but NOT
    race-safe against a room of concurrent first-runs on a brand-new database.

Lab 7 and the Case are untouched — they use their own order data.
"""
from __future__ import annotations

import os
import time
import uuid

import streamlit as st

# Seed orders — the single source of truth for BOTH the Neon seed and the
# in-memory fallback, so the lab behaves identically either way.
SEED_ORDERS: dict[str, dict] = {
    "4471": {"placed_days_ago": 12, "status": "delivered", "amount": 240.0, "customer_type": "enterprise"},
    "5012": {"placed_days_ago": 60, "status": "delivered", "amount": 90.0, "customer_type": "standard"},
}

_ADVISORY_LOCK = 447150122   # arbitrary constant — serializes concurrent schema creation


def _secret(name: str):
    try:
        return st.secrets.get(name)  # type: ignore[attr-defined]
    except Exception:
        return None


def db_url() -> str | None:
    return _secret("database_url") or _secret("DATABASE_URL") or os.environ.get("DATABASE_URL")


def configured() -> bool:
    """True whenever a URL is set — each call tries Neon and self-heals on failure
    (no permanent latch, so a cold-start blip doesn't poison the whole session)."""
    return bool(db_url())


def _note_error(reason: str) -> None:
    st.session_state["_ord_error"] = reason      # for the badge; cleared on next success


def _note_ok() -> None:
    st.session_state.pop("_ord_error", None)


def session_id() -> str:
    sid = st.session_state.get("_ord_session")
    if not sid:
        sid = "sess-" + uuid.uuid4().hex[:12]
        st.session_state["_ord_session"] = sid
    return sid


def _connect():
    """A short-lived connection with a bounded retry to absorb Neon's scale-to-zero
    cold start. prepare_threshold=None keeps it compatible with the pooler."""
    import psycopg
    import psycopg.rows

    last = None
    for attempt in range(3):
        try:
            return psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row,
                                   prepare_threshold=None, connect_timeout=15)
        except Exception as e:  # cold-start wake / transient — back off and retry
            last = e
            time.sleep(1.2 * (attempt + 1))
    raise last  # exhausted retries; caller falls back to in-memory


def _ensure_schema() -> None:
    """Create the tables + seed the orders ONCE per session. A transaction advisory
    lock serializes concurrent first-runs (CREATE TABLE IF NOT EXISTS is NOT
    race-safe on its own). Raises on failure so the caller can fall back."""
    if st.session_state.get("_ord_schema_ok"):
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK,))  # serialize DDL
        cur.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "  order_id text PRIMARY KEY, placed_days_ago int, status text,"
            "  amount numeric, customer_type text)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS refunds ("
            "  id bigserial PRIMARY KEY, session_id text NOT NULL, order_id text NOT NULL,"
            "  amount numeric NOT NULL, created_at timestamptz NOT NULL DEFAULT now())"
        )
        for oid, o in SEED_ORDERS.items():
            cur.execute(
                "INSERT INTO orders (order_id, placed_days_ago, status, amount, customer_type) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (order_id) DO NOTHING",
                (oid, o["placed_days_ago"], o["status"], o["amount"], o["customer_type"]),
            )
        conn.commit()  # releases the advisory lock
    st.session_state["_ord_schema_ok"] = True


def get_order(order_id: str) -> dict:
    """Fetch one order — Neon when configured (falling back to the in-memory seed
    on any error), else the seed. Returns the order dict or {'error': ...}."""
    oid = str(order_id).strip()
    if configured():
        try:
            _ensure_schema()
            with _connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT placed_days_ago, status, amount, customer_type "
                    "FROM orders WHERE order_id = %s", (oid,))
                row = cur.fetchone()
            _note_ok()
            if row:
                return {"placed_days_ago": row["placed_days_ago"], "status": row["status"],
                        "amount": float(row["amount"]), "customer_type": row["customer_type"]}
            return {"error": f"order {oid} not found"}
        except Exception as e:
            _note_error(str(e)[:200])  # fall through to in-memory (self-healing, not latched)
    o = SEED_ORDERS.get(oid)
    return dict(o) if o else {"error": f"order {oid} not found"}


def issue_refund(order_id: str, amount: float) -> dict:
    """Record a refund. Writes a REAL row to Neon (tagged to this session) when
    configured; else a no-op success. A non-numeric or non-positive amount is
    rejected (so a bad tool-call arg can't write a wrong-but-successful $0 row)."""
    oid = str(order_id).strip()
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return {"error": f"invalid refund amount {amount!r} — must be a number"}
    if amt <= 0:
        return {"error": f"refund amount must be positive, got {amt}"}
    if configured():
        try:
            _ensure_schema()
            with _connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO refunds (session_id, order_id, amount) VALUES (%s, %s, %s) "
                    "RETURNING id, created_at", (session_id(), oid, amt))
                rec = cur.fetchone()
                conn.commit()
            _note_ok()
            st.session_state["_ord_wrote"] = True
            return {"status": "refunded", "order_id": oid, "amount": amt,
                    "persisted": "neon", "refund_id": rec["id"]}
        except Exception as e:
            _note_error(str(e)[:200])
    return {"status": "refunded", "order_id": oid, "amount": amt, "persisted": "in-memory"}


def session_refunds() -> list[dict]:
    """This session's recorded refunds (for the 'what was written' panel). Only
    hits the DB once a refund has actually been written this session, so ordinary
    widget reruns don't each make a Neon round-trip."""
    if not configured() or not st.session_state.get("_ord_wrote"):
        return []
    try:
        _ensure_schema()
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT order_id, amount, created_at FROM refunds "
                "WHERE session_id = %s ORDER BY created_at DESC LIMIT 20", (session_id(),))
            rows = list(cur.fetchall())
        _note_ok()
        return rows
    except Exception as e:
        _note_error(str(e)[:200])
        return []


def render_backend_badge() -> None:
    """One-line status — truthful about which order store actually served the last
    call. The error note is checked before claiming Neon."""
    if not db_url():
        st.caption(
            "🧠 **In-memory orders** — the order system is a built-in table for this session. "
            "Set a `database_url` to use a real, persistent Neon Postgres instead."
        )
    elif st.session_state.get("_ord_error"):
        st.caption(
            "🧠 **In-memory orders** — a database URL is set but Postgres was unavailable on the "
            "last call, so it fell back to the built-in orders. It retries automatically."
        )
        st.caption(f"↳ Postgres error: `{st.session_state['_ord_error']}`")
    else:
        st.caption(
            f"🐘 **Real database — Neon Postgres** · orders read from the `orders` table; "
            f"approved refunds are written to `refunds` (tagged `{session_id()}`)."
        )
