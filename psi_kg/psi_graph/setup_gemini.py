"""Configure Gemini privately and verify a small structured-output API request."""

import argparse
import getpass
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import quote, quote_plus

from dotenv import dotenv_values, set_key
from google import genai
from google.genai import types

DEFAULT_ENV = Path.home() / ".config/imperial-thermo-ai/.env"


def save_config(path, key, model):
    """Preserve unrelated provider settings; atomically replace with mode 0600."""
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".gemini-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w") as stream:
            if path.exists():
                stream.write(path.read_text())
        for variable, value in {
            "LLM_PROVIDER": "gemini",
            "LLM_MODEL": model,
            "GEMINI_API_KEY": key,
        }.items():
            set_key(temporary, variable, value)
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class GeminiSetupError(RuntimeError):
    """A message safe to display without request details or credentials."""


def safe_error(error, model=None, key=None):
    if isinstance(error, GeminiSetupError):
        return str(error)
    from google.genai.errors import APIError

    prefix = f"Gemini test for {model}" if model else "Gemini setup"
    if not isinstance(error, APIError):
        return f"{prefix} failed ({type(error).__name__}); no API response details available."
    code = error.code
    message = str(error.message or "")
    for secret in (
        key,
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("GOOGLE_API_KEY"),
    ):
        if secret:
            for form in (secret, quote(secret, safe=""), quote_plus(secret)):
                message = message.replace(form, "[REDACTED]")
                prefix = prefix.replace(form, "[REDACTED]")
    message = re.sub(r"https?://\S+", "[URL omitted]", message)
    message = re.sub(r"AIza[A-Za-z0-9_-]+", "[REDACTED]", message)
    message = re.sub(
        r"(?i)(?:api[_-]?key|authorization|access_token)\s*[:=]\s*[^\s,;]+",
        "[credential omitted]",
        message,
    )
    message = re.sub(r"[\x00-\x1f\x7f]", " ", message)
    hint = {
        400: "Check the model's structured-output support and request configuration.",
        401: "Check the API key.",
        403: "Check the API key's project permissions and model access.",
        404: "A listed model may still be unavailable for generation. Choose a current text model.",
        429: "Check API quota/rate limits and the key's project billing; this is not a model-not-found error.",
        503: "Google reports temporary high demand. Retry later or select another text model.",
    }.get(code, "Retry later if the service is temporarily unavailable.")
    return f"{prefix}: HTTP {code}. {message[:1000]} {hint}"


def text_models(client):
    names = {
        item.name.removeprefix("models/")
        for item in client.models.list()
        if item.name and "generateContent" in (item.supported_actions or [])
    }
    excluded = ("image", "tts", "live", "native-audio", "nano-banana", "omni")
    candidates = [
        name
        for name in names
        if not any(marker in name for marker in excluded)
        and not name.startswith(("antigravity-", "deep-research-", "gemma-"))
    ]
    preferred = (
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
    )
    return sorted(
        candidates,
        key=lambda name: (
            preferred.index(name) if name in preferred else len(preferred),
            name in ("gemini-2.5-flash", "gemini-2.5-pro"),
            name,
        ),
    )


def choose_model(models):
    if not models:
        raise GeminiSetupError(
            "No suitable text-generation models were listed for this key."
        )
    print("Text-model candidates; listing does not guarantee generation access:")
    for index, name in enumerate(models, 1):
        note = " (suggested)" if index == 1 else ""
        if name in ("gemini-2.5-flash", "gemini-2.5-pro"):
            note = " (legacy; restricted for new users)"
        print(f"{index}: {name}{note}")
    while True:
        value = input(
            "Choose a model number or ID [Enter = first; q = cancel]: "
        ).strip()
        if value.lower() == "q":
            raise GeminiSetupError("Setup cancelled; configuration unchanged.")
        if not value:
            return models[0]
        if value.isdigit() and 1 <= int(value) <= len(models):
            return models[int(value) - 1]
        value = value.removeprefix("models/")
        if value in models:
            return value
        print("Choose one of the listed text models.")


def probe(client, model, key):
    from google.genai.errors import APIError

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents="Return a JSON object with ok set to true.",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema={
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                ),
            )
            if json.loads(response.text or "null") != {"ok": True}:
                raise GeminiSetupError(
                    f"{model} did not return the expected structured JSON."
                )
            return
        except APIError as error:
            if error.code not in (500, 502, 503, 504) or attempt == 2:
                raise
            print(safe_error(error, model, key))
            print(f"Retrying the same model ({attempt + 2}/3)...", flush=True)
            time.sleep(attempt + 1)


def configure(path, model=None, *, show_next_step=True):
    from google.genai.errors import APIError

    path = path.expanduser()
    saved = dotenv_values(path) if path.exists() else {}
    key = getpass.getpass(
        "Paste Gemini API key (hidden; Enter keeps saved key): "
    ).strip()
    key = (
        key
        or saved.get("GEMINI_API_KEY")
        or saved.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not key:
        raise GeminiSetupError("No key supplied; configuration unchanged.")
    client = None
    try:
        client = genai.Client(
            api_key=key, http_options=types.HttpOptions(timeout=60000)
        )
        models = None
        unavailable = set()
        while True:
            if not model:
                if models is None:
                    models = text_models(client)
                model = choose_model(
                    [name for name in models if name not in unavailable]
                )
            print(f"Testing structured JSON with {model}...", flush=True)
            try:
                probe(client, model, key)
                break
            except APIError as error:
                detail = safe_error(error, model, key)
                message = (error.message or "").lower()
                if error.code in (401, 403) or (
                    "api key" in message and "invalid" in message
                ):
                    raise GeminiSetupError(detail) from None
                print(detail)
                if error.code == 404:
                    unavailable.add(model)
                print("Choose another model using the same key, or q to stop.")
                model = None
        save_config(path, key, model)
    except GeminiSetupError:
        raise
    except Exception as error:
        raise GeminiSetupError(safe_error(error, model, key)) from None
    finally:
        if client is not None:
            client.close()
    print(f"Gemini API check passed. Saved private configuration to {path}.")
    if show_next_step:
        print("Run: uv run psi-graph-manage")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--model", help="Optional model ID; otherwise list and choose")
    args = parser.parse_args()
    try:
        configure(args.env_file.expanduser(), args.model)
    except (KeyboardInterrupt, EOFError):
        print("Setup cancelled; configuration unchanged.")
        return 1
    except Exception as error:
        print(safe_error(error))
        print("Configuration unchanged.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
