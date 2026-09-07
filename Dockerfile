# syntax=docker/dockerfile:1

# Both stages share this base so the venv's interpreter path exists in the runtime image.
ARG PYTHON_IMAGE=python:3.13-slim-bookworm
ARG UV_VERSION=0.11.21


FROM ${PYTHON_IMAGE} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# dependencies first, without the project, so this layer survives source edits
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --no-editable

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# --no-editable copies the package into the venv, so the runtime stage needs no src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


FROM ${PYTHON_IMAGE} AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
# migrations are not part of the package, so they are copied explicitly
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app entrypoint.sh ./

USER app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
