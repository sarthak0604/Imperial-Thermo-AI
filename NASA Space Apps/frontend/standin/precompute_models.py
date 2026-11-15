#!/usr/bin/env python3
"""Runs the thermo team's models and saves their outputs for the website (data/model_outputs.js).

Usage (from the frontend folder):
    uv run python "NASA Space Apps/frontend/standin/precompute_models.py" --thermo src/Functions --out "NASA Space Apps/frontend/data/model_outputs.js"
    # if THM-04/05/06/15/17-20 are in a different checkout (e.g. the haykm branch): add  --models "<that folder>"

    # THM-01/03/07/08/09 (Liem's branch) sit as loose files in that checkout: add  --liem "<that folder>"  if it differs from --thermo

Models used: THM-01/02/03/07/08/09 (stdlib), THM-04/05/06/11/15/17/18/19/20 (stdlib), THM-16 (needs numpy + scipy).
Inputs are chosen scenarios; THM-16's material is the thermo team's SYNTHETIC demo slab.
Script written with SI assistance (Claude, Anthropic).
"""
import argparse, copy, datetime, importlib.util, json
from pathlib import Path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def r(x, n=6):
    return float(f"{x:.{n}g}") if isinstance(x, (int, float)) and x is not None else x


def thm02(thermo):
    m = load(thermo / "THM-02.py", "thm02")
    run = lambda mix, T, P, target: m.compute_mixture_transport_and_lewis_number(mole_fracs=mix, temp_k=T, pressure_kpa=P, target_species=target)
    pick = lambda res: {"rho": r(res["transport_properties"]["density_kg_m3"]), "k": r(res["transport_properties"]["thermal_conductivity_w_mk"]),
                        "alpha": r(res["transport_properties"]["thermal_diffusivity_m2_s"]), "D": r(res["transport_properties"]["mass_diffusivity_m2_s"]),
                        "mu": r(res["transport_properties"]["dynamic_viscosity_pa_s"]), "Pr": r(res["dimensionless_numbers"]["prandtl_number"], 4),
                        "Sc": r(res["dimensionless_numbers"]["schmidt_number"], 4), "Le": r(res["dimensionless_numbers"]["lewis_number"], 4),
                        "regime": res["thermo_diffusive_stability"]["regime"]}
    T = 300.0
    fuels = {"H2": "Hydrogen", "CH4": "Methane", "C7H16": "n-Heptane"}
    diluents = {"N2": "Nitrogen", "CO2": "Carbon dioxide", "HE": "Helium"}
    pressures = {"29.6": "Spacesuit 4.3 psi", "70.3": "Lunar habitat 10.2 psi", "101.3": "ISS / Earth 14.7 psi"}
    o2s = list(range(15, 101, 5))
    fuel_x = 0.02
    grid = {}
    for f in fuels:
        for d in diluents:
            for p in pressures:
                for o in o2s:
                    o2 = o / 100.0
                    if o2 + fuel_x > 1.0:
                        continue
                    mix = {f: fuel_x, "O2": o2}
                    rest = 1.0 - fuel_x - o2
                    if rest > 1e-9:
                        mix[d] = rest
                    grid[f"{f}|{d}|{p}|{o}"] = pick(run(mix, T, float(p), f))
    # atmospheres (air-like, target O2 — how oxygen itself moves) for the comparison chart
    atmos = {"iss": ({"O2": 0.21, "N2": 0.79}, 101.3, "ISS"), "lunar_habitat": ({"O2": 0.30, "N2": 0.70}, 70.3, "Lunar habitat"),
             "spacesuit": ({"O2": 1.0}, 29.6, "Spacesuit")}
    atm = {k: {"label": lab, "pressure_kPa": P, "o2_pct": round(mix["O2"] * 100), **pick(run(mix, T, P, "O2"))} for k, (mix, P, lab) in atmos.items()}
    gauge = {f: pick(run({f: fuel_x, "O2": 0.21, "N2": 1 - fuel_x - 0.21}, T, 101.3, f)) for f in fuels}
    dil = {d: pick(run({"C7H16": fuel_x, "O2": 0.21, d: 1 - fuel_x - 0.21}, T, 101.3, "C7H16")) for d in diluents}
    return {"model_id": "THM-02", "status": "physics_calculation", "evidence_boundary": "Theoretical / Semi-Empirical Transport",
            "illustrative": False, "temperature_K": T, "fuel_mole_fraction": fuel_x,
            "fuels": fuels, "diluents": diluents, "pressures": pressures, "o2_values": o2s,
            "grid": grid, "atmospheres": atm, "gauge_in_air": gauge, "diluents_for_heptane": dil,
            "note": "Mixture-averaged transport at 300 K from kinetic theory (Python fallback, no Cantera). Lewis number of the fuel."}


