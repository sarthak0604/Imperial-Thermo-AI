"""All 20 dashboard prompts exercise the conversational HTTP adapter's backend."""

import pytest

from request_planner.conversation import ask_conversation


PROMPTS = [
    "How hot could a stoichiometric methane flame get in a hypothetical lunar habitat at 70.3 kPa with 30% oxygen and the rest nitrogen? Start the gases at 298 K.",
    "Figure out the Lewis number for a methane flame in a nitrogen diluted ISS environment.",
    "For pure methane burning in air with 23.2% oxygen by mass, what mixture fraction gives the stoichiometric flame?",
    "Use the oxygen-consumption measurements from NIST burner test NGQC_3m_2kgs. How much heat was released between 995 and 1005 seconds, and when did the heat release rate peak?",
    "How does increasing acrylic sheet thickness from 0.2 mm to 0.3 mm affect the flame spread rate against the airflow in microgravity?",
    "Using the Saffire II SIBAL runs, how fast would the flame spread along the fabric with the airflow at 22.5 cm/s?",
    "Using the demo kinetics, estimate the blowoff speed at 18% oxygen and 101.3 kPa. How close is an airflow of 0.42 m/s to that limit?",
    "On the Moon, would buoyancy or 10 cm/s ventilation dominate around a 10 cm flame if the temperature difference is 1,200 K?",
    "Estimate the Spalding B-number and surface mass-loss rate per square metre for PMMA in air with 23.2% oxygen by mass and 15 cm/s airflow.",
    "How much does a burning fuel droplet shrink in 10 seconds in space?",
    "Using NASA FLEX run R377, show when the n-decane droplet’s hot flame goes out and how much longer the cool flame lasts.",
    "For a 50/50 methanol–water droplet by mole at 25 °C and one atmosphere, which component evaporates and which condenses if the surrounding gas contains 2 kPa of water vapour and no methanol?",
    "Using the illustrative PMMA case at 21% oxygen in microgravity, is 1.2 cm/s enough airflow to offset radiative heat loss?",
    "In the demo radiometer run, what fraction of the fire’s heat was radiated? Use the sensor geometry and the total heat release measurements.",
    "Using the demo ethylene flame, would soot start forming at 1,260 K with 0.4 seconds of residence time and a carbon-to-oxygen atomic ratio of 0.6?",
    "If we expose the demo slab to 35 kW/m² for 90 seconds, when does its surface reach the ignition temperature? Show the surface temperature over time.",
    "Using the BASS‑II PMMA rod fit, what is the lowest oxygen concentration that can sustain flame spread with 2 cm/s airflow in the same direction as the flame?",
    "How much heat could 250 grams of water mist absorb if it warms from 20 °C to 100 °C and half of it evaporates?",
    "Using the Saffire-inspired demo fire history, how do temperature and pressure change in a sealed 16.7 m³ cabin?",
    "With the demo smoke properties, how long would smoke take to travel down a 3 m ventilation duct at 7.5 cm/s, and how would particle size and concentration change?",
]


# Check the quantities requested in the demo, not only status or function ID.
EXPECTED_METRICS = {
    1: ("outputs", "adiabatic_flame_temp_k", 2508.77),
    3: ("outputs", "stoichiometric_mixture_fraction_zst", 0.05496),
    4: ("peak_hrr_time_s", 1000.0),
    6: ("spread_rate_mm_s", 2.3625),
    7: ("outputs", "critical_blowoff_velocity_ms", 0.168),
    8: ("outputs", "richardson_number", 21.61907),
    9: ("outputs", "pyrolysis_mass_flux_gm2s", 1.9237),
    11: ("cool_extinction_time_s", 25.5090909),
    14: ("integrated_radiative_fraction", 0.25),
    17: ("limiting_oxygen_pct", 13.49237245),
    18: ("total_water_heat_sink_kJ", 365.865),
    20: ("mean_advective_travel_time_s", 40.0003),
}


