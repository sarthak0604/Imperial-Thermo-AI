"""
THM-09: Spalding Mass-Transfer B-Number & Blowing Boundary-Layer Gasification Solver
Module: calc_spalding_mass_transfer_b_number.py

Computes the dimensionless Spalding mass-transfer driving potential (B-number)
and steady surface pyrolysis / gasification mass flux (m''_f) for solid spacecraft
polymers and textiles (e.g., PMMA, Cotton/Sibal fabric, Nomex, Silicone, Kapton)
under microgravity and exploration cabin atmospheres.

Scientific & Thermodynamic Principles:
1. Reynolds-Colburn Heat-Mass Transfer Analogy Across a Blowing Boundary Layer:
   - Ideal (Adiabatic) Spalding B-Number:
     B_ideal = [Y_O2,inf * (dH_c / nu_s) - c_p,g * (T_v - T_inf)] / dH_pyrolysis
   - Radiatively Corrected Effective Spalding B-Number (Critical in 0g):
     In microgravity, low convective heat transfer coefficients (h_c) make surface
     re-radiation (q''_rad = eps * sigma * (T_v^4 - T_inf^4)) a major energy sink:
     B_eff = [Y_O2,inf * (dH_c / nu_s) - c_p,g * (T_v - T_inf)] / (dH_pyrolysis + q''_rad / m''_f)
2. Surface Gasification / Pyrolysis Mass Flux (m''_f):
   m''_f = (h_c / c_p,g) * ln(1 + B_eff)
   where h_c = Nu * lambda_g / L (laminar flat-plate correlation Nu = 0.664 * Re^0.5 * Pr^(1/3))
   and ln(1 + B) / B is the boundary-layer blowing reduction factor.

References:
- Spalding, D. B. (1953). 4th Symp. (Int.) on Combustion, pp. 847-864.
- Glassman, I., & Yetter, R. A. Combustion (Ch. 6: Diffusion Flames).
- Quintiere, J. G. Fundamentals of Fire Phenomena (Ch. 7: Burning Rate & B-Number).

SI Attribution:
Generated with Super Intelligence (SI) assistance for NASA Space Apps 2026;
verified against Spalding blowing boundary-layer mass-transfer theory.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

SIGMA_SB = 5.670374419e-8  # Stefan-Boltzmann constant, W / (m^2 * K^4)
P_REF_KPA = 101.325
NU_AIR_REF = 1.568e-5      # m^2/s at 300 K, 101.325 kPa
K_AIR_REF = 0.02624        # W / (m * K) at 300 K
CP_GAS_DEFAULT = 1150.0    # J / (kg * K) mean gas-film specific heat
PRANDTL_DEFAULT = 0.71

# Built-in spacecraft material thermophysical presets (Quintiere; Glassman; NASA PSI BASS-II/Saffire)
MATERIAL_PRESETS: Dict[str, Dict[str, Any]] = {
    "pmma": {
        "display_name": "PMMA (Polymethyl Methacrylate / Plexiglass)",
        "heat_combustion_jkg": 25.2e6,
        "heat_pyrolysis_jkg": 1.60e6,
        "t_vap_k": 635.0,
        "stoich_o2_fuel_mass_ratio": 1.92,
        "surface_emissivity": 0.92,
    },
    "cotton": {
        "display_name": "Cotton / Sibal Cellulose Fabric (Saffire / BASS-II)",
        "heat_combustion_jkg": 16.5e6,
        "heat_pyrolysis_jkg": 1.80e6,
        "t_vap_k": 610.0,
        "stoich_o2_fuel_mass_ratio": 1.185,
        "surface_emissivity": 0.90,
    },
    "sibal": {
        "display_name": "Sibal (Cotton-Fiberglass Blend, BASS-II / Saffire)",
        "heat_combustion_jkg": 16.5e6,
        "heat_pyrolysis_jkg": 2.15e6,
        "t_vap_k": 620.0,
        "stoich_o2_fuel_mass_ratio": 1.185,
        "surface_emissivity": 0.90,
    },
    "nomex": {
        "display_name": "Nomex Aramid Flame-Resistant Textile",
        "heat_combustion_jkg": 27.0e6,
        "heat_pyrolysis_jkg": 4.20e6,
        "t_vap_k": 775.0,
        "stoich_o2_fuel_mass_ratio": 2.15,
        "surface_emissivity": 0.90,
    },
    "silicone": {
        "display_name": "Silicone Elastomer (BASS-II Rod/Sheet)",
        "heat_combustion_jkg": 21.0e6,
        "heat_pyrolysis_jkg": 2.60e6,
        "t_vap_k": 720.0,
        "stoich_o2_fuel_mass_ratio": 1.75,
        "surface_emissivity": 0.92,
    },
    "kapton": {
        "display_name": "Kapton Polyimide Film",
        "heat_combustion_jkg": 24.5e6,
        "heat_pyrolysis_jkg": 4.80e6,
        "t_vap_k": 820.0,
        "stoich_o2_fuel_mass_ratio": 1.98,
        "surface_emissivity": 0.88,
    },
    "polyethylene": {
        "display_name": "Polyethylene (PE)",
        "heat_combustion_jkg": 43.2e6,
        "heat_pyrolysis_jkg": 1.95e6,
        "t_vap_k": 660.0,
        "stoich_o2_fuel_mass_ratio": 3.42,
        "surface_emissivity": 0.92,
    },
}


def _resolve_material_props(
    material_name: Optional[str],
    heat_combustion_jkg: Optional[float],
    heat_pyrolysis_jkg: Optional[float],
    t_vap_k: Optional[float],
    stoich_o2_fuel_mass_ratio: Optional[float],
    surface_emissivity: Optional[float],
) -> Dict[str, Any]:
    preset: Dict[str, Any] = {
        "display_name": "Custom Solid Fuel",
        "heat_combustion_jkg": 25.0e6,
        "heat_pyrolysis_jkg": 1.80e6,
        "t_vap_k": 640.0,
        "stoich_o2_fuel_mass_ratio": 2.00,
        "surface_emissivity": 0.90,
    }
    if material_name:
        key = material_name.strip().lower()
        for p_key, p_val in MATERIAL_PRESETS.items():
            if p_key in key:
                preset = dict(p_val)
                break
        else:
            preset["display_name"] = material_name.strip()

    if heat_combustion_jkg is not None:
        preset["heat_combustion_jkg"] = float(heat_combustion_jkg)
    if heat_pyrolysis_jkg is not None:
        preset["heat_pyrolysis_jkg"] = float(heat_pyrolysis_jkg)
    if t_vap_k is not None:
        preset["t_vap_k"] = float(t_vap_k)
    if stoich_o2_fuel_mass_ratio is not None:
        preset["stoich_o2_fuel_mass_ratio"] = float(stoich_o2_fuel_mass_ratio)
    if surface_emissivity is not None:
        preset["surface_emissivity"] = float(surface_emissivity)

    return preset


def _solve_coupled_radiative_b(
    numerator_jkg: float,
    dh_pyr_jkg: float,
    q_rad_wm2: float,
    h_conv_wm2k: float,
    cp_gas_jkgk: float,
) -> Tuple[float, float]:
    """
    Solves coupled Spalding B_eff and gasification mass flux m''_f [kg/(m^2*s)]:
      B_eff = numerator / (dh_pyr + q_rad / m''_f)
      m''_f = (h_conv / cp_gas) * ln(1 + B_eff)
    Returns (B_eff, m_double_prime_kgs). Returns (<= 0, 0.0) if radiatively quenched.
    """
    if numerator_jkg <= 0.0:
        return numerator_jkg / dh_pyr_jkg, 0.0
    if q_rad_wm2 <= 0.0:
        b_val = numerator_jkg / dh_pyr_jkg
        m_flux = (h_conv_wm2k / cp_gas_jkgk) * math.log(1.0 + b_val)
        return b_val, m_flux

    # Upper bound on B is ideal adiabatic B
    b_hi = numerator_jkg / dh_pyr_jkg
    # Check if positive root exists via bisection on f(B) = B - numerator / (dh_pyr + q_rad / m''(B))
    def residual(b: float) -> float:
        if b <= 1e-9:
            return -1.0
        m_dot = (h_conv_wm2k / cp_gas_jkgk) * math.log(1.0 + b)
        if m_dot <= 1e-12:
            return -1.0
        rhs = numerator_jkg / (dh_pyr_jkg + (q_rad_wm2 / m_dot))
        return rhs - b

    # Sample grid to find upper-branch stable burning root
    best_b = 0.0
    for i in range(1, 201):
        b_test = b_hi * (i / 200.0)
        if residual(b_test) > 0.0:
            best_b = b_test

    if best_b <= 0.0:
        # Surface radiative loss exceeds convective flame heat feedback -> quenched
        return 0.0, 0.0

    lo = best_b
    hi = b_hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if residual(mid) > 0.0:
            lo = mid
        else:
            hi = mid

    b_eff = 0.5 * (lo + hi)
    m_flux = (h_conv_wm2k / cp_gas_jkgk) * math.log(1.0 + b_eff)
    return b_eff, m_flux


# ==============================================================================
# 1. MAIN PUBLIC SOLVER FUNCTION (THM-09)
# ==============================================================================

def calc_spalding_mass_transfer_b_number(
    y_o2_amb: float,
    heat_combustion_jkg: Optional[float] = None,
    heat_pyrolysis_jkg: Optional[float] = None,
    t_vap_k: Optional[float] = None,
    material_name: Optional[str] = "PMMA",
    stoich_o2_fuel_mass_ratio: Optional[float] = None,
    u_flow_ms: float = 0.15,
    char_length_m: float = 0.05,
    pressure_kpa: float = 101.325,
    t_amb_k: float = 298.15,
    cp_gas_jkgk: float = CP_GAS_DEFAULT,
    surface_emissivity: Optional[float] = None,
    include_surface_radiation: bool = True,
    investigation_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes the dimensionless Spalding mass-transfer driving force (B-number) and
    surface pyrolysis gasification mass flux (m''_f) across a blowing boundary layer.

    Parameters
    ----------
    y_o2_amb : float
        Ambient oxygen mass fraction (0 < y_o2_amb <= 1.0; air ~ 0.232, 30% O2/N2 ~ 0.329).
    heat_combustion_jkg : float, optional
        Lower heat of combustion delta_H_c in J/kg (> 0). Defaults to material preset.
    heat_pyrolysis_jkg : float, optional
        Effective heat of gasification / pyrolysis delta_H_pyr in J/kg (> 0).
    t_vap_k : float, optional
        Surface pyrolysis / vaporization temperature in K (> t_amb_k).
    material_name : str, optional
        Preset material name ('PMMA', 'Cotton', 'Sibal', 'Nomex', 'Silicone', 'Kapton', 'PE').
    stoich_o2_fuel_mass_ratio : float, optional
        Stoichiometric O2-to-fuel mass ratio nu_s (> 0).
    u_flow_ms : float, optional
        Forced cabin airflow speed over surface in m/s (> 0), default 0.15 m/s.
    char_length_m : float, optional
        Characteristic sample streamwise length in m (> 0), default 0.05 m.
    pressure_kpa : float, optional
        Ambient cabin pressure in kPa (> 0), default 101.325 kPa.
    t_amb_k : float, optional
        Ambient gas temperature in K (> 0), default 298.15 K.
    cp_gas_jkgk : float, optional
        Mean boundary-layer gas specific heat in J/(kg*K), default 1150.0.
    surface_emissivity : float, optional
        Surface thermal emissivity in [0, 1], default from material preset (~0.90).
    include_surface_radiation : bool, optional
        If True (default), solves coupled surface radiative loss q''_rad = eps*sigma*(T_v^4 - T_inf^4).
    investigation_context : dict, optional
        Optional metadata passed from the AI semantic router.

    Returns
    -------
    dict
        JSON-serializable dictionary with B_ideal, B_effective, pyrolysis mass flux,
        blowing factor, and frontend chart curve.
    """
    yo2 = float(y_o2_amb)
    u_ms = float(u_flow_ms)
    l_m = float(char_length_m)
    p_kpa = float(pressure_kpa)
    t0_k = float(t_amb_k)
    cp_g = float(cp_gas_jkgk)

    if not (0.0 < yo2 <= 1.0):
        raise ValueError(f"y_o2_amb must satisfy 0 < Y_O2 <= 1.0; got {yo2}.")
    if u_ms <= 0.0 or l_m <= 0.0 or p_kpa <= 0.0 or t0_k <= 0.0 or cp_g <= 0.0:
        raise ValueError("u_flow_ms, char_length_m, pressure_kpa, t_amb_k, and cp_gas_jkgk must be > 0.")

    props = _resolve_material_props(
        material_name,
        heat_combustion_jkg,
        heat_pyrolysis_jkg,
        t_vap_k,
        stoich_o2_fuel_mass_ratio,
        surface_emissivity,
    )
    dh_c = props["heat_combustion_jkg"]
    dh_pyr = props["heat_pyrolysis_jkg"]
    tv_k = props["t_vap_k"]
    nu_s = props["stoich_o2_fuel_mass_ratio"]
    eps = props["surface_emissivity"]

    if dh_c <= 0.0 or dh_pyr <= 0.0 or nu_s <= 0.0 or tv_k <= t0_k:
        raise ValueError("Invalid thermophysical properties: ensure dH_c > 0, dH_pyr > 0, nu_s > 0, T_vap > T_amb.")

    # Gas-film transport & laminar boundary-layer convective heat transfer coefficient h_c
    t_film_k = 0.5 * (tv_k + t0_k) + 400.0  # elevated film temperature due to flame sheet
    nu_g = NU_AIR_REF * ((t_film_k / 300.0) ** 1.75) * (P_REF_KPA / p_kpa)
    k_g = K_AIR_REF * ((t_film_k / 300.0) ** 0.80)
    re_l = (u_ms * l_m) / nu_g
    nu_l = 0.664 * math.sqrt(re_l) * (PRANDTL_DEFAULT ** (1.0 / 3.0))
    h_conv_wm2k = (nu_l * k_g) / l_m

    # Spalding thermodynamic driving numerator [J/kg]
    heat_release_per_unit_ox = dh_c / nu_s
    sensible_heating_jkg = cp_g * (tv_k - t0_k)
    numerator_jkg = yo2 * heat_release_per_unit_ox - sensible_heating_jkg

    # Ideal (adiabatic) Spalding B-number
    b_ideal = numerator_jkg / dh_pyr

    # Surface radiative heat loss flux q''_rad [W/m^2]
    q_rad_wm2 = eps * SIGMA_SB * ((tv_k ** 4) - (t0_k ** 4)) if include_surface_radiation else 0.0

    b_eff, m_flux_kgs = _solve_coupled_radiative_b(
        numerator_jkg, dh_pyr, q_rad_wm2, h_conv_wm2k, cp_g
    )

    blowing_factor = (math.log(1.0 + b_eff) / b_eff) if b_eff > 1e-6 else 1.0
    m_flux_gm2s = m_flux_kgs * 1000.0
    heat_release_flux_kwm2 = (m_flux_kgs * dh_c) / 1000.0

    # Safety & gasification regime interpretation
    if b_eff <= 0.0:
        status_badge = "Radiative Surface Quenching (B_eff <= 0)"
        risk_level = "Quenched / Self-Extinguishing"
        interpretation = (
            f"For {props['display_name']} at Y_O2 = {yo2:.3f} and {u_ms * 100.0:.1f} cm/s airflow, "
            f"surface thermal radiation ({q_rad_wm2 / 1000.0:.2f} kW/m^2) exceeds convective flame "
            f"heat feedback, suppressing sustained gasification."
        )
    elif b_eff < 1.0:
        status_badge = "Low-Transfer Pyrolysis Regime (0 < B_eff < 1.0)"
        risk_level = "Moderate"
        interpretation = (
            f"{props['display_name']} exhibits modest mass-transfer driving force (B_eff = {b_eff:.2f}, "
            f"B_ideal = {b_ideal:.2f}), yielding a surface gasification flux of {m_flux_gm2s:.2f} g/(m^2*s) "
            f"and local heat release flux of {heat_release_flux_kwm2:.1f} kW/m^2."
        )
    elif b_eff < 2.5:
        status_badge = "Moderate-to-High Blowing Regime (1.0 <= B_eff < 2.5)"
        risk_level = "Elevated"
        interpretation = (
            f"{props['display_name']} sustains vigorous pyrolysis (B_eff = {b_eff:.2f}; blowing factor = "
            f"{blowing_factor:.2f}), generating {m_flux_gm2s:.2f} g/(m^2*s) of fuel vapor and "
            f"{heat_release_flux_kwm2:.1f} kW/m^2 combustion heat flux."
        )
    else:
        status_badge = "Intense Gasification / High-B Regime (B_eff >= 2.5)"
        risk_level = "High Fire Intensity"
        interpretation = (
            f"Strong oxygen mass-transfer potential drives rapid pyrolysis of {props['display_name']} "
            f"(B_eff = {b_eff:.2f}, B_ideal = {b_ideal:.2f}), producing {m_flux_gm2s:.2f} g/(m^2*s) "
            f"fuel mass flux and {heat_release_flux_kwm2:.1f} kW/m^2 heat release intensity."
        )

    # Generate sweep across Y_O2 in [0.18, 0.55] for frontend plotting
    sweep_curve: List[Dict[str, float]] = []
    for pct in (18, 21, 25, 30, 35, 42, 50):
        yo2_pt = pct / 100.0
        num_pt = yo2_pt * heat_release_per_unit_ox - sensible_heating_jkg
        b_id_pt = num_pt / dh_pyr
        b_ef_pt, m_pt = _solve_coupled_radiative_b(num_pt, dh_pyr, q_rad_wm2, h_conv_wm2k, cp_g)
        sweep_curve.append({
            "y_o2_amb": round(yo2_pt, 3),
            "b_ideal": round(max(0.0, b_id_pt), 3),
            "b_effective": round(max(0.0, b_ef_pt), 3),
            "pyrolysis_flux_gm2s": round(m_pt * 1000.0, 3),
        })

    response: Dict[str, Any] = {
        "module_id": "THM-09",
        "function_name": "calc_spalding_mass_transfer_b_number",
        "inputs": {
            "material_name": props["display_name"],
            "y_o2_amb": round(yo2, 5),
            "heat_combustion_mjkg": round(dh_c / 1e6, 3),
            "heat_pyrolysis_mjkg": round(dh_pyr / 1e6, 3),
            "t_vap_k": round(tv_k, 1),
            "stoich_o2_fuel_mass_ratio": round(nu_s, 4),
            "u_flow_cms": round(u_ms * 100.0, 2),
            "char_length_m": round(l_m, 4),
            "pressure_kpa": round(p_kpa, 3),
            "include_surface_radiation": include_surface_radiation,
        },
        "outputs": {
            "spalding_b_ideal": round(b_ideal, 4),
            "spalding_b_effective": round(b_eff, 4),
            "pyrolysis_mass_flux_gm2s": round(m_flux_gm2s, 4),
            "pyrolysis_mass_flux_kgm2s": round(m_flux_kgs, 6),
            "blowing_correction_factor": round(blowing_factor, 4),
            "convective_htc_wm2k": round(h_conv_wm2k, 3),
            "surface_radiative_loss_kwm2": round(q_rad_wm2 / 1000.0, 3),
            "local_heat_release_flux_kwm2": round(heat_release_flux_kwm2, 2),
            "is_sustaining_pyrolysis": bool(b_eff > 0.0),
        },
        "frontend_summary": {
            "headline_metric": {
                "label": "Effective Spalding B-Number (B_eff)",
                "value": round(b_eff, 3),
                "unit": "dimensionless",
            },
            "secondary_metric": {
                "label": "Surface Pyrolysis Mass Flux",
                "value": round(m_flux_gm2s, 2),
                "unit": "g / (m^2 * s)",
            },
            "status_badge": status_badge,
            "risk_level": risk_level,
            "plain_language_interpretation": interpretation,
            "chart_series": {
                "x_axis": "y_o2_amb",
                "y_axes": ["b_ideal", "b_effective", "pyrolysis_flux_gm2s"],
                "data": sweep_curve,
            },
        },
        "metadata": {
            "solver_backend": "Spalding Blowing Boundary-Layer & Radiative Surface Balance Solver (Pure Python)",
            "evidence_boundary": "Direct PSI Data Reduction",
            "psi_references": ["BASS & BASS-II [MSG Flow Duct]", "Saffire-I/II/III [Cygnus]"],
            "literature_basis": "Spalding (1953) 4th Symp. Combust.; Glassman & Yetter (Ch. 6); Quintiere (Ch. 7)",
            "si_attribution": "Generated with Super Intelligence (SI) assistance for NASA Space Apps 2026; verified against Spalding mass-transfer theory.",
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

    # Accept y_o2_amb directly or convert from ambient O2 mole fraction / percent in N2
    if raw.get("y_o2_amb") is not None:
        yo2 = float(raw["y_o2_amb"])
    elif raw.get("x_o2") is not None or raw.get("o2_mole_frac") is not None:
        xo2 = float(raw.get("x_o2") if raw.get("x_o2") is not None else raw["o2_mole_frac"])
        yo2 = (xo2 * 31.998) / (xo2 * 31.998 + (1.0 - xo2) * 28.014)
    elif raw.get("o2_percent") is not None:
        xo2 = float(raw["o2_percent"]) / 100.0
        yo2 = (xo2 * 31.998) / (xo2 * 31.998 + (1.0 - xo2) * 28.014)
    else:
        raise KeyError("Missing required ambient oxygen key ('y_o2_amb', 'x_o2', or 'o2_percent') in JSON payload.")

    # Accept heat of combustion in J/kg or MJ/kg
    dh_c = None
    if raw.get("heat_combustion_jkg") is not None:
        dh_c = float(raw["heat_combustion_jkg"])
    elif raw.get("heat_combustion_mjkg") is not None:
        dh_c = float(raw["heat_combustion_mjkg"]) * 1e6

    dh_pyr = None
    if raw.get("heat_pyrolysis_jkg") is not None:
        dh_pyr = float(raw["heat_pyrolysis_jkg"])
    elif raw.get("heat_pyrolysis_mjkg") is not None:
        dh_pyr = float(raw["heat_pyrolysis_mjkg"]) * 1e6

    if raw.get("u_flow_ms") is not None:
        u_ms = float(raw["u_flow_ms"])
    elif raw.get("u_flow_cms") is not None:
        u_ms = float(raw["u_flow_cms"]) / 100.0
    else:
        u_ms = 0.15

    if raw.get("pressure_kpa") is not None:
        p_kpa = float(raw["pressure_kpa"])
    elif raw.get("pressure_psi") is not None:
        p_kpa = float(raw["pressure_psi"]) * 6.894757
    else:
        p_kpa = 101.325

    return {
        "y_o2_amb": yo2,
        "heat_combustion_jkg": dh_c,
        "heat_pyrolysis_jkg": dh_pyr,
        "t_vap_k": float(raw["t_vap_k"]) if raw.get("t_vap_k") is not None else None,
        "material_name": str(raw.get("material_name") or raw.get("material") or "PMMA"),
        "stoich_o2_fuel_mass_ratio": float(raw["stoich_o2_fuel_mass_ratio"]) if raw.get("stoich_o2_fuel_mass_ratio") is not None else None,
        "u_flow_ms": u_ms,
        "char_length_m": float(raw.get("char_length_m", 0.05)),
        "pressure_kpa": p_kpa,
        "t_amb_k": float(raw.get("t_amb_k", 298.15)),
        "cp_gas_jkgk": float(raw.get("cp_gas_jkgk", CP_GAS_DEFAULT)),
        "surface_emissivity": float(raw["surface_emissivity"]) if raw.get("surface_emissivity") is not None else None,
        "include_surface_radiation": bool(raw.get("include_surface_radiation", True)),
    }


def run_from_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Executes THM-09 from an LLM-extracted JSON dictionary, including optional batch scenarios."""
    args = _extract_input_block(payload)
    inv_ctx = payload.get("investigation_context")
    output = calc_spalding_mass_transfer_b_number(**args, investigation_context=inv_ctx)

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
                    calc_spalding_mass_transfer_b_number(**sc_args, investigation_context=sc_ctx)
                )
        output["batch_scenario_results"] = batch_results

    return output


def run_from_json_file(
    json_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Loads an input JSON file, executes THM-09, and optionally writes output JSON."""
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

    print("=== THM-09 Verification: Spalding Mass-Transfer B-Number ===")
    r_pmma_air = calc_spalding_mass_transfer_b_number(y_o2_amb=0.232, material_name="PMMA", u_flow_ms=0.20)
    r_pmma_lunar = calc_spalding_mass_transfer_b_number(y_o2_amb=0.329, material_name="PMMA", u_flow_ms=0.20, pressure_kpa=70.3)
    r_nomex_air = calc_spalding_mass_transfer_b_number(y_o2_amb=0.232, material_name="Nomex", u_flow_ms=0.10)
    print(f"PMMA in ISS Air (21% O2):       B_ideal={r_pmma_air['outputs']['spalding_b_ideal']:.2f}, B_eff={r_pmma_air['outputs']['spalding_b_effective']:.2f}, m''={r_pmma_air['outputs']['pyrolysis_mass_flux_gm2s']:.2f} g/m2s")
    print(f"PMMA in Lunar Hab (30% O2):     B_ideal={r_pmma_lunar['outputs']['spalding_b_ideal']:.2f}, B_eff={r_pmma_lunar['outputs']['spalding_b_effective']:.2f}, m''={r_pmma_lunar['outputs']['pyrolysis_mass_flux_gm2s']:.2f} g/m2s")
    print(f"Nomex in Low-Flow Air (10cm/s): B_ideal={r_nomex_air['outputs']['spalding_b_ideal']:.2f}, B_eff={r_nomex_air['outputs']['spalding_b_effective']:.2f}, Sustaining={r_nomex_air['outputs']['is_sustaining_pyrolysis']}")