def req_ev(folder, n):
    """Request + evidence for a model: the single THM-nn_input.json (new layout) or the older _request/_evidence pair."""
    one = folder / f"THM-{n}_input.json"
    if one.exists():
        data = json.loads(one.read_text(encoding="utf-8-sig"))
        return data["request"], data["evidence"]
    request = json.loads((folder / f"THM-{n}_request.json").read_text(encoding="utf-8-sig"))
    evidence = json.loads((folder / f"THM-{n}_evidence.json").read_text(encoding="utf-8-sig"))
    return request, evidence


def thm11(thermo):
    m = load(thermo / "THM-11" / "thm_11.py", "thm11")
    req, ev = req_ev(thermo / "THM-11", "11")
    runs = {}
    for rid, o2, d0 in (("R377", 21, 4.03), ("R379", 17, 3.86)):
        q = copy.deepcopy(req); q["scenario"]["ambient"]["oxygen"]["value"] = o2; q["scenario"]["initial_diameter"]["value"] = d0
        res = m.run_request(q, ev)
        keep = {k: res[k] for k in ("hot_extinction_time_s", "hot_extinction_diameter_mm", "cool_stage_duration_s", "cool_extinction_time_s",
                                    "cool_extinction_diameter_mm", "hot_burning_rate_mm2_s", "cool_burning_rate_mm2_s", "status", "evidence_boundary",
                                    "illustrative", "sources", "limitations")}
        keep = {k: (r(v) if isinstance(v, float) else v) for k, v in keep.items()}
        keep.update(o2_pct=o2, d0_mm=d0, pressure_kPa=50.6625, fuel="n-decane",
                    time_s=[r(x, 5) for x in res["time_s"]], d2_mm2=[r(x, 5) for x in res["diameter_squared_mm2"]], phase=res["phase"])
        if "held_out_check" in res:
            keep["held_out_check"] = {k: (r(v) if isinstance(v, float) else v) for k, v in res["held_out_check"].items()}
        runs[rid] = keep
    return {"model_id": "THM-11", "runs": runs}


def thm16(thermo):
    m = load(thermo / "THM-16" / "thm_16.py", "thm16")
    req, ev = req_ev(thermo / "THM-16", "16")
    by_flux = {}
    for flux in (10, 15, 20, 25, 30, 35, 40):
        q = copy.deepcopy(req); q["scenario"]["exposure"]["heat_flux"]["value"] = flux; q["scenario"]["exposure"]["heating_time"]["value"] = 90
        res = m.run_request(q, ev)
        step = 2   # thin the arrays for the web
        by_flux[str(flux)] = {"time_to_ignition_s": r(res["time_to_ignition_s"]) if res["time_to_ignition_s"] else None,
                              "time_s": [r(x, 4) for x in res["time_s"]], "surface_K": [r(x, 5) for x in res["surface_temperature_K"]],
                              "back_K": [r(x, 5) for x in res["back_temperature_K"]],
                              "penetration_mm": [r(x * 1000, 4) for x in res["thermal_penetration_depth_m"]]}
        if flux == 35:
            heat = {"time_s": [r(x, 4) for x in res["time_s"]][::step], "depth_mm": [r(x * 1000, 4) for x in res["depth_m"]][::2],
                    "T_K": [[r(v, 4) for v in row[::step]] for row in res["temperature_by_depth_K"][::2]]}
    mat = ev["materials"][0]
    return {"model_id": "THM-16", "status": "synthetic_demo", "evidence_boundary": "Theoretical / Partial-g Bound", "illustrative": True,
            "material": mat["name"], "ignition_criterion_K": mat["calibrations"][0]["t_ign_k"], "heating_time_s": 90,
            "conditions": "101.3 kPa, 21% O2, 295 K, 20 cm/s airflow (only calibrated case)", "by_flux": by_flux, "heatmap_35kW": heat,
            "note": "Material properties and calibration are SYNTHETIC demo values from the thermo team (illustrative: true)."}


