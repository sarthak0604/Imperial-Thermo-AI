FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY . /app
RUN uv sync --frozen --no-dev
ENV PYTHONUNBUFFERED=1
CMD ["/app/.venv/bin/python", "/app/cloud_entrypoint.py"]
