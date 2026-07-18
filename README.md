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

## Demo accounts & login

`seed_demo` creates ready-to-use accounts so you can log in and explore the UI
immediately — no manual account setup:

| Username | Role | Sees |
| --- | --- | --- |
| `admin` | Admin | Everything, plus the Django admin at `/admin/` |
| `engineer1`, `engineer2`, `engineer3` | Engineer | Queue, work orders, dashboard, equipment |
| `staff1` … `staff10` | Staff | Lodge and view their own complaints |

**All demo accounts share one password**, set by the `DEMO_PASSWORD` variable in
your `.env` (see `.env.example`). It defaults to **`demo1234`**. To use a
different demo password, set `DEMO_PASSWORD` in `.env` *before* running
`seed_demo` — the value in `.env` becomes the login password for every seeded
account. (The usernames above are fixed in the seeder.)

> `DEMO_PASSWORD` only affects the demo fixture accounts. It is a shared,
> well-known demo password on fake data — change it before any real deployment,
> and create real per-person accounts via the Django admin.

Start with `engineer1` for the fullest view.

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
