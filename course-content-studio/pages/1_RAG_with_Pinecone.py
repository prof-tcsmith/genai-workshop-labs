"""Lab · RAG with a real vector database (Pinecone).

Teaching flow: paste/ingest documents -> chunk -> embed -> upsert to Pinecone;
then ask a question -> embed -> cosine top-k retrieve -> ground an LLM answer on
exactly those chunks (with citations). Maps to Layer 4 (retrieval) and Layer 6
(data).
"""
import streamlit as st

st.set_page_config(page_title="RAG with Pinecone", page_icon="📚", layout="wide")

from lib.config import gate
gate()

from lib import config
from lib.ui import render_deck
from lib.chunk import chunk
from lib import vectors

NAMESPACE = "lab"

SAMPLE_CORPUS = """\
The Aurora Faculty Grant funds course redesign projects up to $12,000 per faculty member. \
Applications open each fall semester and are reviewed by the Teaching Innovation Committee. \
Funds may be used for software, student assistants, and instructional design support, but not for travel or personal hardware.

Retrieval-Augmented Generation (RAG) lets a language model answer questions using your own documents. \
Instead of relying only on what the model memorized during training, RAG retrieves relevant passages from a knowledge base at query time and includes them in the prompt. \
This keeps answers grounded, current, and traceable to a source.

A vector database stores text as high-dimensional embeddings and finds the most similar passages using cosine similarity. \
Pinecone is a managed, serverless vector database: it scales automatically, persists your data, and returns nearest-neighbor matches in milliseconds. \
Namespaces let you keep separate collections (for example, one per course) inside a single index.

Embeddings are numeric vectors that capture meaning: passages about similar topics land near each other in vector space. \
The OpenAI text-embedding-3-small model produces 1536-dimensional vectors. \
Two passages are compared with cosine similarity, which ranges from -1 (opposite) to 1 (identical in direction)."""


st.title("Lab · RAG with a real vector database (Pinecone)")
st.caption(
    "Layer 4 (retrieval) + Layer 6 (data): turn documents into embeddings, store "
    "them in a real vector DB, and ground an LLM answer on cosine top-k matches."
)

render_deck("rag-pinecone")

# --- Configuration gate ---------------------------------------------------
missing = []
if not config.PINECONE_API_KEY:
    missing.append("pinecone_api_key")
if not config.OPENAI_API_KEY:
    missing.append("openai_api_key")
if missing:
    st.info(
        "This lab needs API keys to run. Set the following in **Streamlit "
        "Secrets** (or as environment variables):\n\n"
        + "\n".join(f"- `{name}`" for name in missing)
        + f"\n\nPinecone index name (optional, defaults to `course-content`): "
        f"`pinecone_index` — currently `{config.PINECONE_INDEX}`."
    )
    st.stop()


# --- Cached ingest (so reruns don't re-embed) -----------------------------
@st.cache_data(show_spinner=False)
def ingest(text: str, size_tokens: int, overlap: int) -> dict:
    """Chunk + upsert ``text`` to Pinecone. Cached on the inputs.

    Returns a small summary dict (caching the chunk list, not network handles).
    """
    chunks = chunk(text, size_tokens=size_tokens, overlap=overlap)
    items = [
        {"id": f"c{idx}", "text": ch, "metadata": {"chunk": idx}}
        for idx, ch in enumerate(chunks)
    ]
    count = vectors.upsert_chunks(NAMESPACE, items)
    return {"n_chunks": len(chunks), "n_upserted": count, "preview": chunks[:3]}


# --- 1) Corpus + ingest ---------------------------------------------------
st.subheader("1 · Ingest documents → Pinecone")
st.write(
    "Paste your own text or use the built-in sample, then ingest. We chunk the "
    "text, embed each chunk, and **upsert** the vectors into the `lab` namespace."
)

col_a, col_b = st.columns(2)
with col_a:
    size_tokens = st.slider("Chunk size (tokens)", 100, 800, 400, 50)
with col_b:
    overlap = st.slider("Chunk overlap (tokens)", 0, 200, 60, 10)

text = st.text_area(
    "Corpus", value=SAMPLE_CORPUS, height=220,
    help="This is the knowledge the model will be allowed to answer from.",
)

