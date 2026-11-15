from unittest.mock import patch

from request_planner.conversation import ask_conversation


PROMPT = (
    "Figure out the Lewis number for a methane flame in a nitrogen diluted ISS environment."
    "\tMethane Lewis number of 0.9497 for the nominal ISS case, plus the nitrogen-dilution comparison."
)


def test_browser_chat_returns_missing_thm_inputs_instead_of_internal_error(tmp_path):
    def unexpected(*_):
        raise AssertionError("Known quantity and absent mixture should not need inference")

    with patch("request_planner.providers.configure",
               return_value={"program_generator": unexpected, "function_generator": unexpected}):
        reply = ask_conversation(
            PROMPT, {"THERMO_CONVERSATION_DB": str(tmp_path / "state.sqlite")},
            "browser", {"client_request_id": "lewis"},
        )
    assert reply["meta"]["conversation_state"] == "awaiting_user"
    assert reply["model_decisions"][0]["model_ids"] == ["THM-02"]
    assert "mole fractions" in reply["clarifications"][0]["question"]
    assert not reply["blocks"]
    assert "0.9497" not in reply["summary"]


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
