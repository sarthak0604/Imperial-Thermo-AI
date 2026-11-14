"""
THM-02: Gas-Phase Mixture Transport Properties & Effective Lewis Number Solver
==============================================================================
Module ID:       THM-02
File Name:       compute_mixture_transport_and_lewis_number.py
Challenge:       NASA Space Apps Challenge 2026 — Flame in Freefall
Domain:          Gas-Phase & Chemical Equilibrium / Transport Aerothermodynamics
Evidence Class:  Theoretical / Semi-Empirical Transport (Chapman-Enskog + Wilke/Mathur)
PSI References:  ACME (BRE, CFI-G, Flame Design) [CIR]; FLEX & FLEX-2 [MDCA/CIR]

Scientific Method & Governing Physics:
    Evaluates temperature- and pressure-dependent gas mixture dynamic viscosity (mu),
    thermal conductivity (k), thermal diffusivity (alpha), and mixture-averaged mass
    diffusivity (D_im), alongside dimensionless Prandtl (Pr), Schmidt (Sc), and
    effective Lewis (Le = alpha / D_im) numbers.

    - Primary Backend (if installed): Cantera ('gri30.yaml', transport_model='Mix'),
      implementing exact Chapman-Enskog kinetic theory, Wilke mixture viscosity,
      Mathur-Saxena mixture conductivity, and Hirschfelder-Curtiss diffusion.
    - Built-in Fallback Backend (zero external combustion dependencies): Pure-Python
      Chapman-Enskog Lennard-Jones (12-6) kinetic theory using Neufeld et al. (1972)
      collision integrals, Eucken polyatomic thermal conductivity correction, Wilke's
      (1950) mixture viscosity rule, Mathur-Saxena (1967) thermal conductivity averaging,
      and Hirschfelder-Curtiss mixture-averaged mass diffusivity.

References:
    1. Hirschfelder, J. O., Curtiss, C. F., & Bird, R. B. (1954). Molecular Theory of
       Gases and Liquids. Wiley.
    2. Wilke, C. R. (1950). A Viscosity Equation for Gas Mixtures. J. Chem. Phys., 18, 517.
    3. Mathur, S., Tondon, P. K., & Saxena, S. C. (1967). Thermal conductivity of binary,
       ternary and quaternary mixtures of rare gases. Mol. Phys., 12(6), 569-579.
    4. Neufeld, P. D., Janzen, A. R., & Aziz, R. A. (1972). Empirical Equations to Calculate
       16 of the Transport Collision Integrals for the Lennard-Jones (12-6) Potential.
       J. Chem. Phys., 57, 1100-1102.
    5. Ronney, P. D. (1990). Near-limit flame structures at low Lewis number. Combustion
       and Flame, 82(1), 1-14. (NASA microgravity flame-ball / ACME thermo-diffusive theory).

SI / AI Attribution Notice:
    This module was developed with Super Intelligence (SI) code-generation assistance
    for the NASA Space Apps Challenge 2026 and verified against kinetic-theory benchmarks.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import cantera as ct  # type: ignore
    _HAS_CANTERA = True
except ImportError:
    ct = None
    _HAS_CANTERA = False


# ==============================================================================
# 1. THERMODYNAMIC & LENNARD-JONES (12-6) SPECIES DATABASE (Fallback Solver)
# ==============================================================================
# Parameters:
#   M:          Molar mass [g/mol]
#   sigma:      Lennard-Jones collision diameter [Angstroms]
#   eps_k:      Lennard-Jones potential well depth epsilon / k_B [K]
#   dof_rot:    Rotational degrees of freedom (0=monatomic, 2=linear, 3=non-linear)
#   cp_coeffs:  [a0, a1, a2, a3] for molar Cp(T) [J/(mol*K)] = a0 + a1*T + a2*T^2 + a3*T^3
#               (valid across ~250 K - 3000 K for engineering transport ratios)
SPECIES_DB: Dict[str, Dict[str, Any]] = {
    "N2": {
        "M": 28.0134,
        "sigma": 3.798,
        "eps_k": 71.4,
        "dof_rot": 2,
        "cp_coeffs": [27.27, 4.93e-3, -0.33e-6, 0.0],
    },
    "O2": {
        "M": 31.9988,
        "sigma": 3.467,
        "eps_k": 106.7,
        "dof_rot": 2,
        "cp_coeffs": [25.48, 15.20e-3, -7.15e-6, 1.31e-9],
    },
    "CO2": {
        "M": 44.0095,
        "sigma": 3.941,
        "eps_k": 195.2,
        "dof_rot": 2,
        "cp_coeffs": [22.26, 59.81e-3, -35.01e-6, 7.47e-9],
    },
    "H2O": {
        "M": 18.0153,
        "sigma": 2.641,
        "eps_k": 809.1,
        "dof_rot": 3,
        "cp_coeffs": [32.24, 1.92e-3, 10.55e-6, -3.59e-9],
    },
    "CO": {
        "M": 28.0101,
        "sigma": 3.690,
        "eps_k": 91.7,
        "dof_rot": 2,
        "cp_coeffs": [28.16, 1.67e-3, 5.37e-6, -2.22e-9],
    },
    "H2": {
        "M": 2.0159,
        "sigma": 2.827,
        "eps_k": 59.7,
        "dof_rot": 2,
        "cp_coeffs": [29.11, -1.92e-3, 4.00e-6, -0.87e-9],
    },
    "HE": {
        "M": 4.0026,
        "sigma": 2.551,
        "eps_k": 10.22,
        "dof_rot": 0,
        "cp_coeffs": [20.786, 0.0, 0.0, 0.0],
    },
    "AR": {
        "M": 39.948,
        "sigma": 3.542,
        "eps_k": 93.3,
        "dof_rot": 0,
        "cp_coeffs": [20.786, 0.0, 0.0, 0.0],
    },
    "CH4": {
        "M": 16.0425,
        "sigma": 3.758,
        "eps_k": 148.6,
        "dof_rot": 3,
        "cp_coeffs": [19.89, 50.24e-3, 12.69e-6, -11.01e-9],
    },
    "C2H4": {
        "M": 28.0532,
        "sigma": 4.163,
        "eps_k": 224.7,
        "dof_rot": 3,
        "cp_coeffs": [3.95, 156.4e-3, -83.4e-6, 17.67e-9],
    },
    "C3H8": {
        "M": 44.0956,
        "sigma": 5.118,
        "eps_k": 237.1,
        "dof_rot": 3,
        "cp_coeffs": [-4.04, 304.8e-3, -157.2e-6, 31.74e-9],
    },
    "N-C4H10": {
        "M": 58.1222,
        "sigma": 4.687,
        "eps_k": 531.4,
        "dof_rot": 3,
        "cp_coeffs": [3.96, 371.5e-3, -183.4e-6, 35.00e-9],
    },
    "CH3OH": {
        "M": 32.0419,
        "sigma": 3.626,
        "eps_k": 481.8,
        "dof_rot": 3,
        "cp_coeffs": [21.15, 70.92e-3, 25.87e-6, -28.52e-9],
    },
    "C7H16": {
        "M": 100.2019,
        "sigma": 6.250,
        "eps_k": 570.0,
        "dof_rot": 3,
        "cp_coeffs": [-5.15, 676.2e-3, -365.1e-6, 76.58e-9],
    },
    "C8H18": {
        "M": 114.2285,
        "sigma": 6.520,
        "eps_k": 610.0,
        "dof_rot": 3,
        "cp_coeffs": [-6.10, 771.2e-3, -419.5e-6, 88.55e-9],
    },
    "C10H22": {
        "M": 142.2817,
        "sigma": 7.050,
        "eps_k": 680.0,
        "dof_rot": 3,
        "cp_coeffs": [-7.91, 960.9e-3, -528.8e-6, 113.1e-9],
    },
}

SPECIES_ALIASES: Dict[str, str] = {
    "NITROGEN": "N2",
    "OXYGEN": "O2",
    "CARBON DIOXIDE": "CO2",
    "WATER": "H2O",
    "STEAM": "H2O",
    "CARBON MONOXIDE": "CO",
    "HYDROGEN": "H2",
    "HELIUM": "HE",
    "ARGON": "AR",
    "METHANE": "CH4",
    "ETHYLENE": "C2H4",
    "ETHENE": "C2H4",
    "PROPANE": "C3H8",
    "BUTANE": "N-C4H10",
    "N-BUTANE": "N-C4H10",
    "NC4H10": "N-C4H10",
    "METHANOL": "CH3OH",
    "HEPTANE": "C7H16",
    "N-HEPTANE": "C7H16",
    "NC7H16": "C7H16",
    "OCTANE": "C8H18",
    "N-OCTANE": "C8H18",
    "NC8H18": "C8H18",
    "DECANE": "C10H22",
    "N-DECANE": "C10H22",
    "NC10H22": "C10H22",
}

COMMON_FUELS = {"CH4", "C2H4", "C3H8", "N-C4H10", "CH3OH", "C7H16", "C8H18", "C10H22", "H2", "CO"}
R_UNIVERSAL = 8.314462618  # J / (mol * K)


def normalize_species_name(name: str) -> str:
    """Normalizes common names or mixed-case formulas to canonical uppercase keys."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Invalid species identifier: {name!r}")
    cleaned = name.strip().upper()
    return SPECIES_ALIASES.get(cleaned, cleaned)


