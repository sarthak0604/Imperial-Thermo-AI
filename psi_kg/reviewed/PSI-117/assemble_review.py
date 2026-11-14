"""Assistant-authored source review for the downloaded PSI-117 snapshot.

This is an explicit, inspectable curated extraction, NOT an external API result.
The reusable pipeline is investigation-agnostic; this review artifact is not.
Quotes are resolved from saved sections and checked before any graph is exported.
"""

import sys
from pathlib import Path

from psi_graph.common import normalized, read_json, write_json
from psi_graph.graph import build
from psi_graph.reviewed import claim_digest, document_digest
from psi_graph.science import Synthesis

out = Path(sys.argv[1] if len(sys.argv) > 1 else "output/PSI-117")
docs = read_json(out / "documents.json")
resources = read_json(out / "resources_manifest.json")["resources"]
metadata = read_json(out / "metadata.json")


def find(fragment):
    matches = [d for d in docs if fragment in d["title"]]
    assert len(matches) == 1, (fragment, len(matches))
    return matches[0]


def ev(doc, locator, quote=None):
    s = next(s for s in doc["sections"] if s["locator"] == locator)
    text = normalized(s["text"])
    if quote:
        quote = normalized(quote)
        assert quote in text, (doc["title"], locator, quote)
    else:
        quote = text
    return {"document_id": doc["id"], "locator": locator, "text": quote}


def page(doc, number, quote=None):
    return ev(doc, f"page {number}", quote)


def concept(name, description, refs, synonyms=()):
    return dict(
        name=name, synonyms=list(synonyms), description=description, evidence=refs
    )


def variable(name, symbol, unit, refs):
    return dict(name=name, symbol=symbol, unit=unit, role="dependent", evidence=refs)


def association(doc, refs):
    return dict(resource_id=doc["id"], evidence=refs)


def doi_assoc(doi, refs):
    return [
        dict(resource_id=r["id"], evidence=refs)
        for r in resources
        if r.get("doi") == doi
    ]


def study(
    key,
    title,
    summary,
    keywords,
    conditions,
    methods,
    concepts,
    variables,
    associations,
    refs,
):
    return dict(
        key=key,
        title=title,
        summary=summary,
        keywords=keywords,
        conditions=[dict(name=k, value=v) for k, v in conditions.items()],
        methods=methods,
        findings=[],
        concepts=concepts,
        variables=variables,
        resources=associations,
        evidence=refs,
    )


index = find("ReadMe_List_of_Data.xlsx")
osc = find("Presentations_Oscillatory_Cool Flame")
extinction = find("Presentations_Extinction_Characteristics")
three = find("Presentations_Three_Stage_Cool")
seminar = find("Presentations_PSI_Users_Group")
thesis = find("Reports_Dissertation")
osc_csv = find("Data_PROCI_2019_Oscillatory_Cool_Flame.csv")
stable_csv = find("Data_PROCI_2019_Stable_Cool.csv")
size_csv = find("Data_PROCI_2023_Alkane_Extinction_Diameter_1atm.csv")
pressure_csv = find("Data_PROCI_2023_C12_Extinction_Diameter_vs_pressure.csv")
three_csv = find("Data_PROCI_C12_2019_Three_Stage.csv")
mst = [
    find("Data_MST_2024_" + name + ".csv")
    for name in [
        "Burning_history_Flame_diameter",
        "Dext",
        "Kavg",
        "Radiance_Flame_Diameter",
    ]
]
inv = next(d for d in docs if d["resource_type"] == "investigation_metadata")

