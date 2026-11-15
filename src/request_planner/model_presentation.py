"""Dashboard metrics and plots derived from solver outputs."""

from math import isfinite


METRICS = {
    "THM-01": [("adiabatic_flame_temp_k", "Adiabatic flame temperature", "K")],
    "THM-03": [("stoichiometric_mixture_fraction_zst", "Stoichiometric mixture fraction (Zₛₜ)", ""),
               ("stoich_o2_to_fuel_mass_ratio_s", "Oxygen to fuel mass ratio", "kg/kg")],
    "THM-04": [("total_heat_release_kJ", "Total heat released", "kJ"),
               ("peak_hrr_W", "Peak heat release rate", "kW", 0.001),
               ("peak_hrr_time_s", "Time of peak", "s")],
    "THM-06": [("spread_rate_mm_s", "Limiting spread rate", "mm/s"),
               ("initial_spread_rate_mm_s", "Initial spread rate", "mm/s")],
    "THM-08": [("richardson_number", "Richardson number", ""),
               ("buoyant_velocity_bl_cms", "Buoyant velocity scale", "cm/s")],
    "THM-09": [("spalding_b_ideal", "Ideal Spalding B-number", ""),
               ("spalding_b_effective", "Effective Spalding B-number", ""),
               ("pyrolysis_mass_flux_gm2s", "Surface mass-loss flux", "g/(m²·s)")],
    "THM-11": [("hot_extinction_time_s", "Hot-flame extinction", "s"),
               ("cool_stage_duration_s", "Cool-flame duration", "s"),
               ("cool_extinction_time_s", "Final extinction", "s")],
    "THM-13": [("critical_speed_m_s", "Low-flow quenching threshold", "cm/s", 100)],
    "THM-14": [("integrated_radiative_fraction", "Integrated radiative fraction", "%", 100),
               ("radiant_energy_j", "Total radiated energy", "J")],
    "THM-15": [("threshold_temperature_K", "Soot-inception threshold", "K"),
               ("temperature_margin_K", "Temperature margin", "K")],
    "THM-16": [("time_to_ignition_s", "Time to ignition criterion", "s"),
               ("ignition_criterion_K", "Surface temperature criterion", "K")],
    "THM-17": [("limiting_oxygen_pct", "Limiting oxygen concentration", "%"),
               ("air_speed_m_s", "Concurrent airflow", "cm/s", 100)],
    "THM-18": [("total_water_heat_sink_kJ", "Total heat absorbed", "kJ"),
               ("sensible_heat_kJ", "Heating the liquid", "kJ"),
               ("latent_heat_kJ", "Evaporating water", "kJ")],
    "THM-19": [("sampled_peak_temperature_K", "Peak cabin temperature", "K"),
               ("sampled_peak_pressure_change_kPa", "Peak pressure rise", "kPa")],
    "THM-20": [("mean_advective_travel_time_s", "Mean smoke travel time", "s"),
               ("equivalent_diameter_at_mean_arrival_m", "Particle diameter at arrival", "µm", 1e6),
               ("number_concentration_at_mean_arrival_m3", "Particle concentration at arrival", "particles/m³")],
}


def model_highlights(model_id, result):
    outputs = result.get("outputs", result)
    metrics = []

    def add(label, value, unit="", note=None):
        metrics.append({"label": label, "value": value, "unit": unit, "note": note})

    for key, label, unit, *factor in METRICS.get(model_id, ()):
        if outputs.get(key) is not None:
            value = outputs[key] * (factor[0] if factor else 1)
            add(label, float(f"{value:.5g}"), unit)
    if model_id == "THM-05" and result.get("rates_mm_s"):
        for thickness, rate in zip(result["thicknesses_mm"], result["rates_mm_s"]):
            add(f"{thickness:g} mm sheet", round(rate, 4), "mm/s")
    if model_id == "THM-10" and "diameter_mm" in result.get("plot_data", {}):
        data = result["plot_data"]
        add("Decrease in diameter", round(data["diameter_mm"][0] - data["diameter_mm"][-1], 4), "mm",
            f"Over {data['time_s'][-1]:g} s of modelled hot-stage burning")
        add("Final plotted diameter", round(data["diameter_mm"][-1], 4), "mm")
    if model_id == "THM-13" and "thermal_budget_w_m2" in result:
        add("Heat balance", result["heat_balance_status"].replace("_", " ").capitalize())
        add("Net heat margin", round(result["thermal_budget_w_m2"]["net_margin"], 2), "W/m²")
    if model_id == "THM-15" and "inception_screen" in result:
        add("Soot-inception screen", result["inception_screen"].replace("_", " ").capitalize())
    if model_id == "THM-16" and result.get("time_to_ignition_s") is None:
        add("Ignition criterion", "Unreached during exposure")
    return metrics