def _normalize_mole_fractions(mole_fracs: Dict[str, float]) -> Dict[str, float]:
    """Validates and normalizes species mole fractions so sum(X_i) == 1.0."""
    if not isinstance(mole_fracs, dict) or len(mole_fracs) == 0:
        raise ValueError("mole_fracs must be a non-empty dictionary of {species: fraction}.")

    cleaned: Dict[str, float] = {}
    for raw_sp, raw_val in mole_fracs.items():
        val = float(raw_val)
        if val < 0.0:
            raise ValueError(f"Negative fraction ({val}) is physically invalid for species {raw_sp!r}.")
        if val == 0.0:
            continue
        sp = normalize_species_name(raw_sp)
        cleaned[sp] = cleaned.get(sp, 0.0) + val

    total = sum(cleaned.values())
    if total <= 0.0:
        raise ValueError("Total sum of mole_fracs must be strictly positive.")

    return {sp: val / total for sp, val in cleaned.items()}


def _select_target_species(
    norm_fracs: Dict[str, float], target_species: Optional[str]
) -> str:
    """Selects or validates the target species for D_im, Sc_i, and Le_i calculation."""
    if target_species is not None:
        norm_target = normalize_species_name(target_species)
        if norm_target not in norm_fracs:
            raise ValueError(
                f"target_species '{target_species}' (normalized: '{norm_target}') "
                f"is not present with positive mole fraction in mole_fracs: {list(norm_fracs.keys())}"
            )
        return norm_target

    # Auto-select deficient fuel if present; otherwise O2; otherwise minor species
    fuels_present = [sp for sp in norm_fracs if sp in COMMON_FUELS]
    if fuels_present:
        return min(fuels_present, key=lambda s: norm_fracs[s])
    if "O2" in norm_fracs and len(norm_fracs) > 1:
        return "O2"
    return min(norm_fracs.keys(), key=lambda s: norm_fracs[s])


