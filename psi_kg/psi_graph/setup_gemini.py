"""Configure Gemini privately and verify a small structured-output API request."""

import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path

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


def configure(path, model=None):
    saved = dotenv_values(path) if path.exists() else {}
    key = getpass.getpass(
        "Paste Gemini API key (hidden; Enter keeps saved key): "
    ).strip()
    key = key or saved.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("No key supplied; configuration unchanged.")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000))
    try:
        if not model:
            models = sorted(
                {
                    item.name.removeprefix("models/")
                    for item in client.models.list()
                    if item.name and "generateContent" in (item.supported_actions or [])
                }
            )
            if not models:
                raise ValueError("No generation models available for this key.")
            for index, name in enumerate(models, 1):
                print(f"{index}: {name}")
            selection = input(
                "Choose a text model number or paste its model ID: "
            ).strip()
            if selection.isdigit():
                if not 1 <= int(selection) <= len(models):
                    raise ValueError("Invalid model number; configuration unchanged.")
                model = models[int(selection) - 1]
            else:
                model = selection.removeprefix("models/")
            if model not in models:
                raise ValueError("Choose a model listed for this key.")
        print("Testing a small structured JSON request...")
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
            raise ValueError("Model failed the structured-output check.")
    finally:
        client.close()
    save_config(path, key, model)
    print(f"Gemini API check passed. Saved private configuration to {path}.")
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
        # Provider exceptions can include request details; never print them or the key.
        code = getattr(error, "code", None)
        print(f"Setup failed ({type(error).__name__}, status {code or 'unavailable'}).")
        print("Check the key, selected model and project quota in Google AI Studio.")
        print("Configuration unchanged.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
