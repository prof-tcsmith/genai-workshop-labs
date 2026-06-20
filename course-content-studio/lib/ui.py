"""Shared UI helpers — embed a concept deck inside a page (same engine as the other apps)."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_DECKS = Path(__file__).resolve().parents[1] / "decks"
PAGES_BASE = "https://prof-tcsmith.github.io/genai-workshop-labs/decks/ccs"


def render_deck(name: str, label: str = "📊 Concept slides (interactive)",
                expanded: bool = False, height: int = 540) -> None:
    deck = _DECKS / f"{name}.html"
    try:
        html = deck.read_text(encoding="utf-8")
    except Exception:
        return
    with st.expander(label, expanded=expanded):
        components.html(html, height=height, scrolling=False)
        st.markdown(f"[↗ Open these slides full-screen in a new tab]({PAGES_BASE}/{name}.html)")
