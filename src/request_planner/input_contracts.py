"""Field-level input contracts for the registered thermo solvers."""

from .function_registry import model_spec


# Each path is relative to its prefix. '#' is an array index, '*' a name in a
# keyed map. '?' marks optional/conditional inputs. C marks an assembly choice,
# S a sourced string, B a Boolean, Q a {value, unit} quantity; other tokens
# are the actual units of numeric model fields.
def fields(prefix, spec):
    answer = {}
    for entry in spec.split():
        path, kind = entry.split(":", 1)
        optional = path.startswith("?")
        path = path.lstrip("?")
        answer[prefix + "/" + path] = (kind.replace("_", " "), not optional)
    return answer


ROUTES = {
    "THM-04": ("heat_release", "estimate_hrr"),
    "THM-05": ("flame_spread", "estimate_spread_rate"),
    "THM-06": ("flame_spread", "estimate_spread_rate"),
    "THM-10": ("droplet_combustion", "estimate_droplet_regression"),
    "THM-11": ("droplet_combustion", "estimate_cool_flame"),
    "THM-12": ("droplet_evaporation", "estimate_multicomponent_evaporation"),
    "THM-13": ("extinction", "estimate_radiative_quench"),
    "THM-14": ("heat_release", "estimate_radiative_fraction"),
    "THM-15": ("soot", "screen_soot_inception"),
    "THM-16": ("ignition", "estimate_ignition"),
    "THM-17": ("flammability", "estimate_limiting_oxygen"),
    "THM-18": ("suppression", "estimate_thermal_capacity"),
    "THM-19": ("cabin_fire", "estimate_cabin_response"),
    "THM-20": ("smoke", "estimate_aerosol_transport"),
}

