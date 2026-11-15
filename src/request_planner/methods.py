"""Methods from the repository registry, paired with the actual callable contract."""

import ast
from functools import lru_cache

from .function_registry import function_root, input_contract


@lru_cache(maxsize=20)
def method_details(model_id):
    tree = ast.parse(function_root().joinpath("thm_literature_map.py").read_text())
    registry = {}
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "THM_LITERATURE_MAP"
        ):
            registry = ast.literal_eval(node.value)
    method = registry.get(model_id, {})
    return {
        "summary": method.get("scientific_method_summary", ""),
        "equations": method.get("governing_equations", []),
        "references": method.get("literature_sources", []),
        "evidence_boundary": method.get("evidence_boundary", ""),
        "implementation": input_contract(model_id),
        "note": "Method references describe the model; they do not establish that a selected NASA run provides every model input.",
    }


def decorate_result(result):
    """Also enrich pre-existing deterministic and saved-request presentation paths."""
    counts = {}
    for block in result.result.blocks:
        if block["type"] == "calculation":
            mid = block["model_id"]
            counts[mid] = counts.get(mid, 0) + 1
            block.setdefault("task_id", mid + "-" + str(counts[mid]))
            block["method"] = method_details(block["model_id"])
    return result