if st.button("Ingest → Pinecone", type="primary"):
    if not text.strip():
        st.warning("Add some text to ingest first.")
    else:
        try:
            with st.spinner("Chunking, embedding, and upserting to Pinecone…"):
                summary = ingest(text, size_tokens, overlap)
            st.session_state["ingested"] = True
            st.success(
                f"Ingested **{summary['n_chunks']} chunks** "
                f"({summary['n_upserted']} vectors upserted) into namespace "
                f"`{NAMESPACE}`."
            )
            if summary["preview"]:
                with st.expander("Preview first chunks"):
                    for i, ch in enumerate(summary["preview"]):
                        st.markdown(f"**Chunk {i}** — {len(ch)} chars")
                        st.text(ch)
        except Exception as e:
            st.error(
                "Ingest failed while talking to OpenAI/Pinecone. Check your keys "
                f"and network, then retry.\n\n```\n{e}\n```"
            )


# --- 2) Query + grounded answer -------------------------------------------
st.subheader("2 · Ask a question (retrieve → ground → answer)")
if not st.session_state.get("ingested"):
    st.caption("Tip: ingest some text above first so there's something to retrieve.")

question = st.text_input(
    "Your question",
    value="How much can the Aurora Faculty Grant fund, and what can it be used for?",
)
top_k = st.slider("Top-k chunks to retrieve", 1, 10, 4)

if st.button("Search + answer"):
    if not question.strip():
        st.warning("Type a question first.")
    else:
        # Retrieve
        try:
            with st.spinner("Embedding the query and running cosine top-k…"):
                hits = vectors.query(NAMESPACE, question, top_k=top_k)
        except Exception as e:
            st.error(
                "Retrieval failed. Make sure you've ingested text and that your "
                f"keys/network are working.\n\n```\n{e}\n```"
            )
            hits = None

        if hits is not None:
            if not hits:
                st.warning(
                    "No matches found in the `lab` namespace. Ingest some text "
                    "above first, then try again."
                )
            else:
                st.markdown("**Retrieved chunks (with cosine score):**")
                for h in hits:
                    score = h.get("score", 0.0)
                    st.markdown(
                        f"- `{h['id']}` · **cosine {score:.3f}**"
                    )
                    st.markdown(
                        f"> {h['text'][:400]}{'…' if len(h['text']) > 400 else ''}"
                    )

                # Ground the answer ONLY on retrieved chunks
                context = "\n\n".join(
                    f"[{h['id']}] {h['text']}" for h in hits
                )
                system = (
                    "You are a careful assistant. Answer the user's question "
                    "USING ONLY the provided context chunks. Cite the chunk ids "
                    "you used in square brackets, e.g. [c0]. If the answer is not "
                    "in the context, say you don't have enough information."
                )
                user = f"Context:\n{context}\n\nQuestion: {question}"
                try:
                    with st.spinner("Generating a grounded answer…"):
                        answer = config.chat_text(system, user, temperature=0)
                    st.markdown("**Grounded answer:**")
                    st.info(answer)
                except Exception as e:
                    st.error(
                        "The LLM call failed. Check your API key/network and "
                        f"retry.\n\n```\n{e}\n```"
                    )


# --- 3) What just happened ------------------------------------------------
with st.expander("What just happened? (embed → upsert → cosine top-k)"):
    st.markdown(
        "1. **Chunk** — long text is split into overlapping, token-sized windows "
        "so each piece embeds and retrieves cleanly.\n"
        "2. **Embed** — each chunk becomes a 1536-dim vector with "
        f"`{config.EMBED_MODEL}`; similar meanings land near each other.\n"
        "3. **Upsert** — vectors (plus the original text as metadata) are stored "
        f"in Pinecone under the `{NAMESPACE}` namespace — persistent and scalable.\n"
        "4. **Query** — your question is embedded the same way; Pinecone returns "
        "the **cosine top-k** nearest chunks.\n"
        "5. **Ground** — those chunks (and nothing else) are handed to "
        f"`{config.CHAT_MODEL}`, which answers and cites them.\n\n"
        "*Why it's nice:* a real, persistent vector DB scales to millions of "
        "chunks and keeps answers grounded in **your** documents."
    )
