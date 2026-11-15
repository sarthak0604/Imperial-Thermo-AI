import json

import pytest

from request_planner.execution import present_result
from request_planner.function_registry import function_root, model_spec, run_model
from request_planner.task_router import CUES, route


@pytest.mark.parametrize("index", range(1, 21))
def test_registered_quantity_routes_and_model_output_has_visual(index):
    model_id = f"THM-{index:02}"
    quantity = CUES[index - 1].split("|")[0]

    def unexpected(_):
        raise AssertionError("A registered quantity should be routed without inference")

    result = route(f"Calculate {quantity} for this setup.", unexpected, function_planner=True)
    assert result.model_ids == [model_id]

    spec = model_spec(model_id)
    template = json.loads(function_root().joinpath(spec["example"]).read_text())
    output = run_model(model_id, template.get("example_request", template))
    blocks = present_result(model_id, output)
    charts = [block for block in blocks if block["type"] == "chart"]
    assert charts
    assert all(len(series["values"]) == len(chart["x"]["values"])
               for chart in charts for series in chart["series"])


def test_unspecific_calculation_uses_shared_planner_for_selection_and_binding():
    def unexpected(_):
        raise AssertionError("The function planner should handle model selection")

    decision = route("Calculate the relevant transport property for this setup.",
                     unexpected, function_planner=True)
    assert decision.intent == "calculation"
    assert decision.model_ids == []
