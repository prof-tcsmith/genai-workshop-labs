"""Grounded assessment-item generation.

Given (a) retrieved source chunks, (b) the course's learning objectives and
rubric, and (c) a generation spec (how many items, which types, difficulty,
points), ask the LLM to write quiz/assignment items that are **grounded only in
the provided chunks**, each carrying a citation back to its source and a
self-reported confidence.

We use OpenAI **structured outputs** (a JSON Schema response format) so the
model returns machine-checkable items instead of free text. Everything is then
re-validated in Python and any malformed item is dropped — the model is a
drafting assistant, not the source of truth.

Public API::

    items = generate_items(spec, grounding, structure)

where each returned item is a dict matching :data:`ITEM_FIELDS`.
"""
from __future__ import annotations

import json

from lib import config

# The item types the downstream QTI builder knows how to render.
ITEM_TYPES = ["mcq", "multiple_answer", "true_false", "short_answer", "essay"]
CONFIDENCE = ["high", "medium", "low"]
ITEM_FIELDS = (
    "type", "stem", "options", "correct", "points", "rationale",
    "citation", "objective_id", "confidence",
)


def _item_json_schema() -> dict:
    """The JSON Schema handed to OpenAI structured outputs.

    ``correct`` is intentionally permissive at the schema level (the exact shape
    depends on ``type``: list[int] for choice, list[str] for short answer, bool
    for true/false) — we enforce the per-type rules in :func:`_validate`.
    """
    item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {"type": "string", "enum": ITEM_TYPES},
            "stem": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            # Always an array of strings at the schema level (OpenAI strict mode
            # requires a concrete type); coerced per-type in _validate().
            "correct": {"type": "array", "items": {"type": "string"}},
            "points": {"type": "number"},
            "rationale": {"type": "string"},
            "citation": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source": {"type": "string"},
                    "loc": {"type": "string"},
                },
                "required": ["source", "loc"],
            },
            # anyOf (not a {"type": [...]} union) so the schema validates on BOTH
            # OpenAI strict mode AND Anthropic structured outputs (Anthropic does
            # not accept JSON-Schema type-union arrays).
            "objective_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "confidence": {"type": "string", "enum": CONFIDENCE},
        },
        "required": [
            "type", "stem", "options", "correct", "points", "rationale",
            "citation", "objective_id", "confidence",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"items": {"type": "array", "items": item}},
        "required": ["items"],
    }


def generate_items(spec: dict, grounding: list[dict], structure: dict) -> list[dict]:
    """Generate assessment items grounded in ``grounding``.

    Args:
        spec: ``{assessment_type, types:[...], count, objective_text,
            difficulty, points_each}``.
        grounding: retrieved chunks ``[{text, source}, ...]`` (``source`` is the
            citation locator, e.g. ``"lecture.pdf · p.3"``).
        structure: ``{objectives: [...], rubric: {...}|None}`` from Postgres.

    Returns:
        A list of validated item dicts (malformed items dropped).

    Raises:
        RuntimeError: if the active chat provider is not configured (no API key).
    """
    grounding = grounding or []
    if not grounding:
        # Nothing to ground on — refuse rather than hallucinate.
        return []

    spec = spec or {}
    types = [t for t in (spec.get("types") or []) if t in ITEM_TYPES] or ["mcq"]
    count = max(1, int(spec.get("count", 5)))
    points_each = spec.get("points_each", 1)
    difficulty = spec.get("difficulty", "medium")
    assessment_type = spec.get("assessment_type", "quiz")
    objective_text = (spec.get("objective_text") or "").strip()

    system = (
        "You are an expert instructional designer writing assessment items for a "
        "university course. You write items GROUNDED ONLY in the source excerpts "
        "you are given — never invent facts, names, numbers, or definitions that "
        "are not present in those excerpts. Every item must be answerable from "
        "the excerpts alone and must cite the excerpt it came from. If the "
        "excerpts do not support a high-quality item, write fewer items rather "
        "than fabricating. Respond using the provided JSON schema only."
    )

    # Build the grounding block with explicit, citable source labels.
    src_lines = []
    for i, g in enumerate(grounding):
        src = (g.get("source") or f"chunk {i}").strip()
        txt = (g.get("text") or "").strip()
        if txt:
            src_lines.append(f"[source: {src}]\n{txt}")
    sources_block = "\n\n---\n\n".join(src_lines)

    obj_lines = []
    for o in (structure or {}).get("objectives") or []:
        oid = o.get("id")
        otext = o.get("text", "")
        bloom = o.get("bloom_level")
        bloom_s = f" (Bloom: {bloom})" if bloom else ""
        obj_lines.append(f"- id={oid}: {otext}{bloom_s}")
    objectives_block = "\n".join(obj_lines) if obj_lines else "(none provided)"

    rubric = (structure or {}).get("rubric")
    rubric_block = _format_rubric(rubric)

    type_rules = (
        "The 'correct' field is ALWAYS a JSON array of strings. Per type:\n"
        "- mcq: 'options' has 3-5 choices; 'correct' = exactly one zero-based "
        "index as a string, e.g. [\"2\"].\n"
        "- multiple_answer: 'options' has 3-6 choices; 'correct' = two or more "
        "zero-based indices as strings, e.g. [\"0\",\"3\"].\n"
        "- true_false: 'options' is [\"True\",\"False\"]; 'correct' = [\"true\"] "
        "or [\"false\"].\n"
        "- short_answer: 'options' is []; 'correct' = acceptable answer strings, "
        "e.g. [\"photosynthesis\"].\n"
        "- essay: 'options' is []; 'correct' = [] (graded manually against the "
        "rubric); put grading guidance in 'rationale'."
    )

    user = (
        f"Create {count} {assessment_type} item(s).\n"
        f"Allowed item types (use only these): {', '.join(types)}.\n"
        f"Target difficulty: {difficulty}. Points per item: {points_each}.\n"
        + (f"Primary learning objective to align to: {objective_text}\n"
           if objective_text else "")
        + "\nAlign each item to one of these course objectives when possible and "
        "set 'objective_id' to that objective's id (or null if none fits):\n"
        f"{objectives_block}\n"
        f"\nCourse rubric (use to shape essay/short-answer expectations):\n"
        f"{rubric_block}\n"
        f"\n{type_rules}\n"
        "\nFor EVERY item set 'citation' to the [source: ...] label of the "
        "excerpt you used (copy 'source' verbatim; put the locator part such as "
        "'p.3' or 'slide 5' into citation.loc, and the document name into "
        "citation.source). Set 'confidence' to how directly the excerpt supports "
        "the item (high/medium/low). Write a short 'rationale' explaining the "
        "correct answer using the excerpt.\n"
        f"\n=== SOURCE EXCERPTS (the ONLY allowed source of truth) ===\n"
        f"{sources_block}\n"
        f"=== END SOURCE EXCERPTS ==="
    )

    try:
        raw = config.chat_json(
            system, user, _item_json_schema(), "assessment_items",
            temperature=0.2,
        )
    except Exception as e:
        raise RuntimeError(f"Item generation failed ({config.chat_provider()}): {e}") from e

    try:
        payload = json.loads(raw)
    except Exception:
        return []

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []

    valid_ids = {o.get("id") for o in (structure or {}).get("objectives") or []}
    out: list[dict] = []
    for it in items:
        cleaned = _validate(it, default_points=points_each, valid_ids=valid_ids)
        if cleaned is not None:
            out.append(cleaned)
    return out


