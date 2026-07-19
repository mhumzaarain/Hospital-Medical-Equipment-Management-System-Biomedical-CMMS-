🚧 Work in Progress: This repository is currently under development. Expect incomplete features, breaking changes, and ongoing updates

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

## AI features (Phase 2)

The app talks to any OpenAI-compatible LLM endpoint — pick one via `.env`:

| Setup | .env |
|---|---|
| Bundled Ollama container (default) | nothing to change |
| Own vLLM server | `LLM_BASE_URL=http://your-host:8000/v1`, `LLM_MODEL=...` |
| Hospital LLM gateway | `LLM_BASE_URL=https://llm.hospital.example/v1`, `LLM_API_KEY=...` |

First start with the bundled container, pull the default model once:

    docker compose up -d ollama
    docker compose exec ollama ollama pull llama3.2:3b

Everything degrades gracefully with no LLM: reports generate without the
narrative, risk scores compute without explanations.

Privacy note: prompts include complaint and remark free-text, engineers'
assistant questions and chat history, service-manual excerpts, and device
details (serial number, department). The default bundled Ollama runs locally,
so nothing leaves your deployment — but if you point `LLM_BASE_URL` at an
external endpoint, all of that is sent there.

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

## Production: real user accounts

Demo accounts (`seed_demo` / `DEMO_PASSWORD`) are throwaway fixtures. Real
accounts are **never** stored in `.env` — they live in the database (passwords
hashed) and are created inside the app.

1. **Create the first admin** (one time), either:
   - Interactive (standard): `python manage.py createsuperuser` — prompts for
     the credentials; nothing is written to a file.
   - Automated/container: set `SUPERUSER_*` in your private `.env` (see
     `.env.example`) and run `python manage.py create_superuser`. It is
     idempotent — safe to run on every deploy; it skips if a superuser already
     exists or the variables are unset. Use `--force` to reset the password.
2. **Create every other user** via the Django admin at `/admin/` — set each
   person's username, role, employee ID, and an initial password.
3. **Each user changes their own password** at `/accounts/password_change/`
   (the "Change password" link in the top nav). Admins can also reset a
   password from `/admin/`.

So `.env` holds infrastructure config plus (optionally) the single bootstrap
admin password; all real people are managed in the app.

## Docs

- Design spec: `docs/superpowers/specs/`
- Implementation plan: `docs/superpowers/plans/`
- Deferred work & pre-production hardening: `docs/FOLLOWUPS.md`

## License

Copyright (C) 2026 Muhammad Humza Arain

This project is licensed under the **GNU Affero General Public License v3.0**
(AGPL-3.0). You may use, modify, and distribute it under the terms of that
license; if you run a modified version as a network service, you must make the
complete corresponding source code available to its users. See the
[`LICENSE`](LICENSE) file for the full text.
