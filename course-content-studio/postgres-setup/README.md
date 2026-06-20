# Structured lookup — cloud Postgres setup

This lab (`pages/2_Structured_lookup_PG.py`) reads **exact, authoritative facts**
— courses, learning objectives, rubrics, and a question bank — from a real
**cloud Postgres** database using parameterized SQL.

You only need to load two files once: **`01_schema.sql`** then **`02_seed.sql`**.

---

## 1. Pick a free cloud Postgres

Either provider works; both give you a free Postgres and a browser SQL editor.

### Option A — Neon (https://neon.tech)
1. Create a project. Note the **database name** (default `neondb`) and the
   connection details (host, user, password) from the **Connection Details**
   panel. Neon requires SSL.
2. Open the **SQL Editor**.
3. Paste the entire contents of **`01_schema.sql`**, run it.
4. Paste the entire contents of **`02_seed.sql`**, run it.

### Option B — Supabase (https://supabase.com)
1. Create a project; choose a strong DB password (you'll need it).
2. Open **SQL Editor → New query**.
3. Paste **`01_schema.sql`**, run it.
4. Paste **`02_seed.sql`**, run it.
5. The seeded tables are created in `public` and have **RLS off** by default for
   tables made in the SQL editor, so the app can read them. If you enabled RLS,
   add a permissive `SELECT` policy or use the service connection string.

### Or from a terminal (either provider) — `psql`
Grab the connection string from the provider, then:

```bash
psql "$CONN" -f 01_schema.sql -f 02_seed.sql
# $CONN looks like:
#   postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

---

## 2. (Recommended) create the least-privilege app role

The app should log in as a **read-mostly** user, not the admin. The exact
SQL is in the comment block at the top of **`01_schema.sql`** — it creates a
`course_app` role with `SELECT` on everything and `INSERT` only on
`question_bank` (so the "save generated items" feature works, nothing else).
Run that block as the DB owner after loading the schema, and point `PG_USER` /
`PG_PASSWORD` at it.

If you skip this, just use the provider's default user — the app still works.

---

## 3. Set these Streamlit Secrets

In `.streamlit/secrets.toml` locally, or in **Streamlit Cloud → App → Settings →
Secrets**:

| Secret        | What it is                          | Example                              |
|---------------|-------------------------------------|--------------------------------------|
| `PG_HOST`     | Database host                       | `ep-cool-bird-123.us-east-2.aws.neon.tech` |
| `PG_PORT`     | Port                                | `5432`                               |
| `PG_DB`       | Database name                       | `neondb` (Neon) / `postgres` (Supabase) |
| `PG_USER`     | App login role                      | `course_app`                         |
| `PG_PASSWORD` | Password for that role              | `your-strong-password`               |
| `PG_SSLMODE`  | SSL mode (cloud needs SSL)          | `require`                            |

Example `secrets.toml`:

```toml
PG_HOST = "ep-cool-bird-123.us-east-2.aws.neon.tech"
PG_PORT = "5432"
PG_DB = "neondb"
PG_USER = "course_app"
PG_PASSWORD = "your-strong-password"
PG_SSLMODE = "require"
```

The page detects whether these are set via `config.pg_configured()`; until then
it shows setup instructions instead of running queries.

---

## 4. (Optional) fully offline Postgres via Docker

No internet? Build the bundled image — it auto-loads both SQL files on first
boot (see the `Dockerfile` here):

```bash
docker build -t ccs-postgres ./postgres-setup
docker run --name ccs-pg -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=course -p 5432:5432 ccs-postgres
```

Then set: `PG_HOST=localhost`, `PG_PORT=5432`, `PG_DB=course`,
`PG_USER=postgres`, `PG_PASSWORD=devpass`, `PG_SSLMODE=disable`.

> Init scripts only run on an **empty** data directory. To reseed:
> `docker rm -v ccs-pg` then `docker run ...` again.
