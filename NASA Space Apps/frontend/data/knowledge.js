// KNOWN FACTS gathered from: challenge Details/Resources pages [brief], NASA Glenn Combustion Science page [nasa-glenn],
// PSI landing/search data [psi], and the thermo team's spreadsheet [thermo]. Each entry names its source.
window.DATA = window.DATA || {};

// ---------- Hardware / facilities ----------
window.DATA.hardware = [
  { id: "cir", short: "CIR rack", name: "Combustion Integrated Rack (CIR)",
    desc: "Rack in the ISS US Laboratory (Destiny) with a 100-litre combustion chamber; the only ISS rack dedicated to combustion. Developed by NASA Glenn, launched November 2008 on STS-126.",
    investigations: [], hosts: ["mdca", "acme"], source: "nasa-glenn" },
  { id: "mdca", short: "MDCA droplet apparatus", name: "Multi-user Droplet Combustion Apparatus (MDCA)",
    desc: "Droplet-combustion facility inside the CIR. FLEX, FLEX-2 and the Cool Flames Investigation (CFI) all burned liquid fuel droplets with it.",
    investigations: ["PSI-69", "PSI-68", "PSI-39"], source: "brief, nasa-glenn" },
  { id: "acme", short: "ACME hardware (CIR)", name: "ACME modular hardware (in the CIR)",
    desc: "Shared modular hardware for the six ACME experiments, all flames of gaseous fuels.",
    investigations: ["PSI-20", "PSI-159", "PSI-10", "PSI-21", "PSI-22", "PSI-23"], source: "brief" },
  { id: "msg-duct", short: "MSG flow duct", name: "Microgravity Science Glovebox (MSG) flow duct",
    desc: "Modular fan-driven flow duct built for SPICE and used inside the MSG by BASS, BASS-II, SPICE and SLICE, covering solid and gaseous fuels. Thermo team reference: low-speed flow up to ~40 cm/s, opposed and concurrent flow.",
    investigations: ["PSI-26", "PSI-25", "PSI-107", "PSI-106"], source: "brief, thermo" },
  { id: "cygnus", short: "Cygnus vehicle", name: "Cygnus cargo vehicle (Saffire)",
    desc: "Saffire-I, -II and -III ran large-scale material burns inside an uncrewed Cygnus resupply vehicle after it left the ISS. Thermo team reference: sample cards up to 0.94 m × 0.4 m; thermocouples, radiometers, O₂/CO₂ and pressure telemetry. Configurations differ between Saffire-I, II and III.",
    investigations: ["PSI-98", "PSI-99", "PSI-100"], source: "psi, thermo" },
  { id: "smoke", short: "Smoke diagnostics", name: "ISS smoke & aerosol diagnostics",
    desc: "Smoke-particle measurement instruments for fire detection (SAME, SAME-R). One SAME instrument (the TSI P-Trak) was tested for dust in DAFT / DAFT-2.",
    investigations: ["PSI-102", "PSI-101", "PSI-47"], source: "brief, psi" }
];