osc_refs = [page(osc, 4), page(osc, 5), page(osc, 6), page(osc, 13), page(thesis, 197)]
osc_vars = [
    variable("Droplet diameter", "D", "mm", [ev(osc_csv, "table, row 1")]),
    variable("Burning rate", "K", "mm^2/s", [ev(osc_csv, "table, row 1")]),
    variable("Peak gas temperature", "T_max", "K", [ev(osc_csv, "table, row 1")]),
    variable(
        "Flame stand-off ratio",
        "D_Tmax/D_drop",
        "dimensionless",
        [ev(osc_csv, "table, row 1")],
    ),
    variable(
        "Normalized squared droplet diameter",
        "(D/Do)^2",
        "dimensionless",
        [ev(osc_csv, "table, row 1")],
    ),
]
studies = [
    study(
        "proci-2018-05-151",
        "Ozone-assisted stable and oscillatory n-heptane droplet cool flames",
        "One-dimensional numerical study of 0.5 mm n-heptane droplets at 1 atm and 298 K. With 5% ozone, the 21% oxygen case sustains a cool flame, while the 10% oxygen case develops increasing oscillations. The reported mechanism couples low-temperature chain branching and propagation/termination with fuel leakage through the flame. These are simulation outputs, not new physical test runs.",
        [
            "cool flame",
            "oscillation",
            "ozone",
            "n-heptane",
            "low-temperature chemistry",
            "negative temperature coefficient",
        ],
        {
            "fuel": "n-heptane",
            "initial_droplet_diameter": "0.5 mm",
            "pressure": "1 atm",
            "ambient_temperature": "298 K",
            "stable_case_oxygen": "21%",
            "oscillatory_case_oxygen": "10%",
            "ozone": "5%",
            "nitrogen": "balance",
            "study_kind": "numerical",
        },
        [
            "One-dimensional sphero-symmetric transient droplet combustion model",
            "Detailed/reduced chemical kinetics",
            "Multicomponent transport",
            "Statistical narrowband radiation",
        ],
        [
            concept(
                "Oscillatory cool flames",
                "Low-temperature droplet burning whose flame temperature and position oscillate as kinetic and transport processes interact.",
                [page(osc, 13)],
                ["cool flame oscillations", "pulsing"],
            ),
            concept(
                "Ozone-assisted cool flame ignition",
                "Ozone seeding permits direct initiation of cool-flame burning in small n-alkane droplets.",
                [page(osc, 5)],
                ["ozone seeding"],
            ),
            concept(
                "Low-temperature chain branching",
                "Competition of degenerate chain branching with propagation and termination participates in cool-flame dynamics.",
                [page(osc, 13)],
                ["degenerate chain branching"],
            ),
        ],
        osc_vars,
        [
            association(osc, [page(osc, 1)]),
            association(
                osc_csv, [ev(index, "sheet Sheet1, row 3"), ev(osc_csv, "table, row 1")]
            ),
            association(
                stable_csv,
                [ev(index, "sheet Sheet1, row 2"), ev(stable_csv, "table, row 1")],
            ),
            association(
                index,
                [ev(index, "sheet Sheet1, row 2"), ev(index, "sheet Sheet1, row 3")],
            ),
            association(thesis, [page(thesis, 194)]),
            association(seminar, [page(seminar, 24)]),
        ]
        + doi_assoc("10.1016/j.proci.2018.05.151", [ev(index, "sheet Sheet1, row 3")]),
        osc_refs,
    )
]

ext_refs = [
    page(extinction, 7),
    page(extinction, 9),
    page(extinction, 11),
    page(extinction, 16),
    ev(index, "sheet Sheet1, row 9"),
]
ext_vars = [
    variable(
        "Hot-flame extinction diameter",
        "Dext_HF",
        "mm",
        [page(extinction, 9), ev(size_csv, "table, row 1")],
    ),
    variable(
        "Cool-flame extinction diameter",
        "Dext_CF",
        "mm",
        [page(extinction, 9), ev(size_csv, "table, row 1")],
    ),
]
studies.append(
    study(
        "proci-2022-07-094-size",
        "Initial diameter and alkane chain-length effects on cool-flame extinction",
        "Transient droplet-combustion calculations for n-heptane, n-decane and n-dodecane are compared with experimental extinction data in atmospheric air. The source reports stronger cool-flame reactivity and smaller cool-flame extinction diameters for longer n-alkanes, while hot-flame extinction characteristics are similar.",
        ["extinction", "n-alkane", "chain length", "initial diameter", "cool flame"],
        {
            "fuels": "n-heptane, n-decane, n-dodecane",
            "pressure": "1 atm",
            "oxygen_mole_fraction": "0.21",
            "nitrogen_mole_fraction": "0.79",
            "initial_diameter_range": "2.0–7.0 mm (data-index range)",
            "study_kind": "numerical comparison with experimental data",
        },
        [
            "Transient coupled liquid/gas droplet-combustion model",
            "Detailed low/intermediate/high-temperature chemistry",
            "Multicomponent diffusion",
            "Statistical narrowband radiation",
        ],
        [
            concept(
                "Cool-flame extinction",
                "Termination of low-temperature droplet burning; compared across alkane chain length and initial droplet size.",
                [page(extinction, 11)],
                ["low-temperature flame extinction"],
            ),
            concept(
                "Alkane chain-length effects",
                "The carbon number of n-alkanes affects cool-flame reactivity and extinction behavior.",
                [page(extinction, 16)],
                ["carbon-number dependence"],
            ),
        ],
        ext_vars,
        [
            association(
                size_csv,
                [ev(index, "sheet Sheet1, row 9"), ev(size_csv, "table, row 1")],
            ),
            association(index, [ev(index, "sheet Sheet1, row 9")]),
            association(extinction, [page(extinction, 11)]),
        ]
        + doi_assoc("10.1016/j.proci.2022.07.094", [ev(index, "sheet Sheet1, row 9")]),
        ext_refs,
    )
)

