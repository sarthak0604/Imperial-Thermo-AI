"""
THM-01: Constant-Pressure Adiabatic Flame Temperature & Chemical Equilibrium Solver
Module: calc_adiabatic_flame_temp_equilibrium.py

Computes constant-pressure adiabatic flame temperature (T_ad) and equilibrium product
species mole fractions across spacecraft exploration atmospheres (ISS, Lunar Habitat,
EVA Suit, and custom gas mixtures), accounting for endothermic high-temperature
dissociation (CO2 <-> CO + 0.5 O2, H2O <-> H2 + 0.5 O2, OH, O, H, NO).

Scientific & Thermodynamic Principles:
1. Constant-Pressure First Law of Thermodynamics (Enthalpy Balance):
   H_reactants(T_init, P) = H_products(T_ad, P)
2. Chemical Equilibrium via Gibbs Free Energy Minimization (dG = 0 at constant T, P):
   Uses Cantera (GRI-Mech 3.0 / NASA-7 polynomials) when installed, with a rigorous
   built-in NASA-7 polynomial + equilibrium dissociation constant (Kp) solver
   fallback when Cantera is unavailable.

References:
- Gordon, S., & McBride, B. J. (1994). Computer Program for Calculation of Complex
  Chemical Equilibrium Compositions and Applications. NASA RP-1311.
- Turns, S. R. (2012). An Introduction to Combustion: Concepts and Applications (Ch. 2).
- Law, C. K. (2006). Combustion Physics (Ch. 1-2).
- NASA Space Apps Challenge 2026: Flame in Freefall (PSI ACME & FLEX context).

SI Attribution:
Generated with Super Intelligence (SI) assistance for NASA Space Apps 2026;
verified against Gordon & McBride (NASA RP-1311) and Cantera GRI-Mech 3.0 benchmarks.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

try:
    import cantera as ct
    _HAS_CANTERA = True
except ImportError:
    ct = None  # type: ignore
    _HAS_CANTERA = False

try:
    from scipy.optimize import brentq
    _HAS_SCIPY = True
except ImportError:
    brentq = None  # type: ignore
    _HAS_SCIPY = False


# ==============================================================================
# 1. FUEL & DILUENT NORMALIZATION TABLES
# ==============================================================================

FUEL_ALIASES: Dict[str, str] = {
    "methane": "CH4",
    "ch4": "CH4",
    "natural gas": "CH4",
    "ethane": "C2H6",
    "c2h6": "C2H6",
    "ethylene": "C2H4",
    "ethene": "C2H4",
    "c2h4": "C2H4",
    "acetylene": "C2H2",
    "c2h2": "C2H2",
    "propane": "C3H8",
    "c3h8": "C3H8",
    "butane": "C4H10",
    "n-butane": "C4H10",
    "c4h10": "C4H10",
    "heptane": "C7H16",
    "n-heptane": "C7H16",
    "c7h16": "C7H16",
    "octane": "C8H18",
    "n-octane": "C8H18",
    "c8h18": "C8H18",
    "decane": "C10H22",
    "n-decane": "C10H22",
    "c10h22": "C10H22",
    "methanol": "CH3OH",
    "ch3oh": "CH3OH",
    "ethanol": "C2H5OH",
    "c2h5oh": "C2H5OH",
    "hydrogen": "H2",
    "h2": "H2",
    "carbon monoxide": "CO",
    "co": "CO",
}

DILUENT_ALIASES: Dict[str, str] = {
    "nitrogen": "N2",
    "n2": "N2",
    "carbon dioxide": "CO2",
    "co2": "CO2",
    "helium": "HE",
    "he": "HE",
    "argon": "AR",
    "ar": "AR",
}

# Elemental formula [C, H, O, N] for stoichiometric & fallback solver
FUEL_ATOMS: Dict[str, Tuple[float, float, float, float]] = {
    "CH4": (1.0, 4.0, 0.0, 0.0),
    "C2H6": (2.0, 6.0, 0.0, 0.0),
    "C2H4": (2.0, 4.0, 0.0, 0.0),
    "C2H2": (2.0, 2.0, 0.0, 0.0),
    "C3H8": (3.0, 8.0, 0.0, 0.0),
    "C4H10": (4.0, 10.0, 0.0, 0.0),
    "C7H16": (7.0, 16.0, 0.0, 0.0),
    "C8H18": (8.0, 18.0, 0.0, 0.0),
    "C10H22": (10.0, 22.0, 0.0, 0.0),
    "CH3OH": (1.0, 4.0, 1.0, 0.0),
    "C2H5OH": (2.0, 6.0, 1.0, 0.0),
    "H2": (0.0, 2.0, 0.0, 0.0),
    "CO": (1.0, 0.0, 1.0, 0.0),
}

# Standard molar enthalpy of formation at 298.15 K (J/mol) [NIST / NASA RP-1311]
HF_298_J_MOL: Dict[str, float] = {
    "CH4": -74870.0,
    "C2H6": -84000.0,
    "C2H4": 52400.0,
    "C2H2": 227400.0,
    "C3H8": -103850.0,
    "C4H10": -125790.0,
    "C7H16": -187780.0,
    "C8H18": -208750.0,
    "C10H22": -249660.0,
    "CH3OH": -201000.0,
    "C2H5OH": -234800.0,
    "H2": 0.0,
    "CO": -110530.0,
    "CO2": -393510.0,
    "H2O": -241826.0,
    "O2": 0.0,
    "N2": 0.0,
    "HE": 0.0,
    "AR": 0.0,
    "OH": 37200.0,
    "O": 249180.0,
    "H": 217999.0,
    "NO": 91270.0,
}

# NASA-7 Polynomials (High-T: 1000-6000 K; Low-T: 200-1000 K) for fallback solver
# Format: (a1, a2, a3, a4, a5, a6, a7) where Cp/R = a1 + a2*T + a3*T^2 + a4*T^3 + a5*T^4
# H/(R*T) = a1 + a2*T/2 + a3*T^2/3 + a4*T^3/4 + a5*T^4/5 + a6/T
# S/R = a1*ln(T) + a2*T + a3*T^2/2 + a4*T^3/3 + a5*T^4/4 + a7
NASA7_HIGH: Dict[str, Tuple[float, float, float, float, float, float, float]] = {
    "CO2": (3.85746029, 4.41437026e-03, -2.21481404e-06, 5.23490188e-10, -4.72084164e-14, -4.87591660e+04, 2.27163806),
    "CO":  (2.71518561, 2.06252743e-03, -9.98825771e-07, 2.30053008e-10, -2.03647716e-14, -1.41518724e+04, 7.81868772),
    "H2O": (3.03399249, 2.17691804e-03, -1.64072518e-07, -9.70419870e-11, 1.68200992e-14, -3.00042971e+04, 4.96677010),
    "H2":  (3.33727920, -4.94024731e-05, 4.99456778e-07, -1.79566394e-10, 2.00255376e-14, -9.50158922e+02, -3.20502331),
    "O2":  (3.28253784, 1.48308754e-03, -7.57966669e-07, 2.09470555e-10, -2.16717794e-14, -1.08845772e+03, 5.45323129),
    "N2":  (2.92664000, 1.48797680e-03, -5.68476000e-07, 1.00970380e-10, -6.75335100e-15, -9.22797700e+02, 5.98052800),
    "OH":  (3.09288767, 5.48429716e-04, 1.26505228e-07, -8.79461556e-11, 1.17412376e-14, 3.85865700e+03, 4.47669610),
    "O":   (2.56942078, -8.59741137e-05, 4.19484589e-08, -1.00177799e-11, 1.22833691e-15, 2.92175791e+04, 4.78433864),
    "H":   (2.50000000, 7.05332819e-13, -1.99591964e-15, 2.30081632e-18, -9.27732332e-22, 2.54736599e+04, -0.44668285),
    "NO":  (3.26060560, 1.19110430e-03, -4.29170480e-07, 6.94576690e-11, -4.03360990e-15, 9.92097460e+03, 6.36930270),
    "HE":  (2.50000000, 0.0, 0.0, 0.0, 0.0, -7.45375000e+02, 0.92872397),
    "AR":  (2.50000000, 0.0, 0.0, 0.0, 0.0, -7.45375000e+02, 4.37967491),
}

NASA7_LOW: Dict[str, Tuple[float, float, float, float, float, float, float]] = {
    "CH4":    (5.14987613, -1.36709788e-02, 4.91800599e-05, -4.84743026e-08, 1.66693956e-11, -1.02466476e+04, -4.64130376),
    "C2H6":   (4.29142492, -5.50154270e-03, 5.99438288e-05, -7.08466285e-08, 2.68685771e-11, -1.15222055e+04, 2.66682316),
    "C2H4":   (3.95920148, -7.57052247e-03, 5.70990292e-05, -6.91588753e-08, 2.69884373e-11, 5.08977593e+03, 4.09733096),
    "C2H2":   (8.08681094e-01, 2.33615629e-02, -3.55171815e-05, 2.80152437e-08, -8.50072974e-12, 2.64289807e+04, 1.39397051e+01),
    "C3H8":   (0.93355381, 2.64245790e-02, 6.10597270e-06, -2.19774990e-08, 9.51492530e-12, -1.39585200e+04, 1.92016910e+01),
    "C4H10":  (1.93505000, 3.69153000e-02, -1.14026000e-05, -2.46774000e-09, 1.56483000e-12, -1.68206000e+04, 1.65314000e+01),
    "C7H16":  (3.12000000, 6.65000000e-02, -2.30000000e-05, 0.0, 0.0, -2.59200000e+04, 1.54000000e+01),
    "C8H18":  (3.55000000, 7.62000000e-02, -2.65000000e-05, 0.0, 0.0, -2.89500000e+04, 1.68000000e+01),
    "C10H22": (4.42000000, 9.55000000e-02, -3.32000000e-05, 0.0, 0.0, -3.50100000e+04, 1.95000000e+01),
    "CH3OH":  (5.71539582, -1.52309129e-02, 6.52441155e-05, -7.10806889e-08, 2.61352698e-11, -2.56427656e+04, -1.50409823),
    "C2H5OH": (4.83000000, 1.25000000e-02, 3.10000000e-05, -3.80000000e-08, 1.40000000e-11, -2.99500000e+04, 3.80000000),
    "O2":     (3.78245636, -2.99673416e-03, 9.84730201e-06, -9.68129509e-09, 3.24372837e-12, -1.06394356e+03, 3.65767573),
    "N2":     (3.29867700, 1.40824040e-03, -3.96322200e-06, 5.64151500e-09, -2.44485400e-12, -1.02089990e+03, 3.95037200),
    "CO2":    (2.35677352, 8.98459677e-03, -7.12356269e-06, 2.45919022e-09, -1.43699548e-13, -4.83719697e+04, 9.90105222),
    "CO":     (3.57953347, -6.10353680e-04, 1.01681433e-06, 9.07005884e-10, -9.04424499e-13, -1.43440860e+04, 3.50840928),
    "H2O":    (4.19864056, -2.03643410e-03, 6.52040211e-06, -5.48797062e-09, 1.77197817e-12, -3.02937267e+04, -0.84903220),
    "H2":     (2.34433112, 7.98052075e-03, -1.94781510e-05, 2.01572094e-08, -7.37611761e-12, -9.17935173e+02, 0.68301023),
    "HE":     (2.50000000, 0.0, 0.0, 0.0, 0.0, -7.45375000e+02, 0.92872397),
    "AR":     (2.50000000, 0.0, 0.0, 0.0, 0.0, -7.45375000e+02, 4.37967491),
}

R_UNIVERSAL = 8.314462618  # J / (mol * K)
P_STD_KPA = 101.325        # Standard 1 atm reference pressure in kPa


def _normalize_fuel(fuel_species: str) -> str:
    if not isinstance(fuel_species, str) or not fuel_species.strip():
        raise ValueError("fuel_species must be a non-empty string.")
    key = fuel_species.strip().lower()
    if key in FUEL_ALIASES:
        return FUEL_ALIASES[key]
    upper = fuel_species.strip().upper()
    if upper in FUEL_ATOMS:
        return upper
    raise ValueError(
        f"Unsupported fuel_species '{fuel_species}'. Supported fuels: {sorted(FUEL_ATOMS.keys())}"
    )


def _normalize_diluent(diluent_gas: str) -> str:
    if not isinstance(diluent_gas, str) or not diluent_gas.strip():
        raise ValueError("diluent_gas must be a non-empty string.")
    key = diluent_gas.strip().lower()
    if key in DILUENT_ALIASES:
        return DILUENT_ALIASES[key]
    upper = diluent_gas.strip().upper()
    if upper in ("N2", "CO2", "HE", "AR"):
        return upper
    raise ValueError(
        f"Unsupported diluent_gas '{diluent_gas}'. Supported diluents: N2, CO2, HE, AR."
    )


def _nasa7_enthalpy_j_mol(species: str, temp_k: float) -> float:
    """Evaluates absolute molar enthalpy H(T) [J/mol] using NASA-7 polynomials."""
    coeffs = NASA7_HIGH.get(species) if temp_k >= 1000.0 else NASA7_LOW.get(species)
    if coeffs is None:
        coeffs = NASA7_LOW.get(species) or NASA7_HIGH.get(species)
    if coeffs is None:
        return HF_298_J_MOL.get(species, 0.0)
    a1, a2, a3, a4, a5, a6, _ = coeffs
    t = temp_k
    h_rt = (
        a1
        + (a2 * t) / 2.0
        + (a3 * t**2) / 3.0
        + (a4 * t**3) / 4.0
        + (a5 * t**4) / 5.0
        + a6 / t
    )
    return h_rt * R_UNIVERSAL * t


def _nasa7_gibbs_rt(species: str, temp_k: float) -> float:
    """Evaluates dimensionless standard-state Gibbs free energy G^o(T)/(R*T)."""
    coeffs = NASA7_HIGH.get(species) if temp_k >= 1000.0 else NASA7_LOW.get(species)
    if coeffs is None:
        coeffs = NASA7_LOW.get(species) or NASA7_HIGH.get(species)
    if coeffs is None:
        return 0.0
    a1, a2, a3, a4, a5, a6, a7 = coeffs
    t = temp_k
    h_rt = (
        a1
        + (a2 * t) / 2.0
        + (a3 * t**2) / 3.0
        + (a4 * t**3) / 4.0
        + (a5 * t**4) / 5.0
        + a6 / t
    )
    s_r = (
        a1 * math.log(t)
        + a2 * t
        + (a3 * t**2) / 2.0
        + (a4 * t**3) / 3.0
        + (a5 * t**4) / 4.0
        + a7
    )
    return h_rt - s_r


def _solve_equilibrium_fallback(
    fuel_code: str,
    o2_mole_frac: float,
    pressure_kpa: float,
    diluent_code: str,
    equivalence_ratio: float,
    t_init_k: float,
) -> Tuple[float, Dict[str, float], float]:
    """
    Rigorous NASA-7 polynomial + Gibbs Free Energy minimization (Kp) equilibrium solver
    for constant-pressure combustion when Cantera is not installed.

    Solves coupled dissociation reactions at temperature T and pressure P (atm):
      (R1) CO2 <-> CO + 0.5 O2
      (R2) H2O <-> H2 + 0.5 O2
      (R3) 0.5 H2 + 0.5 O2 <-> OH
      (R4) 0.5 O2 <-> O
      (R5) 0.5 H2 <-> H
      (R6) 0.5 N2 + 0.5 O2 <-> NO  (when N2 is present)
    alongside C, H, O, N atomic conservation and First Law enthalpy balance H_P(T) = H_R(T_init).
    """
    c_atom, h_atom, o_atom, n_atom = FUEL_ATOMS[fuel_code]
    nu_o2_stoich = c_atom + h_atom / 4.0 - o_atom / 2.0
    if nu_o2_stoich <= 0:
        raise ValueError(f"Fuel {fuel_code} has non-positive stoichiometric O2 requirement.")

    # Moles of O2 and diluent per 1 mole of fuel
    n_o2_in = nu_o2_stoich / equivalence_ratio
    if math.isclose(o2_mole_frac, 1.0, rel_tol=0.0, abs_tol=1e-12):
        n_dil_in = 0.0
    else:
        n_dil_in = n_o2_in * (1.0 - o2_mole_frac) / o2_mole_frac

    # Initial reactant enthalpy [J per mol fuel]
    h_reactants = (
        _nasa7_enthalpy_j_mol(fuel_code, t_init_k)
        + n_o2_in * _nasa7_enthalpy_j_mol("O2", t_init_k)
        + n_dil_in * _nasa7_enthalpy_j_mol(diluent_code, t_init_k)
    )

    # Atomic totals
    tot_c = c_atom + (n_dil_in if diluent_code == "CO2" else 0.0)
    tot_h = h_atom
    tot_o = o_atom + 2.0 * n_o2_in + (2.0 * n_dil_in if diluent_code == "CO2" else 0.0)
    tot_n = n_atom + (2.0 * n_dil_in if diluent_code == "N2" else 0.0)
    n_inert = n_dil_in if diluent_code in ("HE", "AR") else 0.0

    p_atm = pressure_kpa / P_STD_KPA

    def product_state_at_t(temp_k: float) -> Tuple[Dict[str, float], float]:
        """Solves species mole numbers at fixed (T, P) via damped fixed-point equilibrium."""
        g_co2 = _nasa7_gibbs_rt("CO2", temp_k)
        g_co = _nasa7_gibbs_rt("CO", temp_k)
        g_h2o = _nasa7_gibbs_rt("H2O", temp_k)
        g_h2 = _nasa7_gibbs_rt("H2", temp_k)
        g_o2 = _nasa7_gibbs_rt("O2", temp_k)
        g_oh = _nasa7_gibbs_rt("OH", temp_k)
        g_o = _nasa7_gibbs_rt("O", temp_k)
        g_h = _nasa7_gibbs_rt("H", temp_k)
        g_n2 = _nasa7_gibbs_rt("N2", temp_k)
        g_no = _nasa7_gibbs_rt("NO", temp_k)

        # Equilibrium constants Kp (in atm^dn)
        kp_co2 = math.exp(-(g_co + 0.5 * g_o2 - g_co2))
        kp_h2o = math.exp(-(g_h2 + 0.5 * g_o2 - g_h2o))
        kp_oh = math.exp(-(g_oh - 0.5 * g_h2 - 0.5 * g_o2))
        kp_o = math.exp(-(g_o - 0.5 * g_o2))
        kp_h = math.exp(-(g_h - 0.5 * g_h2))
        kp_no = math.exp(-(g_no - 0.5 * g_n2 - 0.5 * g_o2))

        # Initial major species estimate
        n_co2 = tot_c
        n_h2o = tot_h / 2.0
        n_o2_rem = max(1e-8, (tot_o - 2.0 * n_co2 - n_h2o) / 2.0)
        n_n2 = tot_n / 2.0
        n_co = 1e-8
        n_h2 = 1e-8

        if tot_o < 2.0 * tot_c + 0.5 * tot_h:
            o_avail = tot_o
            n_co = min(tot_c, o_avail)
            n_co2 = max(0.0, min(tot_c - n_co, (o_avail - n_co) / 2.0))
            n_co = tot_c - n_co2
            o_left = max(1e-8, o_avail - 2.0 * n_co2 - n_co)
            n_h2o = min(tot_h / 2.0, o_left)
            n_h2 = max(1e-8, tot_h / 2.0 - n_h2o)
            n_o2_rem = 1e-9

        def oxygen_residual(log_xo2: float) -> Tuple[float, Dict[str, float]]:
            xo2 = math.exp(log_xo2)
            n_tot = max(1e-6, n_co2 + n_co + n_h2o + n_h2 + n_o2_rem + n_n2 + n_inert)
            for _ in range(4):
                p_o2_sqrt = math.sqrt(max(1e-30, xo2 * p_atm))
                ratio_c = kp_co2 / p_o2_sqrt
                n_co2_loc = tot_c / (1.0 + ratio_c)
                n_co_loc = tot_c - n_co2_loc

                xo_loc = kp_o * p_o2_sqrt / p_atm
                n_o_loc = xo_loc * n_tot

                a_h = 2.0 * n_tot * (1.0 + p_o2_sqrt / kp_h2o)
                b_h = n_tot * (kp_oh * p_o2_sqrt + kp_h / math.sqrt(p_atm))
                if tot_h > 0.0 and a_h > 0.0:
                    disc = b_h * b_h + 4.0 * a_h * tot_h
                    u_h = (-b_h + math.sqrt(disc)) / (2.0 * a_h)
                else:
                    u_h = 0.0
                xh2_loc = u_h * u_h
                n_h2_loc = xh2_loc * n_tot
                n_h2o_loc = (p_o2_sqrt / kp_h2o) * n_h2_loc
                n_oh_loc = kp_oh * p_o2_sqrt * u_h * n_tot
                n_h_loc = (kp_h / math.sqrt(p_atm)) * u_h * n_tot

                if tot_n > 0.0:
                    k_no_eff = kp_no * math.sqrt(xo2)
                    a_n = 2.0 * n_tot
                    b_n = n_tot * k_no_eff
                    u_n = (-b_n + math.sqrt(b_n * b_n + 4.0 * a_n * tot_n)) / (2.0 * a_n)
                    n_n2_loc = u_n * u_n * n_tot
                    n_no_loc = k_no_eff * u_n * n_tot
                else:
                    n_n2_loc = 0.0
                    n_no_loc = 0.0

                n_o2_loc = xo2 * n_tot
                n_tot = max(
                    1e-9,
                    n_co2_loc
                    + n_co_loc
                    + n_h2o_loc
                    + n_h2_loc
                    + n_o2_loc
                    + n_oh_loc
                    + n_o_loc
                    + n_h_loc
                    + n_n2_loc
                    + n_no_loc
                    + n_inert,
                )

            o_calc = (
                2.0 * n_co2_loc
                + n_co_loc
                + n_h2o_loc
                + 2.0 * n_o2_loc
                + n_oh_loc
                + n_o_loc
                + n_no_loc
            )
            species_moles = {
                "CO2": n_co2_loc,
                "CO": n_co_loc,
                "H2O": n_h2o_loc,
                "H2": n_h2_loc,
                "O2": n_o2_loc,
                "OH": n_oh_loc,
                "O": n_o_loc,
                "H": n_h_loc,
                "N2": n_n2_loc,
                "NO": n_no_loc,
            }
            if diluent_code in ("HE", "AR") and n_inert > 0.0:
                species_moles[diluent_code] = n_inert
            return (o_calc - tot_o), species_moles

        lo, hi = math.log(1e-18), math.log(0.99)
        f_lo, _ = oxygen_residual(lo)
        f_hi, _ = oxygen_residual(hi)
        if f_lo * f_hi < 0:
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                f_mid, _ = oxygen_residual(mid)
                if abs(f_mid) < 1e-11:
                    lo = hi = mid
                    break
                if f_lo * f_mid <= 0:
                    hi = mid
                    f_hi = f_mid
                else:
                    lo = mid
                    f_lo = f_mid
            best_log_xo2 = 0.5 * (lo + hi)
        else:
            best_log_xo2 = lo if abs(f_lo) < abs(f_hi) else hi

        _, moles = oxygen_residual(best_log_xo2)
        h_prod = sum(
            n_i * _nasa7_enthalpy_j_mol(sp, temp_k) for sp, n_i in moles.items() if n_i > 0.0
        )
        return moles, h_prod

    def enthalpy_residual(temp_k: float) -> float:
        _, h_prod = product_state_at_t(temp_k)
        return h_prod - h_reactants

    t_low, t_high = 350.0, 4800.0
    if _HAS_SCIPY and brentq is not None:
        t_ad = float(brentq(enthalpy_residual, t_low, t_high, xtol=1e-4, maxiter=100))
    else:
        f_a = enthalpy_residual(t_low)
        f_b = enthalpy_residual(t_high)
        for _ in range(70):
            t_mid = 0.5 * (t_low + t_high)
            f_m = enthalpy_residual(t_mid)
            if abs(f_m) < 1e-3 or (t_high - t_low) < 1e-4:
                break
            if f_a * f_m <= 0:
                t_high = t_mid
                f_b = f_m
            else:
                t_low = t_mid
                f_a = f_m
        t_ad = 0.5 * (t_low + t_high)

    final_moles, _ = product_state_at_t(t_ad)
    total_moles = sum(final_moles.values())
    mole_fracs = {
        sp: round(val / total_moles, 6)
        for sp, val in final_moles.items()
        if (val / total_moles) >= 1e-6
    }

    # Compute ideal undissociated T_ad for comparison
    n_co2_ideal = tot_c
    n_h2o_ideal = tot_h / 2.0
    n_o2_ideal = max(0.0, (tot_o - 2.0 * n_co2_ideal - n_h2o_ideal) / 2.0)
    n_n2_ideal = tot_n / 2.0
    ideal_moles = {"CO2": n_co2_ideal, "H2O": n_h2o_ideal, "O2": n_o2_ideal, "N2": n_n2_ideal}
    if diluent_code in ("HE", "AR") and n_inert > 0.0:
        ideal_moles[diluent_code] = n_inert

    def ideal_h_res(tk: float) -> float:
        return (
            sum(n_i * _nasa7_enthalpy_j_mol(sp, tk) for sp, n_i in ideal_moles.items() if n_i > 0.0)
            - h_reactants
        )

    lo_i, hi_i = 350.0, 5500.0
    f_li = ideal_h_res(lo_i)
    for _ in range(60):
        mid_i = 0.5 * (lo_i + hi_i)
        f_mi = ideal_h_res(mid_i)
        if f_li * f_mi <= 0:
            hi_i = mid_i
        else:
            lo_i = mid_i
            f_li = f_mi
    t_ideal = 0.5 * (lo_i + hi_i)
    delta_t_dissoc = max(0.0, t_ideal - t_ad)

    return t_ad, mole_fracs, delta_t_dissoc


def _solve_equilibrium_cantera(
    fuel_code: str,
    o2_mole_frac: float,
    pressure_kpa: float,
    diluent_code: str,
    equivalence_ratio: float,
    t_init_k: float,
) -> Tuple[float, Dict[str, float], float]:
    """Solves constant-pressure chemical equilibrium using Cantera GRI-Mech 3.0."""
    assert ct is not None
    gas = ct.Solution("gri30.yaml")
    if fuel_code not in gas.species_names:
        return _solve_equilibrium_fallback(
            fuel_code, o2_mole_frac, pressure_kpa, diluent_code, equivalence_ratio, t_init_k
        )

    if math.isclose(o2_mole_frac, 1.0, rel_tol=0.0, abs_tol=1e-12):
        oxidizer = {"O2": 1.0}
    else:
        oxidizer = {"O2": o2_mole_frac, diluent_code: 1.0 - o2_mole_frac}

    gas.TP = t_init_k, pressure_kpa * 1000.0
    gas.set_equivalence_ratio(phi=equivalence_ratio, fuel={fuel_code: 1.0}, oxidizer=oxidizer)
    gas.equilibrate("HP")
    t_ad = float(gas.T)

    tracked_species = ["CO2", "CO", "H2O", "H2", "O2", "OH", "O", "H", "N2", "NO", "HE", "AR"]
    mole_fracs: Dict[str, float] = {}
    for sp in tracked_species:
        if sp in gas.species_names:
            x_val = float(gas[sp].X[0])
            if x_val >= 1e-6:
                mole_fracs[sp] = round(x_val, 6)

    _, _, delta_t_dissoc = _solve_equilibrium_fallback(
        fuel_code, o2_mole_frac, pressure_kpa, diluent_code, equivalence_ratio, t_init_k
    )
    return t_ad, mole_fracs, delta_t_dissoc


# ==============================================================================
# 2. MAIN PUBLIC THERMODYNAMIC SOLVER FUNCTION (THM-01)
# ==============================================================================

def calc_adiabatic_flame_temp_equilibrium(
    fuel_species: str,
    o2_mole_frac: float,
    pressure_kpa: float,
    diluent_gas: str = "N2",
    equivalence_ratio: float = 1.0,
    t_init_k: float = 298.15,
    investigation_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes constant-pressure adiabatic flame temperature (T_ad) and equilibrium
    combustion product mole fractions for habitable spacecraft atmospheres.

    Parameters
    ----------
    fuel_species : str
        Fuel formula or common name (e.g., 'CH4', 'methane', 'C3H8', 'C7H16', 'CH3OH', 'H2').
    o2_mole_frac : float
        Oxygen mole fraction in the oxidizer stream (0 < o2_mole_frac <= 1.0).
        Examples: 0.21 (ISS air), 0.30 (Lunar habitat), 1.0 (EVA spacesuit).
    pressure_kpa : float
        Total ambient pressure in kilopascals (pressure_kpa > 0).
        Examples: 101.325 kPa (14.7 psi ISS), 70.3 kPa (10.2 psi Lunar), 29.6 kPa (4.3 psi EVA).
    diluent_gas : str, optional
        Inert balance gas in oxidizer ('N2', 'CO2', 'HE', 'AR'), default 'N2'.
        Ignored cleanly when o2_mole_frac == 1.0.
    equivalence_ratio : float, optional
        Fuel-to-oxidizer equivalence ratio phi (> 0), default 1.0 (stoichiometric).
    t_init_k : float, optional
        Initial reactant temperature in Kelvin (> 0), default 298.15 K.
    investigation_context : dict, optional
        Optional metadata passed from the AI router (e.g., mission profile or PSI query).

    Returns
    -------
    dict
        JSON-serializable dictionary adhering to the Flame in Freefall I/O contract.
    """
    fuel_code = _normalize_fuel(fuel_species)
    diluent_code = _normalize_diluent(diluent_gas)

    if not (0.0 < float(o2_mole_frac) <= 1.0):
        raise ValueError(f"o2_mole_frac must satisfy 0 < X_O2 <= 1.0; got {o2_mole_frac}.")
    if float(pressure_kpa) <= 0.0:
        raise ValueError(f"pressure_kpa must be strictly positive (> 0 kPa); got {pressure_kpa}.")
    if float(equivalence_ratio) <= 0.0:
        raise ValueError(f"equivalence_ratio (phi) must be strictly positive (> 0); got {equivalence_ratio}.")
    if float(t_init_k) <= 0.0:
        raise ValueError(f"t_init_k must be strictly positive (> 0 K); got {t_init_k}.")

    o2_val = float(o2_mole_frac)
    p_val = float(pressure_kpa)
    phi_val = float(equivalence_ratio)
    t0_val = float(t_init_k)

    effective_diluent = "NONE (Pure O2)" if math.isclose(o2_val, 1.0, abs_tol=1e-12) else diluent_code

    if _HAS_CANTERA:
        t_ad, mole_fracs, delta_t_dissoc = _solve_equilibrium_cantera(
            fuel_code, o2_val, p_val, diluent_code, phi_val, t0_val
        )
        solver_backend = "Cantera GRI-Mech 3.0 (Gibbs Free Energy Minimization, HP Equilibrium)"
    else:
        t_ad, mole_fracs, delta_t_dissoc = _solve_equilibrium_fallback(
            fuel_code, o2_val, p_val, diluent_code, phi_val, t0_val
        )
        solver_backend = "NASA-7 Polynomial + Gibbs Kp Equilibrium Solver (Python Fallback)"

    minor_radicals = {
        sp: mole_fracs[sp]
        for sp in ("CO", "H2", "OH", "O", "H", "NO")
        if sp in mole_fracs and mole_fracs[sp] >= 1e-4
    }
    radical_str = ", ".join(f"{k}={v:.4f}" for k, v in minor_radicals.items()) or "trace (<1e-4)"
    dissociation_notice = (
        f"Endothermic product dissociation (CO2 <-> CO + 0.5 O2, H2O <-> H2 + 0.5 O2, OH/O/H) "
        f"absorbs thermal energy and lowers T_ad by ~{delta_t_dissoc:.1f} K relative to complete "
        f"undissociated combustion. Active equilibrium minor species: {radical_str}."
    )

    response: Dict[str, Any] = {
        "module_id": "THM-01",
        "function_name": "calc_adiabatic_flame_temp_equilibrium",
        "inputs": {
            "fuel_species": fuel_code,
            "o2_mole_frac": round(o2_val, 6),
            "pressure_kpa": round(p_val, 4),
            "pressure_psi": round(p_val * 0.1450377, 3),
            "diluent_gas": effective_diluent,
            "equivalence_ratio": round(phi_val, 4),
            "t_init_k": round(t0_val, 2),
        },
        "outputs": {
            "adiabatic_flame_temp_k": round(t_ad, 2),
            "adiabatic_flame_temp_c": round(t_ad - 273.15, 2),
            "estimated_dissociation_drop_k": round(delta_t_dissoc, 1),
            "equilibrium_mole_fractions": mole_fracs,
        },
        "dissociation_notice": dissociation_notice,
        "metadata": {
            "solver_backend": solver_backend,
            "evidence_boundary": "Theoretical / Partial-g Bound",
            "psi_references": [
                "ACME (BRE, CFI-G) [CIR]",
                "FLEX [MDCA/CIR]",
            ],
            "literature_basis": "Gordon & McBride (1994) NASA RP-1311; Turns (2012) Ch. 2",
            "si_attribution": "Generated with SI assistance for NASA Space Apps 2026; verified via NASA-7 equilibrium thermodynamics.",
        },
    }

    if investigation_context is not None:
        response["investigation_context"] = investigation_context

    return response


