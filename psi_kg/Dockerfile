FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY . /app
RUN uv sync --frozen --no-dev --extra local \
    && /app/.venv/bin/python -c "import torch; assert torch.version.cuda, 'CUDA-enabled PyTorch is required'; print('PyTorch CUDA build:', torch.version.cuda)"
# Keep the default model in image layers, outside the 10 GiB scratch volume.
# Pin the snapshot so each build uses the same weights and tokenizer.
RUN /app/.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-4B-Instruct-2507', revision='cdbee75f17c01a7cc42f958dc650907174af0554', local_dir='/opt/models/qwen', allow_patterns=['*.json', '*.safetensors', '*.txt', 'LICENSE'])"
ENV PYTHONUNBUFFERED=1 \
    LLM_BUNDLED_MODEL_ID=Qwen/Qwen3-4B-Instruct-2507 \
    LLM_BUNDLED_MODEL_PATH=/opt/models/qwen
CMD ["/app/.venv/bin/python", "/app/cloud_entrypoint.py"]
