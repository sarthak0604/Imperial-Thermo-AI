FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY README.md ./
COPY src/ ./src/
COPY thermo-reference/ ./thermo-reference/
RUN uv sync --locked --no-dev --no-editable

COPY ["NASA Space Apps/frontend/", "/app/frontend/"]

ENTRYPOINT ["/app/.venv/bin/thermo-execute"]
