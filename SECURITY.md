# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities **privately** via
[GitHub security advisories](https://github.com/mhumzaarain/HEMDesk./security/advisories/new)
rather than a public issue. Include steps to reproduce and the impact you
believe it has. You should receive an initial response within a week.

## Supported versions

The project is under active development; only the latest state of `main` is
supported with security fixes.

## Scope notes for deployers

- **Demo fixtures are not accounts.** `seed_demo` creates well-known demo
  users sharing the `DEMO_PASSWORD` from `.env` — never run it against a real
  deployment. Real accounts are created in the Django admin and passwords are
  hashed in the database.
- **`.env` holds secrets** (database credentials, `SECRET_KEY`, optionally an
  LLM API key). Keep it out of version control and readable only by the
  service user.
- **LLM privacy.** Prompts include complaint/remark free-text, engineers'
  assistant questions and chat history, service-manual excerpts, and device
  details. With the default bundled Ollama nothing leaves the deployment;
  pointing `LLM_BASE_URL` at an external endpoint sends that data there.
- **HTTPS hardening** for production deployments is tracked in issue #2;
  review it before exposing an instance beyond a trusted network.