studies.append(
    study(
        "proci-2022-07-094-pressure",
        "Pressure-dependent extinction and warm-flame transitions of n-dodecane droplets",
        "Numerical predictions and measured hot/cool extinction diameters are compared for n-dodecane droplets in air over varying pressure. The presentation reports nonlinear pressure dependence, hot–cool cycling near 1.25 atm and a stable warm-flame regime at 3 atm. The 4 mm extinction sweep is distinct from the 7 mm multicycle example.",
        [
            "pressure",
            "extinction",
            "warm flame",
            "n-dodecane",
            "hot-cool cycling",
            "NTC",
        ],
        {
            "fuel": "n-dodecane",
            "diameter_extinction_sweep": "4.00 mm",
            "pressure_data_range": "0.5–3.0 atm",
            "ambient": "air",
            "multicycle_example": "7.00 mm at 1.25 atm",
            "study_kind": "numerical comparison with experimental data",
        },
        [
            "Transient droplet-combustion simulations",
            "Pressure sweep",
            "Comparison of predicted and measured extinction diameters",
        ],
        [
            concept(
                "Pressure-dependent flame extinction",
                "Ambient pressure changes hot- and cool-flame extinction diameters and burning modes.",
                [page(extinction, 15)],
                ["extinction pressure dependence"],
            ),
            concept(
                "Warm-flame transition",
                "A moderate-temperature burning regime associated in these sources with negative-temperature-coefficient kinetics.",
                [page(extinction, 12)],
                ["warm flame"],
            ),
            concept(
                "Hot-cool flame cycling",
                "Repeated transitions between hot and cool burning modes at elevated pressure.",
                [page(extinction, 13)],
                ["multicycle combustion"],
            ),
        ],
        [
            variable(
                "Hot-flame extinction diameter",
                "Dext_HF",
                "mm",
                [page(extinction, 9), ev(pressure_csv, "table, row 1")],
            ),
            variable(
                "Cool-flame extinction diameter",
                "Dext_CF",
                "mm",
                [page(extinction, 9), ev(pressure_csv, "table, row 1")],
            ),
        ],
        [
            association(
                pressure_csv,
                [ev(index, "sheet Sheet1, row 10"), ev(pressure_csv, "table, row 1")],
            ),
            association(index, [ev(index, "sheet Sheet1, row 10")]),
            association(extinction, [page(extinction, 15)]),
        ]
        + doi_assoc("10.1016/j.proci.2022.07.094", [ev(index, "sheet Sheet1, row 10")]),
        [
            page(extinction, 12),
            page(extinction, 13),
            page(extinction, 15),
            ev(index, "sheet Sheet1, row 10"),
        ],
    )
)

studies.append(
    study(
        "proci-2018-09-015",
        "Three-stage hot, warm and cool droplet burning with helium dilution",
        "Numerical n-heptane studies with helium exchange at elevated pressure predict hot, warm and cool burning stages. The presentation compares those predictions qualitatively with n-dodecane FLEX-1268 observations at 2.75 atm. The associated CSV combines experimental histories and simulations. Rounded composition in the data index differs from the precise FLEX composition reported on the slide; these are preserved separately.",
        [
            "three-stage combustion",
            "helium",
            "warm flame",
            "FLEX 1268",
            "n-dodecane",
            "n-heptane",
        ],
        {
            "numerical_fuel": "n-heptane",
            "numerical_diameter": "4.00 mm",
            "numerical_pressure": "3 atm (5 atm additional case)",
            "numerical_oxygen": "21%, helium exchanged with nitrogen",
            "validation_run": "FLEX 1268",
            "validation_fuel": "n-dodecane",
            "validation_pressure": "2.75 atm",
            "validation_gas_slide": "21.6% O2, 50.2% N2, 28.2% He",
            "dataset_index_gas": "0.21 O2, 0.50 N2, 0.29 He",
            "dataset_index_diameter": "4.5 mm",
        },
        [
            "Transient droplet-combustion model",
            "Detailed chemical kinetics",
            "Coupled radiative and diffusive heat-loss analysis",
            "Comparison with FLEX observations",
        ],
        [
            concept(
                "Three-stage droplet combustion",
                "Successive hot, warm and cool droplet-burning stages documented in simulations and FLEX observations.",
                [page(three, 17)],
                ["hot warm cool burning"],
            ),
            concept(
                "Helium dilution",
                "Exchange of helium with nitrogen changes transport and the observed stages of droplet burning.",
                [page(three, 7), page(three, 17)],
                ["helium exchange"],
            ),
            concept(
                "Radiative and diffusive heat losses",
                "The relative contributions of radiative and diffusive losses change between droplet-burning stages.",
                [page(three, 10)],
            ),
        ],
        [
            variable("Flame diameter", "Dflame", "mm", [ev(three_csv, "table, row 1")]),
            variable("Radiative power", "Q", "W", [ev(three_csv, "table, row 1")]),
            variable(
                "Peak gas temperature", "T_max", "K", [ev(three_csv, "table, row 1")]
            ),
            variable(
                "Normalized squared droplet diameter",
                "(D/Do)^2",
                "dimensionless",
                [ev(three_csv, "table, row 1")],
            ),
        ],
        [
            association(
                three_csv,
                [ev(index, "sheet Sheet1, row 6"), ev(three_csv, "table, row 1")],
            ),
            association(index, [ev(index, "sheet Sheet1, row 6")]),
            association(three, [page(three, 15)]),
            association(seminar, [page(seminar, 21)]),
        ]
        + doi_assoc("10.1016/j.proci.2018.09.015", [ev(index, "sheet Sheet1, row 6")]),
        [
            page(three, 6),
            page(three, 7),
            page(three, 15),
            page(three, 17),
            page(three, 20),
            ev(index, "sheet Sheet1, row 6"),
        ],
    )
)

