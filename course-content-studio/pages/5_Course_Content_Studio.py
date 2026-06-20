"""Capstone · Course Content Studio.

The whole workshop, end to end: a professor uploads their own materials, the app
ingests them into Pinecone, pulls the course's objectives/rubric from Postgres,
generates quiz/assignment items **grounded in the uploaded material** (with
citations + human review), and exports a Canvas-importable **QTI 1.2 .zip**.

    Upload → Ingest/Chunk/Embed → Pinecone + Postgres → Generate (grounded)
           → Review (human-in-the-loop) → Canvas QTI .zip

Nothing exports until a human accepts the items.
"""
import streamlit as st

st.set_page_config(page_title="Course Content Studio", page_icon="🎓",
                   layout="wide")

from lib.config import gate
gate()

from lib import config
from lib import db
from lib import ingest
from lib import generate
from lib import qti
from lib import review
from lib import vectors
from lib.chunk import chunk
from lib.ui import render_deck


NAMESPACE = "capstone"


def _safe_correct_set(item):
    """Indices marked correct, for display (handles true_false bool)."""
    t = item.get("type")
    c = item.get("correct")
    if t == "true_false":
        return {0} if bool(c) else {1}
    if isinstance(c, list):
        return {int(x) for x in c
                if isinstance(x, (int, float)) and not isinstance(x, bool)}
    return set()


st.title("🎓 Course Content Studio — generate Canvas-ready assessments from "
         "your materials")
st.caption(
    "Upload your slides/readings → ground an LLM on them → generate and review "
    "quiz items → export a Canvas QTI .zip. Retrieval (Pinecone) + structure "
    "(Postgres) + grounded generation, with a human in the loop."
)

render_deck("capstone")

review.init()


# =========================================================================
# Step 1 · Upload & ingest
# =========================================================================
st.header("1 · Upload & ingest your materials")

ingest_ready = bool(config.PINECONE_API_KEY and config.OPENAI_API_KEY)
if not ingest_ready:
    missing = []
    if not config.OPENAI_API_KEY:
        missing.append("openai_api_key")
    if not config.PINECONE_API_KEY:
        missing.append("pinecone_api_key")
    st.info(
        "Ingestion needs OpenAI (embeddings) + Pinecone (vector store). Set the "
        "following in **Streamlit Secrets** (or env vars), then reload:\n\n"
        + "\n".join(f"- `{m}`" for m in missing)
    )
else:
    files = st.file_uploader(
        "Upload PDFs, PowerPoint, HTML, or Markdown/text",
        type=["pdf", "pptx", "html", "htm", "md", "markdown", "txt"],
        accept_multiple_files=True,
    )
    if st.button("Ingest → Pinecone", type="primary", disabled=not files):
        summaries = []
        total_chunks = 0
        for f in files or []:
            try:
                data = f.read()
                out = ingest.extract(f.name, data)
                blocks = out.get("blocks", [])
                if not blocks:
                    summaries.append((f.name, 0, "no extractable text"))
                    continue
                # Chunk each located block; keep the source locator on every chunk.
                items = []
                ci = 0
                for b in blocks:
                    loc = b.get("loc", "")
                    source = f"{f.name} · {loc}" if loc else f.name
                    for piece in chunk(b["text"]):
                        items.append({
                            "id": f"{f.name}-{ci}",
                            "text": piece,
                            "metadata": {"source": source, "file": f.name,
                                         "loc": loc},
                        })
                        ci += 1
                if items:
                    with st.spinner(f"Embedding + upserting {f.name}…"):
                        n = vectors.upsert_chunks(NAMESPACE, items)
                    total_chunks += n
                    summaries.append((f.name, n, "ok"))
                else:
                    summaries.append((f.name, 0, "no extractable text"))
            except ValueError as e:
                summaries.append((f.name, 0, f"unsupported: {e}"))
            except Exception as e:
                summaries.append((f.name, 0, f"failed: {e}"))

        st.session_state["ccs_ingested"] = total_chunks > 0
        if total_chunks:
            st.success(f"Ingested **{total_chunks} chunks** into namespace "
                       f"`{NAMESPACE}`.")
        else:
            st.warning("No chunks were ingested — check the files below.")
        for name, n, status in summaries:
            icon = "✅" if status == "ok" else "⚠️"
            st.markdown(f"{icon} **{name}** — {n} chunks · {status}")

    if st.session_state.get("ccs_ingested"):
        st.caption("Materials are in Pinecone. Continue to choose a target "
                   "objective below.")


