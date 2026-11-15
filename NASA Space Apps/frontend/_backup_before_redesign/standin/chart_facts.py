"""What each chart on the site actually shows, for the AI: the chart's own description (same text as js/model_widgets*.js)
plus its headline numbers, read from data/model_outputs.js so the words always match what the chart draws.
Charts marked illustrative/synthetic show shapes only: the AI is told not to quote their numbers."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHAPES_ONLY = {"synthetic", "illustrative"}

# type: (status, title, description)
DESC = {
    'thm02_lewis_gauge': ('physics', 'Lewis number gauge',
        "Where each fuel's flame sits between unstable (Le < 0.9), neutral and quench-prone (Le > 1.1). Fuel at 2% in air, 300 K, 1 atm."),
    'thm02_gas_mixer': ('physics', 'Gas mixer',
        "Pick a fuel, diluent and cabin pressure, then slide the oxygen level. Every number is from THM-02's kinetic-theory calculation (pre-computed grid, 300 K, 2% fuel)."),
    'thm02_atmospheres': ('physics', 'How gases move in each atmosphere',
        'Heat and oxygen diffuse faster at low pressure: about 1.4× faster in a lunar habitat and 3.5× in a spacesuit than on the ISS. Their ratio (Lewis number ≈ 1.02) barely changes.'),
    'thm02_diluents': ('physics', 'Nitrogen vs CO₂ vs helium',
        "Swapping nitrogen for helium makes the gas ~4× better at conducting heat and roughly doubles n-heptane's Lewis number — one reason helium behaves differently as a suppressant (FLEX)."),
    'thm11_droplet': ('reconstruction', 'Droplet burning: hot → cool flame',
        "An n-decane droplet shrinks steadily while the visible flame burns, then keeps burning as an almost invisible cool flame. R377 reconstructs a real FLEX test; R379 is a model estimate checked against NASA's observation."),
    'thm11_held_out': ('estimate', 'Model vs NASA observation',
        "Honest check: for run R379 the model's cool-flame end comes about 11 s after the ≈13 s NASA observed. Shows where the model needs more evidence."),
    'thm11_facts': ('reconstruction', 'Droplet key facts (R377)',
        'Headline numbers for FLEX run R377 from THM-11.'),
    'thm16_heating': ('synthetic', 'Heating to ignition',
        "How fast a solid's surface heats under a radiant heater, and when it reaches the ignition temperature. Slide the heat flux. Material is the thermo team's synthetic 4 mm demo slab."),
    'thm16_heatmap': ('synthetic', 'Heat soaking into the material',
        "Temperature through the slab's thickness over time (darker = hotter) until the surface ignites, at 35 kW/m²."),
    'thm16_ignition_vs_flux': ('synthetic', 'Ignition time vs heat flux',
        "Stronger heating ignites the material sooner; at 25 kW/m² and below it doesn't ignite within 90 s."),
    'thm16_fact': ('synthetic', 'Time to ignition',
        'Headline number from THM-16 for the synthetic slab at 35 kW/m².'),
    'thm04_hrr': ('reduction', 'Fire power from oxygen use',
        "How strong a fire is can be worked out from how much oxygen it uses up (about 13 MJ per kg of O₂). This example reduces 10 s of a NIST natural-gas burner test, a ground test rather than microgravity; its total comes within about 2% of the burner's own meter. NASA's Saffire VI used the same method in orbit."),
    'thm05_spread': ('estimate', 'Flame creeping against airflow',
        'How fast a flame crawls along a PMMA sheet against a gentle 3 cm/s airflow. Thinner sheets burn faster; the model line passes through the BASS-II measurements NASA took in microgravity (hollow circles) at 0.2 and 0.3 mm.'),
    'thm06_rate': ('illustrative', 'Flame spread speeds up as it grows',
        'Flame spreading WITH the airflow over a thin fabric card (Saffire II). The burning zone lengthens and the spread rate climbs toward a limiting value of about 2.4 mm/s. The limiting rate is anchored to NASA runs; the growth curve starts from illustrative values.'),
    'thm06_front': ('illustrative', 'Where the flame front is',
        'Positions of the burning front and the flame tip along the 29 cm fabric card over about 90 s, with airflow in the same direction. The model stops when the heated zone reaches the end of the sample.'),
    'thm15_soot': ('screening', 'Soot inception screen',
        "A quick screen for whether a flame region is hot enough for soot to begin forming, here for an ethylene flame in a drop-tower. The threshold (1190 K at C/O 0.6) is published; the 50 K 'near' band and the flame conditions are illustrative. It says nothing about how much soot is made or how the flame looks."),
    'thm17_limiting_oxygen': ('estimate', 'Oxygen a flame needs vs airflow',
        'The lowest oxygen level at which a flame keeps spreading over a PMMA rod in microgravity, against airflow speed. Very slow flow starves the flame (quench) and fast flow blows it off, so the easiest speed for a flame sits in between. This is the pooled BASS-II fit, with substantial scatter near the limit.'),
    'thm18_dilution': ('budget', 'Adding CO₂ to air',
        'How adding carbon dioxide to air changes the oxygen left and the heat the gas can soak up when warmed from 300 to 400 K. This is a thermal budget only; it does not predict whether a flame goes out. Inputs are illustrative.'),
    'thm18_mist': ('budget', 'Water mist heat sink',
        'Heat taken up by 0.2 kg of water mist warmed from 20 to 100 °C with half of it evaporating. Most of the heat goes into evaporation. A thermal budget only; droplet delivery and evaporation rate are not modelled.'),
    'thm19_cabin': ('illustrative', 'Cabin pressure after a fire',
        'A sealed 16.7 m³ cabin at 54.6 kPa and 30% oxygen with a small fire (peaking at 2.4 kW) for 3 minutes: pressure and temperature rise, then ease as the walls absorb heat. The fire history is illustrative, inspired by Saffire VI.'),
    'thm20_smoke': ('illustrative', 'Smoke ageing in a duct',
        "Smoke particles drifting along a 3 m vent duct. Over the ≈40 s the smoke takes to reach the far end, particles clump together so the count falls by almost a third, while their size grows by less than 1%. Illustrative duct and smoke values, inspired by NASA's SAME experiments."),
    'thm01_flame_temp': ('physics', 'Flame temperature by atmosphere',
        "The hottest a flame can get (adiabatic flame temperature) for methane, hydrogen and propane burning with just enough oxygen in three atmospheres: ISS cabin air (21% O₂, 14.7 psi), the lunar habitat (30%, 10.2 psi) and a spacesuit (100% O₂, 4.3 psi). More oxygen means a hotter flame, and the calculation includes molecules splitting apart at high temperature, which takes about 100 K off methane's answer in air. It is a thermodynamic ceiling: real flames lose heat, so they run cooler."),
    'thm03_zst': ('physics', 'Where a space flame sits',
        'In microgravity a methane flame forms a sphere around a small burner (3.2 mm radius). The mixture fraction Z_st says how much of the gas at the flame came from the fuel; the flame sits where fuel and oxygen are in exactly the right proportion. Supplying more oxygen raises Z_st and pulls the flame much closer to the burner. The model classes Z_st below 0.12 as soot-prone (yellow, glowing) and above that as dim blue and soot-free, which for methane happens above roughly 55% oxygen. Idealised infinitely fast chemistry.'),
    'thm07_blowoff': ('physics', 'Airflow that blows a flame off',
        "The Damköhler number compares how long gas takes to flow past the flame's edge with how long the chemistry needs. Above 1 the flame holds on; below 1 the airflow wins and the flame blows off. The curves show the number falling as ventilation speeds up, for ISS air and for the 30% oxygen lunar habitat, where the flame survives faster airflow. Uses a single-step reaction with generic constants, so read it as a trend, not a precise limit."),
    'thm08_richardson': ('bound', 'Buoyancy vs forced airflow',
        "The Richardson number compares buoyancy (hot gas rising) with forced ventilation. On the ISS buoyancy is almost zero, so airflow decides where heat and smoke go. On the Moon, Mars and Earth, buoyancy overtakes a 10 cm/s airflow around a 5 cm object and a rising plume forms. Moon and Mars values are theoretical scaling bounds: NASA's PSI archive has no partial-gravity combustion experiments."),
    'thm09_bnumber': ('physics', 'How oxygen drives burning (B-number)',
        'The Spalding B-number measures how strongly a flame pulls fuel off a solid surface. The ideal line ignores heat the hot surface radiates away; the solid line includes it, which matters in microgravity where airflow carries little heat. For PMMA at 15 cm/s, more oxygen raises both the B-number and the rate the plastic turns to gas. Right panel is that burn rate.')
}


# The correct reading of each chart, in one or two sentences. The AI is told never to contradict these.
MEANS = {
    "thm02_lewis_gauge": "Hydrogen flames (Le < 0.9) can break into cells or flame balls and keep burning below normal limits; heavy fuels such as n-heptane (Le > 1.1) tend to quench locally.",
    "thm02_gas_mixer": "An explorer for the reader to try fuels, diluents, pressures and oxygen levels; use it when the reader should experiment.",
    "thm02_atmospheres": "Lower cabin pressure speeds up the spreading of heat and oxygen by the same factor, so the Lewis number, and with it the flame's stability type, hardly changes between ISS, lunar habitat and spacesuit.",
    "thm02_diluents": "Helium carries heat away from a flame about four times faster than nitrogen and doubles n-heptane's Lewis number, so helium-diluted flames lose heat faster; CO2 differs from nitrogen much less.",
    "thm11_droplet": "A fuel droplet can keep burning as a nearly invisible cool flame after the visible flame goes out: a hidden hazard.",
    "thm11_held_out": "The droplet model is not yet reliable for run R379: it predicts the cool flame lasting about 11 s longer than NASA observed.",
    "thm11_facts": "A fuel droplet can keep burning as a nearly invisible cool flame after the visible flame goes out.",
    "thm16_heating": "Stronger radiant heating ignites a solid much sooner, and below a threshold heat flux it does not ignite at all (synthetic material).",
    "thm16_heatmap": "Heat soaks into a solid from the heated face until the surface reaches ignition (synthetic material).",
    "thm16_ignition_vs_flux": "Stronger radiant heating ignites a solid much sooner; weak heating may never ignite it (synthetic material).",
    "thm16_fact": "Time for a heated solid to ignite (synthetic material).",
    "thm04_hrr": "A fire's power can be measured from the oxygen it consumes; NASA's Saffire VI used the same method in orbit.",
    "thm05_spread": "Against a slow airflow in microgravity, thin sheets spread flame far faster than thick ones; the model matches NASA's BASS-II measurements.",
    "thm06_rate": "Spreading with the airflow, a flame speeds up as it grows until it reaches a limiting speed (Saffire II).",
    "thm06_front": "Spreading with the airflow, the burning zone lengthens and moves along the sample until it reaches the end.",
    "thm15_soot": "A screen for whether a flame region is hot enough to start forming soot; says nothing about how much.",
    "thm17_limiting_oxygen": "In microgravity there is a most dangerous airflow, around 1 cm/s, where a flame survives in the least oxygen; slower air starves the flame and faster air blows it off, so ventilation can help a fire or put it out.",
    "thm18_dilution": "Adding CO2 lowers the oxygen and soaks up heat; a heat budget only, it does not say whether the flame goes out.",
    "thm18_mist": "Most of water mist's cooling comes from evaporating the water, not from warming it.",
    "thm19_cabin": "In a sealed cabin even a small fire raises pressure and temperature, which then ease as the walls absorb heat.",
    "thm20_smoke": "Smoke changes on its way to a detector: particles clump, so there are fewer of them, while their size barely changes.",
    "thm01_flame_temp": "More oxygen makes a hotter flame: lunar-habitat air (30% O2) gives a flame roughly 280 K hotter than ISS air, and a pure-oxygen spacesuit roughly 700 K hotter. The lower pressure itself matters much less than the oxygen.",
    "thm03_zst": "Supplying more oxygen pulls a microgravity flame much closer to the burner and makes it smaller; above roughly 55% oxygen a methane flame becomes soot-free and blue.",
    "thm07_blowoff": "In lunar-habitat air (30% O2) a flame survives about 1.6 times stronger ventilation than in ISS air before blowing off, so airflow is a weaker extinguisher there. A trend with generic constants, not a precise limit.",
    "thm08_richardson": "On the ISS ventilation alone decides where heat and smoke go (no buoyancy). On the Moon (Richardson number about 11) and Mars, buoyancy still beats a 10 cm/s draught: flames rise and form plumes, behaving like weaker Earth flames rather than spherical ISS flames. Theoretical bound only.",
    "thm09_bnumber": "More oxygen makes a plastic (PMMA) surface gasify and burn much faster: about 3.5 times faster in 50% oxygen than in normal air.",
}


def _outputs():
    s = (ROOT / "data" / "model_outputs.js").read_text(encoding="utf-8")
    key = "window.DATA.modelOutputs = "
    return json.JSONDecoder().raw_decode(s[s.index(key) + len(key):])[0]


def _literature():
    """data/literature.js (built by standin/build_literature.py from the thermo team's thm_literature_map.py), or {}."""
    try:
        s = (ROOT / "data" / "literature.js").read_text(encoding="utf-8")
        key = "window.DATA.literature = "
        return json.JSONDecoder().raw_decode(s[s.index(key) + len(key):])[0]
    except Exception:
        return {}


def _numbers(o):
    """Headline numbers per chart, from the pre-computed model outputs. Missing data just means no numbers for that chart."""
    n = {}
    def put(t, f):
        try:
            n[t] = f()
        except Exception:
            pass
    g = lambda fuel, dil="N2", p="101.3", x=20: o["THM02"]["grid"][f"{fuel}|{dil}|{p}|{x}"]
    put("thm02_lewis_gauge", lambda: f"Lewis number: hydrogen {g('H2')['Le']:.2f} (unstable), methane {g('CH4')['Le']:.2f} (near neutral), n-heptane {g('C7H16')['Le']:.2f} (quench-prone).")
    put("thm02_diluents", lambda: "For n-heptane in 20% O2: Lewis number " + ", ".join(f"{name} {g('C7H16', d)['Le']:.2f}" for d, name in (("N2", "nitrogen"), ("CO2", "CO2"), ("HE", "helium"))) +
        "; thermal conductivity " + ", ".join(f"{name} {g('C7H16', d)['k']:.3f} W/m/K" for d, name in (("N2", "nitrogen"), ("CO2", "CO2"), ("HE", "helium"))) + ".")
    r = lambda: o["THM11"]["runs"]["R377"]
    put("thm11_droplet", lambda: f"R377 (n-decane, {r()['d0_mm']:.2f} mm, {r()['o2_pct']}% O2, 0.5 atm): hot flame goes out at {r()['hot_extinction_time_s']:.1f} s, cool flame continues to {r()['cool_extinction_time_s']:.1f} s.")
    n["thm11_facts"] = n.get("thm11_droplet", "")
    put("thm11_held_out", lambda: (lambda h, R: f"R379: model cool-flame end {R['cool_extinction_time_s']:.1f} s vs NASA observed about {h['observed_cool_extinction_time_s']} s ({h['model_minus_observed_s']:.0f} s late).")(o["THM11"]["runs"]["R379"]["held_out_check"], o["THM11"]["runs"]["R379"]))
    put("thm04_hrr", lambda: f"Peak heat release {o['THM04']['peak_kW']:.0f} kW; {o['THM04']['total_kJ'] / 1000:.2f} MJ released over the 10 s window.")
    put("thm05_spread", lambda: f"0.2 mm sheet at 3 cm/s, {o['THM05']['oxygen_pct']}% O2: {o['THM05']['thin_mm_s']:.2f} mm/s; a thick sample would spread at {o['THM05']['thick_mm_s']:.3f} mm/s; thin-to-thick change at about {o['THM05']['transition_mm']:.1f} mm.")
    put("thm17_limiting_oxygen", lambda: (lambda T: (lambda i: f"Lowest oxygen that still burns: about {max(T['quench_pct'][i], T['blowoff_pct'][i]):.1f}% at {T['speed_cm_s_sweep'][i]:.1f} cm/s airflow; it rises to {T['quench_pct'][0]:.1f}% at {T['speed_cm_s_sweep'][0]:.1f} cm/s (starved) and {T['blowoff_pct'][-1]:.1f}% at {T['speed_cm_s_sweep'][-1]:.0f} cm/s (blow-off).")(
        min(range(len(T['speed_cm_s_sweep'])), key=lambda i: max(T['quench_pct'][i], T['blowoff_pct'][i]))))(o["THM17"]))
    put("thm18_dilution", lambda: f"Adding 30% CO2 leaves {o['THM18']['at_30']['o2_pct']:.1f}% O2.")
    put("thm18_mist", lambda: (lambda m: f"Heating the water {m['sensible_heat_kJ']:.0f} kJ, evaporating half {m['latent_heat_kJ']:.0f} kJ, total {m['total_water_heat_sink_kJ']:.0f} kJ.")(o["THM18"]["mist"]))
    put("thm01_flame_temp", lambda: "Methane: " + ", ".join(f"{a['name']} {t:.0f} K" for a, t in zip(o["THM01"]["atmospheres"], o["THM01"]["fuels"]["methane"]["T_ad_K"])) +
        "; hydrogen: " + ", ".join(f"{t:.0f} K" for t in o["THM01"]["fuels"]["hydrogen"]["T_ad_K"]) + " (same order).")
    put("thm03_zst", lambda: (lambda T: f"Flame radius / burner radius: {T['radius_ratio'][0]:.0f} at {T['y_ox_pct'][0]:.0f}% O2 (by mass), {T['air_radius_ratio']:.0f} in air, {T['radius_ratio'][-1]:.1f} in pure oxygen.")(o["THM03"]))
    put("thm07_blowoff", lambda: (lambda c: f"Blow-off airflow: ISS air about {c['iss']['blowoff_cm_s']:.0f} cm/s, lunar habitat air about {c['lunar']['blowoff_cm_s']:.0f} cm/s.")(o["THM07"]["cases"]))
    put("thm08_richardson", lambda: "Richardson number: " + ", ".join(f"{e['name']} {e['Ri']:.3g}" for e in o["THM08"]["envs"]) + " (above 10 = buoyancy dominates, below 0.1 = forced airflow dominates).")
    put("thm09_bnumber", lambda: (lambda T: "PMMA burn rate: " + ", ".join(f"{x:.0f}% O2 {f:.2f} g/m2/s" for x, f in zip(T["o2_pct"], T["flux_g_m2_s"]) if x in (18, 21, 30, 50)) + ".")(o["THM09"]))
    return n


def facts(compact=False, linked=None):
    """{type: text for the prompt}. compact = no long description (for Groq's small free-plan budget).
    linked = {"THM-08": ["PSI-25", ...]}: the NASA investigations each model is built on."""
    try:
        nums = _numbers(_outputs())
    except Exception:
        nums = {}
    out = {}
    lit = {} if compact else _literature()
    for t, (status, title, desc) in DESC.items():
        shapes = status in SHAPES_ONLY
        parts = [title + (" [ILLUSTRATIVE: shapes only, never quote its numbers]" if shapes else "") + "."]
        if not compact:
            parts.append(desc)
        if MEANS.get(t):
            parts.append("Means: " + MEANS[t])
        if nums.get(t) and not shapes:
            parts.append("Shows: " + nums[t])
        L = lit.get("THM-" + t[3:5])
        if L:
            parts.append(f"Method: {L['method']} ({'; '.join(x['short'] for x in L['sources'][:3])}).")
        ids = (linked or {}).get("THM-" + t[3:5], [])
        if ids:
            parts.append("Built on: " + ", ".join(ids[:4]) + ".")
        out[t] = " ".join(parts)
    return out


if __name__ == "__main__":
    for k, v in facts().items():
        print(k, "|", v)