# ==============================================================================
# 2. CHAPMAN-ENSKOG COLLISION INTEGRALS & MIXING RULES (Fallback Solver)
# ==============================================================================
def _omega_22_lj(t_star: float) -> float:
    """Neufeld et al. (1972) empirical collision integral Omega^(2,2)* for viscosity/k."""
    t_star = max(0.3, min(t_star, 400.0))
    return (
        1.16145 * (t_star ** -0.14874)
        + 0.52487 * math.exp(-0.77320 * t_star)
        + 2.16178 * math.exp(-2.43787 * t_star)
    )


def _omega_11_lj(t_star: float) -> float:
    """Neufeld et al. (1972) empirical collision integral Omega^(1,1)* for binary diffusion."""
    t_star = max(0.3, min(t_star, 400.0))
    return (
        1.06036 * (t_star ** -0.15610)
        + 0.19300 * math.exp(-0.47635 * t_star)
        + 1.03587 * math.exp(-1.52996 * t_star)
        + 1.76474 * math.exp(-3.89411 * t_star)
    )


def _molar_cp(sp: str, temp_k: float) -> float:
    """Evaluates species molar heat capacity Cp(T) [J/(mol*K)] with safe high-T clamping."""
    t_clamped = max(200.0, min(temp_k, 3200.0))
    a0, a1, a2, a3 = SPECIES_DB[sp]["cp_coeffs"]
    return a0 + a1 * t_clamped + a2 * (t_clamped ** 2) + a3 * (t_clamped ** 3)


