"""One model interpretation preserves task outputs and validated semantic conditions."""

import json

from imperial_thermo_ai.parser import _json_object, graph_catalogue, parse_question

from .backend_models import Requirement


def enrich(spec, generate, graph):
    """Augment deterministic requirements; never erase an explicit required output."""
    from imperial_thermo_ai.parser import SYSTEM_PROMPT

    raw = generate(
        [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
                + "\nReturn an object with two keys: search and tasks. "
                "search is the complete search JSON described above. tasks is a list of {kind, source_text, model_id}. "
                "kind is calculation/chart/inspection/document/video/image/explanation/discovery. List every requested output. "
                "source_text must quote the original question. model_id is an explicit THM ID or null. "
                "Distinguish showing a document from explaining its contents, and calculations from their input sources. "
                "THM-01 through THM-20 are implemented calculation models, not graph concepts or variables. "
                "Ask clarifications only for contradictions or essential missing scientific inputs, never optional scope preferences. "
                "Never ask what a THM ID means. Pure scenario inputs are inputs to calculation, not required NASA measurements. "
                "For descriptive document titles prefer title contains with meaningful title words, not an invented exact title.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": spec.original_prompt,
                        "context": spec.context,
                        "graph_catalogue": graph_catalogue(graph),
                    }
                ),
            },
        ]
    )
    result = _json_object(raw)
    original = spec.original_prompt.casefold()
    for task in result.get("tasks", []):
        req = Requirement(id="task-" + str(len(spec.requirements) + 1), **task)
        if req.source_text.casefold() not in original:
            raise ValueError("A task must quote the original prompt.")
        if req.model_id and req.model_id.casefold() not in original:
            raise ValueError(
                "A model-specific requirement must be explicitly requested."
            )
        if not any(
            r.kind == req.kind and r.model_id == req.model_id for r in spec.requirements
        ):
            spec.requirements.append(req)
    spec.semantic_plan = parse_question(
        spec.original_prompt, lambda _: json.dumps(result["search"]), graph=graph
    )
    spec.clarifications.extend(
        c["question"] for c in spec.semantic_plan["clarifications"]
    )
    return spec