// ---------- What the challenge brief says about specific investigations ----------
window.DATA.briefNotes = {
  "PSI-26":  ["Solid-material flammability (fabrics, plastics) — prevention.", "Run in the MSG flow duct built for SPICE."],
  "PSI-25":  ["Solid-material flammability (fabrics, plastics) — prevention.", "Run in the MSG flow duct built for SPICE."],
  "PSI-98":  ["Spacecraft Fire Safety Demonstration: solid-material flammability."],
  "PSI-99":  ["Spacecraft Fire Safety Demonstration: solid-material flammability."],
  "PSI-100": ["Spacecraft Fire Safety Demonstration: solid-material flammability."],
  "PSI-102": ["Tested fire detection in microgravity."],
  "PSI-101": ["Tested fire detection in microgravity."],
  "PSI-69":  ["Studied suppression by diluting the chamber atmosphere with carbon dioxide and helium.", "Burned liquid droplets in the MDCA."],
  "PSI-68":  ["Burned liquid droplets in the MDCA (shared with FLEX and CFI)."],
  "PSI-39":  ["Burned liquid droplets in the MDCA (shared with FLEX and FLEX-2)."],
  "PSI-47":  ["Used one of the SAME smoke instruments to detect dust instead."],
  "PSI-20":  ["Burned gaseous fuels, but studied materials flammability in still atmospheres as a function of material properties."],
  "PSI-159": ["Highest-oxygen microgravity tests: chamber filled with nitrogen + a flammable gas (e.g. propane) while an O₂/N₂ mix of up to 85% O₂ flowed from the spherical burner — an inside-out flame. This is NOT an 85% O₂ cabin atmosphere."],
  "PSI-22":  ["Mimicked partial gravity using an electric field acting on ions in the flame — an analogue, not real lunar or Martian gravity."],
  "PSI-10":  ["One of the six ACME gaseous-fuel experiments in the CIR."],
  "PSI-21":  ["One of the six ACME gaseous-fuel experiments in the CIR."],
  "PSI-23":  ["One of the six ACME gaseous-fuel experiments in the CIR."],
  "PSI-107": ["The MSG flow duct used by BASS, BASS-II and SLICE was built for SPICE."],
  "PSI-106": ["Run in the MSG flow duct built for SPICE."]
};
window.DATA.dois = { "PSI-47": "10.60555/ztgj-d202" };   // others: TODO from PSI landing pages

// ---------- Thermo model ↔ PSI investigation links (from the tracker's "NASA PSI Investigation & Hardware" column) ----------
window.DATA.modelInvestigations = {
  "THM-01": ["PSI-20", "PSI-159", "PSI-69"], "THM-02": ["PSI-20", "PSI-10", "PSI-69"], "THM-03": ["PSI-159", "PSI-10"],
  "THM-04": ["PSI-98", "PSI-99", "PSI-100", "PSI-25"], "THM-05": ["PSI-26", "PSI-25", "PSI-98", "PSI-99", "PSI-100"],
  "THM-06": ["PSI-26", "PSI-25", "PSI-98", "PSI-99", "PSI-100"], "THM-07": ["PSI-25", "PSI-106"], "THM-08": ["PSI-25", "PSI-22"],
  "THM-09": ["PSI-26", "PSI-25", "PSI-98", "PSI-99", "PSI-100"], "THM-10": ["PSI-69", "PSI-68", "PSI-39"],
  "THM-11": ["PSI-69", "PSI-68", "PSI-159"], "THM-12": ["PSI-69", "PSI-68"], "THM-13": ["PSI-25", "PSI-20"],
  "THM-14": ["PSI-98", "PSI-99", "PSI-100", "PSI-10"], "THM-15": ["PSI-10", "PSI-159", "PSI-69"],
  "THM-16": ["PSI-26", "PSI-25", "PSI-98", "PSI-99", "PSI-100"], "THM-17": ["PSI-25", "PSI-20"], "THM-18": ["PSI-69", "PSI-25"],
  "THM-19": ["PSI-98", "PSI-99", "PSI-100"], "THM-20": ["PSI-102", "PSI-101", "PSI-98", "PSI-99", "PSI-100"]
};

