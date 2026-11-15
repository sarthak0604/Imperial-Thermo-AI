"""Provider-neutral structured generation, content-addressed cache and secret-safe errors."""

import json
import math
import os
import time
from urllib.request import Request, urlopen

from .common import digest, now, read_json, write_json
from .nasa_access import tls_context

KEYS = {
    "local": (),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai-compatible": ("LLM_API_KEY",),
}
DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


class QuotaExceededError(RuntimeError):
    """Stop cleanly on rate/quota limits; preserve caches for a later resume."""


class LLM:
    def __init__(self, output, provider, model, base_url=None, api_key_env=None):
        if provider not in KEYS:
            raise ValueError("Unsupported provider: " + provider)
        self.provider, self.model, self.output = provider, model, output
        self.base_url = (
            base_url or os.environ.get("LLM_BASE_URL") or DEFAULT_URLS.get(provider, "")
        ).rstrip("/")
        names = (api_key_env,) if api_key_env else KEYS[provider]
        self.key = next((os.environ[n] for n in names if os.environ.get(n)), None)
        local = self.base_url.startswith(("http://localhost:", "http://127.0.0.1:"))
        if (
            not self.key
            and provider != "local"
            and not (provider == "openai-compatible" and local)
        ):
            raise RuntimeError(
                "Missing credential. Set "
                + " or ".join(names)
                + "; parsed files remain cached."
            )
        if not model:
            raise ValueError(
                "Set --model or LLM_MODEL to a model available to your provider/account."
            )
        if provider == "openai-compatible" and not self.base_url:
            raise ValueError(
                "OpenAI-compatible providers require --base-url or LLM_BASE_URL"
            )
        if self.base_url and not (self.base_url.startswith("https://") or local):
            raise ValueError(
                "API base URL must use HTTPS, except explicit localhost endpoints"
            )
        self.min_request_interval = float(
            os.environ.get("LLM_MIN_REQUEST_INTERVAL_SECONDS", "0")
        )
        if (
            not math.isfinite(self.min_request_interval)
            or not 0 <= self.min_request_interval <= 60
        ):
            raise ValueError(
                "LLM_MIN_REQUEST_INTERVAL_SECONDS must be between 0 and 60"
            )
        self.last_request_at = None
        self.usage = []
        self.client = None
        if provider == "local":
            from .local_model import LocalModel

            self.client = LocalModel(model)
            self.base_url = ""
        elif provider == "gemini":
            from google import genai
            from google.genai import types

            self.client = genai.Client(
                api_key=self.key, http_options=types.HttpOptions(timeout=300000)
            )

    def post(self, route, body, headers):
        request = Request(
            self.base_url + route,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **headers},
        )
        with urlopen(request, timeout=300, context=tls_context()) as response:
            return json.load(response)

    def generate(self, system, prompt, schema):
        if self.provider == "local":
            return self.client.generate(system, prompt, schema)
        shape = schema.model_json_schema()
        if self.provider == "gemini":
            from google.genai import types

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_json_schema=shape,
                    max_output_tokens=32768,
                ),
            )
            result = schema.model_validate_json(response.text or "")
            usage = (
                response.usage_metadata.model_dump(mode="json")
                if response.usage_metadata
                else {}
            )
        elif self.provider == "openai":
            response = self.post(
                "/responses",
                dict(
                    model=self.model,
                    instructions=system,
                    input=prompt,
                    max_output_tokens=32768,
                    store=False,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": schema.__name__,
                            "strict": True,
                            "schema": shape,
                        }
                    },
                ),
                {"Authorization": "Bearer " + self.key},
            )
            if response.get("status") not in (None, "completed"):
                raise ValueError("Incomplete model response")
            text = "".join(
                part.get("text", "")
                for message in response.get("output", [])
                for part in message.get("content", [])
                if part.get("type") == "output_text"
            )
            result, usage = schema.model_validate_json(text), response.get("usage", {})
        elif self.provider == "anthropic":
            response = self.post(
                "/messages",
                dict(
                    model=self.model,
                    max_tokens=32768,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    tools=[
                        {
                            "name": "emit_science",
                            "description": "Return validated scientific extraction",
                            "input_schema": shape,
                        }
                    ],
                    tool_choice={"type": "tool", "name": "emit_science"},
                ),
                {
                    "x-api-key": self.key,
                    "anthropic-version": os.environ.get(
                        "ANTHROPIC_VERSION", "2023-06-01"
                    ),
                },
            )
            blocks = [
                p["input"]
                for p in response.get("content", [])
                if p.get("type") == "tool_use" and p.get("name") == "emit_science"
            ]
            if len(blocks) != 1 or response.get("stop_reason") == "max_tokens":
                raise ValueError("Missing/truncated structured tool result")
            result, usage = schema.model_validate(blocks[0]), response.get("usage", {})
        else:
            response = self.post(
                "/chat/completions",
                dict(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema.__name__,
                            "strict": True,
                            "schema": shape,
                        },
                    },
                ),
                {"Authorization": "Bearer " + self.key} if self.key else {},
            )
            choice = response["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                raise ValueError("Incomplete compatible API response")
            result = schema.model_validate_json(choice["message"]["content"])
            usage = response.get("usage", {})
        return result, usage

    def call(self, stage, payload, schema):
        from .science import PROMPT_VERSION, SYSTEM

        body = json.dumps(payload, ensure_ascii=False)
        key = digest(
            PROMPT_VERSION
            + self.provider
            + self.base_url
            + self.model
            + (
                json.dumps(
                    {
                        name: os.environ.get(name)
                        for name in (
                            "LLM_CONTEXT_TOKENS",
                            "LLM_MAX_NEW_TOKENS",
                            "LLM_DEVICE",
                        )
                    },
                    sort_keys=True,
                )
                if self.provider == "local"
                else ""
            )
            + stage
            + SYSTEM
            + body
            + json.dumps(schema.model_json_schema(), sort_keys=True)
        )
        cache = self.output / "llm_cache" / (key + ".json")
        if cache.exists():
            data = read_json(cache)
            self.usage.append(
                dict(stage=stage, cached=True, cache_key=key, **data.get("usage", {}))
            )
            return schema.model_validate(data["result"])
        prompt = f"STAGE: {stage}\nReturn the requested schema.\nINPUT DATA:\n" + body
        for attempt in range(4):
            try:
                if self.last_request_at is not None:
                    delay = self.min_request_interval - (
                        time.monotonic() - self.last_request_at
                    )
                    if delay > 0:
                        time.sleep(delay)
                self.last_request_at = time.monotonic()
                result, usage = self.generate(SYSTEM, prompt, schema)
                write_json(
                    cache,
                    dict(
                        stage=stage,
                        provider=self.provider,
                        model=self.model,
                        timestamp=now(),
                        prompt_version=PROMPT_VERSION,
                        usage=usage,
                        result=result.model_dump(),
                    ),
                )
                self.usage.append(
                    dict(stage=stage, cached=False, cache_key=key, **usage)
                )
                write_json(self.output / "llm_usage.json", self.usage)
                return result
            except Exception as exc:
                from .local_model import LocalModelError

                if isinstance(exc, LocalModelError):
                    raise
                code = getattr(exc, "code", None)
                if code == 429:
                    raise QuotaExceededError(
                        f"{self.provider} quota/rate limit reached during {stage} (HTTP 429). "
                        "Stopped without changing providers or models. Completed calls remain cached; "
                        "resume the same prepared run with --stage generate after quota is available."
                    ) from None
                if code in (400, 401, 403, 404):
                    raise RuntimeError(
                        f"{self.provider} API rejected {stage}: HTTP {code}; check model, key, endpoint and billing."
                    ) from None
                if attempt == 3:
                    raise RuntimeError(
                        f"{self.provider} {stage} failed: {type(exc).__name__}, code={code}"
                    ) from None
                time.sleep(min(2 ** (attempt + 2), 30))
