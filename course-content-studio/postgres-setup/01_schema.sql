-- ===========================================================================
-- Course Content Studio — Structured lookup schema (Postgres)
-- ===========================================================================
-- Target: a CLOUD Postgres (Neon or Supabase). Load this file first, then
-- 02_seed.sql. See README.md for provider-specific steps.
--
-- The app connects with a READ-MOSTLY user. Below is how to create a
-- least-privilege role `course_app` (SELECT everywhere; INSERT only on the
-- question_bank, since the "save generated items" feature writes there).
--
-- ---------------------------------------------------------------------------
-- LEAST-PRIVILEGE APP ROLE  (run ONCE, as the DB owner / admin, AFTER the
-- tables below exist — i.e. re-run this block after the CREATE TABLEs, or just
-- paste it at the end of your first load). Replace 'CHANGE-ME-strong-pw'.
-- ---------------------------------------------------------------------------
--
--   -- 1) Create the role the app logs in as (set PG_USER / PG_PASSWORD to match):
--   CREATE ROLE course_app LOGIN PASSWORD 'CHANGE-ME-strong-pw';
--
--   -- 2) Let it reach the schema:
--   GRANT CONNECT ON DATABASE course TO course_app;   -- use your DB name
--   GRANT USAGE   ON SCHEMA public   TO course_app;
--
--   -- 3) Read-only on everything (the "lookup" part of the lab):
--   GRANT SELECT ON ALL TABLES IN SCHEMA public TO course_app;
--   ALTER DEFAULT PRIVILEGES IN SCHEMA public
--     GRANT SELECT ON TABLES TO course_app;            -- future tables too
--
--   -- 4) Writer grant for ONE table only — the question bank (save_items()):
--   GRANT INSERT ON question_bank TO course_app;
--   GRANT USAGE, SELECT ON SEQUENCE question_bank_id_seq TO course_app;  -- serial PK
--
--   -- Result: course_app can read all reference data but can only ADD bank
--   -- questions — it cannot UPDATE/DELETE anything or touch other tables.
--   -- On Supabase, also confirm RLS is OFF for these tables (it is by default
--   -- for tables you create via the SQL editor) or add permissive policies.
-- ===========================================================================

-- Clean re-load (safe to run repeatedly). Order respects foreign keys.
DROP TABLE IF EXISTS rubric_criteria   CASCADE;
DROP TABLE IF EXISTS rubrics           CASCADE;
DROP TABLE IF EXISTS question_bank     CASCADE;
DROP TABLE IF EXISTS learning_objectives CASCADE;
DROP TABLE IF EXISTS content_sources   CASCADE;
DROP TABLE IF EXISTS courses           CASCADE;

CREATE TABLE courses (
    id    serial PRIMARY KEY,
    code  text NOT NULL,
    title text NOT NULL,
    term  text
);

CREATE TABLE learning_objectives (
    id          serial PRIMARY KEY,
    course_id   int NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    text        text NOT NULL,
    bloom_level text
);

CREATE TABLE rubrics (
    id        serial PRIMARY KEY,
    course_id int NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title     text NOT NULL
);

CREATE TABLE rubric_criteria (
    id          serial PRIMARY KEY,
    rubric_id   int NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,
    criterion   text NOT NULL,
    levels_json jsonb
);

CREATE TABLE question_bank (
    id           serial PRIMARY KEY,
    course_id    int NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    objective_id int REFERENCES learning_objectives(id) ON DELETE SET NULL,
    type         text NOT NULL,            -- e.g. 'mcq', 'short_answer', 'true_false'
    stem         text NOT NULL,
    options_json jsonb,                     -- choices for mcq / true_false
    correct_json jsonb,                     -- correct answer(s)
    points       numeric DEFAULT 1,
    source       text                       -- provenance: 'seed', 'generated', etc.
);

CREATE TABLE content_sources (
    id          serial PRIMARY KEY,
    course_id   int NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    filename    text NOT NULL,
    kind        text,                       -- 'syllabus', 'reading', 'slides', ...
    ingested_at timestamptz NOT NULL DEFAULT now(),
    chunk_count int
);

-- Helpful lookup indexes (the app filters by these FKs).
CREATE INDEX idx_objectives_course ON learning_objectives(course_id);
CREATE INDEX idx_rubrics_course    ON rubrics(course_id);
CREATE INDEX idx_criteria_rubric   ON rubric_criteria(rubric_id);
CREATE INDEX idx_bank_course       ON question_bank(course_id);
CREATE INDEX idx_bank_objective    ON question_bank(objective_id);
CREATE INDEX idx_sources_course    ON content_sources(course_id);