# ---------- the models added from the haykm branch (all take one {request, evidence} payload) ----------
def run_new(models, n, mutate=None):
    m = load(models / f"THM-{n}" / f"thm_{n}.py", f"thm{n}")
    req, ev = req_ev(models / f"THM-{n}", n)
    payload = {"request": copy.deepcopy(req), "evidence": copy.deepcopy(ev)}
    if mutate: mutate(payload)
    return m.run_request(payload), payload


def rl(xs, n=5, step=1):
    return [r(x, n) for x in xs][::step]


def src_keep(res):
    return {"status": res.get("status"), "evidence_boundary": res.get("evidence_boundary"), "illustrative": (res.get("provenance") or {}).get("illustrative", True),
            "sources": [{"url": s_.get("url"), "locator": s_.get("locator")} for s_ in res.get("sources", [])], "limitations": res.get("limitations", [])}


def thm04(models):
    res, _ = run_new(models, "04")
    b = res.get("benchmark_check") or {}
    return {"model_id": "THM-04", **src_keep(res), "run_id": res["run_id"], "method": res["measurement_method"],
            "time_s": rl(res["time_s"]), "hrr_kW": rl(res["hrr_kW"]), "cumulative_kJ": rl(res["cumulative_heat_kJ"]),
            "total_kJ": r(res["total_heat_release_kJ"]), "peak_kW": r(res["peak_hrr_W"] / 1000), "peak_time_s": res["peak_hrr_time_s"],
            "reference_kW": rl([v / 1000 for v in b.get("reference_hrr_W", [])]), "reference_total_kJ": r(b.get("reference_total_heat_kJ")),
            "reference_peak_kW": r(b.get("reference_peak_hrr_W", 0) / 1000), "model_minus_reference_kJ": r(b.get("model_minus_reference_kJ")),
            "heat_per_kg_o2_MJ": r(res["heat_per_kg_o2_J"] / 1e6), "oxygen_kg_s": rl(res["oxygen_consumption_kg_s"], 4),
            "note": "10 s excerpt of a NIST ground-based natural-gas burner test (not microgravity)."}


def thm05(models):
    res, _ = run_new(models, "05")
    sweep = []
    for mm in (0.1, 0.15, 0.2, 0.3, 0.4):
        def mut(p, mm=mm): p["request"]["scenario"]["specimen_thickness"]["value"] = mm / 1000
        try:
            q, _ = run_new(models, "05", mut)
            sweep.append({"thickness_mm": mm, "rate_mm_s": r(q["spread_rate_mm_s"]), "thin_mm_s": r(q["thin_limit_mm_s"]), "thick_mm_s": r(q["thick_limit_mm_s"]), "regime": q["thermal_regime"]})
        except Exception as e:   # outside the calibrated range: skip that thickness
            print("  THM-05 thickness", mm, "skipped:", str(e)[:80])
    return {"model_id": "THM-05", **src_keep(res), "spread_rate_mm_s": r(res["spread_rate_mm_s"]), "thin_mm_s": r(res["thin_limit_mm_s"]), "thick_mm_s": r(res["thick_limit_mm_s"]),
            "transition_mm": r(res["transition_thickness_m"] * 1000), "regime": res["thermal_regime"], "thickness_mm": r(res["sample_thickness_m"] * 1000),
            "air_speed_cm_s": r(res["opposed_gas_speed_m_s"] * 100), "oxygen_pct": res["ambient"]["oxygen_pct"], "flame_coefficient": res["flame_coefficient"],
            "sweep": sweep, "checks": [{"run": c["run_id"], "thickness_mm": r(c["thickness_m"] * 1000), "observed_mm_s": c["spread_rate_mm_s"], "model_mm_s": r(c["model_spread_rate_mm_s"])}
                                        for c in res.get("spread_rate_checks", [])],
            "note": "PMMA sheet, opposed airflow of 3 cm/s, BASS-II conditions (21% O2, 1 atm)."}


