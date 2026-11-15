// Global state: persona, scenario, compare list, conversation. Persona + scenario persist in localStorage.
window.PERSONAS = {
  student: {
    label: "Student",
    depth: "introductory",
    nav: ["home", "learn", "ask", "explore", "lab", "about"],
    homeTools: [
      ["learn", "Start here: how fire behaves in space"],
      ["ask", "Ask a question in plain language"],
      ["lab", "Play with the physics models"]
    ]
  },
  professor: {
    label: "Professor / researcher",
    depth: "technical",
    nav: ["home", "ask", "explore", "compare", "hardware", "graph", "gaps", "lab", "about"],
    homeTools: [
      ["explore", "Browse and filter all PSI combustion investigations"],
      ["compare", "Compare investigations side by side"],
      ["graph", "Knowledge graph explorer"],
      ["gaps", "Research-gap finder"]
    ]
  },
  engineer: {
    label: "Engineer",
    depth: "decision",
    nav: ["home", "scenario", "ask", "explore", "lab", "about"],
    homeTools: [
      ["scenario", "Scenario tool: atmosphere + material + airflow"],
      ["ask", "Ask a design question"],
      ["explore", "Find the evidence behind a decision"]
    ]
  }
};

window.ROUTE_LABELS = {
  home: "Home", ask: "Ask", explore: "Explore", compare: "Compare", graph: "Knowledge graph",
  gaps: "Research gaps", lab: "Physics lab", scenario: "Scenario tool", learn: "Learn", about: "About & methods", hardware: "Hardware", dev: "All pages (dev)"
};

window.S = (() => {
  const KEY = "fif-state-v1";
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { saved = {}; }
  const st = {
    persona: PERSONAS[saved.persona] ? saved.persona : null,   // null = not chosen yet
    scenario: DATA.scenarios[saved.scenario] ? saved.scenario : "iss",
    compare: Array.isArray(saved.compare) ? saved.compare : [],
    conversation: []                                         // session only
  };
  const subs = [];
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify({ persona: st.persona, scenario: st.scenario, compare: st.compare })); } catch (e) {}
  }
  return {
    get: () => st,
    set(patch, opts = {}) { Object.assign(st, patch); persist(); if (!opts.silent) subs.forEach(f => f(st)); },
    toggleCompare(id, silent) {
      const c = st.compare.includes(id) ? st.compare.filter(x => x !== id) : [...st.compare, id].slice(-4);
      this.set({ compare: c }, { silent: !!silent });
    },
    on(f) { subs.push(f); },
    personaCfg: () => PERSONAS[st.persona || "student"]
  };
})();