// ---------- Dimensionless groups & key constants [thermo] ----------
window.DATA.dimensionless = [
  { name: "Damköhler number", formula: "Da = τ_flow / τ_chem = (α_g / U_g²) / τ_chem", meaning: "Gas residence time vs chemical reaction time.", threshold: "Da < Da_crit → blow-off extinction at high flow.", models: ["THM-07", "THM-17"] },
  { name: "Lewis number", formula: "Le = α / D = k / (ρ c_p D)", meaning: "Heat vs mass diffusion of the limiting reactant; shifts temperature in curved 0 g flames.", threshold: "Le < 1 (H₂, CH₄) strengthens flame balls; Le > 1 favours diffusive-thermal extinction.", models: ["THM-02", "THM-03"] },
  { name: "Richardson number", formula: "Ri = Gr / Re² = g β ΔT L / U_g²", meaning: "Buoyancy vs forced ventilation.", threshold: "Ri ≪ 1 forced-flow dominated (0 g); Ri ≫ 1 buoyancy dominated (1 g).", models: ["THM-08"] },
  { name: "Spalding B-number", formula: "B = [Y_O2,∞ (ΔH_c/ν_s) − c_p,g (T_v − T_∞)] / ΔH_pyr", meaning: "Driving potential for pyrolysis or droplet evaporation.", threshold: "Higher B → faster surface regression and droplet burning.", models: ["THM-09", "THM-10"] },
  { name: "Radiative loss fraction", formula: "χ_r = Q_rad / Q_total", meaning: "Share of heat release lost to radiation (CO₂, H₂O, soot, surfaces).", threshold: "At very low airflow (< 1–2 cm/s) radiation dominates → radiative quenching.", models: ["THM-13", "THM-14"] },
  { name: "Oxygen consumption constant", formula: "E_O2 ≈ 13.1 MJ per kg O₂ (±5%)", meaning: "Converts O₂ depletion into fire heat-release rate.", threshold: "Valid for most organic polymers, fabrics and hydrocarbons.", models: ["THM-04", "THM-19"] }
];

// ---------- Atmosphere significance [thermo] ----------
window.DATA.scenarioSignificance = {
  iss: "No buoyancy; burning controlled by forced ventilation (team reference: 5–40 cm/s) and molecular diffusion.",
  lunar_habitat: "Lower pressure reduces convective cooling and diluent heat capacity while more O₂ raises flame temperature and spread rate. Chosen to shorten EVA pre-breathing.",
  spacesuit: "Pure oxygen removes the nitrogen heat sink: very easy ignition and rapid flame spread.",
  earth: "Buoyant plume draws in fresh O₂ (team reference: ~30–50 cm/s). Baseline for NASA-STD-6001 Test 1 upward-burn screening."
};

// ---------- Extra glossary terms [brief, nasa-glenn, thermo] ----------
window.DATA.glossaryExtra = [
  { term: "Spherical diffusion flame", def: "Without buoyancy a candle flame becomes a dim blue sphere fed by diffusion instead of a flickering teardrop." },
  { term: "Prevention / detection / suppression", def: "The three pillars of NASA spacecraft fire safety: stop fires starting (ignition control, material selection), find them early, put them out." },
  { term: "Pre-breathing", def: "Breathing 100% O₂ before a spacewalk to flush absorbed nitrogen and avoid the bends. A lunar base at ~10.2 psi / ≥30% O₂ shortens it." },
  { term: "Inside-out (inverse) flame", def: "Oxygen flows out of the burner into a fuel-filled chamber — the reverse of a normal flame (ACME CFI-G)." },
  { term: "Cool flame", def: "A low-temperature, nearly invisible flame that can persist after the hot flame goes out (studied in FLEX, CFI, CFI-G)." },
  { term: "Opposed vs concurrent flame spread", def: "Opposed: flame spreads against the airflow. Concurrent: airflow pushes hot gases over unburned fuel ahead of the flame." },
  { term: "NASA-STD-6001", def: "NASA's standard for testing and selecting spacecraft materials (flammability, odour, offgassing). Its 1 g flame test may not be conservative in low gravity." },
  { term: "Soot", def: "Carbon particles from fuel-rich burning; they make flames yellow and radiate heat. Soot behaves differently in 0 g." },
  { term: "Combustion Integrated Rack (CIR)", def: "The ISS rack with a 100-litre chamber dedicated to combustion experiments." },
  { term: "Microgravity Science Glovebox (MSG)", def: "Sealed ISS workspace where BASS, BASS-II, SPICE and SLICE ran in a fan-driven flow duct." }
];