def thm06(models):
    res, _ = run_new(models, "06")
    k = 2
    chk = (res.get("spread_rate_checks") or [{}])[0]
    return {"model_id": "THM-06", **src_keep(res), "limiting_mm_s": r(res["spread_rate_mm_s"]), "initial_mm_s": r(res["initial_spread_rate_mm_s"]),
            "sample_length_m": res["sample_length_m"], "edge_time_s": r(res["edge_influence_time_s"]), "end_reason": res["end_reason"],
            "time_s": rl(res["time_s"], 4, k), "rate_mm_s": rl(res["spread_rate_series_mm_s"], 4, k), "front_m": rl(res["pyrolysis_front_position_m"], 4, k),
            "base_m": rl(res["pyrolysis_base_position_m"], 4, k), "tip_m": rl(res["effective_flame_tip_position_m"], 4, k),
            "conditions": {"air_speed_cm_s": r(res["conditions"]["air_speed_m_s"] * 100), "oxygen_pct": res["conditions"]["oxygen_pct"], "length_cm": r(res["conditions"]["sample_length_m"] * 100)},
            "check": {"run": chk.get("run_id"), "air_speed_cm_s": r((chk.get("air_speed_m_s") or 0) * 100), "observed_mm_s": chk.get("spread_rate_mm_s"), "model_mm_s": r(chk.get("model_spread_rate_mm_s"))},
            "note": "Thin SIBAL fabric card, concurrent flow of 22.5 cm/s (Saffire II). The growth curve starts from illustrative values."}


def thm15(models):
    res, payload = run_new(models, "15")
    sc = payload["request"]["scenario"]
    sweep = []
    for T in range(1050, 1351, 10):
        def mut(p, T=T): p["request"]["scenario"]["flame_temperature_K"] = T
        q, _ = run_new(models, "15", mut); sweep.append([T, q["inception_screen"]])
    return {"model_id": "THM-15", **src_keep(res), "screen": res["inception_screen"], "threshold_K": res["threshold_temperature_K"], "margin_K": res["temperature_margin_K"],
            "local_K": sc["flame_temperature_K"], "co_ratio": sc["carbon_to_oxygen_atomic_ratio"], "residence_s": sc["residence_time_s"], "fuel": sc["fuel_id"],
            "thermophoretic_mm_s": r(res["thermophoretic_velocity_m_s"] * 1000), "net_radial_mm_s": r(res["net_radial_particle_velocity_m_s"] * 1000),
            "sweep": sweep, "note": "Ethylene diffusion flame, drop-tower microgravity. The 1190 K threshold is published; the screening band and flow values are illustrative."}


def thm17(models):
    res, payload = run_new(models, "17")
    sw = res["sweep"]; k = 2
    return {"model_id": "THM-17", **src_keep(res), "limit_pct": r(res["limiting_oxygen_pct"]), "speed_cm_s": r(res["air_speed_m_s"] * 100), "larger_branch": res["larger_branch"],
            "ambient_pct": payload["request"]["scenario"].get("ambient_oxygen_pct"), "margin_pts": r(res.get("ambient_minus_limit_percentage_points")),
            "speed_cm_s_sweep": [r(v * 100, 4) for v in sw["air_speed_m_s"]][::k], "quench_pct": rl(sw["quench_oxygen_pct"], 4, k), "blowoff_pct": rl(sw["blowoff_oxygen_pct"], 4, k),
            "limit_curve_pct": rl(sw["limiting_oxygen_pct"], 4, k), "reference_1g_pct": (res.get("reference_1g") or {}).get("oxygen_pct"),
            "note": "PMMA rod, 3.18 mm radius, concurrent flow, BASS-II pooled fit."}


