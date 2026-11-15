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
    elif provider == "local":
        from imperial_thermo_ai.parser import DEFAULT_MODEL

        generate = local_model(env.get("PSI_PARSER_MODEL") or DEFAULT_MODEL).generate
        planner = LocalPlanner(generate, timed_generate=generate)
    else:
        raise ValueError("THERMO_PLANNER must be local, api or retrieval.")
    return {
        "planner": planner,
        "program_generator": generate,
        "answer_generator": generate
        if env.get("THERMO_COMPOSE", "true") == "true"
        else None,
        "semantic_generator": generate
        if env.get("THERMO_SEMANTIC", "true" if provider == "api" else "false")
        == "true"
        else None,
    }
