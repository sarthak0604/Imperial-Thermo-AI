// STORY — the answer page as a story: a header row, one full-width row per point of the answer (its text plus the
// 0–2 charts that show it, or a card for the NASA experiment behind it), then caveats / evidence / ask next.
// No DOM in here: points() cleans what the AI sent, rows() builds the rows, solve() sizes one justified row.
const STORY = (() => {
  const MAX_POINTS = 5, MAX_CHARTS = 2, MAX_PSI = 3, FALLBACK_POINTS = 4;
  const str = s => (typeof s === "string" ? s : s == null ? "" : String(s)).trim();
  const arr = x => Array.isArray(x) ? x : [];

  function points(a, env) {
    a = a || {};
    const used = new Set(), out = [];
    for (const p of arr(a.points)) {
      if (out.length >= MAX_POINTS) break;
      const text = str(p && p.text);
      if (!text) continue;
      const psi = [...new Set(arr(p.psi_ids).map(x => str(x).toUpperCase()).filter(env.isPsi))].slice(0, MAX_PSI);
      const charts = arr(p.charts).filter(t => typeof t === "string" && env.isChart(t) && !used.has(t)).slice(0, MAX_CHARTS);
      charts.forEach(t => used.add(t));
      out.push({ text, psi_ids: psi, charts });
    }
    if (out.length) return out;
    // older answer shape (a list of charts with a "why" each), or a mock answer: one point per chart
    for (const w of arr(a.widgets)) {
      if (out.length >= FALLBACK_POINTS) break;
      const t = w && w.type;
      if (typeof t !== "string" || !env.isChart(t) || used.has(t)) continue;
      used.add(t);
      out.push({ text: str(w.why) || str(env.desc(t)), psi_ids: arr(env.linked(t)).filter(env.isPsi).slice(0, 1), charts: [t] });
    }
    return out;
  }

  function rows(a, pts) {
    a = a || {};
    const out = [{ kind: "header", items: [{ type: "lead", params: { title: str(a.title), summary: str(a.summary), note: !!a.note } },
      ...arr(a.key_facts).filter(f => f && f.label && f.value).slice(0, 3).map(f => ({ type: "key_fact", params: f }))] }];
    const shownPsi = new Set();
    pts.forEach((p, k) => {
      const n = k + 1, side = n % 2 ? "left" : "right";
      const pt = { type: "point", params: { n, text: p.text, psi_ids: p.psi_ids, charts: p.charts, side } };
      // the charts that show this point, and (when there is room) a NASA experiment it rests on not already shown
      const others = p.charts.map(t => ({ type: t, params: {} }));
      const psi = p.psi_ids.find(id => !shownPsi.has(id));
      if (psi && p.charts.length < 2) { shownPsi.add(psi); others.push({ type: "experiment", params: { psi_id: psi } }); }
      out.push({ kind: "point", items: side === "left" ? [pt, ...others] : [...others.reverse(), pt] });
    });
    for (const block of arr(a.blocks)) {
      out.push({ kind: "point", items: [{ type: "workflow_result", params: block }] });
    }
    const close = [];
    if (str(a.limitations)) close.push({ type: "limitations", params: { text: a.limitations } });
    if (arr(a.evidence).length) close.push({ type: "evidence", params: { items: a.evidence.slice(0, 6) } });
    if (arr(a.follow_ups).length) close.push({ type: "follow_ups", params: { items: a.follow_ups.slice(0, 3) } });
    if (close.length) out.push({ kind: "close", items: close });
    return out;
  }

  // One justified row: charts keep their shape (aspect within [amin, amax]), text boxes take what is left, the row
  // fills width W exactly. items: {flex:true, need: px²} for text, {aspect, amin, amax} for a chart.
  function solve(items, W, o) {
    const gap = o.gap, hmin = o.hmin, hmax = o.hmax, minT = o.minText * W;
    const avail = W - gap * (items.length - 1);
    const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
    const F = [], C = [];
    items.forEach((it, k) => (it.flex ? F : C).push(k));
    const need = F.reduce((s, k) => s + Math.max(1, items[k].need || 1), 0);
    const widths = new Array(items.length).fill(0);
    const splitFlex = total => {                       // share the text width by need, nobody below 20%
      const floor = Math.min(0.2 * W, total / F.length);
      let free = F.slice(), rest = total;
      for (let pass = 0; pass < F.length; pass++) {
        const n = free.reduce((s, k) => s + Math.max(1, items[k].need || 1), 0), low = [];
        free.forEach(k => { const w = rest * Math.max(1, items[k].need || 1) / n; if (w < floor) low.push(k); else widths[k] = w; });
        if (!low.length) break;
        low.forEach(k => { widths[k] = floor; rest -= floor; });
        free = free.filter(k => !low.includes(k));
      }
    };
    if (!C.length) {
      splitFlex(avail);
      return { h: clamp(need / avail, hmin, hmax), widths };
    }
    const lo = C.reduce((s, k) => s + items[k].amin, 0), hi = C.reduce((s, k) => s + items[k].amax, 0);
    const nat = C.reduce((s, k) => s + items[k].aspect, 0);
    const lerp = sum => { const t = hi > lo ? clamp((sum - lo) / (hi - lo), 0, 1) : 0; return C.map(k => items[k].amin + t * (items[k].amax - items[k].amin)); };
    const sumOf = a => a.reduce((s, x) => s + x, 0);
    const tfMin = F.length ? Math.max(o.minText, 0.22 * F.length) * W / avail : 0, tfMax = F.length ? Math.max(0.55, tfMin + 0.1) : 0;
    const hp = clamp(o.hpref || (hmin + hmax) / 2, hmin, hmax);
    const tf = F.length ? clamp(need / (hp * avail), tfMin, tfMax) : 0;        // share of the width the words need at a comfortable height
    const target = avail * (1 - tf);
    let h = clamp(target / nat, hmin, hmax);                                    // charts at their natural shape, row height within limits
    let as = lerp(target / h), chartW = h * sumOf(as);                         // then bend the charts within their own range
    if (F.length && avail - chartW < tfMin * avail) {                         // too little room for words: slimmest charts, then a lower row
      as = C.map(k => items[k].amin); chartW = h * lo;
      if (avail - chartW < tfMin * avail) { h = Math.max(160, (avail - tfMin * avail) / lo); chartW = h * lo; }
    }
    if (F.length && avail - chartW > tfMax * avail) {                         // words would sprawl: grow the charts (and row) instead
      const want = avail * (1 - tfMax); h = clamp(want / hi, hmin, hmax); as = lerp(want / h); chartW = h * sumOf(as);
    }
    if (!F.length) { const k = avail / chartW; as = as.map(x => x * k); chartW = avail; }
    C.forEach((k, j) => { widths[k] = h * as[j]; });
    if (F.length) splitFlex(avail - chartW);
    return { h, widths };
  }

  return { points, rows, solve };
})();
if (typeof module !== "undefined") module.exports = STORY;
