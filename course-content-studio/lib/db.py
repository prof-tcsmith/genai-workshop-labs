"""Structured lookup against a real cloud Postgres (Neon / Supabase).

This is the counterpart to ``lib.vectors`` (fuzzy meaning) — here we fetch
**exact, authoritative facts** with parameterized SQL. Connection details come
from Secrets via :mod:`lib.config` (``PG_*``); we never build SQL by string
formatting — every value is bound with ``%s`` so the queries are safe and
repeatable. Rows come back as dicts (``psycopg.rows.dict_row``) and every
connection is opened in a ``with`` block so it always closes cleanly.
"""
from __future__ import annotations

import psycopg
import psycopg.rows

from lib import config


def connect() -> psycopg.Connection:
    """Open a connection to the configured cloud Postgres.

    Rows are returned as dicts. Raises a clear error if the ``PG_*`` secrets
    have not been set yet (so the page can show setup instructions instead of a
    cryptic driver error).
    """
    if not config.pg_configured():
        raise RuntimeError(
            "Postgres not configured — set PG_* secrets "
            "(see postgres-setup/README.md)."
        )
    # prepare_threshold=None disables server-side prepared statements so this
    # works over a transaction-mode pooler (e.g. Neon's -pooler host / PgBouncer)
    # as well as a direct connection. Queries here aren't hot-looped, so there's
    # no meaningful downside.
    return psycopg.connect(
        config.pg_dsn(), row_factory=psycopg.rows.dict_row, prepare_threshold=None
    )


def list_courses() -> list[dict]:
    """All courses, ordered by code."""
    sql = "SELECT id, code, title, term FROM courses ORDER BY code;"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def list_objectives(course_id: int) -> list[dict]:
    """Learning objectives for one course (parameterized)."""
    sql = (
        "SELECT id, course_id, text, bloom_level "
        "FROM learning_objectives "
        "WHERE course_id = %s "
        "ORDER BY id;"
    )
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (course_id,))
        return cur.fetchall()


def get_rubric(course_id: int) -> dict | None:
    """The course's rubric plus its criteria list, or None if it has none.

    Returns ``{id, course_id, title, criteria: [ {criterion, levels_json}, ... ]}``.
    """
    rubric_sql = (
        "SELECT id, course_id, title FROM rubrics "
        "WHERE course_id = %s ORDER BY id LIMIT 1;"
    )
    criteria_sql = (
        "SELECT id, rubric_id, criterion, levels_json "
        "FROM rubric_criteria WHERE rubric_id = %s ORDER BY id;"
    )
    with connect() as conn, conn.cursor() as cur:
        cur.execute(rubric_sql, (course_id,))
        rubric = cur.fetchone()
        if rubric is None:
            return None
        cur.execute(criteria_sql, (rubric["id"],))
        rubric["criteria"] = cur.fetchall()
        return rubric


def list_bank(course_id: int, objective_id: int | None = None) -> list[dict]:
    """Question-bank items for a course, optionally filtered to one objective.

    Both filters are passed as bound parameters (never interpolated).
    """
    if objective_id is None:
        sql = (
            "SELECT id, course_id, objective_id, type, stem, "
            "options_json, correct_json, points, source "
            "FROM question_bank WHERE course_id = %s ORDER BY id;"
        )
        params: tuple = (course_id,)
    else:
        sql = (
            "SELECT id, course_id, objective_id, type, stem, "
            "options_json, correct_json, points, source "
            "FROM question_bank "
            "WHERE course_id = %s AND objective_id = %s ORDER BY id;"
        )
        params = (course_id, objective_id)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def save_items(course_id: int, items: list[dict]) -> int:
    """Insert generated question-bank items for a course; return the count.

    Each item dict may carry: ``objective_id, type, stem, options_json,
    correct_json, points, source``. Missing keys fall back to sensible
    defaults. All values are bound parameters.
    """
    if not items:
        return 0
    sql = (
        "INSERT INTO question_bank "
        "(course_id, objective_id, type, stem, options_json, correct_json, "
        "points, source) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s);"
    )
    rows = [
        (
            course_id,
            it.get("objective_id"),
            it.get("type", "short_answer"),
            it.get("stem", ""),
            it.get("options_json"),
            it.get("correct_json"),
            it.get("points", 1),
            it.get("source", "generated"),
        )
        for it in items
    ]
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(sql, rows)
        conn.commit()
        return len(rows)