def _pure_species_viscosity_and_conductivity(sp: str, temp_k: float) -> Tuple[float, float, float]:
    """
    Computes pure-species dynamic viscosity mu_i [Pa*s], thermal conductivity
    k_i [W/(m*K)], and molar Cp_i [J/(mol*K)] via Chapman-Enskog + Eucken correction.
    """
    props = SPECIES_DB[sp]
    m_g = props["M"]
    sigma = props["sigma"]
    eps_k = props["eps_k"]

    t_star = temp_k / eps_k
    omega_22 = _omega_22_lj(t_star)

    # Chapman-Enskog pure gas viscosity [Pa*s]
    mu_i = 2.6693e-6 * math.sqrt(m_g * temp_k) / ((sigma ** 2) * omega_22)

    cp_molar = _molar_cp(sp, temp_k)
    cv_molar = max(1.5 * R_UNIVERSAL, cp_molar - R_UNIVERSAL)
    m_kg = m_g * 1e-3

    # Modified Eucken correlation for polyatomic thermal conductivity [W/(m*K)]
    f_eucken = 1.0 + (9.0 / 4.0) * (R_UNIVERSAL / cv_molar)
    k_i = f_eucken * (mu_i * cv_molar / m_kg)

    return mu_i, k_i, cp_molar


def _binary_diffusivity_ce(sp_i: str, sp_j: str, temp_k: float, pressure_pa: float) -> float:
    """
    Computes Chapman-Enskog binary mass diffusivity D_ij [m^2/s] between species i and j.
    """
    p_i = SPECIES_DB[sp_i]
    p_j = SPECIES_DB[sp_j]

    m_ij = 2.0 / (1.0 / p_i["M"] + 1.0 / p_j["M"])
    sigma_ij = 0.5 * (p_i["sigma"] + p_j["sigma"])
    eps_ij = math.sqrt(p_i["eps_k"] * p_j["eps_k"])

    t_star = temp_k / eps_ij
    omega_11 = _omega_11_lj(t_star)
    p_atm = pressure_pa / 101325.0

    # Chapman-Enskog binary diffusion coefficient [cm^2/s] -> convert to [m^2/s]
    d_ij_cm2s = (
        0.00266 * (temp_k ** 1.5)
        / (p_atm * math.sqrt(m_ij) * (sigma_ij ** 2) * omega_11)
    )
    return d_ij_cm2s * 1e-4


