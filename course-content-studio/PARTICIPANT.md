# Course Content Studio — Participant Quick Start

Welcome! In this track you'll build a **real professor tool**, one piece at a time — and finish by
generating a quiz from your own slides that imports straight into Canvas.

---

## Getting in
1. Open the app link your facilitator shared.
2. Enter the **participant code** they gave you. (The app never stores the code itself — only a hash.)
3. You'll land on the home page. Read the framing, then walk the **"Start here"** slides.

A few ground rules:
- The keys are **shared workshop keys** — please don't redistribute them.
- **Don't paste sensitive or confidential data.** Use sample or non-confidential course materials.
- Everything the app generates is a **draft** — review and approve before you trust or export it.

---

## What each lab shows

Work through them **in order** (use the sidebar or the home-page links). Every lab has an interactive
concept deck — open it and click through the slides.

| # | Lab | What you'll see |
|---|-----|-----------------|
| 1 | **RAG with Pinecone** | Turn your documents into searchable chunks in a real vector DB; ask a question and get a **grounded, cited** answer. |
| 2 | **Structured lookup (Postgres)** | Pull **authoritative facts** — learning objectives, rubrics, a reusable question bank — from a real database. |
| 3 | **The coupling problem** | See why an app wired *directly* to each tool is brittle and hard to share. |
| 4 | **MCP — decoupled tools** | The same vector search + database lookup, now offered as **standard tools** any app (or agent) can call. |
| 5 | **Course Content Studio** (capstone) | Upload your materials → generate grounded quizzes/assignments → **export a Canvas QTI .zip**. |
| 6 | **What's next — agents** | We built this by hand; next session, agents and **harnesses** do the assembling themselves. |

---

## Using the capstone (Lab 5)
1. **Upload** your course materials — **PDF, PPTX, HTML, or Markdown**. The app extracts text, chunks it,
   embeds it, and stores it under your course.
2. **Choose structured context** — a course, learning objective(s), Bloom level, and a rubric template.
3. **Specify the assessment** — quiz or assignment, target objective(s), how many questions and which
   **types** (multiple-choice, multiple-answer, true/false, short answer, essay), difficulty, points.
4. **Generate.** The app retrieves grounding (vector search) + structured context (database) and drafts
   items — each with a stem, options, correct answer(s), **rationale**, **source citation**, and
   **objective alignment**.
5. **Review (human-in-the-loop).** Edit, regenerate, or accept/reject each item. Low-confidence items are
   flagged. **Nothing exports until you approve it.**
6. **Export.** Download the **Canvas QTI .zip** (plus a human-readable answer key / rubric).

---

## Importing the QTI .zip into Canvas
1. In Canvas, open your **Course**.
2. Go to **Settings → Import Course Content**.
3. **Content Type:** choose **QTI .zip file**.
4. Upload the `.zip` you exported, then **Import**.
5. When the import finishes, find the quiz under **Quizzes** and review it before publishing.

> Tip: Canvas imports **QTI 1.2 (classic quizzes)** most reliably, which is what this app exports.
> If your course uses New Quizzes, you may need to migrate the imported classic quiz.

---

## Troubleshooting
- **"Not configured" on the home page?** A service Secret is missing — tell your facilitator which one is ⬜.
- **Slow first response?** A free Cloud app may be waking up; give it a moment and retry.
- **An item looks wrong?** That's expected — it's a draft. Edit or regenerate it, and only export what
  you've approved.
