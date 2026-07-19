FROM python:3.12-slim

# uv provides fast, reproducible dependency installation from uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# WeasyPrint's runtime libraries (PDF rendering, Task 6).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer) from the lockfile, without dev deps.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Put the project's virtualenv on PATH so `python`/`gunicorn` resolve to it.
ENV PATH="/app/.venv/bin:$PATH"

ENV DJANGO_SETTINGS_MODULE=config.settings.prod
RUN SECRET_KEY=collectstatic-dummy python manage.py collectstatic --noinput

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