def _solve_fallback_chapman_enskog(
    norm_fracs: Dict[str, float],
    temp_k: float,
    pressure_kpa: float,
    target_sp: str,
) -> Dict[str, Any]:
    """Pure-Python Chapman-Enskog + Wilke + Mathur-Saxena + Hirschfelder-Curtiss solver."""
    for sp in norm_fracs:
        if sp not in SPECIES_DB:
            raise ValueError(
                f"Species '{sp}' is not in the fallback kinetic-theory database. "
                f"Supported species: {sorted(SPECIES_DB.keys())}"
            )

    pressure_pa = pressure_kpa * 1000.0
    species_list = list(norm_fracs.keys())
    x_vec = [norm_fracs[sp] for sp in species_list]

    pure_mu: List[float] = []
    pure_k: List[float] = []
    pure_cp: List[float] = []
    m_list: List[float] = []

    for sp in species_list:
        mu_i, k_i, cp_i = _pure_species_viscosity_and_conductivity(sp, temp_k)
        pure_mu.append(mu_i)
        pure_k.append(k_i)
        pure_cp.append(cp_i)
        m_list.append(SPECIES_DB[sp]["M"])

    # Mixture molecular weight [g/mol] and density [kg/m^3]
    m_mix_g = sum(x * m for x, m in zip(x_vec, m_list))
    m_mix_kg = m_mix_g * 1e-3
    rho_mix = (pressure_pa * m_mix_kg) / (R_UNIVERSAL * temp_k)

    # Mixture specific heat cp [J/(kg*K)]
    cp_mix_molar = sum(x * cp for x, cp in zip(x_vec, pure_cp))
    cp_mix_mass = cp_mix_molar / m_mix_kg

    # Wilke's (1950) semi-empirical rule for mixture dynamic viscosity mu_mix [Pa*s]
    n_sp = len(species_list)
    mu_mix = 0.0
    for i in range(n_sp):
        denom = 0.0
        for j in range(n_sp):
            if i == j:
                phi_ij = 1.0
            else:
                num = (1.0 + math.sqrt(pure_mu[i] / pure_mu[j]) * ((m_list[j] / m_list[i]) ** 0.25)) ** 2
                den = math.sqrt(8.0 * (1.0 + m_list[i] / m_list[j]))
                phi_ij = num / den
            denom += x_vec[j] * phi_ij
        mu_mix += (x_vec[i] * pure_mu[i]) / denom

    # Mathur-Saxena (1967) empirical averaging for mixture thermal conductivity k_mix [W/(m*K)]
    k_arith = sum(x * k for x, k in zip(x_vec, pure_k))
    k_harm_inv = sum(x / k for x, k in zip(x_vec, pure_k))
    k_mix = 0.5 * (k_arith + (1.0 / k_harm_inv))

    # Hirschfelder-Curtiss mixture-averaged mass diffusivity D_im [m^2/s] for target_sp
    x_target = norm_fracs[target_sp]
    if n_sp == 1 or x_target >= 0.999999:
        # Self-diffusion limit
        d_im = _binary_diffusivity_ce(target_sp, target_sp, temp_k, pressure_pa)
    else:
        sum_xj_over_dij = 0.0
        for sp_j, x_j in norm_fracs.items():
            if sp_j == target_sp:
                continue
            d_ij = _binary_diffusivity_ce(target_sp, sp_j, temp_k, pressure_pa)
            sum_xj_over_dij += x_j / d_ij
        d_im = (1.0 - x_target) / sum_xj_over_dij

    return {
        "backend": "Chapman-Enskog / Wilke / Mathur-Saxena Kinetic Theory (Python Fallback)",
        "molar_mass_g_mol": m_mix_g,
        "density_kg_m3": rho_mix,
        "specific_heat_cp_j_kgk": cp_mix_mass,
        "dynamic_viscosity_pa_s": mu_mix,
        "thermal_conductivity_w_mk": k_mix,
        "mass_diffusivity_m2_s": d_im,
    }


def _solve_cantera(
    norm_fracs: Dict[str, float],
    temp_k: float,
    pressure_kpa: float,
    target_sp: str,
) -> Dict[str, Any]:
    """Solves exact mixture-averaged transport properties via Cantera ('gri30.yaml')."""
    gas = ct.Solution("gri30.yaml")
    gas.transport_model = "Mix"

    # Map uppercase species keys to Cantera's gri30 case-sensitive species names
    ct_species_map = {s.upper(): s for s in gas.species_names}
    ct_comp = {}
    for sp, x_val in norm_fracs.items():
        if sp not in ct_species_map:
            raise ValueError(f"Species '{sp}' not found in Cantera gri30.yaml mechanism.")
        ct_comp[ct_species_map[sp]] = x_val

    gas.TPX = temp_k, pressure_kpa * 1000.0, ct_comp
    target_idx = gas.species_index(ct_species_map[target_sp])
    d_im = float(gas.mix_diff_coeffs[target_idx])

    return {
        "backend": "Cantera Mix Transport (Chapman-Enskog / Wilke / Mathur-Saxena)",
        "molar_mass_g_mol": float(gas.mean_molecular_weight),
        "density_kg_m3": float(gas.density),
        "specific_heat_cp_j_kgk": float(gas.cp_mass),
        "dynamic_viscosity_pa_s": float(gas.viscosity),
        "thermal_conductivity_w_mk": float(gas.thermal_conductivity),
        "mass_diffusivity_m2_s": d_im,
    }