# =========================================================================
# Step 2 · Target (course / objective)
# =========================================================================
st.header("2 · Choose your target objective")

objective_text = ""
objective_id = None
course_id = None
structure = {"objectives": [], "rubric": None}

if config.pg_configured():
    try:
        courses = db.list_courses()
    except Exception as e:
        courses = []
        st.warning(f"Couldn't load courses from Postgres: {e}")

    if courses:
        labels = {f"{c['code']} — {c['title']}": c for c in courses}
        pick = st.selectbox("Course", list(labels.keys()))
        course = labels[pick]
        course_id = course["id"]
        try:
            objectives = db.list_objectives(course_id)
        except Exception as e:
            objectives = []
            st.warning(f"Couldn't load objectives: {e}")
        try:
            rubric = db.get_rubric(course_id)
        except Exception:
            rubric = None
        structure = {"objectives": objectives, "rubric": rubric}

        if objectives:
            olabels = {f"[{o['id']}] {o['text']}": o for o in objectives}
            opick = st.selectbox("Learning objective", list(olabels.keys()))
            chosen = olabels[opick]
            objective_id = chosen["id"]
            objective_text = chosen["text"]
        else:
            st.info("This course has no objectives yet — type one below.")
            objective_text = st.text_input("Objective (free text)")
        if rubric:
            st.caption(f"Rubric loaded: **{rubric.get('title', 'Rubric')}** "
                       f"({len(rubric.get('criteria', []))} criteria).")
    else:
        st.info("No courses found. Type a free-text objective to continue.")
        objective_text = st.text_input("Objective (free text)")
else:
    st.info(
        "Postgres isn't configured, so course/objective/rubric lookup is "
        "unavailable. You can still run the capstone with a **free-text "
        "objective** below."
    )
    objective_text = st.text_input(
        "Objective (free text)",
        placeholder="e.g. Explain how retrieval-augmented generation grounds "
                    "answers in source documents.",
    )


# =========================================================================
# Step 3 · Generate
# =========================================================================
st.header("3 · Generate grounded items")

if not config.OPENAI_API_KEY:
    st.info("Generation needs OpenAI. Set `openai_api_key` in Secrets.")
elif not st.session_state.get("ccs_ingested"):
    st.info("Ingest some materials in Step 1 first — items are grounded in them.")
elif not (objective_text and objective_text.strip()):
    st.info("Choose or type an objective in Step 2 first.")
else:
    with st.form("generate"):
        c1, c2, c3 = st.columns(3)
        with c1:
            assessment_type = st.selectbox("Assessment type",
                                           ["quiz", "assignment"])
        with c2:
            count = st.slider("How many items", 1, 15, 5)
        with c3:
            difficulty = st.selectbox("Difficulty",
                                      ["easy", "medium", "hard"], index=1)
        types = st.multiselect(
            "Question types",
            generate.ITEM_TYPES,
            default=["mcq", "true_false"],
        )
        points_each = st.number_input("Points per item", 0.5, 100.0, 1.0, 0.5)
        top_k = st.slider("Grounding chunks to retrieve (top-k)", 2, 12, 6)
        submitted = st.form_submit_button("Generate", type="primary")

    if submitted:
        if not types:
            st.warning("Pick at least one question type.")
        else:
            try:
                with st.spinner("Retrieving grounding from Pinecone…"):
                    hits = vectors.query(NAMESPACE, objective_text, top_k=top_k)
                grounding = [
                    {"text": h.get("text", ""),
                     "source": (h.get("metadata") or {}).get("source", h["id"])}
                    for h in hits if h.get("text")
                ]
                if not grounding:
                    st.warning("No grounding found. Ingest more material or pick "
                               "an objective closer to your content.")
                else:
                    spec = {
                        "assessment_type": assessment_type,
                        "types": types,
                        "count": count,
                        "objective_text": objective_text,
                        "difficulty": difficulty,
                        "points_each": points_each,
                    }
                    with st.spinner("Generating grounded items with the LLM…"):
                        items = generate.generate_items(spec, grounding, structure)
                    # carry the chosen objective id onto items lacking one
                    for it in items:
                        if it.get("objective_id") is None and objective_id:
                            it["objective_id"] = objective_id
                    review.set_items(items)
                    st.session_state["ccs_assessment_type"] = assessment_type
                    if items:
                        st.success(f"Generated **{len(items)}** items. Review "
                                   "them below.")
                    else:
                        st.warning("The model returned no usable items. Try a "
                                   "different objective or more grounding.")
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Generation failed: {e}")


