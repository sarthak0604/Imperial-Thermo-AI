"""Local Qwen inference, matching origin/test's Transformers model and chat template.

Reference: test@6005a8e0cc116073bcd681d1602b329fc0302a36,
src/imperial_thermo_ai/parser.py. No repository code or remote model code is executed.
"""

import json
import os
from pathlib import Path

from pydantic import ValidationError

DEFAULT_MODEL = "Qwen/Qwen3-4B-Instruct-2507"


class LocalModelError(RuntimeError):
    """Local configuration/capacity failure: stop rather than skip source documents."""


def model_source(model_id):
    """Use the image's pinned default snapshot without writing a runtime cache."""
    if model_id == os.environ.get("LLM_BUNDLED_MODEL_ID"):
        path = Path(os.environ.get("LLM_BUNDLED_MODEL_PATH", "/opt/models/qwen"))
        if not path.is_dir() or not (path / "config.json").is_file():
            raise LocalModelError(
                "Bundled model is missing; rebuild the container image."
            )
        return str(path), True
    return model_id, os.environ.get("LLM_LOCAL_FILES_ONLY", "0") == "1"


def positive_setting(name, default):
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        raise LocalModelError(f"{name} must be a positive integer") from None
    if value <= 0:
        raise LocalModelError(f"{name} must be a positive integer")
    return value


def validate_json(text, schema):
    text = text.strip()
    # Accept only a surrounding code fence; never salvage a partial/truncated object.
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    elif text.startswith("```\n") and text.endswith("```"):
        text = text[4:-3].strip()
    return schema.model_validate_json(text)