def _format_rubric(rubric: dict | None) -> str:
    if not rubric:
        return "(none provided)"
    lines = [f"Rubric: {rubric.get('title', 'Untitled')}"]
    for c in rubric.get("criteria") or []:
        lines.append(f"- {c.get('criterion', '')}")
    return "\n".join(lines)


def _validate(it: dict, default_points, valid_ids: set) -> dict | None:
    """Validate + normalize one item; return None if it can't be salvaged."""
    if not isinstance(it, dict):
        return None
    t = it.get("type")
    if t not in ITEM_TYPES:
        return None
    stem = (it.get("stem") or "").strip()
    if not stem:
        return None

    options = it.get("options") or []
    if not isinstance(options, list):
        options = []
    options = [str(o) for o in options]

    correct = it.get("correct")

    if t == "mcq":
        idxs = _as_index_list(correct)
        if len(options) < 2 or len(idxs) != 1:
            return None
        if not all(0 <= i < len(options) for i in idxs):
            return None
        correct = idxs
    elif t == "multiple_answer":
        idxs = _as_index_list(correct)
        if len(options) < 2 or len(idxs) < 1:
            return None
        if not all(0 <= i < len(options) for i in idxs):
            return None
        correct = sorted(set(idxs))
    elif t == "true_false":
        b = _as_bool(correct)
        if b is None:
            return None
        options = ["True", "False"]
        correct = b
    elif t == "short_answer":
        answers = [str(a).strip() for a in correct] if isinstance(correct, list) \
            else ([str(correct).strip()] if correct not in (None, "") else [])
        answers = [a for a in answers if a]
        if not answers:
            return None
        options = []
        correct = answers
    elif t == "essay":
        options = []
        correct = []

    citation = it.get("citation") or {}
    if not isinstance(citation, dict):
        citation = {}
    citation = {
        "source": str(citation.get("source", "")).strip(),
        "loc": str(citation.get("loc", "")).strip(),
    }

    oid = it.get("objective_id")
    if oid is not None:
        try:
            oid = int(oid)
        except Exception:
            oid = None
        if valid_ids and oid not in valid_ids:
            oid = None

    try:
        points = float(it.get("points", default_points))
    except Exception:
        points = float(default_points) if default_points is not None else 1.0
    if points <= 0:
        points = float(default_points) if default_points else 1.0

    conf = it.get("confidence")
    if conf not in CONFIDENCE:
        conf = "medium"

    return {
        "type": t,
        "stem": stem,
        "options": options,
        "correct": correct,
        "points": points,
        "rationale": (it.get("rationale") or "").strip(),
        "citation": citation,
        "objective_id": oid,
        "confidence": conf,
    }


def _as_index_list(v) -> list[int]:
    """Coerce a 'correct' value into a list of integer indices."""
    if v is None:
        return []
    if isinstance(v, bool):  # avoid True->1 surprises
        return []
    if isinstance(v, int):
        return [v]
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, bool):
                continue
            try:
                out.append(int(x))
            except Exception:
                continue
        return out
    return []


def _as_bool(v):
    """Coerce a 'correct' value into a bool, or None if ambiguous."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, list) and len(v) == 1:
        return _as_bool(v[0])
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "t", "yes", "1"):
            return True
        if s in ("false", "f", "no", "0"):
            return False
    return None
