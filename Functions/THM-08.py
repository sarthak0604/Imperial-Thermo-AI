"""
THM-08: Mixed-Convection Richardson & Grashof Partial-Gravity Scaling Model
Module: calc_mixed_convection_richardson_scaling.py

Quantifies the competition between buoyancy-driven natural convection and forced
spacecraft cabin ventilation across microgravity (ISS ~ 0g), Lunar gravity (0.165g),
Martian gravity (0.378g), and terrestrial gravity (1.0g) to establish theoretical
partial-gravity flammability and convective transport bounds.

Scientific & Thermodynamic Principles:
1. Dimensionless Buoyancy & Inertia Groups:
   - Grashof Number:   Gr = (g * beta * delta_T * L^3) / nu^2
   - Reynolds Number:  Re = (U_forced * L) / nu
   - Richardson Number: Ri = Gr / Re^2 = (g * beta * delta_T * L) / U_forced^2
2. Induced Buoyant Plume Velocity Scales:
   - Boundary-layer buoyant velocity: U_b,BL = sqrt(g * beta * delta_T * L)
   - Sacksteder thermal-diffusive buoyant scale: U_b,diff = (g * beta * delta_T * alpha_g)^(1/3)
   - Effective mixed-convection velocity: U_eff = (U_forced^3 + U_b,diff^3)^(1/3)
3. Space Apps 2026 Partial-Gravity Evidence Boundary:
   NASA PSI currently contains NO direct partial-gravity combustion data (pending
   future LUCI and FM2 investigations). All lunar (0.165g) and Martian (0.378g)
   outputs are explicitly labeled as theoretical scaling bounds between 0g and 1g.

References:
- Altenkirch, R. A., Eichhorn, R., & Shang, P. C. (1980). Combustion & Flame, 37, 71-83.
- Sacksteder, K. R. (1990). 23rd Symp. (Int.) on Combustion, pp. 1589-1596.
- NASA/TM-2015-218492 (Section 5.1: Partial-Gravity Flammability Bounds).

SI Attribution:
Generated with Super Intelligence (SI) assistance for NASA Space Apps 2026;
verified against classical mixed-convection boundary-layer scaling laws.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

G_EARTH_MS2 = 9.80665
P_REF_KPA = 101.325
NU_AIR_REF = 1.568e-5     # m^2/s at 300 K, 101.325 kPa
ALPHA_AIR_REF = 2.216e-5  # m^2/s at 300 K, 101.325 kPa

GRAVITY_PRESETS: Dict[str, Tuple[float, str]] = {
    "iss": (1.0e-6, "ISS Low-Earth Orbit (~10^-6 g)"),
    "microgravity": (1.0e-6, "Microgravity (~10^-6 g)"),
    "0g": (1.0e-6, "Microgravity (~10^-6 g)"),
    "moon": (0.165, "Lunar Surface (0.165 g)"),
    "lunar": (0.165, "Lunar Surface (0.165 g)"),
    "0.16g": (0.165, "Lunar Surface (0.165 g)"),
    "mars": (0.378, "Martian Surface (0.378 g)"),
    "martian": (0.378, "Martian Surface (0.378 g)"),
    "0.38g": (0.378, "Martian Surface (0.378 g)"),
    "earth": (1.0, "Earth Sea-Level Standard (1.0 g)"),
    "1g": (1.0, "Earth Sea-Level Standard (1.0 g)"),
}


def _resolve_gravity(gravity_g: Union[float, str]) -> Tuple[float, str]:
    if isinstance(gravity_g, str):
        key = gravity_g.strip().lower()
        if key in GRAVITY_PRESETS:
            return GRAVITY_PRESETS[key]
        # Allow strings like "0.16g" or "0.38"
        cleaned = key.rstrip("g").strip()
        val = float(cleaned)
    else:
        val = float(gravity_g)

    if val < 0.0:
        raise ValueError(f"gravity_g must be >= 0.0; got {val}.")

    if val <= 1e-4:
        label = f"Microgravity ({val:.2e} g)"
    elif math.isclose(val, 0.165, abs_tol=0.015):
        label = f"Lunar Gravity Analogue ({val:.3f} g)"
    elif math.isclose(val, 0.378, abs_tol=0.02):
        label = f"Martian Gravity Analogue ({val:.3f} g)"
    elif math.isclose(val, 1.0, abs_tol=0.02):
        label = f"Terrestrial Gravity ({val:.3f} g)"
    else:
        label = f"Custom Partial/Hyper-Gravity ({val:.4f} g)"
    return val, label


# ==============================================================================
# 1. MAIN PUBLIC SOLVER FUNCTION (THM-08)
# ==============================================================================

def calc_mixed_convection_richardson_scaling(
    gravity_g: Union[float, str],
    u_forced_ms: float,
    char_length_m: float = 0.05,
    delta_t_k: float = 1400.0,
    pressure_kpa: float = 101.325,
    t_amb_k: float = 298.15,
    investigation_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes Grashof (Gr), Reynolds (Re), Richardson (Ri = Gr/Re^2), and buoyant
    plume velocity scales across microgravity, partial-gravity, and 1g environments.

    Parameters
    ----------
    gravity_g : float or str
        Gravitational acceleration as a fraction of Earth g (e.g., 0.0, 1e-6, 0.165,
        0.378, 1.0) or preset name ('ISS', 'Moon', 'Mars', 'Earth').
    u_forced_ms : float
        Forced cabin ventilation velocity in m/s (>= 0).
    char_length_m : float, optional
        Characteristic fuel or sample length scale L in meters (> 0), default 0.05 m.
    delta_t_k : float, optional
        Characteristic flame-to-ambient temperature difference (T_f - T_amb) in K (> 0),
        default 1400.0 K.
    pressure_kpa : float, optional
        Cabin ambient pressure in kPa (> 0), default 101.325 kPa.
    t_amb_k : float, optional
        Ambient cabin temperature in K (> 0), default 298.15 K.
    investigation_context : dict, optional
        Optional metadata passed from the AI semantic router.

    Returns
    -------
    dict
        JSON-serializable dictionary with dimensionless groups, buoyant velocities,
        planetary comparison table, and partial-gravity evidence disclosures.
    """
    g_frac, env_label = _resolve_gravity(gravity_g)
    u_forced = float(u_forced_ms)
    length_m = float(char_length_m)
    dt_k = float(delta_t_k)
    p_kpa = float(pressure_kpa)
    t0_k = float(t_amb_k)

    if u_forced < 0.0:
        raise ValueError(f"u_forced_ms must be >= 0; got {u_forced}.")
    if length_m <= 0.0 or dt_k <= 0.0 or p_kpa <= 0.0 or t0_k <= 0.0:
        raise ValueError("char_length_m, delta_t_k, pressure_kpa, and t_amb_k must be > 0.")

    # Film temperature & temperature/pressure-scaled transport properties
    t_film_k = t0_k + 0.5 * dt_k
    beta_k_inv = 1.0 / t_film_k
    nu_m2s = NU_AIR_REF * ((t_film_k / 300.0) ** 1.75) * (P_REF_KPA / p_kpa)
    alpha_m2s = ALPHA_AIR_REF * ((t_film_k / 300.0) ** 1.75) * (P_REF_KPA / p_kpa)
    prandtl = nu_m2s / alpha_m2s

    g_ms2 = g_frac * G_EARTH_MS2

    # Grashof & Rayleigh numbers
    grashof = (g_ms2 * beta_k_inv * dt_k * (length_m ** 3)) / (nu_m2s ** 2)
    rayleigh = grashof * prandtl

    # Induced buoyant velocity scales
    u_buoyant_bl_ms = math.sqrt(max(0.0, g_ms2 * beta_k_inv * dt_k * length_m))
    u_buoyant_sacksteder_ms = (max(0.0, g_ms2 * beta_k_inv * dt_k * alpha_m2s)) ** (1.0 / 3.0)

    # Reynolds & Richardson numbers
    reynolds = (u_forced * length_m) / nu_m2s
    if u_forced > 1e-9:
        richardson = grashof / (reynolds ** 2)
        ri_display: Union[float, str] = round(richardson, 5)
    else:
        richardson = float("inf")
        ri_display = "Infinity (Pure Natural Convection)"

    # Combined mixed-convection effective velocity
    u_effective_ms = ((u_forced ** 3) + (u_buoyant_sacksteder_ms ** 3)) ** (1.0 / 3.0)

    # Regime classification
    if richardson < 0.1:
        regime_badge = "Forced-Convection Dominated (Ri < 0.1)"
        risk_level = "Microgravity / HVAC Controlled"
        interpretation = (
            f"At {env_label} with {u_forced * 100.0:.1f} cm/s ventilation, Ri = {richardson:.4f} << 0.1. "
            f"Buoyant plume speed ({u_buoyant_sacksteder_ms * 100.0:.2f} cm/s) is negligible compared to "
            f"forced HVAC flow; flame behavior closely follows microgravity (0g) forced-flow physics."
        )
    elif richardson <= 10.0:
        regime_badge = "Mixed-Convection Transition Regime (0.1 <= Ri <= 10)"
        risk_level = "Partial-Gravity Transitional"
        interpretation = (
            f"At {env_label} with {u_forced * 100.0:.1f} cm/s ventilation, Ri = {richardson:.2f} lies in the "
            f"mixed-convection regime. Induced buoyant flow ({u_buoyant_sacksteder_ms * 100.0:.1f} cm/s) and "
            f"cabin ventilation jointly govern oxygen transport (U_eff = {u_effective_ms * 100.0:.1f} cm/s)."
        )
    else:
        ri_str = f"{richardson:.1f}" if math.isfinite(richardson) else "Inf"
        regime_badge = "Buoyancy-Dominated Natural Convection (Ri > 10)"
        risk_level = "Buoyant Plume Dominated"
        interpretation = (
            f"At {env_label} with {u_forced * 100.0:.1f} cm/s ventilation, Ri = {ri_str} > 10. "
            f"Buoyancy-induced convection ({u_buoyant_sacksteder_ms * 100.0:.1f} cm/s) overwhelms forced "
            f"airflow, establishing an upward buoyant plume."
        )

    # 4-Environment Planetary Comparison Table for Frontend Visualization
    planetary_benchmarks = [
        ("ISS (0g)", 1.0e-6),
        ("Moon (0.165g)", 0.165),
        ("Mars (0.378g)", 0.378),
        ("Earth (1.0g)", 1.0),
    ]
    comparison_table: List[Dict[str, Any]] = []
    for label_p, g_p in planetary_benchmarks:
        gp_ms2 = g_p * G_EARTH_MS2
        gr_p = (gp_ms2 * beta_k_inv * dt_k * (length_m ** 3)) / (nu_m2s ** 2)
        ub_p = (gp_ms2 * beta_k_inv * dt_k * alpha_m2s) ** (1.0 / 3.0)
        ueff_p = ((u_forced ** 3) + (ub_p ** 3)) ** (1.0 / 3.0)
        ri_p = round(gr_p / (reynolds ** 2), 4) if u_forced > 1e-9 else None
        comparison_table.append({
            "environment": label_p,
            "gravity_g": g_p,
            "grashof_number": round(gr_p, 2),
            "richardson_number": ri_p,
            "buoyant_velocity_cms": round(ub_p * 100.0, 2),
            "effective_velocity_cms": round(ueff_p * 100.0, 2),
        })

    is_partial_g = 1e-4 < g_frac < 0.95
    partial_g_notice = (
        "THEORETICAL PARTIAL-GRAVITY BOUND: NASA PSI currently contains no direct lunar (0.165g) "
        "or Martian (0.378g) combustion measurements (pending future LUCI/FM2 missions). Partial-g "
        "metrics represent theoretical dimensionless scaling bounds between 0g and 1g."
        if is_partial_g
        else "Evaluated at boundary gravity regime (0g or 1g); partial-g entries in comparison table are theoretical bounds."
    )

    response: Dict[str, Any] = {
        "module_id": "THM-08",
        "function_name": "calc_mixed_convection_richardson_scaling",
        "inputs": {
            "gravity_g": g_frac,
            "environment_label": env_label,
            "u_forced_ms": round(u_forced, 5),
            "u_forced_cms": round(u_forced * 100.0, 2),
            "char_length_m": round(length_m, 4),
            "delta_t_k": round(dt_k, 1),
            "pressure_kpa": round(p_kpa, 3),
            "t_amb_k": round(t0_k, 2),
        },
        "outputs": {
            "grashof_number": round(grashof, 3),
            "rayleigh_number": round(rayleigh, 3),
            "reynolds_number": round(reynolds, 3),
            "richardson_number": ri_display,
            "buoyant_velocity_sacksteder_cms": round(u_buoyant_sacksteder_ms * 100.0, 2),
            "buoyant_velocity_bl_cms": round(u_buoyant_bl_ms * 100.0, 2),
            "effective_mixed_velocity_cms": round(u_effective_ms * 100.0, 2),
            "convection_regime": regime_badge,
            "partial_gravity_disclaimer": partial_g_notice,
        },
        "frontend_summary": {
            "headline_metric": {
                "label": "Richardson Number (Ri = Gr / Re^2)",
                "value": ri_display,
                "unit": "dimensionless",
            },
            "secondary_metric": {
                "label": "Effective Mixed-Convection Velocity",
                "value": round(u_effective_ms * 100.0, 2),
                "unit": "cm/s",
            },
            "status_badge": regime_badge,
            "risk_level": risk_level,
            "plain_language_interpretation": interpretation,
            "planetary_comparison_table": comparison_table,
        },
        "metadata": {
            "solver_backend": "Dimensionless Grashof-Reynolds-Richardson Mixed-Convection Solver (Pure Python)",
            "evidence_boundary": "Theoretical / Partial-g Bound",
            "psi_references": ["BASS-II [MSG]", "E-FIELD Flames [ACME/CIR] (Analogue)"],
            "literature_basis": "Altenkirch et al. (1980) Combust. Flame; Sacksteder (1990) 23rd Symp. Combust.; NASA/TM-2015-218492 Sec. 5.1",
            "si_attribution": "Generated with Super Intelligence (SI) assistance for NASA Space Apps 2026; partial-g outputs explicitly marked as theoretical bounds.",
        },
    }

    if investigation_context is not None:
        response["investigation_context"] = investigation_context

    return response