mst_refs = [ev(index, f"sheet Sheet1, row {n}") for n in [13, 14, 15, 16]]
studies.append(
    study(
        "mst-2024-10115-x",
        "Pressure-dependent burning histories, radiative power and flame diameter of n-dodecane",
        "The deposited MST-2024 datasets provide experimental and model burning histories, cool-flame average burning rates, extinction diameters, radiative power and flame diameters for n-dodecane droplets over pressure. The data index maps the four files to figures 1, 5, 4 and 11 of DOI 10.1007/s12217-024-10115-x. No additional causal conclusion is inferred from aggregate column statistics.",
        [
            "n-dodecane",
            "pressure",
            "radiative power",
            "flame diameter",
            "burning rate",
            "extinction diameter",
        ],
        {
            "fuel": "n-dodecane",
            "oxygen_mole_fraction": "0.21",
            "nitrogen_mole_fraction": "0.79",
            "burning_history": "4 mm, 1 atm",
            "extinction_series": "4 mm, 0.5–1.5 atm",
            "burning_rate_series": "4.5 mm, 0.5–5.0 atm",
            "radiance_comparison": "approximately 4.5 mm, 0.5 and 5.0 atm",
        },
        [
            "Experimental/model data comparison",
            "Time-resolved droplet and flame histories",
            "Pressure-dependent data inspection",
        ],
        [
            concept(
                "Droplet burning history",
                "Time evolution of droplet size, flame size and radiative output recorded in experimental/model datasets.",
                [ev(mst[0], "table, row 1"), ev(mst[0], "table, row 2")],
            ),
            concept(
                "Radiative power",
                "Radiative output recorded in watts in the deposited data, whose original header uses the term radiance.",
                [ev(mst[3], "table, row 1")],
                ["flame radiance"],
            ),
            concept(
                "Pressure-dependent burning rate",
                "Average cool-flame burning rates compared over ambient pressure.",
                [ev(mst[2], "table, row 1"), mst_refs[2]],
            ),
        ],
        [
            variable(
                "Squared droplet diameter", "d^2", "mm^2", [ev(mst[0], "table, row 1")]
            ),
            variable("Flame diameter", "Dflame", "mm", [ev(mst[3], "table, row 1")]),
            variable("Radiative power", "Q", "W", [ev(mst[3], "table, row 1")]),
            variable(
                "Average burning rate", "Kavg", "mm^2/s", [ev(mst[2], "table, row 1")]
            ),
            variable(
                "Peak gas temperature", "T_max", "K", [ev(mst[3], "table, row 1")]
            ),
            variable(
                "Cool-flame extinction diameter",
                "Dext_CF",
                None,
                [ev(mst[1], "table, row 1")],
            ),
        ],
        [association(d, [r, ev(d, "table, row 1")]) for d, r in zip(mst, mst_refs)]
        + [association(index, mst_refs)]
        + doi_assoc("10.1007/s12217-024-10115-x", mst_refs),
        mst_refs + [ev(mst[0], "table, row 2"), ev(mst[3], "table, row 1")],
    )
)

studies.append(
    study(
        "dissertation-ch3-xenon",
        "Methanol droplet combustion and xenon fire-suppression assessment",
        "The supplied dissertation reports one-dimensional numerical methanol-droplet studies, comparisons with ISS data and comparisons among xenon, argon, carbon dioxide, helium and nitrogen diluents. The source concludes that xenon is ineffective for improved reduced-gravity fire safety because of its long burn times, higher peak temperature and low limiting oxygen index relative to the alternatives. This is a supporting dissertation study, not a newly identified PSI flight.",
        [
            "xenon",
            "methanol",
            "fire suppression",
            "limiting oxygen index",
            "thermal diffusivity",
            "microgravity",
        ],
        {
            "fuel": "methanol",
            "initial_droplet_diameters": "1.0, 1.5, 2.0 mm",
            "gravity": "microgravity model with ISS-data comparison",
            "diluents": "Xe, Ar, CO2, He, N2",
        },
        [
            "One-dimensional sphero-symmetric transient droplet-combustion model",
            "Detailed chemistry, multicomponent diffusion and radiative coupling",
            "Comparison against ISS experiments",
        ],
        [
            concept(
                "Xenon fire suppression",
                "Assessment of xenon as a diluent for suppressing reduced-gravity methanol droplet combustion.",
                [page(thesis, 60), page(thesis, 85)],
                ["xenon suppressant"],
            ),
            concept(
                "Limiting oxygen index",
                "Minimum oxygen conditions supporting droplet burning, compared between diluent gases in this study.",
                [page(thesis, 64), page(thesis, 85)],
                ["LOI"],
            ),
        ],
        [
            variable("Limiting oxygen index", "LOI", "%", [page(thesis, 85)]),
            variable("Peak gas temperature", "T_max", None, [page(thesis, 64)]),
            variable(
                "Normalized extinction diameter",
                "Dext/Do",
                "dimensionless",
                [page(thesis, 64)],
            ),
        ],
        [association(thesis, [page(thesis, 60)])],
        [page(thesis, 60), page(thesis, 64), page(thesis, 85)],
    )
)