def thm18(models):
    res, _ = run_new(models, "18")
    sw = res["sweep"]
    def mist(p):
        p["request"]["scenario"] = {"profile_id": "water_at_373_15K", "mode": "water_mist", "pressure_kPa": 101.325, "water_mass_kg": 0.2,
                                    "inlet_water_temperature_K": 293.15, "liquid_endpoint_temperature_K": 373.15, "evaporated_fraction": 0.5}
    wm, _ = run_new(models, "18", mist)
    return {"model_id": "THM-18", **src_keep(res), "agent": "CO₂", "added_pct": [r(v * 100, 4) for v in sw["agent_mole_fraction"]],
            "o2_pct": [r(v * 100, 4) for v in sw["oxygen_mole_fraction"]], "heat_kJ_m3": rl(sw["mixture_sensible_heat_kJ_per_initial_m3"], 5),
            "at_30": {"added_pct": r(res["final_agent_mole_fraction"] * 100), "o2_pct": r(res["oxygen_mole_fraction"] * 100), "o2_kPa": r(res["oxygen_partial_pressure_kPa"]),
                      "extra_heat_kJ_m3": r(res["change_from_base_kJ_per_initial_m3"])},
            "mist": {k_: wm[k_] for k_ in wm if isinstance(wm[k_], (int, float)) and not isinstance(wm[k_], bool)} | {"sweep": wm.get("sweep")},
            "note": "Dilution of air by CO₂, heated from 300 K to 400 K, 1 atm. Water mist: 0.2 kg from 20 °C, half evaporated."}


def thm19(models):
    def dense(p):   # same fire history, linearly interpolated every 5 s so the curves are smooth (the model integrates it exactly)
        f = p["evidence"]["fires"][0]; ts = f["time_s"]; new_t = list(range(0, int(ts[-1]) + 1, 5))
        def interp(arr):
            out = []
            for t in new_t:
                for i in range(len(ts) - 1):
                    if ts[i] <= t <= ts[i + 1]:
                        out.append(arr[i] + (arr[i + 1] - arr[i]) * (t - ts[i]) / (ts[i + 1] - ts[i])); break
            return out
        f["hrr_W"] = interp(f["hrr_W"]); f["species"] = {k_: interp(v) for k_, v in f["species"].items()}; f["time_s"] = new_t
    res, _ = run_new(models, "19", dense)
    return {"model_id": "THM-19", **src_keep(res), "time_s": res["time_s"], "hrr_kW": rl([v / 1000 for v in res["hrr_W"]], 4), "pressure_kPa": rl(res["pressure_kPa"], 6),
            "temperature_K": rl(res["temperature_K"], 5), "pressure_change_kPa": rl(res["pressure_change_kPa"], 4),
            "o2_pct": rl([v * 100 for v in res["oxygen_mole_fraction"]], 4), "co2_pct": rl([v * 100 for v in res["carbon_dioxide_mole_fraction"]], 4),
            "co_ppm": rl([v * 1e6 for v in res["carbon_monoxide_mole_fraction"]], 4),
            "peak_dp_kPa": r(res["sampled_peak_pressure_change_kPa"]), "peak_T_K": r(res["sampled_peak_temperature_K"]), "p0_kPa": res["pressure_kPa"][0], "T0_K": res["temperature_K"][0],
            "peak_hrr_kW": r(max(res["hrr_W"]) / 1000), "volume_m3": 16.7,
            "note": "Sealed 16.7 m³ cabin at 54.6 kPa and 30% O₂ with an illustrative 2.4 kW fire (Saffire VI-inspired)."}


