// Guided walkthrough: story order, captions, step state, "skip" preference. No DOM in here, so Node can test it.
const TOUR = (() => {
  const STAGES = ["context", "mechanism", "limits"];
  const STAGE_LABEL = { context: "Context", mechanism: "Mechanism", limits: "Limits" };
  const STAGE_WHY = {
    context: "Sets the scene for your question.",
    mechanism: "Shows how this works.",
    limits: "Shows where this stops holding or how far to trust it."
  };
  const STAGE_RULE = {};
  ["thm02_lewis_gauge", "thm02_atmospheres", "thm01_flame_temp", "thm03_zst", "thm04_hrr", "thm11_facts", "thm16_fact"].forEach(t => STAGE_RULE[t] = "context");
  ["thm11_held_out", "thm08_richardson", "thm16_heating", "thm16_heatmap", "thm16_ignition_vs_flux", "thm20_smoke"].forEach(t => STAGE_RULE[t] = "limits");

  const TEXT_RANK = { answer: 0, key_fact: 1, explain: 3, limitations: 4, evidence: 5, follow_ups: 6 };
  const TEXT_CAPTION = {
    answer: ["Start here", "This is the direct answer; the boxes that follow are the evidence for it."],
    key_fact: ["Key fact", "A number from the data that backs the answer."],
    explain: ["Recap", "Ties each chart back to your question."],
    limitations: ["Caveats", "What this answer cannot tell you."],
    evidence: ["Evidence", "The NASA experiments this answer relies on."],
    follow_ups: ["Ask next", "Where to go from here."]
  };
  const MIN_BOXES = 3;

  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const stageOf = w => {
    const s = w && w.stage;
    if (typeof s === "string" && STAGES.includes(s)) return s;
    return (w && has(STAGE_RULE, w.type) && STAGE_RULE[w.type]) || "mechanism";
  };
  const rankOf = w => (w && has(TEXT_RANK, w.type)) ? TEXT_RANK[w.type] : 2;

  function order(widgets) {
    const key = (w, i) => [rankOf(w), rankOf(w) === 2 ? STAGES.indexOf(stageOf(w)) : 0, i];
    return widgets.map((w, i) => ({ i, k: key(w, i) }))
      .sort((a, b) => a.k[0] - b.k[0] || a.k[1] - b.k[1] || a.k[2] - b.k[2]).map(o => o.i);
  }

  function caption(w) {
    w = w || {};
    if (has(TEXT_CAPTION, w.type)) return { kicker: TEXT_CAPTION[w.type][0], why: TEXT_CAPTION[w.type][1] };
    const st = stageOf(w), why = typeof w.why === "string" ? w.why.trim() : "";
    return { kicker: STAGE_LABEL[st], why: why || STAGE_WHY[st] };
  }

  function create(widgets) {
    const ord = order(widgets), t = {
      order: ord, total: ord.length, pos: 0,
      index() { return ord[t.pos]; },
      revealed() { return ord.slice(0, t.pos); },
      atEnd() { return t.pos >= ord.length - 1; },
      next() { if (t.atEnd()) return false; t.pos++; return true; },
      back() { if (t.pos <= 0) return false; t.pos--; return true; }
    };
    return t;
  }

  const KEY = "tour-off";
  const pref = {
    off() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } },
    set(v) { try { v ? localStorage.setItem(KEY, "1") : localStorage.removeItem(KEY); } catch (e) {} }
  };

  return { STAGES, MIN_BOXES, stageOf, order, caption, create, pref };
})();
if (typeof module !== "undefined") module.exports = TOUR;