studies.append(
    study(
        "dissertation-ch4-n-butanol",
        "Reduced-gravity n-butanol droplet experiments and numerical comparison",
        "Cornell drop-tower experiments track n-butanol droplets with initial diameters 0.56–0.57 mm in standard atmosphere under reduced gravity. Video-derived diameter, flame stand-off ratio and burning-rate measurements are compared with transient combustion simulations. The dissertation reports complete burning without flame extinction under the experimental conditions. Model species/reaction counts differ between abstract and methods, so no count is selected here.",
        [
            "n-butanol",
            "drop tower",
            "reduced gravity",
            "droplet combustion",
            "flame stand-off ratio",
        ],
        {
            "fuel": "n-butanol",
            "initial_droplet_diameter": "0.56–0.57 mm",
            "ambient": "standard atmosphere",
            "gravity": "reduced gravity",
            "facility": "Cornell University drop tower",
        },
        [
            "Drop-tower free fall",
            "Spark ignition",
            "Video image analysis",
            "Sphero-symmetric transient combustion simulations with detailed/reduced kinetics",
        ],
        [
            concept(
                "Reduced-gravity droplet combustion",
                "Reduced-gravity experiments promote nearly spherical droplet burning for comparison with one-dimensional models.",
                [page(thesis, 95), page(thesis, 98)],
                ["drop-tower combustion"],
            ),
            concept(
                "Butanol combustion",
                "Experimental and numerical burning behavior of isolated butanol droplets.",
                [page(thesis, 95)],
                ["n-butanol droplet burning"],
            ),
        ],
        [
            variable("Droplet diameter", "D", "mm", [page(thesis, 95)]),
            variable(
                "Flame stand-off ratio", "Df/D", "dimensionless", [page(thesis, 95)]
            ),
            variable("Burning rate", "K", None, [page(thesis, 95)]),
        ],
        [association(thesis, [page(thesis, 95)])],
        [page(thesis, 95), page(thesis, 98), page(thesis, 100), page(thesis, 113)],
    )
)

studies.append(
    study(
        "dissertation-ch5-butanol-isomers",
        "Butanol-isomer droplet combustion and transport-model sensitivity",
        "Reduced-gravity experiments compare n-, iso-, sec- and tert-butanol droplets with detailed-model predictions. The dissertation reports that transport-property differences explain important deviations in the Sarathy/LLNL model and recommends reexamining isomer-specific transport parameters. Predictions from the Merchant/MIT model generally agree better with the measurements, while tert-butanol remains more discrepant.",
        [
            "butanol isomers",
            "transport properties",
            "chemical kinetics",
            "model validation",
            "Lennard-Jones",
        ],
        {
            "fuels": "n-, iso-, sec-, tert-butanol",
            "initial_droplet_diameter": "0.52–0.56 mm",
            "ambient": "standard atmosphere",
            "gravity": "reduced gravity; approximately 10^-4 g",
            "support": "approximately 14 µm SiC filaments",
        },
        [
            "Free-fall droplet experiments",
            "Detailed numerical model",
            "Separate perturbation analyses of kinetics, thermodynamics and transport properties",
        ],
        [
            concept(
                "Butanol-isomer effects",
                "Butanol isomer structure affects droplet burning and flame structure.",
                [page(thesis, 121), page(thesis, 145)],
                ["butanol isomers"],
            ),
            concept(
                "Transport-property sensitivity",
                "Sensitivity of droplet combustion predictions to isomer-specific transport parameters.",
                [page(thesis, 145)],
                ["transport parameters"],
            ),
        ],
        [
            variable("Squared droplet diameter", "D^2", None, [page(thesis, 145)]),
            variable(
                "Flame stand-off ratio",
                "FSR",
                "dimensionless",
                [page(thesis, 121), page(thesis, 95)],
            ),
            variable("Burning rate", "K", None, [page(thesis, 145)]),
        ],
        [association(thesis, [page(thesis, 121), page(thesis, 145)])],
        [page(thesis, 121), page(thesis, 126), page(thesis, 145)],
    )
)

