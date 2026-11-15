// PIPELINE (demo) — what the real backend will do, with fake data: read the question, find the NASA investigations
// that fit, run the thermo models on the question's own conditions, and turn the model output into figures and text.
//   1. parse: environment defaults (gravity, pressure, O₂, cabin airflow) + anything the question states
//      (material, fuel, "30% oxygen", "8 psi", "20 cm/s", "35 kW/m²", "2 mm droplet", "CO₂"…)
//   2. plan: which analyses answer it (spread, oxygen limit, flame temperature, ignition, droplet, buoyancy, suppression)
//   3. run: each analysis is a small physics model (de Ris spread, U-shaped flammability map, d²-law…) evaluated on the
//      question's numbers, plus SYNTHETIC "NASA-style" observations scattered around it (seeded, so the same question
//      always gives the same data). Nothing here is real NASA data: every figure is labelled demo data.
//   4. write: title, summary, key facts, findings (each with its figure), limits, follow-ups and the method.
// The live AI gets the same figures (their readings) and writes about them; with no AI the text below is used.
// Written with SI assistance (Claude, Anthropic).
window.PIPE = (() => {
  const TAU = Math.PI * 2, cl = (v, a, b) => v < a ? a : v > b ? b : v;
  const r1 = n => Math.round(n * 10) / 10, r2 = n => Math.round(n * 100) / 100, sig = n => +(+n).toPrecision(3);
  const f1 = n => n >= 100 ? String(Math.round(n)) : n >= 10 ? n.toFixed(0) : n.toFixed(1);
  const f2 = n => n >= 10 ? n.toFixed(1) : n.toFixed(2);
  const pct = x => `${Math.round(x * 100)}%`;
  const grp = n => Math.round(n).toLocaleString("en-GB");
  function hash(s) { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const gauss = r => { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(TAU * v); };

  // ---------- 1. conditions ----------
  // NASA's exploration atmosphere for Moon and Mars habitats is 8.2 psia (56.5 kPa) with 34% O₂.
  const ENV = {
    iss:           { label: "ISS cabin",      nm: "ISS",           at: "on the ISS",            g: 0,     P: 101.3, O2: 21,  u: 0.15, src: "ISS cabin air, 14.7 psi · 21% O₂ · microgravity" },
    lunar_habitat: { label: "Lunar habitat",  nm: "lunar habitat", at: "in a lunar habitat",    g: 0.165, P: 70.3,  O2: 30,  u: 0.10, src: "challenge brief: ≤ 10.2 psi · ≥ 30% O₂ · 0.16 g" },
    moon:          { label: "Moon",           nm: "Moon",          at: "on the Moon",           g: 0.165, P: 56.5,  O2: 34,  u: 0.10, src: "NASA exploration atmosphere, 8.2 psi · 34% O₂ · 0.16 g" },
    mars:          { label: "Mars",           nm: "Mars",          at: "on Mars",               g: 0.38,  P: 56.5,  O2: 34,  u: 0.10, src: "NASA exploration atmosphere, 8.2 psi · 34% O₂ · 0.38 g" },
    spacesuit:     { label: "Spacesuit",      nm: "spacesuit",     at: "inside a spacesuit",    g: 0,     P: 29.6,  O2: 100, u: 0.05, src: "suit atmosphere, 4.3 psi · 100% O₂" },
    earth:         { label: "Earth, 1 g",     nm: "Earth",         at: "on Earth",              g: 1,     P: 101.3, O2: 21,  u: 0,    src: "sea-level air, 14.7 psi · 21% O₂ · 1 g" }
  };
  const MAT = {
    cotton:  { label: "cotton fabric",                 short: "cotton",   m: 0.12, c: 1.3, Tv: 590, Tig: 620, LOC: 0.15,  thick: false, re: /cotton|cloth|clothing|garment|towel|t-shirt|shirt/ },
    sibal:   { label: "cotton–fibreglass fabric (SIBAL)", short: "SIBAL fabric", m: 0.10, c: 1.2, Tv: 600, Tig: 630, LOC: 0.16, thick: false, re: /sibal|fibre ?glass|fiberglass|fabric|textile/ },
    paper:   { label: "paper",                         short: "paper",    m: 0.05, c: 1.3, Tv: 590, Tig: 600, LOC: 0.14,  thick: false, re: /paper|kimwipe|tissue|cardboard|card\b|notebook|filter/ },
    pmma:    { label: "PMMA (acrylic)",                short: "acrylic",  m: 0.60, c: 1.4, Tv: 660, Tig: 630, LOC: 0.17,  thick: true, kpc: 0.32, re: /pmma|acrylic|plexiglas|perspex|plastic sheet/ },
    nomex:   { label: "Nomex",                         short: "Nomex",    m: 0.22, c: 1.2, Tv: 700, Tig: 700, LOC: 0.27,  thick: false, re: /nomex|aramid|flame.?resist/ },
    pe:      { label: "polyethylene wire insulation",  short: "wire insulation", m: 0.35, c: 2.0, Tv: 640, Tig: 640, LOC: 0.175, thick: true, kpc: 0.70, re: /wire|cable|insulation|polyethylene|electrical|short.?circuit/ },
    silicone:{ label: "silicone rubber",               short: "silicone", m: 1.20, c: 1.3, Tv: 720, Tig: 680, LOC: 0.25,  thick: true, kpc: 0.90, re: /silicone|rubber|seal|gasket/ },
    foam:    { label: "polyurethane foam",             short: "foam",     m: 0.05, c: 1.4, Tv: 570, Tig: 600, LOC: 0.16,  thick: false, re: /foam|cushion|padding|polyurethane/ }
  };
  const FUEL = {
    methane:  { label: "methane",   base: 2800, k: 0.19, re: /methane|natural gas|ch4/ },
    propane:  { label: "propane",   base: 2850, k: 0.19, re: /propane|lpg|c3h8/ },
    ethylene: { label: "ethylene",  base: 2950, k: 0.18, re: /ethylene|c2h4/ },
    hydrogen: { label: "hydrogen",  base: 2850, k: 0.15, re: /hydrogen|\bh2\b/ },
    heptane:  { label: "n-heptane", base: 2830, k: 0.19, K0: 0.65, liquid: true, re: /heptane/ },
    decane:   { label: "n-decane",  base: 2840, k: 0.19, K0: 0.55, liquid: true, re: /decane|jet fuel|kerosene/ },
    ethanol:  { label: "ethanol",   base: 2700, k: 0.20, K0: 0.45, liquid: true, re: /ethanol|alcohol|hand sanitiser|sanitizer/ },
    methanol: { label: "methanol",  base: 2550, k: 0.21, K0: 0.40, liquid: true, re: /methanol/ }
  };
  const DIL = {
    co2: { label: "CO₂",      cp: 1.6,  re: /co2|co₂|carbon dioxide/ },
    n2:  { label: "nitrogen", cp: 1.0,  re: /nitrogen|\bn2\b|n₂/ },
    he:  { label: "helium",   cp: 0.72, re: /helium|\bhe\b/ },
    h2o: { label: "water mist", cp: 2.4, re: /water|mist|spray|sprinkler/ }
  };

  function parse(q, s) {
    const t = " " + String(q || "").toLowerCase() + " ", E = ENV[s] || ENV.iss, P = { env: ENV[s] ? s : "iss", g: E.g, P: E.P, O2: E.O2, u: E.u, notes: [] };
    const num = re => { const m = t.match(re); return m ? parseFloat(m[1]) : null; };
    const o2 = num(/(\d+(?:\.\d+)?)\s*%\s*(?:o2|o₂|oxygen)/) ?? num(/(?:oxygen|o2|o₂)\s*(?:at|of|is|=|level of|concentration of)?\s*(\d+(?:\.\d+)?)\s*%/);
    if (o2 && o2 > 5 && o2 <= 100) { P.O2 = o2; P.notes.push(`O₂ = ${o2}% (from the question)`); }
    const psi = num(/(\d+(?:\.\d+)?)\s*psi/), kpa = num(/(\d+(?:\.\d+)?)\s*kpa/), atm = num(/(\d+(?:\.\d+)?)\s*(?:atm|bar)\b/);
    const pk = psi ? psi * 6.895 : kpa || (atm ? atm * 101.3 : null);
    if (pk && pk > 5 && pk < 400) { P.P = r1(pk); P.notes.push(`pressure = ${r1(pk)} kPa (from the question)`); }
    const cms = num(/(\d+(?:\.\d+)?)\s*cm\/s/), mms = num(/(\d+(?:\.\d+)?)\s*mm\/s/), ms = num(/(\d+(?:\.\d+)?)\s*m\/s/);
    const u = cms != null ? cms / 100 : mms != null ? mms / 1000 : ms;
    if (u != null && u >= 0 && u < 5) { P.u = u; P.notes.push(`airflow = ${f1(u * 100)} cm/s (from the question)`); }
    const qf = num(/(\d+(?:\.\d+)?)\s*kw/); if (qf && qf > 2 && qf < 200) { P.q = qf; P.notes.push(`heat flux = ${qf} kW/m² (from the question)`); }
    const dd = num(/(\d+(?:\.\d+)?)\s*mm\b(?!\/)/); if (dd && dd > 0.3 && dd < 10) P.d0 = dd;
    if (/zero.?g|weightless|microgravity|in orbit/.test(t) && !ENV[s]) P.g = 0;
    P.mat = Object.keys(MAT).find(k => MAT[k].re.test(t)) || null;
    P.fuel = Object.keys(FUEL).find(k => FUEL[k].re.test(t)) || null;
    P.dil = Object.keys(DIL).find(k => DIL[k].re.test(t)) || null;
    return P;
  }

  const DEF_MAT = "sibal";            // no material named: the cotton–fibreglass fabric NASA burned in BASS-II and Saffire
  // ---------- small physics (demo-grade, each mirrors the team's model of the same name) ----------
  const G0 = 1;
  const ubuoy = (g, P) => g <= 0 ? 0 : 0.4 * Math.cbrt(g / G0) * Math.cbrt(101.3 / P);          // m/s, ~40 cm/s on Earth (team reference 30–50)
  const ueff = (u, g, P) => Math.hypot(u, ubuoy(g, P));
  const Tad = (X, fuel, Pk) => { const F = FUEL[fuel] || FUEL.methane; return 300 + F.base * (1 - Math.exp(-X / F.k)) - 45 * (1 - Pk / 101.3) * X; };
  function LOC(u, mat, Pk) {                                                       // U-shaped flammability map (THM-17)
    const M = MAT[mat] || MAT.cotton, lo = M.LOC * Math.pow(101.3 / Pk, 0.08), um = 0.08, U = Math.max(u, 0.002);
    return U < um ? lo + 0.055 * Math.log(um / U) ** 2 : lo + 0.012 * Math.log(U / um) ** 2;
  }
  function spread(X, u, g, Pk, mat) {                                             // de Ris thin-fuel spread, mm/s (THM-05)
    const M = MAT[mat] || MAT.cotton, ue = ueff(u, g, Pk), lim = LOC(ue, mat, Pk);
    if (X <= lim) return 0;
    const Tf = 0.82 * Tad(X, "methane", Pk) + 60 - 250 * Math.exp(-ue / 0.04);
    if (Tf <= M.Tv) return 0;
    const V = (Math.PI / 4) * 0.07 * (Tf - M.Tv) / (M.m * M.c * 1000 * (M.Tv - 300)) * (M.thick ? 0.35 : 1);
    return 1000 * V * Math.sqrt((X - lim) / (X - lim + 0.04));
  }
  function tig(q, u, g, Pk, mat) {                                                // ignition delay under radiant heating, s (THM-16)
    const M = MAT[mat] || MAT.pmma, ue = ueff(u, g, Pk), loss = 3 + 9 * Math.sqrt(Math.min(1.4, ue / 0.4)) * Math.pow(Pk / 101.3, 0.3), net = q - loss;
    if (net <= 0.2) return Infinity;
    return M.thick ? (Math.PI / 4) * M.kpc * ((M.Tig - 300) / net) ** 2 : (M.m * M.c) * (M.Tig - 300) / net;
  }
  const qcrit = (u, g, Pk) => 3 + 9 * Math.sqrt(Math.min(1.4, ueff(u, g, Pk) / 0.4)) * Math.pow(Pk / 101.3, 0.3);
  function Kburn(X, g, Pk, fuel, d0) {                                            // droplet burning-rate constant, mm²/s (THM-11)
    const F = FUEL[fuel] && FUEL[fuel].K0 ? FUEL[fuel] : FUEL.heptane, B21 = 6, B = B21 * X / 0.21;
    return F.K0 * Math.log(1 + B) / Math.log(1 + B21) * (1 + 0.3 * Math.sqrt(g) * Math.pow(d0 / 2, 0.75)) * Math.pow(Pk / 101.3, 0.1);
  }
  const Tdil = (d, X0, dil, fuel, Pk) => 300 + (Tad(X0 * (1 - d), fuel, Pk) - 300) / (1 + d * ((DIL[dil] || DIL.co2).cp - 1));

  // ---------- figure helpers ----------
  const lin = (a, b, n) => Array.from({ length: n + 1 }, (_, k) => a + (b - a) * k / n);
  const logs = (a, b, n) => lin(Math.log10(a), Math.log10(b), n).map(v => 10 ** v);
  const obsAlong = (r, xs, f, rel, err) => xs.map(x => { const y = f(x); return y > 0 && isFinite(y) ? [r2(x), sig(y * (1 + rel * gauss(r))), sig(y * err)] : null; }).filter(Boolean);
  const envName = k => ENV[k].label, cap = s => s.charAt(0).toUpperCase() + s.slice(1), Nm = k => cap(ENV[k].nm);
  const others = (P, ks) => ks.filter(k => k !== P.env);

  // ---------- 2–3. the analyses ----------
  // Each returns { kind, model, lib, psi, spec, facts, find (finding text by persona), sum (a sentence for the summary), shows }
  const A = {};

  A.spread = (P, r) => {
    const mat = P.mat || DEF_MAT, M = MAT[mat], E = ENV[P.env];
    const xmax = P.O2 > 45 ? 100 : 50, xs = lin(10, xmax, 90);
    const curve = k => { const e = ENV[k], pk = k === P.env ? P.P : e.P, uu = k === P.env ? P.u : e.u, gg = k === P.env ? P.g : e.g; return xs.map(x => [x, sig(spread(x / 100, uu, gg, pk, mat))]); };
    const cmp = others(P, ["iss", "earth"]);
    const V = spread(P.O2 / 100, P.u, P.g, P.P, mat), lim = LOC(ueff(P.u, P.g, P.P), mat, P.P) * 100;
    const Viss = spread(0.21, ENV.iss.u, 0, ENV.iss.P, mat), Vearth = spread(0.21, 0, 1, 101.3, mat);
    const ratio = Viss > 0 ? V / Viss : null;
    const series = [{ name: `${envName(P.env)} · ${f1(P.P)} kPa`, pts: curve(P.env), style: "solid" }, ...cmp.map((k, i) => ({ name: envName(k) + " air", pts: curve(k), style: i ? "thin" : "dash" }))];
    const obs = obsAlong(r, lin(Math.max(lim + 2, 12), Math.min(xmax - 4, Math.max(lim + 20, P.O2 + 8)), 6), x => spread(x / 100, P.u, P.g, P.P, mat), 0.09, 0.08);
    const spec = { kind: "line", title: `Flame spread over ${M.short} vs oxygen`, model: "THM-05",
      x: { label: "Oxygen", unit: "%", min: 10, max: xmax }, y: { label: "Spread rate", unit: "mm/s", min: 0 },
      series, obs: { name: "NASA-style runs (synthetic)", pts: obs },
      refs: [{ x: lim, label: `Stops < ${f1(lim)}%` }],
      mark: V > 0 ? { x: P.O2, y: V, label: `${f2(V)} mm/s at ${f1(P.O2)}% O₂` } : { x: P.O2, y: 0, label: `No spread at ${f1(P.O2)}% O₂` },
      shape: [1.85, 1.3, 2.7] };
    const shows = `${E.label}: ${V > 0 ? `${f2(V)} mm/s at ${f1(P.O2)}% O₂` : "no spread"}; spread stops below ${f1(lim)}% O₂; ISS air ${f2(Viss)} mm/s; Earth 1 g ${f2(Vearth)} mm/s.`;
    const cmpTxt = ratio && P.env !== "iss" && V > 0 ? ` That is ${f1(ratio)}× the rate in ISS air (${f2(Viss)} mm/s).` : P.env === "iss" ? ` On Earth, in the same 21% air, it is ${f2(Vearth)} mm/s.` : "";
    const base = V > 0 ? `Over ${M.label}, a flame ${E.at} creeps at about ${f2(V)} mm/s in ${f1(P.O2)}% oxygen.${cmpTxt}` : `At ${f1(P.O2)}% oxygen a flame ${E.at} would not keep spreading over ${M.label}: the model's limit there is ${f1(lim)}%.`;
    return { kind: "spread", model: "THM-05", lib: "thm05_spread", psi: ["PSI-25", "PSI-98"], spec, shows,
      facts: [{ label: `Flame spread over ${M.short}`, value: V > 0 ? `${f2(V)} mm/s` : "No spread", source: "THM-05 on demo data" }],
      sum: V > 0 ? `a fire on ${M.short} would spread at about ${f2(V)} mm/s${ratio && P.env !== "iss" ? ` (${f1(ratio)}× ISS air)` : ""}` : `${M.short} would not sustain a spreading flame`,
      find: { g: base + " More oxygen makes the flame hotter, and a hotter flame preheats the material ahead of it faster.",
        student: base + " Think of the flame as a heater walking along the cloth: more oxygen turns the heater up, so the next bit catches sooner.",
        professor: base + ` In the thermal (de Ris) regime the rate scales with λ(T_f − T_v)/(ρτc(T_v − T∞)); the extra O₂ raises T_f, and the near-limit factor takes over below ${f1(lim)}%.`,
        engineer: base + ` Design against the ${f1(P.O2)}% case, and note the margin: the flame needs only ${f1(lim)}% O₂ to keep going.` } };
  };

  A.limit = (P, r) => {
    const mat = P.mat || DEF_MAT, M = MAT[mat], E = ENV[P.env], ue = ueff(P.u, P.g, P.P);
    const xs = logs(0.3, 100, 80), cur = pk => xs.map(c => [r2(c), r2(LOC(c / 100, mat, pk) * 100)]);
    const lim = LOC(ue, mat, P.P) * 100, best = xs.reduce((b, c) => LOC(c / 100, mat, P.P) < LOC(b / 100, mat, P.P) ? c : b, xs[0]), bestL = LOC(best / 100, mat, P.P) * 100;
    const series = [{ name: `${E.label} · ${f1(P.P)} kPa`, pts: cur(P.P), style: "solid", fill: "above" }];
    if (Math.abs(P.P - 101.3) > 5) series.push({ name: "Sea-level pressure", pts: cur(101.3), style: "dash" });
    const obs = obsAlong(r, logs(1.2, 40, 6), c => LOC(c / 100, mat, P.P) * 100, 0.035, 0.03);
    const spec = { kind: "line", title: `Oxygen ${M.short} needs to burn vs airflow`, model: "THM-17",
      x: { label: "Airflow", unit: "cm/s", min: 0.3, max: 100, log: true, ticks: [0.3, 1, 3, 10, 30, 100] }, y: { label: "Limiting oxygen", unit: "%", min: 10, max: Math.max(60, Math.ceil((P.O2 + 6) / 10) * 10) },
      series, obs: { name: "NASA-style limit tests (synthetic)", pts: obs },
      refs: [{ y: P.O2, label: `Your air ${f1(P.O2)}%` }], zones: [{ label: "Burns", at: "above" }, { label: "Goes out", at: "below" }],
      mark: { x: ue * 100, y: P.O2, label: `${E.label}: ${f1(ue * 100)} cm/s · ${f1(P.O2)}% O₂` }, shape: [1.85, 1.3, 2.7] };
    const margin = P.O2 - lim;
    const shows = `lowest oxygen that still burns ${M.short} is ${f1(bestL)}% at ${f1(best)} cm/s; at this environment's effective flow (${f1(ue * 100)} cm/s, cabin fan plus buoyancy) the limit is ${f1(lim)}%, so ${f1(P.O2)}% air is ${margin >= 0 ? f1(margin) + " points above" : f1(-margin) + " points below"} it.`;
    const base = margin >= 0 ? `${Nm(P.env)} air (${f1(P.O2)}% O₂) is ${f1(margin)} percentage points above the oxygen ${M.label} needs to keep burning at its airflow (${f1(lim)}%).` : `${Nm(P.env)} air (${f1(P.O2)}% O₂) is below the ${f1(lim)}% that ${M.label} needs at its airflow, so a flame should go out.`;
    return { kind: "limit", model: "THM-17", lib: "thm17_limiting_oxygen", psi: ["PSI-25", "PSI-20"], spec, shows,
      facts: [{ label: `Oxygen needed to burn ${M.short}`, value: `${f1(lim)}% O₂`, source: "THM-17 on demo data" }],
      sum: margin >= 0 ? `the air is ${f1(margin)} points above the ${f1(lim)}% oxygen limit` : `the air sits below the ${f1(lim)}% oxygen limit`,
      find: { g: base + ` The easiest airflow for a flame is around ${f1(best)} cm/s: slower starves it of oxygen, faster blows it off.`,
        student: base + ` It's a U-shape: too little breeze and the flame suffocates, too much and it's blown out; around ${f1(best)} cm/s it is happiest.`,
        professor: base + ` The map has a radiative-quench branch at low flow and a Damköhler blow-off branch at high flow, meeting at ${f1(bestL)}% near ${f1(best)} cm/s.`,
        engineer: base + ` Keep ventilation away from ~${f1(best)} cm/s near ignition sources, where the material is most flammable.` } };
  };

  A.temp = (P, r) => {
    const fuel = P.fuel || "methane", F = FUEL[fuel], E = ENV[P.env], xs = lin(10, 100, 90);
    const T = Tad(P.O2 / 100, fuel, P.P), Tair = Tad(0.21, fuel, 101.3);
    const series = [{ name: `${F.label} · ${f1(P.P)} kPa`, pts: xs.map(x => [x, Math.round(Tad(x / 100, fuel, P.P))]), style: "solid" }];
    if (Math.abs(P.P - 101.3) > 5) series.push({ name: "Sea-level pressure", pts: xs.map(x => [x, Math.round(Tad(x / 100, fuel, 101.3))]), style: "dash" });
    const obs = lin(15, 95, 7).map(x => { const t = Tad(x / 100, fuel, P.P) * (0.86 + 0.025 * gauss(r)); return [x, Math.round(t), 40]; });
    const spec = { kind: "line", title: `Hottest ${F.label} flame vs oxygen`, model: "THM-01",
      x: { label: "Oxygen", unit: "%", min: 10, max: 100 }, y: { label: "Flame temperature", unit: "K", min: 1000, max: 3400 },
      series, obs: { name: "Measured-style peaks (synthetic)", pts: obs }, refs: [{ x: 21, label: "Air 21%" }],
      mark: { x: P.O2, y: T, label: `${grp(T)} K at ${f1(P.O2)}% O₂` }, shape: [1.85, 1.3, 2.7] };
    const shows = `${F.label} ceiling ${grp(T)} K at ${f1(P.O2)}% O₂ and ${f1(P.P)} kPa vs ${grp(Tair)} K in sea-level air; real flames (synthetic peaks) run about 14% cooler.`;
    const d = T - Tair;
    const base = `The hottest a ${F.label} flame can get ${E.at} is about ${grp(T)} K, ${d > 15 ? `${grp(d)} K hotter than in ordinary air` : Math.abs(d) <= 15 ? "about the same as in ordinary air" : `${grp(-d)} K cooler than in ordinary air`}.`;
    return { kind: "temp", model: "THM-01", lib: "thm01_flame_temp", psi: ["PSI-20", "PSI-159"], spec, shows,
      facts: [{ label: `Hottest ${F.label} flame`, value: `${grp(T)} K`, source: "THM-01 on demo data" }],
      sum: `the flame can reach about ${grp(T)} K`,
      find: { g: base + (P.O2 > 23 ? " With less nitrogen to soak up the heat, the same fuel burns hotter." : " Raising the oxygen is what would push it higher: less nitrogen to soak up the heat."),
        student: base + " Nitrogen is like ballast: every bit of it has to be heated too. Swap some for oxygen and there's less ballast, so the flame gets hotter.",
        professor: base + " This is the equilibrium adiabatic temperature with dissociation; lower pressure dissociates slightly more, which trims the peak at high O₂.",
        engineer: base + " Treat it as a ceiling for material exposure: measured flames sit a few hundred kelvin lower." } };
  };

  A.ignite = (P, r) => {
    const mat = P.mat || DEF_MAT, M = MAT[mat], E = ENV[P.env], xs = lin(4, 60, 112), cap = M.thick ? 400 : 60;
    const cur = (u, g, pk) => xs.map(q => { const t = tig(q, u, g, pk, mat); return [q, isFinite(t) ? r1(Math.min(cap * 1.4, t)) : null]; }).filter(p => p[1] != null);
    const q0 = P.q || 25, t0 = tig(q0, P.u, P.g, P.P, mat), qc = qcrit(P.u, P.g, P.P), tE = tig(q0, 0, 1, 101.3, mat);
    const series = [{ name: E.label, pts: cur(P.u, P.g, P.P), style: "solid" }];
    if (P.env !== "earth") series.push({ name: "Earth, 1 g", pts: cur(0, 1, 101.3), style: "dash" });
    const obs = obsAlong(r, lin(qc + 6, 55, 6), q => tig(q, P.u, P.g, P.P, mat), 0.1, 0.08);
    const spec = { kind: "line", title: `Time to ignite ${M.short} vs heat flux`, model: "THM-16",
      x: { label: "Heat flux", unit: "kW/m²", min: 0, max: 60 }, y: { label: "Time to ignition", unit: "s", min: 0, max: cap },
      series, obs: { name: "Cone-style tests (synthetic)", pts: obs }, refs: [{ x: qc, label: `No ignition < ${f1(qc)}` }],
      mark: isFinite(t0) ? { x: q0, y: Math.min(t0, cap), label: `${f1(t0)} s at ${q0} kW/m²` } : { x: q0, y: 0, label: `No ignition at ${q0} kW/m²` }, shape: [1.85, 1.3, 2.7] };
    const shows = `${E.label}: ${isFinite(t0) ? f1(t0) + " s" : "no ignition"} at ${q0} kW/m²; no ignition below ${f1(qc)} kW/m²; Earth 1 g ${isFinite(tE) ? f1(tE) + " s" : "no ignition"} at ${q0} kW/m².`;
    const faster = isFinite(t0) && isFinite(tE) && P.env !== "earth" ? (t0 < tE ? `, sooner than the ${f1(tE)} s it takes on Earth, because weak or absent buoyancy carries less heat away from the surface` : `, versus ${f1(tE)} s on Earth`) : "";
    const base = isFinite(t0) ? `Under ${q0} kW/m² of radiant heat, ${M.label} ${E.at} ignites after about ${f1(t0)} s${faster}.` : `At ${q0} kW/m², ${M.label} ${E.at} would not ignite: it needs more than ${f1(qc)} kW/m².`;
    return { kind: "ignite", model: "THM-16", lib: "thm16_ignition_vs_flux", psi: ["PSI-25", "PSI-26"], spec, shows,
      facts: [{ label: `Time to ignite ${M.short} at ${q0} kW/m²`, value: isFinite(t0) ? `${f1(t0)} s` : "No ignition", source: "THM-16 on demo data" }],
      sum: isFinite(t0) ? `${M.short} ignites after about ${f1(t0)} s at ${q0} kW/m²` : `${M.short} does not ignite at ${q0} kW/m²`,
      find: { g: base + ` Below about ${f1(qc)} kW/m² the surface loses heat as fast as it gains it and never ignites.`,
        student: base + ` It's like a pan on a hob: below about ${f1(qc)} kW/m² the heat leaks away as fast as it arrives.`,
        professor: base + ` ${M.thick ? "Thermally thick: t_ig = (π/4)kρc[(T_ig − T₀)/q̇″_net]²" : "Thermally thin: t_ig = ρcτ(T_ig − T₀)/q̇″_net"}, with the convective loss shrinking as buoyancy weakens.`,
        engineer: base + ` Keep surface heat fluxes under ${f1(qc)} kW/m², with margin, near this material.` } };
  };

  A.droplet = (P, r) => {
    const fuel = P.fuel && FUEL[P.fuel].liquid ? P.fuel : "heptane", F = FUEL[fuel], E = ENV[P.env], d0 = P.d0 || 3;
    const K = Kburn(P.O2 / 100, P.g, P.P, fuel, d0), KE = Kburn(0.21, 1, 101.3, fuel, d0), de = 0.25 * d0;
    const tb = (d0 * d0 - de * de) / K, tbE = (d0 * d0 - de * de) / KE, tmax = Math.max(tb, tbE) * 1.08;
    const curve = k => lin(0, (d0 * d0 - de * de) / k, 40).map(t => [r2(t), r2(Math.max(de * de, d0 * d0 - k * t))]);
    const series = [{ name: `${E.label}`, pts: curve(K), style: "solid" }];
    if (P.env !== "earth") series.push({ name: "Earth, 1 g", pts: curve(KE), style: "dash" });
    const obs = lin(0.4, tb * 0.9, 8).map(t => [r2(t), r2(Math.max(0.05, (d0 * d0 - K * t) * (1 + 0.035 * gauss(r)))), 0.12]);
    const spec = { kind: "line", title: `${d0} mm ${F.label} droplet burning down`, model: "THM-11",
      x: { label: "Time", unit: "s", min: 0, max: Math.ceil(tmax) }, y: { label: "Diameter²", unit: "mm²", min: 0, max: Math.ceil(d0 * d0 * 1.08) },
      series, obs: { name: "FLEX-style run (synthetic)", pts: obs }, refs: [],
      mark: { x: tb, y: de * de, label: `Out at ${f1(tb)} s` }, shape: [1.7, 1.25, 2.5] };
    const shows = `${E.label}: burning-rate constant ${f2(K)} mm²/s, a ${d0} mm droplet burns for ${f1(tb)} s; Earth 1 g ${f2(KE)} mm²/s, ${f1(tbE)} s.`;
    const base = `A ${d0} mm ${F.label} droplet ${E.at} burns for about ${f1(tb)} s, shrinking at ${f2(K)} mm² of diameter² every second${P.env !== "earth" ? ` (on Earth: ${f1(tbE)} s)` : ""}.`;
    return { kind: "droplet", model: "THM-11", lib: "thm11_droplet", psi: ["PSI-69", "PSI-68"], spec, shows,
      facts: [{ label: `${d0} mm ${F.label} droplet burn time`, value: `${f1(tb)} s`, source: "THM-11 on demo data" }],
      sum: `a ${d0} mm ${F.label} droplet burns for about ${f1(tb)} s`,
      find: { g: base + " Without gravity the flame wraps the droplet in a sphere, so the fuel burns more slowly and evenly.",
        student: base + " The square of the diameter falls in a straight line: that's the classic d²-law.",
        professor: base + ` d²(t) = d₀² − Kt with K ∝ ln(1 + B); the synthetic FLEX-style points follow the line until diffusive extinction near ${f2(de)} mm.`,
        engineer: base + " Burn time scales with d₀², so a droplet twice the size burns four times as long." } };
  };

  A.gravity = (P, r) => {
    const E = ENV[P.env], keys = ["iss", "moon", "mars", "earth"]; if (!keys.includes(P.env)) keys.splice(1, 0, P.env);
    const val = k => { const e = ENV[k]; return (k === P.env ? ubuoy(P.g, P.P) : ubuoy(e.g, e.P)) * 100; };
    const bars = keys.map(k => ({ label: envName(k), value: r1(val(k)), hi: k === P.env }));
    const ub = val(P.env), fan = P.u * 100, ratio = fan > 0 ? ub / fan : null;
    const spec = { kind: "bar", title: "Air the flame pulls in by itself (buoyancy)", model: "THM-08",
      x: { label: "Buoyant flow", unit: "cm/s", min: 0, max: Math.max(45, Math.ceil(Math.max(...bars.map(b => b.value)) / 5) * 5 + 5) },
      bars, refs: fan > 0 ? [{ x: fan, label: `Cabin fan ${f1(fan)} cm/s` }] : [], shape: [2.1, 1.4, 3.0] };
    const shows = bars.map(b => `${b.label} ${f1(b.value)} cm/s`).join(", ") + (fan > 0 ? `; cabin ventilation ${f1(fan)} cm/s.` : ".");
    const who = P.g <= 0 ? `${E.at.replace(/^(on|in|inside) /, "")} has no buoyant flow at all, so the cabin fan (${f1(fan)} cm/s) is the only thing feeding the flame fresh air`
      : `${Nm(P.env)} gravity still drives about ${f1(ub)} cm/s of buoyant flow${ratio ? `, ${f1(ratio)}× the cabin fan` : ""}`;
    const base = `${who.charAt(0).toUpperCase() + who.slice(1)}.`;
    return { kind: "gravity", model: "THM-08", lib: "thm08_richardson", psi: ["PSI-25", "PSI-22"], spec, shows,
      facts: [{ label: "Buoyant flow feeding the flame", value: P.g > 0 ? `${f1(ub)} cm/s` : "None (0 g)", source: "THM-08 on demo data" }],
      sum: P.g > 0 ? `buoyancy still feeds it about ${f1(ub)} cm/s of fresh air` : "only the ventilation feeds it fresh air",
      find: { g: base + (P.g >= 1 ? " That steady draught is what gives an Earth flame its familiar teardrop shape." : P.g > 0 ? " That is why a lunar or Martian flame behaves more like an Earth flame than an ISS one." : " Without it the flame becomes a dim, rounded ball fed only by the fan and by slow diffusion."),
        student: base + " Hot gas rises because it is lighter; weaker gravity means a gentler draught, and zero gravity means none.",
        professor: base + ` Comparing buoyant and forced flow (Richardson number Ri ≈ u_b²/u_f² = ${ratio ? f1(ratio * ratio) : "0"}) sets the regime; partial-g values are theoretical bounds.`,
        engineer: base + " Size smoke detection and suppression for buoyant plumes on planetary surfaces, but for fan-driven flow in orbit." } };
  };

  A.suppress = (P, r) => {
    const dil = P.dil || "co2", D = DIL[dil], fuel = P.fuel && !FUEL[P.fuel].liquid ? P.fuel : "methane", F = FUEL[fuel], E = ENV[P.env], X0 = P.O2 / 100;
    const xs = lin(0, 60, 60), lim = 1500;
    const cur = k => xs.map(x => [x, Math.round(Tdil(x / 100, X0, k, fuel, P.P))]);
    const find0 = k => { for (const x of lin(0, 80, 800)) if (Tdil(x / 100, X0, k, fuel, P.P) <= lim) return x; return null; };
    const dOut = find0(dil), alt = dil === "co2" ? "n2" : "co2", dAlt = find0(alt);
    const spec = { kind: "line", title: `Adding ${D.label} until the flame goes out`, model: "THM-18",
      x: { label: `${D.label} added`, unit: "%", min: 0, max: 60 }, y: { label: "Flame temperature", unit: "K", min: 800, max: Math.ceil(Tad(X0, fuel, P.P) / 200) * 200 + 200 },
      series: [{ name: D.label, pts: cur(dil), style: "solid" }, { name: DIL[alt].label, pts: cur(alt), style: "dash" }],
      refs: [{ y: lim, label: "Flame goes out ~1500 K" }],
      mark: dOut != null ? { x: dOut, y: lim, label: `Out at ${f1(dOut)}% ${D.label}` } : null, shape: [1.85, 1.3, 2.7] };
    const shows = `${D.label}: flame temperature falls below ~1500 K at ${dOut != null ? f1(dOut) + "%" : "over 80%"} added; ${DIL[alt].label}: ${dAlt != null ? f1(dAlt) + "%" : "over 80%"}.`;
    const base = dOut != null ? `${E.label} air needs about ${f1(dOut)}% ${D.label} mixed in before a ${F.label} flame drops below the ~1500 K it needs to survive${dAlt != null ? ` (${DIL[alt].label}: ${f1(dAlt)}%)` : ""}.` : `Even 80% ${D.label} does not cool a ${F.label} flame ${E.at} below ~1500 K in this model.`;
    return { kind: "suppress", model: "THM-18", lib: "thm18_dilution", psi: ["PSI-69", "PSI-25"], spec, shows,
      facts: [{ label: `${D.label} needed to put it out`, value: dOut != null ? `${f1(dOut)}%` : "> 80%", source: "THM-18 on demo data" }],
      sum: dOut != null ? `about ${f1(dOut)}% ${D.label} would put it out` : `${D.label} alone would struggle to put it out`,
      find: { g: base + ` ${D.label} works by diluting the oxygen and soaking up heat.`,
        student: base + ` The extra gas steals oxygen and absorbs heat, like adding cold water to a hot bath until it's lukewarm.`,
        professor: base + ` A thermal-budget estimate: extinction is taken at a 1500 K limiting temperature, with ${D.label}'s heat capacity (×${D.cp} of N₂) doing most of the work.`,
        engineer: base + ` Plan the suppressant mass for the ${f1(P.O2)}% O₂ case; enriched air needs much more agent.` } };
  };

  // ---------- 2. plan ----------
  const INTENT = [
    ["spread",   /spread|spreading|propagat|how fast.*(burn|fire)|creep|travel|race along|fabric|cotton|paper|textile|cloth/],
    ["limit",    /limit|minimum|least oxygen|enough oxygen|flammab|airflow|air ?flow|ventilat|fan|draught|draft|breeze|blow|quench|keep burning|self.?extinguish/],
    ["temp",     /temperature|how hot|hottest|hotter|kelvin|degrees|°|methane|propane|hydrogen|ethylene|gas flame|burner/],
    ["ignite",   /ignit|catch fire|catches fire|light up|heat flux|heater|radiant|kw|overheat|short.?circuit|wire|spark|hot surface/],
    ["droplet",  /droplet|liquid|spill|heptane|decane|ethanol|methanol|alcohol|jet fuel|kerosene|sanitiser|sanitizer/],
    ["gravity",  /gravity|buoyan|plume|rise|convection|shape|moon|lunar|mars|martian|partial|compare|versus|\bvs\b|earth/],
    ["suppress", /suppress|extinguish|put (it )?out|fight|co2|co₂|carbon dioxide|nitrogen|helium|inert|dilut|water|mist|halon/]
  ];
  function plan(q, P) {
    const t = String(q || "").toLowerCase(), score = {};
    INTENT.forEach(([k, re], i) => { const m = t.match(new RegExp(re.source, "g")); if (m) score[k] = m.length * 10 - i * .1; });
    if (P.mat) score.spread = (score.spread || 0) + 6;
    if (P.fuel && FUEL[P.fuel].liquid) score.droplet = (score.droplet || 0) + 8;
    if (P.fuel && !FUEL[P.fuel].liquid) score.temp = (score.temp || 0) + 6;
    if (P.q) score.ignite = (score.ignite || 0) + 8;
    if (P.dil) score.suppress = (score.suppress || 0) + 8;
    const ranked = Object.keys(score).sort((a, b) => score[b] - score[a]);
    const pick = ranked.slice(0, 3);
    const fill = ["spread", "limit", P.g > 0 || ["moon", "mars", "lunar_habitat"].includes(P.env) ? "gravity" : "temp", "temp", "ignite"];
    for (const k of fill) { if (pick.length >= 3) break; if (!pick.includes(k)) pick.push(k); }
    if (pick.length < 4 && (P.g > 0) && !pick.includes("gravity")) pick.push("gravity");
    return pick.slice(0, 4);
  }

  // ---------- 4. the whole run ----------
  const NEXT = {
    spread: P => `What if the oxygen dropped to ${Math.max(16, Math.round(P.O2 - 8))}%?`,
    limit: () => "Which airflow makes a fire easiest to start?",
    temp: () => "How much cooler is a real flame than this ceiling?",
    ignite: P => `How long would ${(MAT[P.mat || DEF_MAT]).short} take to ignite at 50 kW/m²?`,
    droplet: () => "How does droplet size change the burn time?",
    gravity: P => P.env === "mars" ? "How would the same fire behave on the Moon?" : "How would the same fire behave on Mars?",
    suppress: P => P.dil === "he" ? "Is CO₂ a better suppressant than helium?" : "Would helium put it out with less gas?"
  };
  function title(q, P, kinds) {
    const M = P.mat ? MAT[P.mat].short : null, F = P.fuel ? FUEL[P.fuel].label : null, where = ENV[P.env].label;
    const subj = { spread: `${M || "Fabric"} fire spread`, limit: `Oxygen limit for ${M || "a fire"}`, temp: `${F ? F.charAt(0).toUpperCase() + F.slice(1) : "Flame"} temperature`,
      ignite: `Igniting ${M || "a plastic"}`, droplet: `${F || "Fuel"} droplet burning`, gravity: "Flames and gravity", suppress: `Putting out a fire` }[kinds[0]];
    return `${/^n-/.test(subj) ? subj : cap(subj)} · ${where}`;
  }
  function run(q, persona, s) {
    const P = parse(q, s), kinds = plan(q, P), seed = hash(String(q).toLowerCase().trim() + "|" + (persona || "") + "|" + P.env), r = rng(seed);
    const who = ["student", "professor", "engineer"].includes(persona) ? persona : "g";
    const res = kinds.map(k => A[k](P, r));
    const id = k => `f${seed.toString(36)}_${k}`;
    const figures = {};
    res.forEach(x => { figures[id(x.kind)] = { ...x.spec, id: id(x.kind), analysis: x.kind, lib: x.lib, psi: x.psi, desc: x.shows, status: "demo", cat: x.spec.kind === "bar" ? "visual" : "graph", params: { q, persona, s: P.env } }; });
    const E = ENV[P.env];
    const lead = res[0], rest = res.slice(1, 3);
    const summary = `${Nm(P.env)} (${f1(P.O2)}% O₂, ${f1(P.P)} kPa${P.g > 0 ? `, ${P.g} g` : ", microgravity"}): ${lead.sum}${rest.length ? ", " + rest.map(x => x.sum).join(" and ") : ""}.`
      .replace(/: (\w)/, (m, c) => ": " + c);
    const points = res.map(x => ({ text: x.find[who] || x.find.g, psi_ids: x.psi.slice(0, 2), charts: [id(x.kind)] }));
    const facts = res.slice(0, 3).map(x => ({ ...x.facts[0], psi_id: null, tag: "semi_empirical" }));
    const MODELS = res.map(x => x.model);
    const steps = [
      { title: "Read the question", text: `Environment ${E.label} (${E.src}); ${[P.mat && `material: ${MAT[P.mat].label}`, P.fuel && `fuel: ${FUEL[P.fuel].label}`, P.dil && `suppressant: ${DIL[P.dil].label}`, ...P.notes].filter(Boolean).join("; ") || "no material, fuel or numbers named, so the environment's defaults were used"}.` },
      { title: "Found the NASA data", text: `${[...new Set(res.flatMap(x => x.psi))].map(i => { const v = window.U && U.inv(i); return v ? `${v.acronym || v.id} (${v.id})` : i; }).join(", ")}. In this demo the data points are synthetic, shaped like those investigations' runs.` },
      { title: "Ran the thermo models", text: res.map(x => `${x.model} (${x.kind})`).join(", ") + ` on the question's conditions: gravity ${P.g} g, ${f1(P.P)} kPa, ${f1(P.O2)}% O₂, cabin airflow ${f1(P.u * 100)} cm/s.` },
      { title: "Drew the figures", text: `${res.length} figures from the model output, each with the synthetic observations it was checked against.` },
      { title: "Wrote the answer", text: "Every number in the text is read from a figure." }
    ];
    const answer = {
      title: title(q, P, kinds), summary, key_facts: facts, points, figures,
      widgets: res.map(x => ({ type: id(x.kind), params: {}, why: x.find.g })),
      evidence: [...new Set(res.flatMap(x => x.psi.slice(0, 2)))].map(i => ({ psi_id: i, tag: "semi_empirical", note: "Its runs are what the demo's synthetic observations imitate." })),
      limitations: `Demo data: every observation in these figures is synthetic, generated to look like NASA runs; the model curves are simplified versions of the team's models.${P.g > 0 && P.g < 1 ? " NASA's PSI database has no partial-gravity combustion data, so Moon and Mars values are theoretical bounds." : ""}`,
      follow_ups: [...new Set([...res.map(x => NEXT[x.kind](P)), ...Object.keys(NEXT).filter(k => !kinds.includes(k)).map(k => NEXT[k](P))])].slice(0, 3),
      method: { summary: "Demo pipeline: the same steps the live system will run, with synthetic data in place of the NASA database.", steps },
      meta: { source: "demo", models: MODELS }
    };
    // what the live AI is told about each figure (it may only quote these numbers)
    const brief = res.map(x => ({ id: id(x.kind), title: x.spec.title, model: x.model, shows: x.shows, built_on: x.psi }));
    const thinking = [
      `Reading the question: ${E.label}${P.mat ? ", " + MAT[P.mat].short : ""}${P.fuel ? ", " + FUEL[P.fuel].label : ""}`,
      `Finding NASA data: ${[...new Set(res.flatMap(x => x.psi.slice(0, 1)))].map(i => (window.U && U.inv(i) || {}).acronym || i).join(", ")}`,
      `Running ${MODELS.join(", ")} on your conditions`,
      `Drawing ${res.length} figures from the model output`
    ];
    return { params: P, kinds, figures, brief, answer, thinking };
  }
  // re-run one analysis with changed inputs (the sliders in a figure's full-screen view)
  function rerun(kind, p, change) {
    const P = parse(p.q, p.s); Object.assign(P, change);
    const x = A[kind](P, rng(hash(p.q + kind)));
    return { ...x.spec, analysis: kind, lib: x.lib, psi: x.psi, desc: x.shows, status: "demo", params: p };
  }
  // the inputs a figure's full view lets you change
  const CONTROLS = {
    spread: [["O2", "Oxygen", 12, 100, 1, "%"], ["P", "Pressure", 20, 101, 1, "kPa"], ["u", "Cabin airflow", 0, 0.5, 0.01, "m/s"]],
    limit: [["O2", "Your oxygen", 12, 100, 1, "%"], ["P", "Pressure", 20, 101, 1, "kPa"], ["u", "Cabin airflow", 0, 0.5, 0.01, "m/s"]],
    temp: [["O2", "Oxygen", 12, 100, 1, "%"], ["P", "Pressure", 20, 101, 1, "kPa"]],
    ignite: [["q", "Heat flux", 5, 60, 1, "kW/m²"], ["u", "Cabin airflow", 0, 0.5, 0.01, "m/s"]],
    droplet: [["d0", "Droplet size", 0.5, 6, 0.1, "mm"], ["O2", "Oxygen", 15, 100, 1, "%"]],
    gravity: [["u", "Cabin fan", 0, 0.5, 0.01, "m/s"]],
    suppress: [["O2", "Oxygen", 15, 100, 1, "%"]]
  };
  return { run, rerun, parse, plan, CONTROLS, ENV, MAT, FUEL, DIL, hash, physics: { spread, LOC, Tad, tig, Kburn, ubuoy, Tdil } };
})();
