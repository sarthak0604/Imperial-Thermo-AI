// SYNTHETIC MOCK DASHBOARDS — test layout only. Shown with a clear "placeholder" label; never shipped as real answers.
// Format = the dashboard contract (plan doc). `answer` duplicates `summary` for the old skeleton page.
window.DATA = window.DATA || {};
window.DATA.mockAnswers = {
  student: {
    question: "Why are flames round in space?",
    title: "Why flames are round in microgravity",
    summary: "MOCK DASHBOARD — placeholder text, not a real result. A plain-language summary answering the question will appear here.",
    key_facts: [
      { label: "Flame temperature vs room air", value: "~2,300 K vs ~300 K", source: "NASA Glenn Combustion Science", psi_id: null, tag: null },
      { label: "Density change across a flame", value: "~8× over ~1 cm", source: "NASA Glenn Combustion Science", psi_id: null, tag: null },
      { label: "Spherical-flame investigations", value: "PLACEHOLDER", source: "PSI", psi_id: "PSI-23", tag: "direct_psi" }
    ],
    widgets: [
      { type: "gravity_scaling", params: {}, why: "Placeholder: how buoyancy fades from 1 g to 0 g." },
      { type: "investigation_card", params: { id: "PSI-23" }, why: "Placeholder: spherical diffusion flames on the ISS." },
      { type: "droplet_burning", params: { fuel: "n-heptane" }, why: "Placeholder: a burning droplet shrinks steadily." },
      { type: "investigation_network", params: { node: "PSI-23" }, why: "Placeholder: related flame studies." }
    ],
    evidence: [
      { psi_id: "PSI-23", tag: "direct_psi", note: "Placeholder" },
      { psi_id: "PSI-69", tag: "direct_psi", note: "Placeholder" }
    ],
    limitations: "Placeholder limitations text.",
    follow_ups: ["What happens to a candle on the Moon?", "What is buoyancy?"],
    meta: { model: "none", si_generated: true, source: "mock" }
  },
  professor: {
    question: "Which investigations studied cool flames, and how do their conditions differ?",
    title: "Cool-flame investigations in PSI",
    summary: "MOCK DASHBOARD — placeholder text, not a real result. A technical comparison will appear here.",
    key_facts: [
      { label: "Matching investigations", value: "PLACEHOLDER", source: "PSI", psi_id: null, tag: "direct_psi" },
      { label: "Highest O₂ in a burner stream", value: "up to 85% (CFI-G)", source: "Challenge brief", psi_id: "PSI-159", tag: "direct_psi" }
    ],
    widgets: [
      { type: "investigation_compare", params: { ids: ["PSI-69", "PSI-39", "PSI-159"] }, why: "Placeholder: conditions side by side." },
      { type: "droplet_burning", params: { fuel: "n-heptane" }, why: "Placeholder: two-stage burning." },
      { type: "investigation_network", params: { node: "PSI-69" }, why: "Placeholder: related studies." },
      { type: "investigation_timeline", params: { ids: ["PSI-69", "PSI-68", "PSI-39", "PSI-159", "PSI-142", "PSI-117"] }, why: "Placeholder: when each ran." },
      { type: "coverage_matrix", params: {}, why: "Placeholder: where data is thin." }
    ],
    evidence: [
      { psi_id: "PSI-69", tag: "direct_psi", note: "Placeholder" },
      { psi_id: "PSI-39", tag: "direct_psi", note: "Placeholder" },
      { psi_id: "PSI-159", tag: "direct_psi", note: "Placeholder" },
      { psi_id: "PSI-142", tag: "semi_empirical", note: "Placeholder: ground modelling study using FLEX data" }
    ],
    limitations: "Placeholder limitations text.",
    follow_ups: ["Which conditions have no data yet?", "Which models use FLEX data?"],
    meta: { model: "none", si_generated: true, source: "mock" }
  },
  engineer: {
    question: "Can cotton-fiberglass fabric burn in a 30% O2, 10.2 psi lunar habitat?",
    title: "Fabric flammability in a lunar habitat atmosphere",
    summary: "MOCK DASHBOARD — placeholder text, not a real result. A short, decision-focused answer will appear here. Research support only — not safety certification.",
    key_facts: [
      { label: "Lunar habitat atmosphere", value: "≥30% O₂ · ≤10.2 psi", source: "Challenge brief", psi_id: null, tag: null },
      { label: "Partial-gravity data in PSI", value: "0 datasets", source: "Challenge brief", psi_id: null, tag: null },
      { label: "Fabric burn tests (BASS)", value: "PLACEHOLDER", source: "PSI", psi_id: "PSI-26", tag: "direct_psi" }
    ],
    widgets: [
      { type: "flammability_map", params: { scenario: "lunar_habitat", material: "cotton_fiberglass", o2: 30, airflow: 8 }, why: "Placeholder: where this fabric can burn." },
      { type: "atmosphere_explorer", params: { pressure: 10.2, o2: 30 }, why: "Placeholder: how the habitat differs from the ISS." },
      { type: "flame_spread_curve", params: { scenario: "lunar_habitat" }, why: "Placeholder: spread rate vs ventilation." },
      { type: "suppressant_compare", params: {}, why: "Placeholder: which agent to choose." },
      { type: "ranked_list", params: { items: [ { id: "PSI-25", reason: "Placeholder reason" }, { id: "PSI-26", reason: "Placeholder reason" }, { id: "PSI-98", reason: "Placeholder reason" } ] }, why: "Placeholder: most relevant tests." }
    ],
    evidence: [
      { psi_id: "PSI-26", tag: "direct_psi", note: "Placeholder" },
      { psi_id: "PSI-25", tag: "direct_psi", note: "Placeholder" },
      { psi_id: "PSI-98", tag: "direct_psi", note: "Placeholder" }
    ],
    limitations: "Placeholder: PSI has no partial-gravity data; lunar values would be theoretical bounds.",
    follow_ups: ["How does airflow speed change this?", "Which suppressant would work best?"],
    meta: { model: "none", si_generated: true, source: "mock" }
  }
};
for (const k in window.DATA.mockAnswers) window.DATA.mockAnswers[k].answer = window.DATA.mockAnswers[k].summary;
