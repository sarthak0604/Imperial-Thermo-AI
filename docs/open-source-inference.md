# Open-source inference and validation

The backend now accepts `THERMO_PLANNER=open_source`, using an OpenAI-compatible
chat endpoint. This supports vLLM deployments without loading a model separately
inside each website process. All scientific executions retain the same allowlist,
source checks, and function validators. Provider selection is explicit; API failure
does not silently switch to a model with unknown accuracy.

Start a separately provisioned inference service, for example:

```bash
vllm serve Qwen/Qwen3-4B-Instruct-2507 --port 8016 --enable-prefix-caching
```

Then start the website from the repository root:

```bash
AI_PROVIDER=thermo THERMO_PLANNER=open_source \
PSI_PARSER_MODEL=Qwen/Qwen3-4B-Instruct-2507 \
THERMO_INFERENCE_URL=http://127.0.0.1:8016/v1 \
PORT=8015 .venv/bin/python 'NASA Space Apps/frontend/standin/server.py'
```

`THERMO_INFERENCE_KEY` configures endpoint authentication; the default `local` is
suitable only for a protected local service. `THERMO_MAX_OUTPUT_TOKENS` defaults
to 2400. The service requests JSON responses with temperature zero. Server/model
support for JSON mode must be checked on the chosen deployment.

Prefer serving the existing checkpoint more efficiently before reducing model
size or precision. vLLM documents prefix caching and its OpenAI-compatible API:
[server documentation](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/),
[prefix caching](https://docs.vllm.ai/en/stable/design/prefix_caching/).
Qwen documents the Instruct-2507 models as non-thinking:
[Qwen deployment](https://qwen.readthedocs.io/en/stable/deployment/vllm.html),
[Qwen quickstart](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/quickstart.md).

Caching avoids repeated prefix processing; it does not remove the need to measure
model quality, end-to-end latency, or numerical differences across runtimes.
Smaller checkpoints, quantization, and more aggressive decoding are separate
experiments. Do not claim unchanged accuracy without held-out comparison.

Run a labelled routing comparison with the same JSONL cases for each provider:

```bash
uv run python examples/evaluate_model_routing.py --provider api \
  --cases examples/model-routing-cases.jsonl --output /tmp/api-routing.json
uv run python examples/evaluate_model_routing.py --provider open_source \
  --cases examples/model-routing-cases.jsonl --output /tmp/local-routing.json
```

Each JSONL case contains `id`, `question`, `intent`, and `model_ids`. The small
bundled smoke set checks the harness, not the full plan's human-reviewed 120-case
release benchmark. Include unsupported cases, scientific domain distinctions,
input questions and complete conversations before changing production defaults.

GPU access in the implementation workspace was blocked by the operating system.
No GPU speedup, checkpoint accuracy parity, or new model deployment is claimed.
