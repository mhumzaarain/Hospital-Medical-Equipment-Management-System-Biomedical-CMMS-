# Biomedical CMMS

Hospital Medical Equipment Management System — track medical equipment and
manage malfunction complaints and repairs. Phase 1: a complete, server-rendered
Django CMMS (no AI features yet).

## Stack

Django 5.2 · PostgreSQL · HTMX + Alpine.js + Chart.js + Tailwind ·
Procrastinate (Postgres task queue) · uv for dependency management.

## Local development

Requires [uv](https://docs.astral.sh/uv/) and Docker (for Postgres).

```bash
docker compose up -d db          # start Postgres
uv sync                          # create .venv and install deps (incl. dev)
uv run python manage.py migrate
uv run python manage.py seed_demo   # optional: 90 days of demo data
uv run python manage.py runserver
```

Demo logins (after `seed_demo`): `admin` / `engineer1` / `staff1`, password `demo1234`.

## Tests

```bash
uv run pytest
```

## Full stack (Docker)

```bash
cp .env.example .env
docker compose up --build        # nginx :8080 -> gunicorn, worker, postgres
docker compose exec web python manage.py seed_demo
```

## Docs

- Design spec: `docs/superpowers/specs/`
- Implementation plan: `docs/superpowers/plans/`
- Deferred work & pre-production hardening: `docs/FOLLOWUPS.md`