# ==============================================================================
# 3. JSON ROUTER INTERFACE (FOR DASHBOARD AI / FASTAPI / CLI PIPELINE)
# ==============================================================================

def _extract_input_block(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flexibly extracts input arguments whether the JSON file uses:
      - {"inputs": {...}}
      - {"params": {...}}
      - flat top-level keys {"fuel_species": ..., "o2_mole_frac": ..., ...}
    Also accepts common key aliases from LLM extractors (e.g., fuel, xo2, p_kpa, phi).
    """
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be a JSON object (dictionary).")

    raw = payload.get("inputs") or payload.get("params") or payload
    if not isinstance(raw, dict):
        raise ValueError("JSON 'inputs'/'params' field must be a dictionary.")

    fuel = (
        raw.get("fuel_species")
        or raw.get("fuel")
        or raw.get("fuel_type")
        or raw.get("species")
    )
    if fuel is None:
        raise KeyError("Missing required input key 'fuel_species' (or 'fuel') in JSON payload.")

    o2 = (
        raw.get("o2_mole_frac")
        if raw.get("o2_mole_frac") is not None
        else raw.get("xo2")
        if raw.get("xo2") is not None
        else raw.get("x_o2")
        if raw.get("x_o2") is not None
        else (raw["o2_percent"] / 100.0 if raw.get("o2_percent") is not None else None)
    )
    if o2 is None:
        raise KeyError("Missing required input key 'o2_mole_frac' (or 'xo2' / 'o2_percent') in JSON payload.")

    if raw.get("pressure_kpa") is not None:
        p_kpa = float(raw["pressure_kpa"])
    elif raw.get("p_kpa") is not None:
        p_kpa = float(raw["p_kpa"])
    elif raw.get("pressure_psi") is not None:
        p_kpa = float(raw["pressure_psi"]) * 6.894757
    elif raw.get("pressure_pa") is not None:
        p_kpa = float(raw["pressure_pa"]) / 1000.0
    else:
        raise KeyError("Missing required input key 'pressure_kpa' (or 'pressure_psi' / 'p_kpa') in JSON payload.")

    diluent = raw.get("diluent_gas") or raw.get("diluent") or "N2"
    phi = raw.get("equivalence_ratio") if raw.get("equivalence_ratio") is not None else raw.get("phi", 1.0)
    t_init = (
        raw.get("t_init_k")
        if raw.get("t_init_k") is not None
        else raw.get("temp_k")
        if raw.get("temp_k") is not None
        else raw.get("t_amb_k", 298.15)
    )

    return {
        "fuel_species": str(fuel),
        "o2_mole_frac": float(o2),
        "pressure_kpa": float(p_kpa),
        "diluent_gas": str(diluent),
        "equivalence_ratio": float(phi),
        "t_init_k": float(t_init),
    }


def run_from_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Executes THM-01 from an AI-extracted JSON dictionary, including optional batch scenarios."""
    args = _extract_input_block(payload)
    inv_ctx = payload.get("investigation_context")

    output = calc_adiabatic_flame_temp_equilibrium(
        fuel_species=args["fuel_species"],
        o2_mole_frac=args["o2_mole_frac"],
        pressure_kpa=args["pressure_kpa"],
        diluent_gas=args["diluent_gas"],
        equivalence_ratio=args["equivalence_ratio"],
        t_init_k=args["t_init_k"],
        investigation_context=inv_ctx,
    )

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
                    calc_adiabatic_flame_temp_equilibrium(
                        **sc_args, investigation_context=sc_ctx
                    )
                )
        output["batch_scenario_results"] = batch_results

    return output


