# One image, two install modes. Set INSTALL_DEV=true for dev.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
# The venv is outside /app. In dev, the bind mount of the source code on /app
# does not hide the installed packages.

WORKDIR /app

ARG INSTALL_DEV=false

# Install dependencies first. This layer is cached until the lock file changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    if [ "$INSTALL_DEV" = "true" ]; then \
        uv sync --frozen --no-install-project; \
    else \
        uv sync --frozen --no-install-project --no-dev; \
    fi

COPY . .

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