S = "/request/scenario"
E = "/evidence"
MAT = E + "/materials/#"
CAL = MAT + "/calibrations/#"
PRO = E + "/profiles/#"
RUN = E + "/runs/#"
ECAL = E + "/calibrations/#"
FIRE = E + "/fires/#"
SETUP = E + "/setups/#"
P = "/params"
AMBIENT = "ambient/pressure:QkPa ambient/oxygen:Qm% ambient/air_speed:Qcm/s"
SPREAD_SETUP = fields(SETUP, "id:C model:C gravity_regime:C flow_direction:C") | fields(
    MAT, "id:C ?name:S"
) | fields(CAL, "id:C setup_id:C")
ROD_IDENT = "material_id:C setup_id:C gravity:C flow_direction:C"
COND13 = {
    "u_flow_ms": "m/s", "x_o2": "mf", "pressure_kpa": "kPa", "t_amb_k": "K",
    "co2_frac": "mf", "h2o_frac": "mf", "surface_emissivity": "1",
}
COND20 = {
    "duct_length_m": "m", "duct_area_m2": "m2", "air_speed_m_s": "m/s",
    "axial_temperature_gradient_K_m": "K/m", "smoke_mass_rate_kg_s": "kg/s", "duration_s": "s",
}
BOUNDS06 = {
    "air_speed_m_s": "m/s", "pressure_kPa": "kPa", "oxygen_pct": "m%",
    "ambient_temperature_K": "K", "sample_length_m": "m", "sample_width_m": "m", "sample_thickness_m": "m",
}
SPECIES19 = {
    "oxygen_consumption_kg_s": "kg/s", "co2_production_kg_s": "kg/s",
    "co_production_kg_s": "kg/s", "other_net_gas_mol_s": "mol/s",
}
CHECK_META = "?run_id:C ?measurement_basis:S ?source_locator:S"
heat_material = """
    ?heat_combustion_jkg:J/kg ?heat_pyrolysis_jkg:J/kg ?t_vap_k:K
    ?stoich_o2_fuel_mass_ratio:1 ?surface_emissivity:1 ?cp_gas_jkgk:J/(kg_K)
    ?material_name:C ?include_surface_radiation:B
"""
CONTRACTS = {
    "THM-01": fields(P, """fuel_species:C o2_mole_frac:mf pressure_kpa:kPa
                          ?diluent_gas:C ?equivalence_ratio:1 ?t_init_k:K"""),
    "THM-02": fields(P, "mole_fracs/*:mf temp_k:K pressure_kpa:kPa ?target_species:C"),
    "THM-03": fields(P, """fuel_formula:C ?y_fuel_stream:yf ?y_ox_stream:yf ?x_fuel_stream:mf
                         ?x_ox_stream:mf ?fuel_diluent:C ?ox_diluent:C ?burner_radius_mm:mm
                         ?total_flow_rate_sccm:sccm ?pressure_kpa:kPa ?t_film_k:K ?flame_configuration:C"""),
    "THM-04": fields(S, "run_id:C ?time_window_s/#:s") | fields(RUN, """
        id:C measurement_method:C ?gas_basis:C ?heat_per_kg_o2_J:J/kg
        samples/#/time_s:s ?samples/#/mass_flow_kg_s:kg/s
        ?samples/#/o2_vol_frac:mf ?samples/#/co2_vol_frac:mf ?samples/#/co_vol_frac:mf
        ?samples/#/inlet_o2_kg_s:kg/s ?samples/#/outlet_o2_kg_s:kg/s
        ?samples/#/net_co_kg_s:kg/s ?samples/#/net_co2_kg_s:kg/s
        ?samples/#/soot_carbon_kg_s:kg/s ?samples/#/reference_hrr_W:W
        ?inlet/o2_vol_frac:mf ?inlet/co2_vol_frac:mf ?inlet/co_vol_frac:mf
        ?inlet/water_vapor_vol_frac:mf ?inlet/expansion_factor:1 ?inlet/gas_molar_mass_kg_mol:kg/mol
        ?benchmark/source_locator:S ?benchmark/source_url:S
    """),
    "THM-05": SPREAD_SETUP | fields(S, f"""materials/#:C setup_id:C gravity:C flow_direction:C
        {AMBIENT} specimen_thickness:Qm sample_width:Qm
    """) | fields(CAL, """air_speed_range_m_s/#:m/s pressure_range_kPa/#:kPa oxygen_range_pct/#:m%
        thickness_range_m/#:m width_range_m/#:m
        ?thermal/prefactors/thin_m2_s:m2/s ?thermal/prefactors/thick_dimensionless:1
        ?thermal/flame_coefficient:1 ?thermal/ambient_temperature_K:K
        ?thermal/vaporization_temperature_K:K ?thermal/effective_flame_temperature_K:K
        ?thermal/gas/density_reference_pressure_kPa:kPa
    """) | fields(CAL + "/thermal/solid", "?conductivity_W_m_K:W/(m_K) ?density_kg_m3:kg/m3 ?specific_heat_J_kg_K:J/(kg_K)") |
        fields(CAL + "/thermal/gas", "?conductivity_W_m_K:W/(m_K) ?density_kg_m3:kg/m3 ?specific_heat_J_kg_K:J/(kg_K)") |
        fields(CAL + "/spread_rate_checks/#", f"?thickness_m:m ?spread_rate_mm_s:mm/s ?air_speed_m_s:m/s {CHECK_META}"),
    "THM-06": SPREAD_SETUP | fields(S, f"""materials/#:C setup_id:C gravity:C flow_direction:C
        {AMBIENT} ambient/temperature:QK specimen_thickness:Qm sample_width:Qm sample_length:Qm
        ?initial_pyrolysis_length:Qm ?initial_front_position:Qm ?duration:Qs
    """) | fields(CAL, """
        thermal/specific_heat_J_kg_K:J/(kg_K) thermal/pyrolysis_temperature_K:K
        ?thermal/areal_mass_kg_m2:kg/m2 ?thermal/density_kg_m3:kg/m3
        gas/kinematic_viscosity_ref_m2_s:m2/s gas/conductivity_W_m_K:W/(m_K)
        gas/prandtl:1 gas/effective_flame_temperature_K:K
        heated_to_pyrolysis_length_ratio:1 growth_length_m:m
        pyrolysis_length_flow_exponent:1 ?effective_heat_feedback_factor:1
        reference/air_speed_m_s:m/s reference/pressure_kPa:kPa reference/oxygen_pct:m%
        reference/ambient_temperature_K:K reference/pyrolysis_length_m:m ?reference/spread_rate_mm_s:mm/s
        ?reference/sample_thickness_m:m ?reference/sample_width_m:m ?reference/sample_length_m:m ?reference/run_id:C
    """) | fields(CAL + "/bounds", " ".join(f"{key}/#:{unit}" for key, unit in BOUNDS06.items())) |
        fields(CAL + "/spread_rate_checks/#", f"?spread_rate_mm_s:mm/s {CHECK_META} " +
               " ".join(f"?{key}:{unit}" for key, unit in BOUNDS06.items())),
    "THM-07": fields(P, """u_flow_ms:m/s x_o2:mf ?pressure_kpa:kPa ?activation_energy_j:J/mol
                         ?flame_temp_k:K ?t_amb_k:K ?pre_exp_factor:1/s
                         ?reaction_order_n:1 ?o2_order_m:1 ?da_critical:1"""),
    "THM-08": fields(P, """gravity_g:g ?u_forced_ms:m/s ?char_length_m:m
                         ?delta_t_k:dK ?pressure_kpa:kPa ?t_amb_k:K"""),
    "THM-09": fields(P, f"""y_o2_amb:yf {heat_material} ?u_flow_ms:m/s ?char_length_m:m ?pressure_kpa:kPa ?t_amb_k:K"""),
    "THM-10": fields(S, """profile_id:C fuel_type:C process:C d0_mm:mm x_o2:mf pressure_kpa:kPa
        ?t_amb_k:K ?endpoint_diameter_mm:mm ?time_limit_s:s ?plot_points:I
    """) | fields(PRO, """id:C fuel_type:C process:C method:C
        validity/d0_mm/#:mm validity/x_o2/#:mf validity/pressure_kpa/#:kPa ?validity/t_amb_k/#:K
        ?regression_rate_mm2_s:mm2/s ?comparison_rate_mm2_s:mm2/s
        ?liquid_density_kg_m3:kg/m3 ?gas_conductivity_w_m_k:W/(m_K) ?gas_cp_j_kg_k:J/(kg_K)
        ?spalding_heat_transfer_number:1 ?surface_temperature_k:K ?effective_vaporization_heat_j_kg:J/kg
    """),
    "THM-11": fields(S, """setup_id:C materials/#:C ?gravity:C initial_diameter:Qmm
        ambient/pressure:QkPa ambient/oxygen:Qm% ambient/additional_diluent:C
    """) | fields(SETUP, "id:C model:C gravity_regime:C additional_diluent:C") | fields(MAT, "id:C") |
        fields(CAL, """id:C setup_id:C pressure_kPa:kPa oxygen_pct:m% initial_diameter_range_mm/#:mm
        observed_initial_diameter_mm:mm hot_extinction_time_s:s hot_extinction_diameter_squared_mm2:mm2
        cool_burning_rate_mm2_s:mm2/s ?held_out_cool_extinction/time_s:s ?held_out_cool_extinction/method:S
    """) | fields(MAT + "/cool_extinction_references/#", """setup_id:C run_id:C pressure_kPa:kPa oxygen_pct:m%
        diameter_squared_mm2:mm2 cool_burning_rate_mm2_s:mm2/s
    """),
    "THM-12": fields(S, """profile_id:C t_surface_k:K pressure_kpa:kPa liquid_fractions/*:mf
       ambient_partial_pressures_kpa/*:kPa ?liquid_transport/radius_m:m
       ?liquid_transport/circulation_speed_m_s:m/s ?liquid_transport/mass_diffusivity_m2_s:m2/s
       ?time_evolution/initial_total_moles:mol ?time_evolution/duration_s:s
       ?time_evolution/min_total_moles:mol ?time_evolution/plot_points:I
    """) | fields(PRO, """id:C validity/t_surface_k/#:K validity/pressure_kpa/#:kPa
       components/#/id:C components/#/activity_coefficient:1 ?components/#/volatile:B
       ?components/#/reference_temperature_k:K ?components/#/reference_vapor_pressure_kpa:kPa
       ?components/#/vaporization_enthalpy_j_mol:J/mol ?components/#/transfer_conductance_mol_s_kpa:mol/(s_kPa)
    """),
    "THM-13": fields(S, "profile_id:C " + ROD_IDENT + " ?surroundings_temperature_k:K " +
        " ".join(f"{key}:{unit}" for key, unit in COND13.items())) |
        fields(PRO, "id:C " + ROD_IDENT + """
        flame_temperature_k:K surface_temperature_k:K planck_mean_per_atm_m_inv/co2:1/(atm_m)
        planck_mean_per_atm_m_inv/h2o:1/(atm_m) optical_path_length_m:m gas_volume_per_reference_area_m:m
        oxygen_heat_coupling_factor:1 heat_per_mol_oxygen_j:J/mol ?soot_absorption_m_inv:1/m
        ?emitting_surface_to_reference_area:1 ?other_loss_w_m2:W/m2
        ?oxygen_diffusion/diffusivity_m2_s:m2/s ?oxygen_diffusion/length_m:m
    """) | fields(PRO + "/validity", " ".join(f"{key}/#:{unit}" for key, unit in COND13.items())),
    "THM-14": fields(S, "run_id:C") | fields(RUN, """id:C samples/#/time_s:s
        samples/#/radiometer_flux_w_m2:W/m2 samples/#/total_hrr_w:W ?samples/#/background_flux_w_m2:W/m2
        geometry/method:C ?geometry/transmission:1 ?geometry/background_flux_w_m2:W/m2
        ?geometry/detector_area_m2:m2 ?geometry/view_factor_f12:1
        ?geometry/source_distance_m:m ?geometry/incidence_angle_deg:deg
        ?geometry/gray_body/emitting_area_m2:m2 ?geometry/gray_body/emissivity:1
        ?geometry/gray_body/temperature_k:K ?geometry/gray_body/surroundings_temperature_k:K
    """),
    "THM-15": fields(S, """calibration_id:C fuel_id:C setup_id:C gravity:C pressure_kPa:kPa
        flame_temperature_K:K temperature_gradient_K_m:K/m residence_time_s:s
        carbon_to_oxygen_atomic_ratio:1 radial_gas_velocity_m_s:m/s
    """) | fields(ECAL, """id:C fuel_id:C setup_id:C gravity:C pressure_range_kPa/#:kPa
        min_carbon_to_oxygen_atomic_ratio:1 threshold_curve/#/residence_time_s:s
        threshold_curve/#/threshold_temperature_K:K kinematic_viscosity_m2_s:m2/s
        thermophoretic_coefficient:1 ?temperature_margin_band_K:K
    """),
    "THM-16": fields(S, f"""setup_id:C materials/#:C ?gravity:C ?specimen_thickness:Qm {AMBIENT}
        ambient/temperature:QK exposure/heat_flux:QkW/m2 exposure/heating_time:Qs
    """) | fields(SETUP, "id:C model:C gravity_regime:C h_W_m2K:W/(m2_K) ?h_back_W_m2K:W/(m2_K)") |
        fields(MAT, """id:C properties/thickness_m:m properties/density_kg_m3:kg/m3
        properties/cp_J_kgK:J/(kg_K) properties/conductivity_W_mK:W/(m_K)
        properties/absorptivity:1 properties/emissivity:1 properties/pyrolysis_pre_exponential_s_inv:1/s
        properties/pyrolysis_activation_energy_j_mol:J/mol properties/heat_of_pyrolysis_j_kg:J/kg
    """) | fields(CAL, """id:C setup_id:C pressure_kPa:kPa oxygen_pct:m%
        speed_range_m_s/#:m/s ambient_temperature_range_K/#:K flux_range_kW_m2/#:kW/m2
        max_heating_time_s:s t_ign_k:K
    """),
    "THM-17": fields(S, "calibration_id:C " + ROD_IDENT + " pressure_kPa:kPa air_speed_m_s:m/s ?ambient_oxygen_pct:%") |
        fields(ECAL, "id:C " + ROD_IDENT + """ pressure_range_kPa/#:kPa air_speed_range_m_s/#:m/s
        ?axis_units_per_m_s:D combination_rule:C ?shared_baseline_pct:%
        ?reference_1g/oxygen_pct:% ?reference_1g/label:S
    """) | {
        path: rule for branch in ("quench", "blowoff") for path, rule in fields(
        ECAL + "/" + branch, """form:C ?intercept_pct:% ?slope_pct_per_axis_unit:D
        ?base_pct:% ?amplitude_pct:% ?decay_per_axis_unit:D ?points/#/0:D ?points/#/1:%
    """).items()},
    "THM-18": fields(S, """profile_id:C mode:C pressure_kPa:kPa ?initial_temperature_K:K
        ?target_temperature_K:K ?agent_mole_fraction:mf ?base_gas_mole_fractions/*:mf
        ?water_mass_kg:kg ?inlet_water_temperature_K:K ?liquid_endpoint_temperature_K:K ?evaporated_fraction:1
    """) | fields(PRO, """id:C mode:C pressure_range_kPa/#:kPa ?agent_species:C ?oxygen_species:C
        ?species/*/cp_at_reference_J_mol_K:J/(mol_K) ?species/*/cp_reference_temperature_K:K
        ?species/*/cp_slope_J_mol_K2:J/(mol_K2) ?species/*/temperature_range_K/#:K
        ?conduction/agent_mole_fraction:mf ?conduction/area_m2:m2 ?conduction/path_length_m:m
        ?conduction/base_conductivity_W_m_K:W/(m_K) ?conduction/mix_conductivity_W_m_K:W/(m_K)
        ?liquid_cp_J_kg_K:J/(kg_K) ?liquid_temperature_range_K/#:K
        ?vaporization_enthalpy_J_kg:J/kg ?phase_change_temperature_range_K/#:K
    """),
    "THM-19": fields(S, """fire_id:C cabin/volume_m3:m3 cabin/initial_pressure_kPa:kPa
        cabin/initial_temperature_K:K cabin/wall_temperature_K:K cabin/wall_ua_W_K:W/K
        cabin/effective_molar_cv_J_mol_K:J/(mol_K) cabin/fire_heat_fraction_to_gas:1
        ?cabin/initial_mole_fractions/oxygen:mf ?cabin/initial_mole_fractions/carbon_dioxide:mf
        ?cabin/initial_mole_fractions/carbon_monoxide:mf
    """) | fields(FIRE, "id:C time_s/#:s hrr_W/#:W " +
                " ".join(f"?species/{key}/#:{unit}" for key, unit in SPECIES19.items())),
    "THM-20": fields(S, "profile_id:C setup_id:C " +
                     " ".join(f"{key}:{unit}" for key, unit in COND20.items())) |
        fields(PRO, """id:C setup_id:C gas_temperature_K:K gas_dynamic_viscosity_Pa_s:Pa_s
        gas_density_kg_m3:kg/m3 source_particle_diameter_m:m particle_density_kg_m3:kg/m3
        thermophoretic_coefficient:1 axial_dispersion_m2_s:m2/s ?wall_loss_rate_s_inv:1/s
        ?collision_kernel_m3_s:m3/s ?gas_mean_free_path_m:m ?cunningham_slip_factor:1 ?laminar_shear_rate_s_inv:1/s
    """) | fields(PRO + "/scenario_bounds", " ".join(
            f"{'?' if key == 'duration_s' else ''}{key}/#:{unit}" for key, unit in COND20.items()
        )),
}