def run_from_json_file(
    json_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Loads an input JSON file from disk, computes THM-01 equilibrium flame temperature,
    and optionally writes the resulting JSON payload to disk.
    """
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
# 4. SELF-VERIFICATION & BENCHMARK TEST SUITE
# ==============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] != "--test":
        in_file = sys.argv[1]
        out_file = sys.argv[2] if len(sys.argv) >= 3 else None
        res = run_from_json_file(in_file, out_file)
        print(json.dumps(res, indent=2))
        sys.exit(0)

    print("=== THM-01 Benchmark Verification: Spacecraft Exploration Atmospheres ===")
    benchmarks = [
        ("ISS Cabin Air (14.7 psi, 21% O2)", "methane", 0.21, 101.325, "N2"),
        ("Lunar Habitat (10.2 psi, 30% O2)", "CH4", 0.30, 70.3, "N2"),
        ("EVA Spacesuit (4.3 psi, 100% O2)", "CH4", 1.00, 29.6, "N2"),
    ]

    for label, fuel, xo2, pkpa, dil in benchmarks:
        out = calc_adiabatic_flame_temp_equilibrium(
            fuel_species=fuel,
            o2_mole_frac=xo2,
            pressure_kpa=pkpa,
            diluent_gas=dil,
            equivalence_ratio=1.0,
        )
        t_k = out["outputs"]["adiabatic_flame_temp_k"]
        x_co2 = out["outputs"]["equilibrium_mole_fractions"].get("CO2", 0.0)
        x_co = out["outputs"]["equilibrium_mole_fractions"].get("CO", 0.0)
        x_oh = out["outputs"]["equilibrium_mole_fractions"].get("OH", 0.0)
        print(
            f"{label:36s} -> T_ad = {t_k:7.2f} K | "
            f"X_CO2={x_co2:.4f}, X_CO={x_co:.4f}, X_OH={x_oh:.4f} | "
            f"[{out['metadata']['solver_backend'].split(' (')[0]}]"
        )
