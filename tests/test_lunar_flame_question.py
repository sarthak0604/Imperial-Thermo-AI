from request_planner.backend import answer
from request_planner.task_router import route


PROMPT = (
    "How hot could a stoichiometric methane flame get in a hypothetical lunar habitat "
    "at 70.3 kPa with 30% oxygen and the rest nitrogen? Start the gases at 298 K."
    "\tAdiabatic flame temperature and equilibrium gas composition"
)


def test_fully_specified_lunar_prompt_runs_python_without_inference():
    def unexpected(_):
        raise AssertionError("The prompt already specifies all THM-01 inputs")

    assert route(PROMPT, unexpected).model_ids == ["THM-01"]
    result = answer(PROMPT, function_generator=unexpected, routing_generator=unexpected)
    assert result.status == "completed"
    calculation, chart = result.result.blocks
    assert calculation["model_id"] == "THM-01"
    assert calculation["data"]["inputs"]["t_init_k"] == 298
    assert calculation["data"]["inputs"]["pressure_kpa"] == 70.3
    assert calculation["data"]["inputs"]["o2_mole_frac"] == 0.3
    assert chart["chart_type"] == "bar"
    assert "CO2" in chart["categories"]


def test_temperature_inputs_accept_reordered_values_and_reject_ambiguous_values():
    from request_planner.flame_temperature import flame_temperature_inputs

    question = (
        "Calculate adiabatic flame temperature for CH4. Start at 298 K with "
        "30 mol% O2 in N2. Pressure is 70.3 kPa, phi = 1."
    )
    assert flame_temperature_inputs(question) == flame_temperature_inputs(PROMPT)
    assert flame_temperature_inputs(question + " Also use 90 kPa.") is None
    assert flame_temperature_inputs(question.replace("298 K", "-298 K")) is None


def test_function_planner_timeout_preserves_graph_sources():
    from request_planner.model_worker import InferenceError

    def timeout(_, max_time):
        assert max_time <= 30
        raise InferenceError("Planner timed out")

    result = answer(
        "Calculate the adiabatic flame temperature with FLEX data",
        function_generator=timeout,
    )
    assert result.retrieval.graph_id != "unavailable"
    assert not result.result.blocks
    assert any(source["investigation_id"] == "PSI-69" for source in result.result.sources)
    assert any("planning did not finish" in warning for warning in result.result.warnings)