studies.append(
    study(
        "dissertation-ch6-ozone-initiation",
        "Direct ozone-assisted cool-flame initiation of small n-alkane droplets",
        "The dissertation computationally studies direct cool-flame initiation of n-heptane and n-decane droplets at atmospheric and higher pressure. Fuel volatility, ozone loading, initial size and ignition energy affect cool/hot flame outcomes. The conclusion reports 1 and 25 atm; an earlier methods passage mentions 30 atm, so that inconsistency is retained as a caveat rather than reconciled without evidence.",
        [
            "ozone",
            "direct ignition",
            "n-heptane",
            "n-decane",
            "fuel volatility",
            "cool flame",
        ],
        {
            "fuels": "n-heptane, n-decane",
            "initial_diameters": "0.1 and 0.5 mm",
            "pressures_conclusion": "1 and 25 atm",
            "source_discrepancy": "methods page 138 mentions 30 atm; conclusion page 163 specifies 25 atm",
            "ozone": "varied",
        },
        [
            "One-dimensional sphero-symmetric transient droplet-combustion model",
            "Reduced chemical kinetic mechanisms with ozone reaction subset",
            "Parametric simulation",
        ],
        [
            concept(
                "Ozone-assisted cool flame ignition",
                "Ozone seeding permits direct initiation of cool-flame burning in small n-alkane droplets.",
                [page(thesis, 155), page(thesis, 185)],
                ["ozone seeding"],
            ),
            concept(
                "Fuel-volatility effects",
                "Fuel flash point and vapor pressure affect initiation and transition of cool-flame droplet burning.",
                [page(thesis, 155), page(thesis, 185)],
                ["flash-point dependence"],
            ),
        ],
        [
            variable("Gas-phase temperature", None, None, [page(thesis, 184)]),
            variable(
                "Hydrogen peroxide mole fraction",
                "X_H2O2",
                "dimensionless",
                [page(thesis, 184)],
            ),
            variable(
                "Hydroxyl radical mole fraction",
                "X_OH",
                "dimensionless",
                [page(thesis, 184)],
            ),
        ],
        [
            association(thesis, [page(thesis, 155)]),
            association(seminar, [page(seminar, 23)]),
        ],
        [page(thesis, 155), page(thesis, 159), page(thesis, 184), page(thesis, 185)],
    )
)

studies.append(
    study(
        "seminar-2026-dme-counterflow",
        "Buoyancy and multidimensional transport in DME counterflow cool flames",
        "The PSI seminar compares one- and two-dimensional DME counterflow cool-flame predictions with and without buoyancy. It reports upward flame displacement with buoyancy and differences in temperature, heat-release rate and velocity fields. The analysis is documented in the supplied seminar; no separate raw dataset is inferred.",
        ["DME", "counterflow", "buoyancy", "multidimensional transport", "strain rate"],
        {
            "fuel": "DME",
            "fuel_mole_fraction": "0.587",
            "fuel_velocity": "62.3 cm/s",
            "oxidizer_velocity": "50.9 cm/s",
            "global_strain_rate": "approximately 90 s^-1",
            "pressure": "1 atm",
        },
        [
            "Comparison of one- and two-dimensional models",
            "Simulations with and without buoyancy",
            "Flow-field and heat-release analysis",
        ],
        [
            concept(
                "Buoyancy in counterflow cool flames",
                "Buoyancy and multidimensional flow change the location and structure of DME counterflow cool flames.",
                [page(seminar, 28)],
                ["DME counterflow", "buoyancy effects"],
            ),
            concept(
                "Strain-rate effects",
                "Global strain rate changes the relative importance of convection and buoyancy and the flame location.",
                [page(seminar, 30)],
                ["global strain rate"],
            ),
        ],
        [
            variable("Flame temperature", None, None, [page(seminar, 28)]),
            variable("Heat release rate", "HRR", None, [page(seminar, 28)]),
            variable("Axial velocity", None, None, [page(seminar, 29)]),
        ],
        [association(seminar, [page(seminar, 28), page(seminar, 29)])],
        [page(seminar, 28), page(seminar, 29), page(seminar, 30)],
    )
)