# ==============================================================================
# 3. PRIMARY PUBLIC FUNCTION (THM-02)
# ==============================================================================
def compute_mixture_transport_and_lewis_number(
    mole_fracs: Dict[str, float],
    temp_k: float,
    pressure_kpa: float,
    target_species: Optional[str] = None,
    psi_citations: Optional[List[str]] = None,
    investigation_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes gas-phase mixture transport properties and dimensionless Prandtl,
    Schmidt, and effective Lewis numbers for microgravity combustion analysis.

    Parameters
    ----------
    mole_fracs : dict[str, float]
        Species mole fractions (e.g., {"CH4": 0.095, "O2": 0.190, "N2": 0.715}).
        Automatically normalized if sum != 1.0 (e.g., if percentages are passed).
    temp_k : float
        Gas evaluation temperature in Kelvin (T > 0).
    pressure_kpa : float
        Static ambient pressure in kilopascals (P > 0).
    target_species : str, optional
        Deficient/limiting species for D_im, Sc, and Le evaluation. If None,
        automatically selects the limiting fuel or oxidizer present.
    psi_citations : list[str], optional
        Traceable NASA PSI investigation IDs (e.g., ["PSI-69", "PSI-159"]).
    investigation_context : dict, optional
        Metadata extracted from NASA PSI by the upstream LLM router.

    Returns
    -------
    dict
        JSON-serializable dictionary of transport properties, dimensionless ratios,
        thermo-diffusive stability classification, and NASA PSI provenance.
    """
    if temp_k <= 0.0:
        raise ValueError(f"temp_k must be strictly positive, got {temp_k}.")
    if pressure_kpa <= 0.0:
        raise ValueError(f"pressure_kpa must be strictly positive, got {pressure_kpa}.")

    norm_fracs = _normalize_mole_fractions(mole_fracs)
    target_sp = _select_target_species(norm_fracs, target_species)

    if _HAS_CANTERA:
        try:
            raw = _solve_cantera(norm_fracs, float(temp_k), float(pressure_kpa), target_sp)
        except Exception:
            raw = _solve_fallback_chapman_enskog(
                norm_fracs, float(temp_k), float(pressure_kpa), target_sp
            )
    else:
        raw = _solve_fallback_chapman_enskog(
            norm_fracs, float(temp_k), float(pressure_kpa), target_sp
        )

    rho = raw["density_kg_m3"]
    cp = raw["specific_heat_cp_j_kgk"]
    mu = raw["dynamic_viscosity_pa_s"]
    k = raw["thermal_conductivity_w_mk"]
    d_im = raw["mass_diffusivity_m2_s"]

    # Kinematic diffusivities [m^2/s]
    nu = mu / rho
    alpha = k / (rho * cp)

    # Dimensionless transport groups
    prandtl = nu / alpha
    schmidt = nu / d_im
    lewis = alpha / d_im

    # Thermo-diffusive microgravity flame stability classification
    if lewis < 0.90:
        stability_regime = "Thermo-Diffusively Unstable / Cellular & Flame-Ball Risk (Le < 0.90)"
        stability_note = (
            f"Mass diffusivity of {target_sp} exceeds thermal diffusivity (Le = {lewis:.3f} < 1). "
            "Curved microgravity flames focus reactants faster than heat conducts out, "
            "raising local flame temperature above T_ad and promoting cellular splitting."
        )
    elif lewis <= 1.10:
        stability_regime = "Equidiffusive / Neutral Stability (0.90 <= Le <= 1.10)"
        stability_note = (
            f"Thermal and mass diffusion rates are balanced (Le = {lewis:.3f} ~ 1.0), "
            "yielding smooth laminar flame fronts without strong preferential-diffusion shifts."
        )
    else:
        stability_regime = "Diffusively Damped / Quench-Prone (Le > 1.10)"
        stability_note = (
            f"Thermal diffusion outpaces {target_sp} mass diffusion (Le = {lewis:.3f} > 1). "
            "Stretch or curvature extracts heat faster than fuel diffuses in, weakening the "
            "flame and promoting extinction (characteristic of heavy alkanes or Helium dilution)."
        )

    citations = psi_citations if psi_citations else ["ACME (PSI-159)", "FLEX (PSI-69)"]

    result: Dict[str, Any] = {
        "module_id": "THM-02",
        "function_name": "compute_mixture_transport_and_lewis_number",
        "inputs": {
            "normalized_mole_fracs": {sp: round(val, 6) for sp, val in norm_fracs.items()},
            "temp_k": float(temp_k),
            "pressure_kpa": float(pressure_kpa),
            "target_species": target_sp,
        },
        "transport_properties": {
            "mixture_molar_mass_g_mol": round(raw["molar_mass_g_mol"], 4),
            "density_kg_m3": round(rho, 6),
            "specific_heat_cp_j_kgk": round(cp, 3),
            "dynamic_viscosity_pa_s": float(f"{mu:.6e}"),
            "kinematic_viscosity_m2_s": float(f"{nu:.6e}"),
            "thermal_conductivity_w_mk": round(k, 6),
            "thermal_diffusivity_m2_s": float(f"{alpha:.6e}"),
            "mass_diffusivity_m2_s": float(f"{d_im:.6e}"),
        },
        "dimensionless_numbers": {
            "prandtl_number": round(prandtl, 4),
            "schmidt_number": round(schmidt, 4),
            "lewis_number": round(lewis, 4),
        },
        "thermo_diffusive_stability": {
            "regime": stability_regime,
            "interpretation": stability_note,
        },
        "metadata": {
            "solver_backend": raw["backend"],
            "evidence_boundary": "Theoretical / Semi-Empirical Transport",
            "psi_references": citations,
            "si_attribution": "Generated with SI assistance for NASA Space Apps 2026; verified via kinetic theory.",
        },
    }

    if investigation_context is not None:
        result["investigation_context"] = investigation_context

    return result


# Alias matching alternate naming convention
calc_mixture_transport_lewis_number = compute_mixture_transport_and_lewis_number


# ==============================================================================
# 4. LLM JSON PAYLOAD INGESTION & CLI RUNNER
# ==============================================================================
def run_from_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses an LLM-extracted JSON payload (either nested under 'params' per the
    dashboard router schema or flat at top level) and executes THM-02.
    """
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be a JSON object (dictionary).")

    # Support both dashboard router schema {"params": {...}} and flat JSON {"mole_fracs": ...}
    params = payload.get("params", payload)
    if not isinstance(params, dict):
        raise ValueError("'params' field in JSON payload must be a dictionary.")

    # Flexible key lookup for LLM-extracted parameters
    mole_fracs = (
        params.get("mole_fracs")
        or params.get("gas_composition")
        or params.get("species_mole_fractions")
    )
    if mole_fracs is None:
        raise KeyError("Missing required parameter 'mole_fracs' (or 'gas_composition') in JSON.")

    temp_k = params.get("temp_k") or params.get("temperature_k")
    if temp_k is None:
        raise KeyError("Missing required parameter 'temp_k' (or 'temperature_k') in JSON.")

    pressure_kpa = params.get("pressure_kpa")
    if pressure_kpa is None and "pressure_atm" in params:
        pressure_kpa = float(params["pressure_atm"]) * 101.325
    elif pressure_kpa is None and "pressure_psi" in params:
        pressure_kpa = float(params["pressure_psi"]) * 6.894757
    if pressure_kpa is None:
        raise KeyError("Missing required parameter 'pressure_kpa' (or 'pressure_atm'/'pressure_psi') in JSON.")

    target_species = params.get("target_species") or params.get("limiting_species")
    psi_citations = payload.get("psi_citations") or params.get("psi_citations")
    investigation_context = payload.get("investigation_context") or payload.get("data_slice")

    # If the JSON includes a list of benchmark scenarios ('test_cases'), run all of them
    output = compute_mixture_transport_and_lewis_number(
        mole_fracs=mole_fracs,
        temp_k=float(temp_k),
        pressure_kpa=float(pressure_kpa),
        target_species=target_species,
        psi_citations=psi_citations,
        investigation_context=investigation_context,
    )

    if "batch_scenarios" in payload and isinstance(payload["batch_scenarios"], list):
        batch_results = []
        for idx, scenario in enumerate(payload["batch_scenarios"]):
            sc_params = scenario.get("params", scenario)
            sc_res = compute_mixture_transport_and_lewis_number(
                mole_fracs=sc_params["mole_fracs"],
                temp_k=float(sc_params["temp_k"]),
                pressure_kpa=float(sc_params["pressure_kpa"]),
                target_species=sc_params.get("target_species"),
                psi_citations=scenario.get("psi_citations", psi_citations),
                investigation_context={"scenario_name": scenario.get("scenario_name", f"Scenario {idx+1}")},
            )
            batch_results.append(sc_res)
        output["batch_scenario_results"] = batch_results

    return output


def run_from_json_file(json_path: str | Path, output_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Loads an LLM-generated JSON file from disk, runs THM-02, and optionally saves output."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Input JSON file not found: {path.resolve()}")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    result = run_from_json_payload(payload)

    if output_path is not None:
        out_p = Path(output_path)
        with out_p.open("w", encoding="utf-8") as f_out:
            json.dump(result, f_out, indent=2)

    return result


# ==============================================================================
# 5. SELF-VERIFICATION & UNIT TEST SUITE
# ==============================================================================
def _run_validation_tests() -> None:
    print("Running THM-02 Validation Benchmarks...")

    # Test 1: Standard ISS Air (21% O2, 79% N2 at 298.15 K, 101.325 kPa)
    res_air = compute_mixture_transport_and_lewis_number(
        mole_fracs={"O2": 0.21, "N2": 0.79},
        temp_k=298.15,
        pressure_kpa=101.325,
        target_species="O2",
    )
    pr_air = res_air["dimensionless_numbers"]["prandtl_number"]
    mu_air = res_air["transport_properties"]["dynamic_viscosity_pa_s"]
    assert 0.68 <= pr_air <= 0.75, f"Unexpected Pr for air: {pr_air}"
    assert 1.70e-5 <= mu_air <= 1.95e-5, f"Unexpected mu for air: {mu_air}"
    print(f"  [PASS] Test 1 (ISS Air 298 K): mu = {mu_air:.3e} Pa*s, Pr = {pr_air:.3f}")

    # Test 2: Stoichiometric CH4-Air (Le ~ 1.0, Neutral Stability)
    res_ch4 = compute_mixture_transport_and_lewis_number(
        mole_fracs={"CH4": 0.095, "O2": 0.190, "N2": 0.715},
        temp_k=298.15,
        pressure_kpa=101.325,
        target_species="CH4",
    )
    le_ch4 = res_ch4["dimensionless_numbers"]["lewis_number"]
    assert 0.90 <= le_ch4 <= 1.10, f"Unexpected Le for CH4-air: {le_ch4}"
    print(f"  [PASS] Test 2 (CH4-Air): Le = {le_ch4:.3f} -> {res_ch4['thermo_diffusive_stability']['regime']}")

    # Test 3: Lean H2 in O2/CO2 (Le < 0.90, Thermo-Diffusively Unstable Flame-Ball Regime)
    res_h2 = compute_mixture_transport_and_lewis_number(
        mole_fracs={"H2": 0.08, "O2": 0.20, "CO2": 0.72},
        temp_k=298.15,
        pressure_kpa=101.325,
        target_species="H2",
    )
    le_h2 = res_h2["dimensionless_numbers"]["lewis_number"]
    assert le_h2 < 0.50, f"Expected Le < 0.50 for H2/O2/CO2, got {le_h2}"
    print(f"  [PASS] Test 3 (Lean H2/O2/CO2): Le = {le_h2:.3f} -> {res_h2['thermo_diffusive_stability']['regime']}")

    # Test 4: Heavy Alkane n-Heptane (FLEX Droplet Fuel, Le > 2.0) + Helium Dilution
    res_hep_he = compute_mixture_transport_and_lewis_number(
        mole_fracs={"C7H16": 0.02, "O2": 0.21, "He": 0.77},
        temp_k=500.0,
        pressure_kpa=70.3,
        target_species="C7H16",
    )
    le_hep = res_hep_he["dimensionless_numbers"]["lewis_number"]
    k_hep = res_hep_he["transport_properties"]["thermal_conductivity_w_mk"]
    assert le_hep > 2.5, f"Expected high Le (>2.5) for C7H16 in He, got {le_hep}"
    print(f"  [PASS] Test 4 (FLEX n-Heptane + He at Lunar P): k = {k_hep:.4f} W/mK, Le = {le_hep:.3f}")

    print("All THM-02 validation checks passed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="THM-02: Compute gas-phase mixture transport properties and Lewis number."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Path to LLM-generated JSON input file (e.g., test_thm02_llm_input.json).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to write JSON output results.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in kinetic-theory unit tests.",
    )
    args = parser.parse_args()

    if args.test or args.input is None:
        _run_validation_tests()

    if args.input is not None:
        output_data = run_from_json_file(args.input, args.output)
        print("\nJSON Execution Output:")
        print(json.dumps(output_data, indent=2))
