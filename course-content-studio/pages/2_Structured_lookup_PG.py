"""Lab · Structured lookup with a real database (Postgres).

Counterpart to the RAG lab: instead of fuzzy meaning (vectors), this pulls
**exact, authoritative facts** — learning objectives, rubrics, and a question
bank — from a real cloud Postgres with parameterized SQL. Maps to Layer 5
(enterprise systems) and Layer 6 (data).
"""
import streamlit as st

st.set_page_config(
    page_title="Structured lookup (Postgres)", page_icon="🗄️", layout="wide"
)

from lib.config import gate
gate()

from lib import config
from lib import db
from lib.ui import render_deck


st.title("Lab · Structured lookup with a real database (Postgres)")
st.caption(
    "Layer 5 (enterprise systems) + Layer 6 (data): query a real cloud Postgres "
    "with parameterized SQL to get exact, authoritative facts — courses, "
    "objectives, rubrics, and question banks — not similar-sounding text."
)

render_deck("structured-pg")


# --- Configuration gate ---------------------------------------------------
if not config.pg_configured():
    st.info(
        "This lab needs a **cloud Postgres** (Neon or Supabase). Set the "
        "following in **Streamlit Secrets** (or as environment variables):\n\n"
        "- `PG_HOST`\n"
        "- `PG_PORT`\n"
        "- `PG_DB`\n"
        "- `PG_USER`\n"
        "- `PG_PASSWORD`\n"
        "- `PG_SSLMODE`\n\n"
        "Then load `postgres-setup/01_schema.sql` and "
        "`postgres-setup/02_seed.sql` into your database. Step-by-step "
        "instructions (Neon, Supabase, or `psql`) are in "
        "**`postgres-setup/README.md`**."
    )
    st.stop()


# --- Why this lab? vector search vs SQL -----------------------------------
left, right = st.columns(2)
with left:
    st.markdown(
        "#### 🔎 Vector search (fuzzy meaning)\n"
        "- Finds passages that *sound similar* by **cosine similarity**.\n"
        "- Great for open questions over unstructured docs.\n"
        "- Returns **approximate**, ranked text — not a guaranteed value.\n"
        "- *That was the Pinecone lab.*"
    )
with right:
    st.markdown(
        "#### 🗄️ SQL lookup (exact, authoritative facts)\n"
        "- Returns the **one correct record** from a typed schema.\n"
        "- Great for IDs, counts, points, rubric levels — facts.\n"
        "- **Deterministic**: same query → same answer, every time.\n"
        "- *This lab — the database is the source of truth.*"
    )

st.divider()


# --- Load courses ----------------------------------------------------------
try:
    courses = db.list_courses()
except RuntimeError as e:
    st.error(str(e))
    st.stop()
except Exception as e:
    st.error(
        "Couldn't reach Postgres. Check your `PG_*` secrets and that the schema "
        "is loaded (see `postgres-setup/README.md`).\n\n"
        f"```\n{e}\n```"
    )
    st.stop()

if not courses:
    st.warning(
        "Connected, but no courses found. Load `postgres-setup/02_seed.sql` "
        "into your database, then refresh."
    )
    st.stop()

labels = {f"{c['code']} — {c['title']} ({c['term']})": c for c in courses}
choice = st.selectbox("Course", list(labels.keys()))
course = labels[choice]
course_id = course["id"]


# --- Objectives ------------------------------------------------------------
st.subheader("📋 Learning objectives")
st.code(
    "SELECT id, course_id, text, bloom_level\n"
    "FROM learning_objectives\n"
    "WHERE course_id = %s\n"
    "ORDER BY id;\n"
    f"-- params: ({course_id},)",
    language="sql",
)
try:
    objectives = db.list_objectives(course_id)
    if not objectives:
        st.caption("No objectives recorded for this course.")
    else:
        for o in objectives:
            bloom = o.get("bloom_level") or "—"
            st.markdown(f"- **[{bloom}]** {o['text']}")
except Exception as e:
    st.error(f"Failed to load objectives.\n\n```\n{e}\n```")
    objectives = []


# --- Rubric ----------------------------------------------------------------
st.subheader("📐 Rubric")
st.code(
    "SELECT id, course_id, title FROM rubrics\n"
    "WHERE course_id = %s ORDER BY id LIMIT 1;\n"
    f"-- params: ({course_id},)\n"
    "-- then, for that rubric's id:\n"
    "SELECT id, rubric_id, criterion, levels_json\n"
    "FROM rubric_criteria WHERE rubric_id = %s ORDER BY id;",
    language="sql",
)
try:
    rubric = db.get_rubric(course_id)
    if rubric is None:
        st.caption("No rubric on file for this course.")
    else:
        st.markdown(f"**{rubric['title']}**")
        for crit in rubric.get("criteria", []):
            with st.expander(crit["criterion"]):
                levels = crit.get("levels_json")
                if isinstance(levels, dict) and levels:
                    for level, desc in levels.items():
                        st.markdown(f"- **{level.title()}** — {desc}")
                else:
                    st.caption("No level descriptors recorded.")
except Exception as e:
    st.error(f"Failed to load the rubric.\n\n```\n{e}\n```")


# --- Question bank ---------------------------------------------------------
st.subheader("🧠 Question bank")

obj_filter_label = "All objectives"
obj_options = {obj_filter_label: None}
for o in objectives:
    obj_options[f"{o['text'][:60]}…" if len(o["text"]) > 60 else o["text"]] = o["id"]
filter_choice = st.selectbox("Filter by objective", list(obj_options.keys()))
objective_id = obj_options[filter_choice]

if objective_id is None:
    st.code(
        "SELECT id, type, stem, options_json, correct_json, points, source\n"
        "FROM question_bank\n"
        "WHERE course_id = %s\n"
        "ORDER BY id;\n"
        f"-- params: ({course_id},)",
        language="sql",
    )
else:
    st.code(
        "SELECT id, type, stem, options_json, correct_json, points, source\n"
        "FROM question_bank\n"
        "WHERE course_id = %s AND objective_id = %s\n"
        "ORDER BY id;\n"
        f"-- params: ({course_id}, {objective_id})",
        language="sql",
    )

try:
    bank = db.list_bank(course_id, objective_id)
    if not bank:
        st.caption("No bank questions match this filter.")
    else:
        for q in bank:
            st.markdown(
                f"**Q{q['id']}** · `{q['type']}` · "
                f"**{q.get('points', '?')} pts** · _source: {q.get('source', '—')}_"
            )
            st.markdown(f"> {q['stem']}")
            if q.get("options_json"):
                st.markdown(f"Options: `{q['options_json']}`")
            if q.get("correct_json"):
                with st.expander("Show correct answer"):
                    st.code(str(q["correct_json"]))
            st.markdown("---")
except Exception as e:
    st.error(f"Failed to load the question bank.\n\n```\n{e}\n```")


# --- Teaching note ---------------------------------------------------------
with st.expander("What just happened? (parameterized SQL vs vector search)"):
    st.markdown(
        "1. **Connect** — `db.connect()` opens a `with`-managed connection to "
        "your cloud Postgres using the `PG_*` secrets.\n"
        "2. **Parameterize** — every value (like the `course_id`) is bound with "
        "`%s`, never string-formatted, so the query is **safe and repeatable**.\n"
        "3. **Exact rows** — Postgres returns the *one correct record* for each "
        "lookup, the same way every time.\n\n"
        "*Contrast:* the Pinecone lab returned **similar-sounding** text by "
        "meaning. This lab returns **authoritative facts** by key. Real "
        "assistants need both — and that's exactly the coupling problem the "
        "next lab (MCP) untangles."
    )