# Additional associated papers were actually accessed at their publisher pages.
jet = next(d for d in docs if d["id"] == "res:PSI-117:2d5158c29653f497a717")
mixture = next(d for d in docs if d["id"] == "res:PSI-117:22d91bbfcbf81affa77e")
jet_ref = ev(jet, "HTML body")
mix_ref = ev(mixture, "HTML body")
studies.append(
    study(
        "proci-2020-06-200",
        "Preferential vaporization in multicomponent Jet-A surrogate droplets",
        "The accessed paper abstract describes numerical studies of three multicomponent Jet-A surrogates with different distillation properties. A one-dimensional transient model uses reduced kinetics, multicomponent diffusion and UNIFAC liquid activity coefficients. Comparisons with published 550 µm drop-tower data support mixture-1 predictions; the authors report nonlinear dependence of preferential vaporization on droplet size and pressure. This extraction is grounded in the accessible abstract, not an assertion of full-text access.",
        [
            "preferential vaporization",
            "Jet-A",
            "surrogate fuel",
            "UNIFAC",
            "batch distillation",
        ],
        {
            "mixture_1_molar_ratio": "n-decane/iso-octane/toluene 42.7/33.0/24.3",
            "mixture_2_molar_ratio": "n-dodecane/iso-octane/1,3,5-trimethylbenzene 49.0/21.0/30.0",
            "mixture_3_molar_ratio": "n-hexadecane/iso-octane/1,3,5-trimethylbenzene 36.5/31.0/32.5",
            "validation_diameter": "550 µm",
            "validation_ambient": "air",
            "study_kind": "numerical, compared with published drop-tower data",
        },
        [
            "Transient one-dimensional sphero-symmetric model",
            "Reduced detailed kinetics",
            "Multicomponent gas diffusion",
            "UNIFAC liquid activity coefficients",
            "Stagnant versus internally mixed liquid models",
        ],
        [
            concept(
                "Preferential vaporization",
                "Different components of a multicomponent droplet vaporize differently, affecting physical and chemical burning behavior.",
                [jet_ref],
                [],
            ),
            concept(
                "Jet-fuel surrogate combustion",
                "Combustion modeling of multicomponent mixtures representing Jet-A fuel.",
                [jet_ref],
                ["Jet-A surrogate"],
            ),
        ],
        [
            variable("Droplet diameter", "D", None, [jet_ref]),
            variable(
                "Flame stand-off ratio",
                "FSR",
                "dimensionless",
                [jet_ref, page(thesis, 95)],
            ),
        ],
        doi_assoc("10.1016/j.proci.2020.06.200", [jet_ref]),
        [jet_ref],
    )
)
studies.append(
    study(
        "combustflame-2020-06-012",
        "Initial-size effects in free-floating n-heptane/iso-octane droplets on the ISS",
        "The accessed abstract reports ISS experiments and numerical simulations of equi-volume n-heptane/iso-octane droplets with initial diameters from 0.8 mm to below 5 mm. Smaller droplets remain in the hot-flame regime; larger droplets can undergo radiative extinction and cool-flame transition. Measured flame radiance supports radiation as a controlling mechanism. No preferential vaporization was observed for the close-boiling component pair.",
        [
            "n-heptane",
            "iso-octane",
            "ISS",
            "radiative extinction",
            "initial diameter",
            "cool flame",
        ],
        {
            "fuel": "equi-volume n-heptane/iso-octane",
            "initial_diameter_range": "0.8 mm <= Do < 5 mm",
            "gravity": "low gravity on ISS",
            "deployment": "unsupported/free-floating droplets",
            "hot_flame_only_range": "Do < 3 mm",
        },
        [
            "ISS sealed-chamber droplet experiments",
            "Spherically symmetric transient simulation",
            "Multistep and low-temperature chemical kinetics",
            "Non-luminous radiation and liquid species diffusion",
        ],
        [
            concept(
                "Radiative extinction",
                "Radiative heat loss can extinguish hot droplet flames and lead to cool-flame burning.",
                [mix_ref],
                ["radiation-driven extinction"],
            ),
            concept(
                "Initial droplet-size effects",
                "Initial diameter affects whether a mixed-fuel droplet remains in hot burning or transitions to cool-flame behavior.",
                [mix_ref],
                ["initial diameter dependence"],
            ),
        ],
        [
            variable("Droplet diameter", "D", "mm", [mix_ref]),
            variable("Radiative extinction diameter", None, "mm", [mix_ref]),
            variable("Flame radiance", None, None, [mix_ref]),
            variable("Burning rate", "K", None, [mix_ref]),
        ],
        doi_assoc("10.1016/j.combustflame.2020.06.012", [mix_ref]),
        [mix_ref],
    )
)

