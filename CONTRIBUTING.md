# Contributing

Thanks for your interest in improving HEMDesk (Biomedical CMMS). This guide
covers the local setup, the conventions the codebase follows, and how changes
get merged.

## Development setup

Requirements: [uv](https://docs.astral.sh/uv/) and Docker (for Postgres).

```bash
docker compose up -d db             # Postgres
uv sync                             # .venv with all deps, incl. dev
uv run python manage.py migrate
uv run python manage.py seed_demo   # optional demo data + accounts
uv run python manage.py runserver
```

The AI features talk to any OpenAI-compatible endpoint configured in `.env`
(see `.env.example`); for local work `docker compose up -d ollama` plus a
one-time `docker compose exec ollama ollama pull llama3.2:3b` is enough.
Everything degrades gracefully when no LLM is reachable.

## Running checks

```bash
uv run pytest        # full suite — needs the db container running
uv run ruff check .  # lint (E, F, I — line length 88)
```

Both must be green before a PR. CI runs them on every pull request.

## Workflow

- Branch from `main` for every change; open a PR back to `main`.
- Link the issue your PR addresses (`Closes #NN`); open an issue first for
  anything non-trivial.
- Commit messages: a single concise line, imperative mood
  (`feat: ...`, `fix: ...`, `chore: ...`).

## Code conventions

- **State changes go through services.** Views stay thin; mutations live in
  each app's `services.py`, wrapped in `transaction.atomic` and recorded via
  `apps.core.audit.record(...)`. Don't write model mutations directly in views.
- **Role gating everywhere.** New views use `RoleRequiredMixin` (or the
  `_require_engineer_or_admin` pattern) *and* templates hide UI the role
  can't use. Staff must never reach engineer/admin surfaces.
- **No hard deletes.** Follow the append-only / no-delete model conventions
  from `apps.core`; equipment is condemned, not deleted.
- **Numbers from SQL, words from LLM.** Metrics and scores are computed in
  queries; the LLM only writes narrative, and its failure must never block a
  workflow.
- **Templates** use the design-system classes (`card`, `btn btn-primary`,
  `input`, `badge`, `link`, `text-muted`) rather than ad-hoc Tailwind color
  utilities.
- **Migrations** accompany every model change (`uv run python manage.py
  makemigrations`).
- **Tests** live in `tests/`, run against real Postgres, and should verify
  behavior rather than mocks (the LLM client is the one thing routinely
  monkeypatched). Tests that write uploaded files must point `MEDIA_ROOT` at
  `tmp_path` — see the `isolated_media_root` fixtures for the pattern.

## Reporting bugs & proposing features

Use the issue templates. For security problems, see [SECURITY.md](SECURITY.md)
— please don't open a public issue.