def scenario_summary(model_id, data):
    """Report the comparison or engineering outcome as well as the headline."""
    if model_id == "THM-06" and "spread_rate_mm_s" in data:
        return f"THM-06 estimates a limiting SIBAL flame-spread rate of {data['spread_rate_mm_s']:.4g} mm/s for the Saffire II concurrent-flow case."
    if model_id == "THM-08" and "richardson_number" in data.get("outputs", {}):
        o = data["outputs"]
        return (f"THM-08 estimates a Richardson number of {o['richardson_number']:.4g}. "
                f"{o['convection_regime']}. This is a theoretical mixed-convection estimate.")
    if model_id == "THM-10" and "diameter_mm" in data.get("plot_data", {}):
        p = data["plot_data"]
        start, end = p["diameter_mm"][0], p["diameter_mm"][-1]
        return (f"THM-10 estimates a decrease of {start-end:.3f} mm over {p['time_s'][-1]:g} s "
                f"of hot-stage burning, from {start:.3f} to {end:.3f} mm.")
    if model_id == "THM-11" and "hot_extinction_time_s" in data:
        return (f"THM-11 reconstructs hot-flame extinction at {data['hot_extinction_time_s']:.1f} s. "
                f"The cool flame lasts another {data['cool_stage_duration_s']:.1f} s, "
                f"ending near {data['cool_extinction_time_s']:.1f} s.")
    if model_id == "THM-13" and "thermal_budget_w_m2" in data:
        budget = data["thermal_budget_w_m2"]
        adequate = "offsets" if budget["net_margin"] >= 0 else "falls short of"
        threshold = data["critical_speed_m_s"]
        tail = f" The low-flow threshold is {100 * threshold:.3g} cm/s." if threshold is not None else ""
        return (f"At {100 * data['air_speed_m_s']:g} cm/s, predicted chemical heating {adequate} "
                f"the heat-loss budget. The net margin is {budget['net_margin']:.3g} W/m²." + tail)
    if model_id == "THM-15" and "temperature_margin_K" in data:
        margin = data["temperature_margin_K"]
        direction = "above" if margin >= 0 else "below"
        return (f"THM-15 puts the flame {abs(margin):.3g} K {direction} the temperature threshold. "
                f"The combined screen returned '{data['inception_screen'].replace('_', ' ')}'.")
    if model_id == "THM-16" and "criterion_reached" in data:
        if data["criterion_reached"]:
            return (f"THM-16 predicts that the slab surface reaches "
                    f"{data['ignition_criterion_K']:g} K at {data['time_to_ignition_s']:.3g} s.")
        return (f"The surface stayed below the {data['ignition_criterion_K']:g} K criterion "
                f"during the {data['requested_exposure_s']:g} s exposure.")
    if model_id == "THM-20" and data.get("equivalent_diameter_at_mean_arrival_m") is not None:
        diameter = 1e6 * data["equivalent_diameter_at_mean_arrival_m"]
        initial_diameter = 1e6 * data["parcel_equivalent_diameter_m"][0]
        number_ratio = data["number_concentration_at_mean_arrival_m3"] / data["parcel_number_concentration_m3"][0]
        return (f"THM-20 estimates a mean travel time of {data['mean_advective_travel_time_s']:.3g} s. "
                f"At mean arrival, equivalent particle diameter changes from {initial_diameter:.3g} to "
                f"{diameter:.3g} µm and number concentration is {number_ratio:.1%} of its initial value.")
    return ""