def contract_for(model_id):
    model_spec(model_id)
    return CONTRACTS[model_id]


MODE_REQUIREMENTS = {
    "THM-03": "Choose the mass fractions or the corresponding mole fractions and diluents. Use burner data for a geometry estimate.",
    "THM-04": "Choose paired_oxygen_mass_flow (inlet/outlet oxygen) or exhaust_mass_flow (flow, gas samples and dry inlet). Bound all channels to one synchronized run.",
    "THM-05": "Choose solid and gas thermal properties or both calibrated prefactors. Add a supported flame coefficient or the three temperature inputs. Match the calibration envelope.",
    "THM-06": "Use fixed areal mass or density and reference sample thickness. Supply a reference spread rate or fitted heat-feedback factor.",
    "THM-07": "Built-in kinetics and gas estimates are approximations. For a real material-specific limit, use matched kinetics and flame state.",
    "THM-09": "Supply named material properties. Built-in presets and generic defaults serve as approximations only.",
    "THM-10": "measured_rate needs regression_rate_mm2_s. heat_transfer needs gas and liquid properties, ambient temperature and Spalding inputs. Missing temperature is allowed for measured_rate with no temperature bounds.",
    "THM-11": "Needs a hot-stage endpoint and a separately identified cool-extinction reference. Use a run where both stages apply.",
    "THM-12": "Each volatile component needs vapor-pressure and enthalpy data. Time evolution also needs conductance and initial inventory.",
    "THM-13": "O2 is inlet gas. CO2 and H2O are radiating gas composition. Supply geometry, absorption and heat feedback for that same flame.",
    "THM-14": "Use a detector area and source-to-detector view factor, or distance and incidence angle for a far-field isotropic point source. Match HRR and radiometer time.",
    "THM-16": "Match material grade, heat exposure, setup and ignition criterion. A table of material properties alone cannot select an ignition calibration.",
    "THM-17": "Supply matched quench and blowoff branches. Forms are linear, exponential, or table. A shared-baseline fit needs its baseline.",
    "THM-18": "gas_dilution needs mixture, temperatures and gas properties. water_mist needs water mass, temperatures, evaporated fraction and water properties.",
    "THM-19": "For species evolution supply every source-rate channel and initial fractions. The heat-only mode uses the HRR history and cabin properties.",
    "THM-20": "Needs a smoke source and duct evidence. Choose a collision kernel, or mean free path and Cunningham slip factor within the continuum/slip regime.",
}


def catalog():
    """Compact field list the planner can use to select and source inputs."""
    return {
        model_id: {
            "route": ROUTES.get(model_id),
            "conditions": MODE_REQUIREMENTS.get(model_id),
            "fields": {path: (unit if required else f"?{unit}")
                       for path, (unit, required) in contract.items()},
        }
        for model_id, contract in CONTRACTS.items()
    }
