// REFERENCE DATA for the skeleton.
// Scenario figures: challenge brief (spacesuit, Earth, lunar) + team thermo spreadsheet (ISS). Glossary: team thermo spreadsheet.
window.DATA = window.DATA || {};

window.DATA.scenarios = {
  iss:           { label: "ISS cabin",                          pressure: "14.7 psi", o2: "21%",   gravity: "~0 g (microgravity)", note: "Forced ventilation; no buoyancy." },
  lunar_habitat: { label: "Lunar habitat / pressurized rover",  pressure: "≤ 10.2 psi", o2: "≥ 30%", gravity: "0.16 g — NO PSI DATA (theoretical bound only)", note: "Expected conditions per the challenge brief." },
  spacesuit:     { label: "Spacesuit",                          pressure: "4.3 psi",  o2: "100%",  gravity: "0 / 0.16 / 0.38 g", note: "Pure oxygen, no nitrogen diluent." },
  earth:         { label: "Earth sea level (1 g baseline)",     pressure: "14.7 psi", o2: "21%",   gravity: "1 g", note: "Baseline for NASA-STD-6001 Test 1." }
};

window.DATA.materials = [
  { id: "sibal_fabric", label: "SIBAL cotton-fiberglass fabric" },
  { id: "cotton_fiberglass", label: "Cotton / fiberglass (BASS)" },
  { id: "pmma", label: "PMMA (acrylic)" },
  { id: "nomex", label: "Nomex" }
];

window.DATA.evidenceTags = {
  direct_psi:        { label: "Direct PSI data",               short: "PSI" },
  semi_empirical:    { label: "Semi-empirical model",          short: "MODEL" },
  theoretical_bound: { label: "Theoretical / partial-g bound", short: "THEORY" },
  synthetic:         { label: "SYNTHETIC placeholder",         short: "FAKE" }
};
// Spreadsheet wording → tag id
window.DATA.evidenceFromSheet = {
  "Direct PSI Data Reduction": "direct_psi",
  "Semi-Empirical Correlation": "semi_empirical",
  "Theoretical / Partial-g Bound": "theoretical_bound"
};

window.DATA.glossary = [
  { term: "Microgravity", def: "Near-weightless conditions (e.g. ISS) where buoyancy-driven flow is almost absent, so flames rely on diffusion and forced airflow." },
  { term: "Partial gravity", def: "Gravity between 0 g and 1 g (Moon 0.16 g, Mars 0.38 g). PSI currently holds no partial-gravity combustion data." },
  { term: "Limiting Oxygen Index (LOI)", def: "Minimum oxygen fraction that sustains burning of a material." },
  { term: "Damköhler number", def: "Da = τ_flow / τ_chem. Low Da → flame blows off because flow outpaces chemistry." },
  { term: "Lewis number", def: "Le = α / D. Ratio of heat to mass diffusion; shifts flame temperature in curved 0 g flames." },
  { term: "Richardson number", def: "Ri = Gr / Re². Buoyancy vs forced flow; Ri ≪ 1 means forced-flow dominated (0 g)." },
  { term: "Spalding B-number", def: "Driving force for fuel vaporisation or pyrolysis; higher B → faster burning." },
  { term: "Radiative loss fraction", def: "χ_r = Q_rad / Q_total. At very low airflow, radiation losses can quench the flame." },
  { term: "Oxygen consumption calorimetry", def: "Heat release ≈ 13.1 MJ per kg of O₂ consumed; used to get fire heat-release rate from gas analysers." }
];

window.DATA.incidents = [
  { name: "Apollo 1 (1967)", summary: "Crew died when fire erupted in an oxygen-filled spacecraft during a pre-launch test.", url: "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1" },
  { name: "Apollo 13 (1970)", summary: "Oxygen tank explosion on the way to the Moon.", url: "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13" },
  { name: "Mir fire (1997)", summary: "Fire from an oxygen generator failure aboard the Mir station.", url: "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/" },
  { name: "Artemis II smoke alarm", summary: "A smoke alarm went off during the mission, ~80,000 miles from Earth (challenge brief).", url: "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=details" }
];

window.DATA.resources = [
  { name: "PSI Data Repository — Combustion Science", url: "https://psi.nasa.gov/physci/repo/search?q=combustion" },
  { name: "NASA Combustion Science (Glenn)", url: "https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/" },
  { name: "A Researcher's Guide to ISS Combustion Science (2015)", url: "https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/" },
  { name: "NASA ScienceCasts: The Power of Studying Combustion on the ISS", url: "https://www.youtube.com/watch?v=W1oXykoz9zg" }
];