# Upgrade the 2024 dataset study with evidence from its accessed full article.
mst_paper = next(
    d for d in docs if d["source_url"] == "https://doi.org/10.1007/s12217-024-10115-x"
)
abstract_text = normalized(mst_paper["sections"][0]["text"])
start = abstract_text.index("This paper presents data from large, isolated")
end = abstract_text.index("Similar content", start)
mst_ref = ev(mst_paper, "HTML body", abstract_text[start:end])
for item in studies:
    if item["key"] == "mst-2024-10115-x":
        item["summary"] = (
            "ISS experiments on isolated n-dodecane droplets are compared with numerical and analytic predictions over 0.50–5.0 atm. The article reports that total radiative loss at hot-flame extinction is nearly pressure-independent, peak flame diameter decreases with pressure, and cool-flame extinction diameter increases while burning rate decreases as pressure falls. Warm-flame burning and reignitions become prevalent above 1.25 atm. Four deposited CSVs map to figures 1, 4, 5 and 11."
        )
        item["evidence"].append(mst_ref)
        item["methods"] += [
            "ISS microgravity droplet experiments",
            "Radiometer and imaging measurements",
            "Numerical/analytic comparison",
        ]
        item["conditions"].append(dict(name="gravity", value="microgravity aboard ISS"))
        item["concepts"].append(
            concept(
                "Radiative extinction",
                "Radiative heat loss can extinguish hot droplet flames and lead to cool-flame burning.",
                [mst_ref],
                ["radiation-driven extinction"],
            )
        )
        for assoc in item["resources"]:
            if any(
                r["id"] == assoc["resource_id"]
                and r.get("doi") == "10.1007/s12217-024-10115-x"
                for r in resources
            ):
                assoc["evidence"].append(mst_ref)

resource_science = []
for d in docs:
    if d["id"].startswith("metadata:"):
        continue
    linked = [
        s for s in studies if any(a["resource_id"] == d["id"] for a in s["resources"])
    ]
    refs = []
    for s in linked:
        for a in s["resources"]:
            if a["resource_id"] == d["id"]:
                refs.extend(e for e in a["evidence"] if e not in refs)
    if not linked:
        continue
    if d["title"].endswith(".csv"):
        profile = next(s for s in d["sections"] if "computed profile" in s["locator"])
        summary = (
            "Deposited numerical table for "
            + "; ".join(s["title"] for s in linked)
            + ". All rows were inspected; original data remain in the cached CSV."
        )
    elif d["resource_type"] == "citation":
        summary = (
            "Bibliographic citation associated with "
            + "; ".join(s["title"] for s in linked)
            + "; full text was not parsed."
        )
    else:
        summary = "Supporting source for " + "; ".join(s["title"] for s in linked) + "."
    resource_science.append(
        dict(
            resource_id=d["id"],
            summary=summary,
            keywords=sorted({k for s in linked for k in s["keywords"]}),
            variables=sorted(
                {
                    v["name"]
                    for s in linked
                    for v in s["variables"]
                    if any(e["document_id"] == d["id"] for e in v["evidence"])
                }
            ),
            evidence=refs,
        )
    )

synthesis = Synthesis(
    investigation_summary="Ground investigation of externally forced droplet cool-flame dynamics using numerical models and NASA FLEX data. The deposited resources cover low-temperature chemistry, ozone-assisted oscillations, extinction, multistage burning, pressure and radiative behavior, together with related supporting dissertation studies.",
    investigation_keywords=[
        "cool flame",
        "droplet combustion",
        "microgravity",
        "FLEX",
        "low-temperature chemistry",
        "CFD",
    ],
    investigation_evidence=[
        ev(inv, "metadata.objective"),
        ev(inv, "metadata.approach"),
    ],
    studies=studies,
    resources=resource_science,
    caveats=[
        "Curated assistant source review; no external LLM API calls were made.",
        "Experiment nodes represent documented analysis units, including simulations and supporting dissertation studies, not a claim that NASA exposes ten independent experiment records.",
        "Data-index nitrogen entries 74 and 85 are not fractions; graph conditions use corroborating presentation values and preserve the spreadsheet unchanged.",
        "FLEX-1268 slide composition differs from rounded data-index values; both are retained.",
        "Chapter 6 pressure and Chapter 4 kinetic-model-count inconsistencies were not silently reconciled.",
        "PDF figures and embedded media are not comprehensively digitized; targeted representative slide images were visually checked.",
    ],
)
write_json(Path(__file__).with_name("science.json"), synthesis.model_dump())
print(f"Wrote source-reviewed science for {len(studies)} studies; no API was used.")

# Bind these reviewed claims to the actual source snapshot. Replays cannot silently
# apply approvals to edited claims or newly downloaded/reparsed scientific content.

science = synthesis.model_dump()
graph, provenance, rejected = build(
    synthesis, resources, metadata, inv["source_url"], docs
)
assert not rejected, rejected
approvals = []
for claim in graph["nodes"] + graph["edges"]:
    content = (
        {k: claim["properties"].get(k) for k in ("summary", "keywords", "variables")}
        if claim.get("type") == "Resource"
        else claim
    )
    approvals.append(
        dict(
            id=claim["id"],
            claim_digest=claim_digest(content),
            supported=True,
            reason="Assistant source review of the explicitly authored extraction and cited source passages; not an independent external API or domain-expert review.",
        )
    )
write_json(
    Path(__file__).with_name("reviewed_bundle.json"),
    dict(
        source_url=inv["source_url"],
        document_digest=document_digest(docs),
        reviewer="Codex assistant source review",
        science=science,
        reviewed_claims=approvals,
    ),
)
