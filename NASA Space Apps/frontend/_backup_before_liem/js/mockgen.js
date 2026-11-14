// MOCK GENERATOR — when no live AI is connected, picks a different set of model widgets for each question.
// Seeded by question + persona (same question → same dashboard). Keywords and persona tilt the choice.
window.MOCKGEN = (() => {
  const KEYWORDS = {
    thm02_lewis_gauge: "lewis stable unstable hydrogen methane fuel flame ball diffus",
    thm02_gas_mixer: "oxygen o2 mix gas helium nitrogen pressure habitat atmosphere air",
    thm02_atmospheres: "atmosphere iss moon lunar habitat suit spacesuit pressure air",
    thm02_diluents: "helium nitrogen co2 suppress diluent extingu inert put out",
    thm11_droplet: "droplet liquid fuel cool flame burn decane heptane flex",
    thm11_held_out: "accurate model valid check observ nasa test prediction trust",
    thm11_facts: "how long time droplet burn last",
    thm16_heating: "ignit heat fabric material solid catch fire burn temperature",
    thm16_heatmap: "heat inside material solid depth slab soak",
    thm16_ignition_vs_flux: "ignit heat flux radiant heater how fast",
    thm16_fact: "how long ignit time catch",
    thm04_hrr: "heat release power oxygen calorimetry fire size kw hrr burner total energy",
    thm05_spread: "spread opposed flame creep thickness thin sheet pmma airflow speed",
    thm06_rate: "spread concurrent fabric saffire sibal grow faster accelerate flame growth",
    thm06_front: "flame front reach sample edge concurrent saffire sibal burn distance",
    thm15_soot: "soot smoke inception particles incomplete carbon black sooting",
    thm17_limiting_oxygen: "oxygen limit minimum flammab quench blowoff airflow wind draught draft ventilat need enough extinct low",
    thm18_dilution: "suppress extinguish co2 dilution fire suppression agent inert",
    thm18_mist: "water mist spray sprinkler cool heat absorb suppression",
    thm19_cabin: "cabin pressure temperature sealed fire habitat vehicle closed room",
    thm20_smoke: "smoke detector duct particles aerosol ageing alarm sensor"
  };
  const QUOTA = { graph: 1, interactive: 1, visual: 1, data: 1 };
  const LEAN = {
    student: { cat: { visual: 2, data: 1.5 }, type: { thm02_lewis_gauge: 2, thm11_facts: 2, thm16_fact: 2 } },
    professor: { cat: { graph: 2, explanation: 3 }, type: { thm11_held_out: 3, thm02_diluents: 2, thm16_heatmap: 2 } },
    engineer: { cat: { interactive: 3, graph: 1.5 }, type: { thm16_ignition_vs_flux: 2, thm02_atmospheres: 2 } }
  };
  function answer(question, persona) {
    const who = LEAN[persona] ? persona : "general";
    const rand = TILER.rng(TILER.hash(question.toLowerCase().trim() + "|" + who));
    const q = question.toLowerCase(), lean = LEAN[who] || { cat: {}, type: {} };
    const weight = t => (1 + 4 * KEYWORDS[t].split(" ").filter(k => q.includes(k)).length) * (lean.cat[W.def(t).cat] || 1) * (lean.type[t] || 1);
    const picked = [];
    const draw = (pool, n) => { pool = pool.filter(t => !picked.includes(t)).map(t => ({ t, w: weight(t) }));
      while (n-- > 0 && pool.length) { const sum = pool.reduce((s, p) => s + p.w, 0); let x = rand() * sum, i = 0; while ((x -= pool[i].w) > 0) i++; picked.push(pool.splice(i, 1)[0].t); } };
    const k = 5 + Math.floor(rand() * 4);                           // 5–8 of the 21 widgets
    for (const [cat, n] of Object.entries(QUOTA)) draw(W.byCat(cat), n);
    draw(W.types(), k - picked.length);
    for (let i = picked.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [picked[i], picked[j]] = [picked[j], picked[i]]; }
    const title = question.trim().replace(/\?+$/, "");
    return { title: title.charAt(0).toUpperCase() + title.slice(1), summary: "", answer: "", key_facts: [],
      widgets: picked.map(t => ({ type: t, params: {} })), evidence: [], limitations: "", follow_ups: [], meta: { source: "mock", si_generated: false } };
  }
  return { answer };
})();
