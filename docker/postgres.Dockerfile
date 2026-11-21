# Local development database only. Production uses Supabase Postgres,
# which ships the same three extensions (PostGIS, pgvector, pg_trgm).
FROM postgres:17-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-17-postgis-3 postgresql-17-pgvector \
 && rm -rf /var/lib/apt/lists/*
