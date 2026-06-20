"""Human-in-the-loop review state for generated items.

Generated assessment items are *drafts*: a professor edits, accepts, or rejects
each one before anything is exported. This module keeps that working set in
``st.session_state`` and exposes small, testable helpers over it.

Nothing here is auto-published — :func:`accepted` returns only the items a human
explicitly kept, and the export step uses that list.

Streamlit is imported lazily inside each function so this module can be imported
(and unit-tested) without a running Streamlit context.
"""
from __future__ import annotations

import copy

_KEY = "ccs_review"  # st.session_state slot: {"items": [...], "accept": [bool]}


def _state():
    import streamlit as st
    if _KEY not in st.session_state:
        st.session_state[_KEY] = {"items": [], "accept": []}
    return st.session_state[_KEY]


def init() -> None:
    """Ensure the review slot exists (idempotent)."""
    _state()


def set_items(items: list[dict]) -> None:
    """Replace the working set with freshly generated ``items``.

    Items are accepted by default *except* low-confidence ones, which start
    unchecked so they get a deliberate human look.
    """
    items = [copy.deepcopy(it) for it in (items or [])]
    st_state = _state()
    st_state["items"] = items
    st_state["accept"] = [it.get("confidence") != "low" for it in items]


def items() -> list[dict]:
    """All items currently in the working set (accepted or not)."""
    return _state()["items"]


def count() -> int:
    return len(_state()["items"])


def is_accepted(i: int) -> bool:
    flags = _state()["accept"]
    return bool(flags[i]) if 0 <= i < len(flags) else False


def toggle_accept(i: int) -> None:
    """Flip the accept flag for item ``i``."""
    flags = _state()["accept"]
    if 0 <= i < len(flags):
        flags[i] = not flags[i]


def set_accept(i: int, value: bool) -> None:
    flags = _state()["accept"]
    if 0 <= i < len(flags):
        flags[i] = bool(value)


def reject(i: int) -> None:
    """Mark item ``i`` as not accepted (convenience alias)."""
    set_accept(i, False)


def update_item(i: int, field: str, value) -> None:
    """Edit one ``field`` of item ``i`` in place."""
    its = _state()["items"]
    if 0 <= i < len(its):
        its[i][field] = value


def accepted() -> list[dict]:
    """Deep copies of only the accepted items, in order."""
    st_state = _state()
    its, flags = st_state["items"], st_state["accept"]
    return [copy.deepcopy(it) for it, ok in zip(its, flags) if ok]


def accepted_count() -> int:
    return sum(1 for ok in _state()["accept"] if ok)


def clear() -> None:
    """Empty the working set."""
    st_state = _state()
    st_state["items"] = []
    st_state["accept"] = []