# ==============================================================================
# 2. JSON ROUTER INTERFACE
# ==============================================================================

def _extract_input_block(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be a dictionary.")
    raw = payload.get("inputs") or payload.get("params") or payload
    if not isinstance(raw, dict):
        raise ValueError("JSON 'inputs' block must be a dictionary.")

    grav = raw.get("gravity_g") if raw.get("gravity_g") is not None else raw.get("gravity") or raw.get("environment")
    if grav is None:
        raise KeyError("Missing required 'gravity_g' (e.g., 0.165, 0.378, 'Moon', 'Mars', 'ISS') in JSON payload.")

    if raw.get("u_forced_ms") is not None:
        u_ms = float(raw["u_forced_ms"])
    elif raw.get("u_forced_cms") is not None:
        u_ms = float(raw["u_forced_cms"]) / 100.0
    elif raw.get("u_flow_ms") is not None:
        u_ms = float(raw["u_flow_ms"])
    elif raw.get("u_flow_cms") is not None:
        u_ms = float(raw["u_flow_cms"]) / 100.0
    else:
        u_ms = 0.10

    if raw.get("char_length_m") is not None:
        l_m = float(raw["char_length_m"])
    elif raw.get("char_length_cm") is not None:
        l_m = float(raw["char_length_cm"]) / 100.0
    elif raw.get("char_length_mm") is not None:
        l_m = float(raw["char_length_mm"]) / 1000.0
    else:
        l_m = 0.05

    if raw.get("pressure_kpa") is not None:
        p_kpa = float(raw["pressure_kpa"])
    elif raw.get("pressure_psi") is not None:
        p_kpa = float(raw["pressure_psi"]) * 6.894757
    else:
        p_kpa = 101.325

    return {
        "gravity_g": grav,
        "u_forced_ms": u_ms,
        "char_length_m": l_m,
        "delta_t_k": float(raw.get("delta_t_k", 1400.0)),
        "pressure_kpa": p_kpa,
        "t_amb_k": float(raw.get("t_amb_k", 298.15)),
    }


def run_from_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Executes THM-08 from an LLM-extracted JSON dictionary, including optional batch scenarios."""
    args = _extract_input_block(payload)
    inv_ctx = payload.get("investigation_context")
    output = calc_mixed_convection_richardson_scaling(**args, investigation_context=inv_ctx)

    scenarios = payload.get("batch_scenarios") or payload.get("scenarios")
    if isinstance(scenarios, list) and scenarios:
        batch_results = []
        for idx, sc in enumerate(scenarios):
            if isinstance(sc, dict):
                sc_args = _extract_input_block(sc)
                sc_ctx = sc.get("investigation_context") or {
                    "scenario_name": sc.get("scenario_name", f"Scenario {idx + 1}")
                }
                batch_results.append(
                    calc_mixed_convection_richardson_scaling(**sc_args, investigation_context=sc_ctx)
                )
        output["batch_scenario_results"] = batch_results

    return output


def run_from_json_file(
    json_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Loads an input JSON file, executes THM-08, and optionally writes output JSON."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Input JSON file not found: {path.resolve()}")
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    result = run_from_json_payload(payload)
    if output_path is not None:
        with Path(output_path).open("w", encoding="utf-8") as f_out:
            json.dump(result, f_out, indent=2)
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] != "--test":
        res = run_from_json_file(sys.argv[1], sys.argv[2] if len(sys.argv) >= 3 else None)
        print(json.dumps(res, indent=2))
        sys.exit(0)

    print("=== THM-08 Verification: Mixed-Convection Richardson Scaling ===")
    for env in ["ISS", "Moon", "Mars", "Earth"]:
        r = calc_mixed_convection_richardson_scaling(env, u_forced_ms=0.10, char_length_m=0.05)
        print(f"{env:6s}: Ri={str(r['outputs']['richardson_number']):>8s}, Ub={r['outputs']['buoyant_velocity_sacksteder_cms']:5.2f} cm/s, Ueff={r['outputs']['effective_mixed_velocity_cms']:5.2f} cm/s")
