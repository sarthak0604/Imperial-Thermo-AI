// Builds standin/context.json (the data the stand-in AI is allowed to use) from the site's data files.
// Run from the frontend folder:  node standin/build_context.js
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = path.join(__dirname, "..");
const sandbox = { window: {} }; vm.createContext(sandbox);
for (const f of ["reference", "investigations", "models", "knowledge", "project"])
  vm.runInContext(fs.readFileSync(path.join(root, "data", f + ".js"), "utf8"), sandbox);
const D = sandbox.window.DATA, P = sandbox.window.PROJECT;
const cut = (s, n) => { s = String(s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n) + "…" : s; };
const hwFor = id => D.hardware.filter(h => h.investigations.includes(id)).map(h => h.name);
const ctx = {
  challenge: { name: P.challenge.name, objective: P.challenge.objective, outOfScope: P.challenge.outOfScope },
  facts: [
    "PSI contains NO partial-gravity (lunar 0.16 g / Martian 0.38 g) combustion data. LUCI and FM2 may add it in future. Lunar/Martian statements are theoretical bounds between microgravity and 1 g results.",
    "E-FIELD Flames mimicked partial gravity with electric fields: an analogue, not real partial gravity.",
    "CFI-G's up-to-85% O2 was a burner stream into a nitrogen + fuel chamber, not a cabin atmosphere.",
    "Expected lunar habitat/rover atmosphere: >=30% O2 at <=10.2 psi. Spacesuit: 100% O2 at 4.3 psi. Earth sea level and ISS: 21% O2 at 14.7 psi.",
    "Spacecraft fire safety = prevention (ignition control, material selection via flammability limits), detection, suppression.",
    "Rocket/propellant fire safety is out of scope."
  ],
  investigations: D.investigations.map(i => ({
    id: i.id, acronym: i.acronym, title: i.title, type: i.projectType, platform: i.platform, subArea: i.subArea,
    hardware: hwFor(i.id), related: i.related, keywords: cut(i.keywords, 200),
    objectives: cut(i.objectives, 600), approach: cut(i.approach, 250), impacts: cut(i.impacts, 250),
    briefNotes: D.briefNotes[i.id] || [], draftTags: i.draft
  })),
  hardware: D.hardware.map(h => ({ id: h.id, name: h.name, desc: h.desc, investigations: h.investigations })),
  models: D.models.map(m => ({ id: m.id, domain: m.domain, description: cut(m.description, 300), evidence: m.evidence,
    status: m.status, linkedInvestigations: D.modelInvestigations[m.id] || [] })),
  scenarios: Object.fromEntries(Object.entries(D.scenarios).map(([k, s]) => [k, { ...s, significance: D.scenarioSignificance[k] }])),
  futureExperiments: D.futureExperiments
};
fs.writeFileSync(path.join(__dirname, "context.json"), JSON.stringify(ctx));
console.log("context.json:", JSON.stringify(ctx).length, "chars,", ctx.investigations.length, "investigations");
