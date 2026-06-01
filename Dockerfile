# syntax=docker/dockerfile:1.7

# Multi-stage build: install deps in a builder, copy a slim runtime layer.
# This is the API image. The dashboard rides the same image but launches
# `streamlit run`; see docker-compose.yml.

FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Pull a self-contained uv binary from astral-sh's official image. Avoids
# needing curl/wget in the slim base image.
COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /usr/local/bin/uv

WORKDIR /app

# Copy lockfile + project metadata first so the dependency layer caches well.
# README.md and LICENSE are referenced from pyproject.toml ([project].readme
# / [project].license) — hatchling reads them at build time, so they must
# land in the build context before `uv sync` runs.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev


FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    HOME=/home/app

WORKDIR /app
COPY --from=builder /app /app

# Drop privileges. The app user MUST have a writable home directory:
# Streamlit calls expanduser("~") on startup to write its machine-id state
# file, and an unwritable / missing $HOME crashes the dashboard with
# PermissionError. uvicorn never touches $HOME so this only manifests in
# the dashboard service. HOME is also pinned via ENV above so it is not
# dependent on passwd-fallback behaviour under USER app.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home --home-dir /home/app app \
    && chown -R app:app /app /home/app
USER app

EXPOSE 8000

# Default command runs the API. The dashboard image overrides this in compose.
CMD ["uvicorn", "cfn_auditor.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