// ---------- Earth applications [brief, resources tab] ----------
window.DATA.earthApplications = [
  { name: "Fine-water-mist extinguishers", desc: "Developed for the ISS; practical uses on Earth.", url: "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=details" },
  { name: "Fire detector that ignores dust (1970s)", desc: "Shuttle smoke detector that tells smoke from dust, so fewer nuisance alarms; used in industry such as mining.", url: "https://spinoff.nasa.gov/node/9407" },
  { name: "Firefighters' air tanks (1970s)", desc: "Spacesuit technology adapted to improve breathing gear.", url: "https://spinoff.nasa.gov/node/9582" },
  { name: "Firefighter clothing (1980s)", desc: "Spacesuit technology applied to protective clothing.", url: "https://spinoff.nasa.gov/node/9918" }
];

// ---------- Future / other experiments, not yet in PSI [brief, nasa-glenn] ----------
window.DATA.futureExperiments = [
  { name: "LUCI — Lunar-g Combustion Investigation", desc: "Expected future source of partial-gravity combustion data.", source: "brief" },
  { name: "FM2 — Flammability of Materials on the Moon", desc: "First combustion experiment on another planetary body; burns materials at lunar 1/6 g.", source: "brief, nasa-glenn" },
  { name: "SoFIE — Solid Fuel Ignition and Extinction", desc: "ISS investigation of fire growth; motivated by concern that NASA-STD-6001's 1 g test is not conservative in low g.", source: "nasa-glenn" },
  { name: "FLARE — Flammability Limits At Reduced-g Experiment", desc: "Method to estimate microgravity flammability limits from ground tests; JAXA, NASA, ESA, CNES, DLR and universities.", source: "nasa-glenn" }
];

// ---------- SI use so far (frontend) — keep updated for the submission's SI field ----------
window.DATA.siUse = [
  { what: "Collecting and summarising the challenge pages, guides and PSI investigation listings into reference files", tool: "Claude (Anthropic)", where: "website_scrape/ folder" },
  { what: "Generating the frontend skeleton code, routing and minimal stylesheet from the team's plan", tool: "Claude (Anthropic)", where: "frontend/ js, css" },
  { what: "Draft heuristic tags on investigations (fuel phase, hardware group, fire-safety role, relevance)", tool: "Claude (Anthropic)", where: "data/investigations.js → draft" },
  { what: "Placeholder mock AI answers (clearly labelled, to be removed)", tool: "Claude (Anthropic)", where: "data/mock_answers.js" },
  { what: "Answers on the Ask page (knowledge-graph search + generation)", tool: null, where: "Backend — model TBC" }
];

// ---------- References ----------
window.DATA.references = [
  { group: "Challenge & rules", items: [
    ["Flame in Freefall — challenge details", "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=details"],
    ["Flame in Freefall — resources", "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=resources"],
    ["Project Submission Guide", "https://www.spaceappschallenge.org/resources/project-submission-guide/"],
    ["Judging & Awards Guide", "https://www.spaceappschallenge.org/resources/judging-awards-guide/"],
    ["Participant FAQs", "https://www.spaceappschallenge.org/resources/participant-faqs/"] ] },
  { group: "NASA data & background", items: [
    ["NASA Physical Sciences Informatics (PSI) — Combustion Science", "https://psi.nasa.gov/physci/repo/search?q=combustion"],
    ["NASA Glenn — Combustion Science", "https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/"],
    ["A Researcher's Guide to ISS Combustion Science (2015)", "https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/"],
    ["NASA ScienceCasts: The Power of Studying Combustion on the ISS (2018)", "https://www.youtube.com/watch?v=W1oXykoz9zg"],
    ["Apollo 1 — lessons learned", "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1"],
    ["Apollo 13 — lessons learned", "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13"],
    ["25 Years Ago: Fire Aboard Space Station Mir", "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/"],
    ["NASA Spinoff — Fireman's Air Tanks", "https://spinoff.nasa.gov/node/9582"],
    ["NASA Spinoff — Fire Detector", "https://spinoff.nasa.gov/node/9407"],
    ["NASA Spinoff — New Technology for the Fire Attire", "https://spinoff.nasa.gov/node/9918"] ] },
  { group: "Software", items: [
    ["No third-party libraries yet (vanilla HTML/CSS/JS). Planned: Plotly.js (charts), Cytoscape.js (graph view).", null] ] }
];