def thm20(models):
    res, _ = run_new(models, "20"); k = 3
    return {"model_id": "THM-20", **src_keep(res), "time_s": rl(res["time_s"], 4, k), "number_1e11_m3": [r(v / 1e11, 5) for v in res["parcel_number_concentration_m3"]][::k],
            "diameter_um": [r(v * 1e6, 5) for v in res["parcel_equivalent_diameter_m"]][::k], "arrival_fraction": rl(res["packet_transport_arrival_fraction"], 4, k),
            "travel_s": r(res["mean_advective_travel_time_s"]), "d_arrival_um": r(res["equivalent_diameter_at_mean_arrival_m"] * 1e6, 5),
            "n_arrival_1e11_m3": r(res["number_concentration_at_mean_arrival_m3"] / 1e11), "d0_um": r(res["parcel_equivalent_diameter_m"][0] * 1e6, 4),
            "n0_1e11_m3": r(res["parcel_number_concentration_m3"][0] / 1e11), "duct": {"length_m": 3, "speed_cm_s": 7.5},
            "note": "Illustrative straight vent duct (3 m, 7.5 cm/s); SAME/SAME-R-inspired."}


# ---------- Liem's models: THM-01, 03, 07, 08, 09 (loose files) ----------
def thm01(liem):
    path = liem / "THM-01.py"
    if not path.is_file():
        path = liem / "calc_adiabatic_flame_temp_equilibrium.py"
    m = load(path, "thm01")
    atm = [("ISS cabin air", 0.21, 101.325), ("Lunar habitat", 0.30, 70.3), ("Spacesuit", 1.0, 29.6)]
    fuels = [("methane", "Methane"), ("hydrogen", "Hydrogen"), ("propane", "Propane")]
    out = {"atmospheres": [{"name": n, "o2_pct": r(x * 100, 4), "kpa": p} for n, x, p in atm], "fuels": {}}
    for key, label in fuels:
        rows = [m.calc_adiabatic_flame_temp_equilibrium(key, x, p, "N2")["outputs"] for _, x, p in atm]
        out["fuels"][key] = {"label": label, "T_ad_K": [r(o["adiabatic_flame_temp_k"], 5) for o in rows], "drop_K": [r(o["estimated_dissociation_drop_k"], 4) for o in rows]}
    res = m.calc_adiabatic_flame_temp_equilibrium("methane", 0.21, 101.325, "N2")
    return {"model_id": "THM-01", "status": "physics_calculation", "evidence_boundary": res["metadata"]["evidence_boundary"], "solver": res["metadata"]["solver_backend"],
            "equal_stoichiometric": True, "diluent": "N2", **out}


def thm03(liem):
    m = load(liem / "THM-03.py", "thm03")
    ys = [0.15, 0.21, 0.232, 0.3, 0.4, 0.5, 0.65, 0.85, 1.0]
    rows = [m.calc_stoichiometric_mixture_fraction_zst("CH4", y_ox_stream=y, flame_configuration="normal")["outputs"] for y in ys]
    air = m.calc_stoichiometric_mixture_fraction_zst("CH4", y_ox_stream=0.232, flame_configuration="normal")
    inv = m.calc_stoichiometric_mixture_fraction_zst("CH4", y_ox_stream=0.232, flame_configuration="inverse")["outputs"]
    return {"model_id": "THM-03", "status": "physics_calculation", "fuel": "CH4", "burner_radius_mm": 3.2, "flow_sccm": 250,
            "y_ox_pct": [r(y * 100, 4) for y in ys], "zst": [r(o["stoichiometric_mixture_fraction_zst"], 5) for o in rows],
            "radius_ratio": [r(o["flame_to_burner_radius_ratio"], 5) for o in rows], "air_zst": r(air["outputs"]["stoichiometric_mixture_fraction_zst"], 5),
            "air_radius_ratio": r(air["outputs"]["flame_to_burner_radius_ratio"], 5), "inverse_radius_ratio": r(inv["flame_to_burner_radius_ratio"], 4),
            "regime": air["frontend_summary"]["status_badge"], "evidence_boundary": "Theoretical / Partial-g Bound"}