@pytest.mark.parametrize("number,prompt", list(enumerate(PROMPTS, 1)), ids=[f"THM-{i:02}" for i in range(1, 21)])
def test_dashboard_prompt(number, prompt, tmp_path, monkeypatch):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("Reviewed standalone examples should execute without provider inference")

    monkeypatch.setattr("request_planner.providers.configure", lambda _: {
        "program_generator": unexpected, "function_generator": unexpected,
        "answer_generator": unexpected,
    })
    reply = ask_conversation(
        prompt, {"THERMO_CONVERSATION_DB": str(tmp_path / "state.sqlite")},
        "dashboard", {"client_request_id": f"model-{number}"},
    )
    assert reply["meta"]["status"] == "completed", (reply["summary"], reply["fulfilment"])
    assert not reply["clarifications"]
    calcs = [b for b in reply["blocks"] if b["type"] == "calculation"]
    charts = [b for b in reply["blocks"] if b["type"] == "chart"]
    assert len(calcs) == (2 if number == 2 else 1)
    assert all(b["model_id"] == f"THM-{number:02}" and b["input_json"] for b in calcs)
    assert len(charts) >= (2 if number in {19, 20} else 1)

    model_result = calcs[0]["data"]
    if number in EXPECTED_METRICS:
        *path, value = EXPECTED_METRICS[number]
        for key in path:
            model_result = model_result[key]
        assert model_result == pytest.approx(value, rel=1e-5)
    elif number == 2:
        base, sensitivity = [b["data"]["dimensionless_numbers"]["lewis_number"] for b in calcs]
        assert base == pytest.approx(0.9497)
        assert sensitivity != base and "dilution" in reply["summary"].lower()
        assert "18% oxygen" in charts[0]["categories"][1]
    elif number == 5:
        assert model_result["rates_mm_s"] == pytest.approx([1.11384, 0.74256], rel=0.002)
        assert "Used bundled BASS-II conditions" in reply["limitations"]
    elif number == 10:
        assert "decrease of 0.546 mm over 10 s" in reply["summary"]
        assert charts[0]["series"][0]["unit"] == "mm"
        assert any("FLEX" in source["note"] for source in reply["evidence"])
    elif number == 12:
        assert [c["transfer_direction"] for c in model_result["components"]] == ["evaporating", "condensing"]
    elif number == 13:
        assert model_result["thermal_budget_w_m2"]["net_margin"] == pytest.approx(482.2745256366)
        assert model_result["critical_speed_m_s"] < 0.012
    elif number == 15:
        assert model_result["inception_screen"] in {"near_threshold", "inception_possible", "below_inception_criteria"}
        assert model_result["temperature_margin_K"] == pytest.approx(1260 - model_result["threshold_temperature_K"])
    elif number == 16:
        assert model_result["criterion_reached"] and 0 < model_result["time_to_ignition_s"] < 90
        assert any("Surface temperature" == series["label"] for series in charts[0]["series"])
    elif number == 19:
        assert model_result["sampled_peak_pressure_change_kPa"] > 0
        assert {"K", "kPa"} == {b["series"][0]["unit"] for b in charts}


def test_mixture_fraction_uses_fuel_and_mass_fraction_from_new_prompts(tmp_path):
    cases = [
        ("Calculate the stoichiometric mixture fraction for pure propane in air with 23.2% oxygen by mass.",
         "C3H8", 0.232),
        ("For pure carbon monoxide with 31% oxygen by mass, what is the stoichiometric mixture fraction?",
         "CO", 0.31),
    ]
    for index, (prompt, fuel, oxygen) in enumerate(cases):
        result = ask_conversation(
            prompt, {"THERMO_CONVERSATION_DB": str(tmp_path / "novel.sqlite"), "THERMO_PLANNER": "retrieval"},
            "dashboard", {"client_request_id": f"novel-{index}"},
        )
        assert result["meta"]["status"] == "completed"
        calculation = next(b for b in result["blocks"] if b["type"] == "calculation")
        assert calculation["model_id"] == "THM-03"
        assert calculation["data"]["inputs"]["fuel_formula"] == fuel
        assert calculation["data"]["inputs"]["y_ox_stream"] == pytest.approx(oxygen)
        assert all(origin["kind"] == "user" for origin in calculation["input_provenance"])
        assert result["blocks"][1]["type"] == "chart"