def scenario_charts(model_id, data, evidence_type, illustrative):
    """Select readable series from models that return engineering histories."""
    charts = []

    def line(title, record, x, xlabel, xunit, *columns, markers=()):
        values = record.get(x, [])
        if len(values) < 2:
            return
        series = []
        for key, label, unit, *factor in columns:
            y = record.get(key, [])
            if len(y) == len(values) and all(type(v) in (int, float) and isfinite(v) for v in y):
                scale = factor[0] if factor else 1
                series.append({"label": label, "unit": unit, "values": [scale * v for v in y]})
        if series:
            chart = {"type": "chart", "chart_type": "line", "title": f"{model_id} {title}",
                     "x": {"label": xlabel, "unit": xunit, "values": values}, "series": series,
                     "evidence_type": evidence_type, "illustrative": illustrative}
            if markers:
                chart["markers"] = [{"label": name, "value": value} for name, value in markers if value is not None]
            charts.append(chart)

    plot, sweep = data.get("plot_data", {}), data.get("sweep", {})
    if model_id == "THM-06":
        line("flame-front position", data, "time_s", "Elapsed time", "s",
             ("pyrolysis_front_position_m", "Pyrolysis front", "cm", 100))
    elif model_id == "THM-10":
        line("droplet diameter", plot, "time_s", "Time since ignition", "s",
             ("diameter_mm", "Droplet diameter", "mm"))
    elif model_id == "THM-11":
        line("hot and cool flame stages", data, "time_s", "Time since ignition", "s",
             ("diameter_mm", "Droplet diameter", "mm"),
             markers=(("Hot flame goes out", data.get("hot_extinction_time_s")),))
    elif model_id == "THM-13":
        line("radiative heat balance", plot, "air_speed_m_s", "Airflow speed", "m/s",
             ("chemical_input_w_m2", "Chemical heat input", "W/m²"),
             ("heat_loss_w_m2", "Total heat loss", "W/m²"),
             markers=(("Quenching threshold", data.get("critical_speed_m_s")),))
    elif model_id == "THM-14":
        line("radiative fraction over time", plot, "time_s", "Elapsed time", "s",
             ("radiative_fraction", "Radiative fraction", "%", 100))
    elif model_id == "THM-16":
        line("slab temperature during exposure", data, "time_s", "Elapsed time", "s",
             ("surface_temperature_K", "Surface temperature", "K"),
             ("back_temperature_K", "Back temperature", "K"),
             markers=(("Surface reaches ignition criterion", data.get("time_to_ignition_s")),))
    elif model_id == "THM-17":
        line("limiting oxygen versus airflow", sweep, "air_speed_m_s", "Airflow speed", "m/s",
             ("limiting_oxygen_pct", "Limiting oxygen", "%"),
             markers=(("Requested airflow", data.get("air_speed_m_s")),))
    elif model_id == "THM-18":
        line("water-mist heat budget", sweep, "evaporated_fraction", "Evaporated portion", "fraction",
             ("total_water_heat_sink_kJ", "Total heat absorbed", "kJ"))
    elif model_id == "THM-19":
        line("sealed-cabin temperature", data, "time_s", "Elapsed time", "s",
             ("temperature_K", "Cabin temperature", "K"))
        line("sealed-cabin pressure", data, "time_s", "Elapsed time", "s", ("pressure_kPa", "Cabin pressure", "kPa"))
    elif model_id == "THM-20":
        marker = (("Mean arrival", data.get("mean_advective_travel_time_s")),)
        line("smoke particle diameter", data, "time_s", "Time since entering duct", "s",
             ("parcel_equivalent_diameter_m", "Equivalent particle diameter", "µm", 1e6), markers=marker)
        line("smoke number concentration", data, "time_s", "Time since entering duct", "s",
             ("parcel_number_concentration_m3", "Number concentration", "particles/m³"), markers=marker)
    return charts
