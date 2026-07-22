import streamlit as st

from shared.core import boot, chat, layer_badge, try_this
from shared import ragstore
from shared import store as rag
from shared.slides import render_slides

client = boot("Build & break a RAG")

st.title("5 · Build & break a RAG")
layer_badge([4, 6])
st.caption("🧭 **Data access:** retrieval quality is data quality.")
st.caption("Layers 4 & 6 · Build a tiny retrieval pipeline, then sabotage it and watch quality collapse.")
render_slides("build-break-rag")

corpus_all = rag.load_corpus()
default_docs = [n for n in corpus_all if "RESTRICTED" not in n]

st.markdown("##### ▶️ The app")
names = st.multiselect("Documents in the corpus", list(corpus_all.keys()), default=default_docs)
rag.render_doc_viewer({n: corpus_all[n] for n in names})

c1, c2, c3 = st.columns(3)
size = c1.slider("Chunk size (chars)", 80, 1200, 600, 20)
overlap = c2.slider("Overlap (chars)", 0, 300, 100, 10)
k = c3.slider("Top-k retrieved", 1, 6, 3)

st.markdown("**Break it** — flip a switch, rebuild, and see what happens:")
b1, b2, b3 = st.columns(3)
tiny = b1.checkbox("Tiny chunks (size 80)", help="Fragments rules across chunks so retrieval misses the full answer.")
stale = b2.checkbox("Add a conflicting 'stale' policy", help="Injects a second refund policy with different numbers — and, like real stale data, nothing in it says it's outdated.")
leak = b3.checkbox("Include the RESTRICTED doc", help="Simulates a permission leak: a doc the user shouldn't see enters retrieval.")

q = st.text_input("Question", "What is the enterprise refund window?")

if st.button("Build index & answer", type="primary"):
    eff_size = 80 if tiny else size
    eff_overlap = min(overlap, eff_size // 2)  # overlap can't exceed half the chunk size
    docs = {n: corpus_all[n] for n in names}
    if leak and "security_notes_RESTRICTED" in corpus_all:
        docs["security_notes_RESTRICTED"] = corpus_all["security_notes_RESTRICTED"]
    if stale:
        # A drifted second copy of the SAME policy (e.g. an internal wiki page) with
        # different numbers. Deliberately symmetric with the real doc — same title,
        # NO "old"/version marker — because real stale data isn't labeled as stale.
        # That's the whole point: nothing in either document says which is current.
        docs["refund_policy_wiki"] = (
            "# Northwind Cloud — Refund Policy\n\n"
            "Enterprise customers may request a refund within 14 days of the order date. "
            "Standard (non-enterprise) customers have a 7-day refund window. "
            "Refunds do not require manager approval."
        )

    if not docs:
        st.warning("Add at least one document to the corpus.")
        st.stop()

    with st.spinner("Chunking + embedding + indexing…"):
        index = ragstore.rebuild(client, docs, size=eff_size, overlap=eff_overlap, scope="lab5")
    hits = ragstore.search(client, index, q, k=k)
    ragstore.render_backend_badge(index)
    context = "\n\n".join(f"[{d['doc']}] {d['text']}" for d, _ in hits)
    msgs = [
        {"role": "system", "content": "Answer ONLY from the provided context. If two sources give DIFFERENT values for the same thing, you MUST report BOTH values and state that the sources conflict — do NOT silently pick one. Quote the sources you used."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {q}"},
    ]
    ans = chat(client, msgs).choices[0].message.content

    st.subheader("Answer")
    st.write(ans)
    st.caption(f"Index: {len(index['items'])} chunks · size {eff_size} · overlap {eff_overlap}")

    with st.expander("Retrieved chunks", expanded=True):
        for d, s in hits:
            st.markdown(f"**{d['doc']}** · score {s:.2f}\n\n> {d['text']}")

    # diagnostics
    if leak and any(d["doc"] == "security_notes_RESTRICTED" for d, _ in hits):
        st.error("⚠️ **Permission leak** — a RESTRICTED document was retrieved and fed to the model. In production this is a real data-leak path: retrieval must enforce the same permissions as the source system.")
    if stale and any(d["doc"] == "refund_policy_wiki" for d, _ in hits):
        st.warning("**Conflicting / stale source retrieved** — the answer now names two different windows (45 vs 14 days) because nothing in the data says which is current. Freshness and de-duplication are data-engineering problems, not model problems.")
    if tiny:
        st.warning("**Tiny chunks** fragment the policy, so a single chunk rarely contains the whole rule. Chunking is a design decision.")

try_this(
    "**Baseline first.** Leave every switch off, hit *Build index & answer*, and note the answer "
    "and the chunks it retrieved. This is your control.",
    "Tick **Tiny chunks (size 80)** and rebuild. The rule gets fragmented across chunks, so no "
    "single chunk carries the whole answer. *You changed a number, not the model.*",
    "Untick that, tick **Add a conflicting 'stale' policy**, rebuild. The answer now hedges and "
    "names *both* windows (45 days and 14 days) — nothing in the data says which document is "
    "current, so the model can't either.",
    "Untick, then tick **Include the RESTRICTED doc**. Content the user should never see is now "
    "in the answer. That is a permissions bug reaching the user through retrieval.",
    "Turn on two at once. Failures compound, and the answer still reads perfectly fluent — which "
    "is exactly why these bugs ship.",
)

st.divider()
st.info("Lesson: retrieval quality dominates output quality. Most RAG failures are data-engineering failures the pipeline simply exposes.")
st.warning("**What's missing — your bot still can't ACT** (book, refund, update a record); it can only read + talk. **➡️ Next — Tools & the agent loop** lets it take actions safely.")