def thm07(liem):
    m = load(liem / "THM-07.py", "thm07")
    import math
    speeds = [round(10 ** (math.log10(4) + i * (math.log10(150) - math.log10(4)) / 39), 3) for i in range(40)]
    cases = {"iss": (0.21, 101.325), "lunar": (0.30, 70.3)}
    out = {"model_id": "THM-07", "status": "physics_calculation", "speed_cm_s": speeds, "cases": {}, "evidence_boundary": "Theoretical / Partial-g Bound"}
    for k, (xo, p) in cases.items():
        das = [m.evaluate_damkohler_blowoff_extinction(u / 100, xo, p)["outputs"]["damkohler_number"] for u in speeds]
        o = m.evaluate_damkohler_blowoff_extinction(0.2, xo, p)
        out["cases"][k] = {"o2_pct": r(xo * 100, 4), "kpa": p, "da": [r(d, 5) for d in das], "blowoff_cm_s": r(o["outputs"]["critical_blowoff_velocity_cms"], 4),
                           "flame_temp_K": r(o["inputs"]["flame_temp_k"], 5)}
    return out


def thm08(liem):
    m = load(liem / "THM-08.py", "thm08")
    envs = [("ISS (≈0 g)", 1e-6), ("Moon (0.165 g)", 0.165), ("Mars (0.378 g)", 0.378), ("Earth (1 g)", 1.0)]
    rows = []
    for name, g in envs:
        o = m.calc_mixed_convection_richardson_scaling(g, 0.1)["outputs"]
        rows.append({"name": name, "g": g, "Ri": r(o["richardson_number"], 5), "regime": o["convection_regime"]})
    return {"model_id": "THM-08", "status": "theoretical_bound", "forced_cm_s": 10, "length_m": 0.05, "delta_T_K": 1400, "envs": rows,
            "evidence_boundary": "Theoretical scaling bound; PSI has no partial-gravity combustion data"}


def thm09(liem):
    m = load(liem / "THM-09.py", "thm09")
    ys = [0.18, 0.21, 0.25, 0.30, 0.35, 0.42, 0.50]
    rows = [m.calc_spalding_mass_transfer_b_number(y, material_name="PMMA", u_flow_ms=0.15)["outputs"] for y in ys]
    air = rows[1]
    return {"model_id": "THM-09", "status": "physics_calculation", "material": "PMMA", "flow_cm_s": 15, "o2_pct": [r(y * 100, 4) for y in ys],
            "b_ideal": [r(o["spalding_b_ideal"], 5) for o in rows], "b_eff": [r(o["spalding_b_effective"], 5) for o in rows],
            "flux_g_m2_s": [r(o["pyrolysis_mass_flux_gm2s"], 5) for o in rows], "air": {"b_eff": r(air["spalding_b_effective"], 4), "b_ideal": r(air["spalding_b_ideal"], 4),
            "flux": r(air["pyrolysis_mass_flux_gm2s"], 4), "heat_release_kW_m2": r(air["local_heat_release_flux_kwm2"], 4)},
            "evidence_boundary": "Theoretical / Partial-g Bound"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--thermo", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--models", help="folder holding THM-04/05/06/15/17-20 if it differs from --thermo")
    ap.add_argument("--liem", help="folder holding THM-01/03/07/08/09 (loose .py files) if it differs from --thermo"); a = ap.parse_args()
    thermo = Path(a.thermo); models = Path(a.models) if a.models else thermo; liem = Path(a.liem) if a.liem else thermo
    out = {"generated": datetime.datetime.now().isoformat(timespec="minutes"), "generator": "standin/precompute_models.py",
           "THM02": thm02(thermo), "THM11": thm11(thermo), "THM16": thm16(thermo),
           "THM04": thm04(models), "THM05": thm05(models), "THM06": thm06(models), "THM15": thm15(models), "THM17": thm17(models),
           "THM18": thm18(models), "THM19": thm19(models), "THM20": thm20(models),
           "THM01": thm01(liem), "THM03": thm03(liem), "THM07": thm07(liem), "THM08": thm08(liem), "THM09": thm09(liem)}
    Path(a.out).write_text("// GENERATED by standin/precompute_models.py from the thermo team's models. Do not hand-edit.\n"
                           "window.DATA = window.DATA || {};\nwindow.DATA.modelOutputs = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print("wrote", a.out, round(Path(a.out).stat().st_size / 1024), "KB")