class LocalModel:
    def __init__(self, model_id=DEFAULT_MODEL):
        try:
            import accelerate  # noqa: F401
            import torch
            import transformers  # noqa: F401
        except ImportError:
            raise LocalModelError(
                "Install the local model dependencies: uv sync --extra local. "
                "Run with uv run --extra local psi-graph-manage."
            ) from None
        self.torch = torch
        self.model_id = model_id
        self.model = self.tokenizer = None
        self.context_tokens = positive_setting("LLM_CONTEXT_TOKENS", 262144)
        self.input_tokens = positive_setting("LLM_INPUT_TOKENS", 8192)
        self.max_new_tokens = positive_setting("LLM_MAX_NEW_TOKENS", 8192)
        if self.max_new_tokens >= self.context_tokens:
            raise LocalModelError(
                "LLM_MAX_NEW_TOKENS must be less than LLM_CONTEXT_TOKENS"
            )
        self.device = os.environ.get("LLM_DEVICE", "auto")
        if self.device not in ("auto", "cpu", "mps", "cuda"):
            raise LocalModelError("LLM_DEVICE must be auto, cpu, mps or cuda")
        if self.device == "auto":
            self.device = (
                "cuda"
                if torch.cuda.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )

        if self.device == "cuda":
            if not torch.cuda.is_available():
                raise LocalModelError(
                    "CUDA was requested but no usable NVIDIA GPU is available. "
                    "Use a CUDA-enabled PyTorch image and attach an L4 to the cloud job. "
                    "CPU fallback is disabled."
                )
            gpu = torch.cuda.get_device_properties(0)
            print(
                f"CUDA ready: {gpu.name}; {gpu.total_memory / 1024**3:.1f} GiB VRAM; "
                f"PyTorch CUDA {torch.version.cuda}",
                flush=True,
            )

    def load(self):
        if self.model is not None:
            return
        from transformers import AutoModelForCausalLM, AutoTokenizer

        source, local_files_only = model_source(self.model_id)
        print(
            f"Loading {self.model_id} on {self.device} from {source}...",
            flush=True,
        )
        kwargs = dict(
            local_files_only=local_files_only,
            trust_remote_code=False,
        )
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(source, **kwargs)
            # Match the test branch's CPU fp32 path; use fp16 on Apple Silicon.
            dtype = self.torch.float32 if self.device == "cpu" else self.torch.float16
            if self.device == "cuda" and self.torch.cuda.is_bf16_supported():
                dtype = self.torch.bfloat16
            self.model = AutoModelForCausalLM.from_pretrained(
                source, device_map=self.device, dtype=dtype, **kwargs
            ).eval()
        except Exception as error:
            raise LocalModelError(
                f"Cannot load local model ({type(error).__name__}). Check free RAM/disk, "
                "Hugging Face connectivity and LLM_LOCAL_FILES_ONLY. No API fallback was used."
            ) from None
        self.context_tokens = min(
            self.context_tokens,
            getattr(self.model.config, "max_position_embeddings", self.context_tokens),
        )

    def complete(self, messages):
        self.load()
        inputs = self.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
            return_dict=True,
            return_tensors="pt",
        )
        count = inputs["input_ids"].shape[1]
        if count + self.max_new_tokens > self.context_tokens:
            raise LocalModelError(
                f"Local model input has {count} tokens plus {self.max_new_tokens} reserved output "
                f"tokens, exceeding LLM_CONTEXT_TOKENS={self.context_tokens}. "
                "No source text was truncated. Increase the context setting only if memory allows; "
                "parsed sources and completed extractions remain cached."
            )
        # A single JSON repair may include the previous bounded response. Keep
        # that allowance explicit rather than falling back to the native ceiling.
        working_limit = getattr(self, "input_tokens", 8192)
        if len(messages) > 2:
            working_limit += self.max_new_tokens + 1024
        if count > working_limit:
            raise LocalModelError(
                f"Local request has {count} input tokens, exceeding its working "
                f"budget of {working_limit}. No inference or truncation occurred; "
                "reduce source batch size or inspect the JSON repair response."
            )
        inputs = inputs.to(self.model.device)
        try:
            with self.torch.inference_mode():
                tokens = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
        except RuntimeError as error:
            raise LocalModelError(
                f"Local inference failed ({type(error).__name__}); reduce LLM_INPUT_TOKENS "
                "(for example to 4096) to create smaller batches, and check GPU memory. "
                "No API fallback was used."
            ) from None
        generated = tokens[0, count:]
        eos = self.model.generation_config.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        if len(generated) >= self.max_new_tokens and int(generated[-1]) not in eos:
            raise LocalModelError(
                "Local output reached LLM_MAX_NEW_TOKENS; increase the output/context budget. "
                "Truncated output was rejected."
            )
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip(), {
            "input_tokens": count,
            "output_tokens": len(generated),
            "device": self.device,
        }

    @staticmethod
    def messages(system, prompt, schema):
        return [
            {
                "role": "system",
                "content": system
                + "\nReturn ONLY one JSON object matching this schema:\n"
                + json.dumps(schema.model_json_schema()),
            },
            {"role": "user", "content": prompt},
        ]

    def fits(self, system, prompt, schema):
        self.load()
        tokens = self.tokenizer.apply_chat_template(
            self.messages(system, prompt, schema),
            return_dict=False,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        return len(tokens) <= min(
            self.input_tokens, self.context_tokens - self.max_new_tokens
        )

    def generate(self, system, prompt, schema):
        messages = self.messages(system, prompt, schema)
        totals = {"input_tokens": 0, "output_tokens": 0, "device": self.device}
        for attempt in range(2):
            text, usage = self.complete(messages)
            for key in ("input_tokens", "output_tokens"):
                totals[key] += usage[key]
            try:
                return validate_json(text, schema), {
                    **totals,
                    "repair_attempts": attempt,
                }
            except ValidationError as error:
                if attempt:
                    raise LocalModelError(
                        "Local model did not produce valid structured JSON after one repair."
                    ) from None
                issues = error.errors(include_input=False, include_url=False)
                messages += [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": "Correct the JSON structure using only the original source evidence. Return the complete object. Validation errors: "
                        + json.dumps(issues, default=str)[:2500],
                    },
                ]
        raise AssertionError("unreachable")
