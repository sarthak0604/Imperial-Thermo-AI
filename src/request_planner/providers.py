"""Identical provider configuration for CLI and HTTP entry points."""

from functools import lru_cache

from .planner import LocalPlanner, OpenAIPlanner


@lru_cache(maxsize=2)
def local_model(name):
    from .model_worker import ModelWorker

    return ModelWorker(name)


def configure(env):
    provider = env.get("THERMO_PLANNER", "local")
    if provider == "retrieval":
        return {"planner": None}
    if provider == "api":
        from openai import OpenAI

        if not env.get("OPENAI_MODEL"):
            raise ValueError("Set OPENAI_MODEL when THERMO_PLANNER=api.")
        planner = OpenAIPlanner(
            env["OPENAI_MODEL"],
            client=OpenAI(api_key=env.get("OPENAI_API_KEY"), timeout=60, max_retries=1),
        )

        def generate(messages, max_time=60):
            return planner.client.responses.create(
                model=planner.model,
                input=messages,
                max_output_tokens=2400,
                store=False,
                timeout=max_time,
            ).output_text
    elif provider == "open_source":
        from openai import OpenAI

        if not env.get("THERMO_INFERENCE_URL") or not env.get("PSI_PARSER_MODEL"):
            raise ValueError(
                "Set THERMO_INFERENCE_URL and PSI_PARSER_MODEL for open_source inference."
            )
        inference = OpenAI(
            base_url=env["THERMO_INFERENCE_URL"],
            api_key=env.get("THERMO_INFERENCE_KEY", "local"),
            timeout=60,
            max_retries=0,
        )

        def generate(messages, max_time=60):
            response = inference.chat.completions.create(
                model=env["PSI_PARSER_MODEL"],
                messages=messages,
                temperature=0,
                max_tokens=int(env.get("THERMO_MAX_OUTPUT_TOKENS", "2400")),
                response_format={"type": "json_object"},
                timeout=max_time,
            )
            text = response.choices[0].message.content
            if not text:
                raise ValueError("Inference endpoint returned empty content.")
            return text

        planner = LocalPlanner(generate, timed_generate=generate)
    elif provider == "local":
        from imperial_thermo_ai.parser import DEFAULT_MODEL

        generate = local_model(env.get("PSI_PARSER_MODEL") or DEFAULT_MODEL).generate
        planner = LocalPlanner(generate, timed_generate=generate)
    else:
        raise ValueError("THERMO_PLANNER must be local, api, open_source or retrieval.")
    return {
        "planner": planner,
        "routing_generator": generate,
        "program_generator": generate,
        "function_generator": generate if env.get('THERMO_FUNCTION_PIPELINE','true') == 'true' else None,
        "answer_generator": generate
        if env.get("THERMO_COMPOSE", "true") == "true"
        else None,
        "semantic_generator": generate
        if env.get(
            "THERMO_SEMANTIC", "true" if provider in {"api", "open_source"} else "false"
        )
        == "true"
        else None,
    }
