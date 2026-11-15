from unittest.mock import patch

from request_planner.conversation import ask_conversation


PROMPT = (
    "Figure out the Lewis number for a methane flame in a nitrogen diluted ISS environment."
    "\tMethane Lewis number of 0.9497 for the nominal ISS case, plus the nitrogen-dilution comparison."
)


def test_browser_chat_fills_the_nominal_iss_state_and_discloses_assumptions(tmp_path):
    def unexpected(*_):
        raise AssertionError("Known quantity and absent mixture should not need inference")

    with patch("request_planner.providers.configure",
               return_value={"program_generator": unexpected, "function_generator": unexpected}):
        reply = ask_conversation(
            PROMPT, {"THERMO_CONVERSATION_DB": str(tmp_path / "state.sqlite")},
            "browser", {"client_request_id": "lewis"},
        )
    assert reply["meta"]["conversation_state"] == "completed"
    assert reply["model_decisions"][0]["model_ids"] == ["THM-02"]
    assert not reply["clarifications"]
    result = next(block for block in reply["blocks"] if block["type"] == "calculation")
    assert result["data"]["dimensionless_numbers"]["lewis_number"] == 0.9497
    assert {"iss_cabin_pressure_nominal", "iss_oxidizer_o2_nominal"} <= {
        entry.get("record_id") for entry in result["input_provenance"]
    }
    assert "Assumed 295 K" in reply["limitations"]
    assert result["illustrative"]
    assert any(source.get("review_status") == "Reference property" for source in reply["evidence"])


def test_malformed_router_output_still_returns_browser_response(tmp_path):
    with patch("request_planner.providers.configure", return_value={
        "program_generator": lambda _: '{"intent":"invalid"}',
    }):
        reply = ask_conversation(
            "Find NASA experiments on combustion",
            {"THERMO_CONVERSATION_DB": str(tmp_path / "state.sqlite")},
            "browser", {"client_request_id": "general"},
        )
    assert reply["meta"]["status"] != "error"
    assert reply["meta"]["graph_id"] != "unavailable"


def test_browser_chat_estimates_blowoff_for_different_prompt_wordings(tmp_path):
    def unexpected(*_):
        raise AssertionError("A standalone blowoff scenario should run without inference")

    prompts = [
        ("Using the demo kinetics, estimate the blowoff speed at 18% oxygen and 101.3 kPa. "
         "How close is an airflow of 0.42 m/s to that limit?", 0.18, 101.3, 0.42, 135000),
        ("At what speed does the flame go out with demo parameters? "
         "O2 is 20 percent, pressure is 95000 Pa, and compare 12 cm/s.", 0.20, 95, 0.12, 135000),
        ("Will 10 cm/s cause flame blow-off at 18% O2 and 1 atm?", 0.18, 101.325, 0.10, 125600),
    ]
    env = {"THERMO_CONVERSATION_DB": str(tmp_path / "state.sqlite")}
    request = {}
    with patch("request_planner.providers.configure", return_value={
        "program_generator": unexpected, "function_generator": unexpected,
    }):
        for index, (prompt, oxygen, pressure, speed, activation) in enumerate(prompts):
            request["client_request_id"] = f"blowoff-{index}"
            reply = ask_conversation(prompt, env, "browser", request)
            assert reply["meta"]["conversation_state"] == "completed", (prompt, reply["summary"], reply["fulfilment"])
            assert reply["model_decisions"][0]["model_ids"] == ["THM-07"]
            assert not reply["clarifications"]
            result = next(b for b in reply["blocks"] if b["type"] == "calculation")
            chart, = [b for b in reply["blocks"] if b["type"] == "chart"]
            inputs = result["data"]["inputs"]
            assert inputs["x_o2"] == oxygen
            assert inputs["pressure_kpa"] == pressure
            assert inputs["u_flow_ms"] == speed
            assert inputs["activation_energy_j"] == activation
            assert len(chart["series"]) == 2 and speed in chart["x"]["values"]
            if index == 0:
                assert result["illustrative"]
                assert result["data"]["outputs"]["critical_blowoff_velocity_ms"] == 0.168
                assert "0.252 m/s above" in reply["summary"]
            request.update(conversation_id=reply["conversation_id"],
                           expected_state_revision=reply["state_revision"])


def test_prior_turn_reference_still_requires_context():
    from request_planner.intent import interpret

    assert interpret("Calculate the blowoff limit for that experiment.").clarifications
    assert not interpret("That airflow of 42 cm/s exceeds the current estimate.").clarifications


def test_droplet_snapshot_uses_stated_composition_and_reference_properties(tmp_path):
    def unexpected(*_):
        raise AssertionError("The reference snapshot has all the necessary inputs")

    cases = [
        ("For a 50/50 methanol–water droplet by mole at 25 °C and one atmosphere, "
         "which component evaporates and which condenses if the surrounding gas contains "
         "2 kPa of water vapour and no methanol?", 0.5, "condensing"),
        ("Which component evaporates from a 60/40 water-methanol droplet by mole at "
         "298.15 K and 1 atm if the ambient gas has no methanol and 1 kPa of water vapour?",
         0.4, "evaporating"),
    ]
    env = {"THERMO_CONVERSATION_DB": str(tmp_path / "state.sqlite")}
    with patch("request_planner.providers.configure", return_value={
        "program_generator": unexpected, "function_generator": unexpected,
    }):
        for index, (prompt, methanol_fraction, water_direction) in enumerate(cases):
            reply = ask_conversation(prompt, env, "browser", {"client_request_id": f"droplet-{index}"})
            assert reply["meta"]["conversation_state"] == "completed"
            assert reply["model_decisions"][0]["model_ids"] == ["THM-12"]
            assert not reply["clarifications"]
            calculation, chart = reply["blocks"]
            inputs = calculation["input_json"]["request"]["scenario"]
            assert inputs["liquid_fractions"]["methanol"] == methanol_fraction
            assert inputs["pressure_kpa"] == 101.325
            parts = {part["id"]: part for part in calculation["data"]["components"]}
            assert parts["methanol"]["transfer_direction"] == "evaporating"
            assert parts["water"]["transfer_direction"] == water_direction
            assert parts["water"]["net_outward_transfer_mol_s"] is None
            assert calculation["illustrative"]
            assert any(origin["kind"] == "reference_property" for origin in calculation["input_provenance"])
            assert chart["series"][0]["unit"] == "kPa"
