# Optional: a fully OFFLINE Postgres for local development of this lab.
#
# The workshop normally points at a CLOUD Postgres (Neon / Supabase) — see
# README.md. This image is only a convenience for working without internet:
# Postgres runs every .sql file in /docker-entrypoint-initdb.d/ on first boot,
# so the schema + seed load automatically into a fresh data volume.
#
# Build & run:
#   docker build -t ccs-postgres ./postgres-setup
#   docker run --name ccs-pg -e POSTGRES_PASSWORD=devpass \
#     -e POSTGRES_DB=course -p 5432:5432 ccs-postgres
#
# Then set Secrets to: PG_HOST=localhost PG_PORT=5432 PG_DB=course
#   PG_USER=postgres PG_PASSWORD=devpass PG_SSLMODE=disable
# (init scripts only run on an EMPTY data dir — `docker rm -v ccs-pg` to reseed.)
FROM postgres:16

COPY 01_schema.sql 02_seed.sql /docker-entrypoint-initdb.d/