# =========================================================================
# Step 4 · Review (human in the loop)
# =========================================================================
st.header("4 · Review, edit, accept")

if review.count() == 0:
    st.caption("Generated items will appear here for review.")
else:
    st.caption(f"{review.accepted_count()} of {review.count()} items accepted. "
               "Low-confidence items start unchecked.")
    for i, item in enumerate(review.items()):
        conf = item.get("confidence", "medium")
        flag = " ⚠️ low confidence" if conf == "low" else ""
        cit = item.get("citation") or {}
        src = " · ".join(x for x in [cit.get("source"), cit.get("loc")] if x)
        header = f"{i + 1}. [{item.get('type')}] {item.get('stem', '')[:70]}"
        with st.expander(header + flag,
                         expanded=(conf == "low")):
            accepted = st.checkbox("Accept this item", value=review.is_accepted(i),
                                   key=f"acc_{i}")
            review.set_accept(i, accepted)

            new_stem = st.text_area("Stem", value=item.get("stem", ""),
                                    key=f"stem_{i}")
            if new_stem != item.get("stem"):
                review.update_item(i, "stem", new_stem)

            options = item.get("options") or []
            if options:
                correct_set = set(_safe_correct_set(item))
                st.markdown("**Options** (✓ = correct):")
                for j, opt in enumerate(options):
                    mark = "✓" if j in correct_set else "·"
                    st.markdown(f"- {mark} {chr(65 + j)}. {opt}")
            elif item.get("type") == "short_answer":
                st.markdown("**Accepted answers:** "
                            + ", ".join(str(a) for a in item.get("correct", [])))
            elif item.get("type") == "essay":
                st.markdown("_Essay — graded manually._")

            meta = []
            if src:
                meta.append(f"📎 {src}")
            if item.get("objective_id"):
                meta.append(f"🎯 objective {item['objective_id']}")
            badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "🟡")
            meta.append(f"{badge} confidence: {conf}")
            st.caption(" · ".join(meta))
            if item.get("rationale"):
                st.caption(f"Rationale: {item['rationale']}")


# =========================================================================
# Step 5 · Export
# =========================================================================
st.header("5 · Export to Canvas")

accepted_items = review.accepted()
if not accepted_items:
    st.info("Accept at least one item in Step 4 to enable export.")
else:
    title = st.text_input("Assessment title", value="Generated Assessment")
    st.caption(f"{len(accepted_items)} accepted item(s) ready to export.")

    col1, col2 = st.columns(2)
    with col1:
        try:
            zip_bytes = qti.build_qti_package(title, accepted_items)
            st.download_button(
                "⬇️ Download Canvas QTI .zip",
                data=zip_bytes,
                file_name=f"{title.strip().replace(' ', '_') or 'assessment'}.zip",
                mime="application/zip",
                type="primary",
            )
            st.caption("Canvas → Course → Settings → Import Course Content → "
                       "**QTI .zip**.")
        except Exception as e:
            st.error(f"Couldn't build the QTI package: {e}")
    with col2:
        try:
            key_md = qti.build_answer_key(title, accepted_items)
            st.download_button(
                "⬇️ Download answer key (.md)",
                data=key_md.encode("utf-8"),
                file_name="answer_key.md",
                mime="text/markdown",
            )
        except Exception as e:
            st.error(f"Couldn't build the answer key: {e}")

    if st.session_state.get("ccs_assessment_type") == "assignment":
        st.markdown("**Assignment brief + rubric**")
        brief = st.text_area(
            "Assignment brief",
            value="Complete the following assignment, grounded in the course "
                  "materials. Cite sources where relevant.",
            height=120,
        )
        try:
            assign_bytes = qti.build_assignment(brief, structure.get("rubric"))
            st.download_button(
                "⬇️ Download assignment brief (.md)",
                data=assign_bytes,
                file_name="assignment.md",
                mime="text/markdown",
            )
        except Exception as e:
            st.error(f"Couldn't build the assignment: {e}")
