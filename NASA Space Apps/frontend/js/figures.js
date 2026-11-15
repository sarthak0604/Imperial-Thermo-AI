// FIGURES — draws the charts the pipeline generates for each question (js/pipeline.js), from their data, in the
// site's chart style (js/charts.js: ink lines, mono numbers, the one accent chip for "your conditions").
// A figure spec: { kind: "line" | "bar", title, model, x: {label, unit, min, max, log, ticks}, y: {…},
//   series: [{ name, pts: [[x, y]…], style: solid|dash|thin, fill: "above" }], obs: { name, pts: [[x, y, err]…] },
//   refs: [{ x | y, label }], zones: [{ label, at: above|below }], mark: { x, y, label }, bars: [{ label, value, hi }] }
// register() adds each generated figure to the chart library (js/model_widgets.js) under its own id, so the answer
// page, the full-screen view and the PDF draw it like any other chart. The full view has sliders that re-run the model.
// Written with SI assistance (Claude, Anthropic).
window.FIG = (() => {
  const { esc } = U;
  const { frame, line, dot, vref, href, chip, title, T, r1, monoW, capsW, tkSize, CHIP_H } = CH;

  // ---------- ticks ----------
  function nice(lo, hi, n = 5) {
    const span = hi - lo || 1, raw = span / n, mag = 10 ** Math.floor(Math.log10(raw)), st = [1, 2, 2.5, 5, 10].map(k => k * mag).find(s => s >= raw);
    const out = []; for (let v = Math.ceil(lo / st - 1e-9) * st; v <= hi + 1e-9; v += st) out.push(Math.round(v * 1e6) / 1e6);
    return out;
  }
  const fmtv = v => Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-GB") : String(Math.round(v * 100) / 100);
  const domain = (spec, axis, pts) => {
    const A = spec[axis] || {}, vs = pts.filter(v => v != null && isFinite(v));
    let lo = A.min ?? Math.min(...vs), hi = A.max ?? Math.max(...vs);
    if (A.max == null) hi = hi + (hi - lo) * .08; if (lo === hi) hi = lo + 1;
    return [lo, hi];
  };

  // ---------- legend: line swatches + names, wrapping into rows at the top ----------
  function legend(items, x0, x1, y0, c) {
    const fs = c ? 10 : 10.5, gap = 16, sw = 22, rows = [[]]; let x = x0;
    items.forEach(it => { const w = sw + 6 + monoW(it.name, fs) * .93; if (x + w > x1 && rows[rows.length - 1].length) { rows.push([]); x = x0; } rows[rows.length - 1].push({ ...it, x, w }); x += w + gap; });
    let s = ""; rows.forEach((row, i) => { const y = y0 + i * 16; row.forEach(it => {
      const m = y - 3.5;
      s += it.style === "obs" ? `<circle class="pt hollow" cx="${r1(it.x + sw / 2)}" cy="${r1(m)}" r="3.5"/>` : `<line class="s${it.style === "dash" ? " dash" : it.style === "thin" ? " thin" : ""}" x1="${r1(it.x)}" x2="${r1(it.x + sw)}" y1="${r1(m)}" y2="${r1(m)}"/>`;
      s += `<text class="lg" x="${r1(it.x + sw + 6)}" y="${r1(y)}">${esc(it.name)}</text>`; }); });
    return { svg: s, h: rows.length * 16 };
  }

  // ---------- line chart ----------
  function lineChart(spec, sz) {
    const { w, h, compact: c, id } = sz;
    const all = (spec.series || []).flatMap(s => s.pts), obs = (spec.obs && spec.obs.pts) || [];
    const [x0, x1] = domain(spec, "x", [...all, ...obs].map(p => p[0]));
    const [y0, y1] = domain(spec, "y", [...all.map(p => p[1]), ...obs.map(p => p[1] + (p[2] || 0))]);
    const lg = [...(spec.series || []).map(s => ({ name: s.name, style: s.style })), ...(obs.length ? [{ name: spec.obs.name, style: "obs" }] : [])];
    const showLg = !c || (lg.length <= 2 && w > 300);
    const lgH = showLg ? legend(lg, 0, w, 0, c).h + 6 : 0;
    const xt = spec.x.ticks || (spec.x.log ? [0.1, 0.3, 1, 3, 10, 30, 100, 300].filter(v => v >= x0 && v <= x1) : nice(x0, x1, c ? 4 : 6));
    const F = frame(sz, { x: [x0, x1], y: [y0, y1], xlog: spec.x.log, xticks: xt, yticks: nice(y0, y1, c ? 3 : 5), xfmt: fmtv, yfmt: fmtv,
      xlabel: spec.x.label, xunit: spec.x.unit, ylabel: spec.y.label, yunit: spec.y.unit, top: lgH });
    const { sx, sy, X0, X1, Y0, Y1 } = F, clip = `${id}-clip`;
    const inY = v => v >= y0 && v <= y1;
    let s = `<defs><clipPath id="${clip}"><rect x="${X0}" y="${Y1 - 2}" width="${r1(X1 - X0)}" height="${r1(Y0 - Y1 + 2)}"/></clipPath></defs>`;
    // shaded side of a limit curve ("burns" above it)
    (spec.series || []).filter(sr => sr.fill).forEach(sr => {
      const pts = sr.pts.filter(p => p[1] != null);
      const d = "M" + pts.map(([x, y]) => `${r1(sx(x))},${r1(sy(Math.min(y1, Math.max(y0, y))))}`).join("L") + `L${r1(sx(pts[pts.length - 1][0]))},${Y1}L${r1(sx(pts[0][0]))},${Y1}Z`;
      s += `<path class="band" d="${d}" clip-path="url(#${clip})"/>`;
    });
    s += F.axes;
    if (showLg) s += legend(lg, 0, w, spec.y.label ? (c ? 10 : 12) + 16 : 12, c).svg;
    // reference lines
    (spec.refs || []).forEach(rf => {
      if (rf.x != null && rf.x >= x0 && rf.x <= x1) { const X = sx(rf.x); s += vref(X, Y1, Y0); if (!c) s += T(X + 4, Y1 + 11, rf.label, "rl"); }
      if (rf.y != null && inY(rf.y)) { const Y = sy(rf.y); s += href(Y, X0, X1); if (!c) s += T(X1 - 4, Y - 5, rf.label, "rl", "end"); }
    });
    // zone words (BURNS / GOES OUT) in the empty corners
    if (!c) (spec.zones || []).forEach(z => { const y = z.at === "above" ? Y1 + 26 : Y0 - 10; s += `<text class="zn" x="${r1(z.at === "above" ? X0 + 10 : X1 - 10)}" y="${r1(y)}" text-anchor="${z.at === "above" ? "start" : "end"}">${esc(z.label.toUpperCase())}</text>`; });
    // the curves
    s += `<g clip-path="url(#${clip})">` + (spec.series || []).map(sr => line(sr.pts.filter(p => p[1] != null), sx, sy, { dashed: sr.style === "dash", thin: sr.style === "thin" })).join("") + `</g>`;
    // synthetic observations with error bars
    s += obs.filter(p => p[0] >= x0 && p[0] <= x1 && inY(p[1])).map(([x, y, e]) => {
      const X = sx(x), Y = sy(y), eb = e ? `<line class="eb" x1="${r1(X)}" x2="${r1(X)}" y1="${r1(sy(Math.min(y1, y + e)))}" y2="${r1(sy(Math.max(y0, y - e)))}"/>` : "";
      return eb + dot(X, Y, { hollow: true, r: c ? 3 : 3.6, tip: `${spec.obs.name}: ${fmtv(x)}, ${fmtv(y)}` });
    }).join("");
    // your conditions
    const mk = spec.mark;
    if (mk && mk.x >= x0 && mk.x <= x1) {
      const X = sx(mk.x), Y = sy(Math.max(y0, Math.min(y1, mk.y))), right = X > (X0 + X1) / 2, cy = Y - 20 < Y1 + 10 ? Y + 22 : Y - 20;
      s += dot(X, Y, { r: c ? 4 : 5 }) + chip(right ? X - 8 : X + 8, cy, mk.label, { anchor: right ? "end" : "start", dark: true, compact: c, bounds: w });
    }
    return s;
  }

  // ---------- horizontal bars (environments compared) ----------
  function barChart(spec, sz) {
    const { w, h, compact: c } = sz, fs = tkSize(c), bars = spec.bars || [];
    const labW = Math.min(w * .34, Math.max(...bars.map(b => monoW(b.label, 12) * .92)) + 10);
    const top = spec.x.label ? (c ? 20 : 26) : 8, bot = c ? 18 : 24, X0 = labW, X1 = w - (c ? 40 : 52), rowH = (h - top - bot) / Math.max(1, bars.length);
    const [, xmax] = [0, spec.x.max || Math.max(...bars.map(b => b.value)) * 1.1], sx = v => X0 + v / xmax * (X1 - X0);
    let s = title(0, c ? 10 : 12, spec.x.label, spec.x.unit);
    nice(0, xmax, c ? 3 : 5).forEach(v => { const X = sx(v); s += `<line class="gv" x1="${r1(X)}" x2="${r1(X)}" y1="${top}" y2="${r1(h - bot)}"/>` + T(X, h - bot + fs + 4, fmtv(v), "tk", "middle"); });
    s += `<line class="base" x1="${X0}" x2="${X0}" y1="${top}" y2="${r1(h - bot)}"/>`;
    bars.forEach((b, i) => {
      const yc = top + rowH * (i + .5), bh = Math.min(c ? 16 : 24, rowH * .56);
      s += `<text class="gl${b.hi ? " hi" : ""}" x="${r1(X0 - 10)}" y="${r1(yc + 4)}" text-anchor="end">${esc(b.label)}</text>`;
      s += `<rect class="bar${b.hi ? "" : " alt"}" x="${X0}" y="${r1(yc - bh / 2)}" width="${r1(Math.max(1.5, sx(b.value) - X0))}" height="${r1(bh)}" rx="3"/>`;
      s += b.hi ? chip(sx(b.value) + 8, yc, `${fmtv(b.value)} ${spec.x.unit || ""}`.trim(), { dark: true, compact: c, bounds: w }) : T(sx(b.value) + 7, yc + 4, fmtv(b.value), "tk");
    });
    (spec.refs || []).forEach(rf => { if (rf.x == null || rf.x > xmax) return; const X = sx(rf.x); s += vref(X, top - 2, h - bot); s += T(Math.min(X + 4, w - capsW(rf.label, 9)), top + 8, rf.label, "rl"); });
    return s;
  }

  const draw = (spec, sz) => spec.kind === "bar" ? barChart(spec, sz) : lineChart(spec, sz);
  const tile = spec => CH.host(sz => draw(spec, sz), { label: spec.title });

  // ---------- full view: the chart, sliders that re-run the model, and what it shows ----------
  const fmtIn = (k, v) => k === "u" ? `${Math.round(v * 100)} cm/s` : String(v);
  function controlsHTML(spec) {
    const C = PIPE.CONTROLS[spec.analysis] || [], P = PIPE.parse(spec.params.q, spec.params.s), cur = { ...P, ...(spec.inputs || {}) };
    if (!C.length) return "";
    return `<div class="controls fig-ctl"><span class="lab">Re-run the model</span>${C.map(([k, label, min, max, step, unit]) => {
      const v = cur[k] ?? (k === "q" ? 25 : k === "d0" ? 3 : min);
      return `<label class="slider">${esc(label)} <input type="range" data-k="${k}" min="${min}" max="${max}" step="${step}" value="${v}"> <output>${esc(fmtIn(k, v))}</output>${k === "u" ? "" : " " + esc(unit)}</label>`; }).join("")}
      <button type="button" class="tg fig-reset">Reset</button></div>`;
  }
  const readHTML = spec => `<p class="fig-read"><span class="badge" data-tag="synthetic">Demo data</span> ${esc(spec.desc || "")}</p>`;
  const full = spec => `${controlsHTML(spec)}<div class="chart-slot">${tile(spec)}</div>${readHTML(spec)}`;
  function mount(el, spec) {
    const inputs = {}, slot = el.querySelector(".chart-slot"), read = el.querySelector(".fig-read");
    let raf = 0;
    const redraw = () => { raf = 0; const sp = { ...PIPE.rerun(spec.analysis, spec.params, inputs), inputs: { ...inputs } }; slot.innerHTML = tile(sp); read.outerHTML = readHTML(sp); };
    const readEl = () => el.querySelector(".fig-read");
    el.querySelectorAll("input[data-k]").forEach(inp => inp.addEventListener("input", () => {
      const k = inp.dataset.k, v = +inp.value; inputs[k] = v;
      inp.nextElementSibling.textContent = fmtIn(k, v);
      if (!raf) raf = requestAnimationFrame(() => { redraw(); });
    }));
    const rs = el.querySelector(".fig-reset");
    if (rs) rs.addEventListener("click", () => { Object.keys(inputs).forEach(k => delete inputs[k]); el.querySelector(".controls").outerHTML = controlsHTML(spec); slot.innerHTML = tile(spec); readEl().outerHTML = readHTML(spec); mount(el, spec); });
  }

  // ---------- into the chart library ----------
  function register(figs) {
    if (!figs || typeof figs !== "object") return [];
    const add = {};
    Object.entries(figs).forEach(([id, sp]) => {
      if (!sp || !sp.kind || !/^[\w-]{1,48}$/.test(id)) return;
      const spec = { ...sp, id };
      add[id] = { reg: { model: spec.model, title: spec.title, cat: spec.cat || "graph", status: "demo", size: "w", desc: spec.desc || "", gen: true, lib: spec.lib, psi: spec.psi || [],
        render: () => full(spec), mount: el => mount(el, spec) }, tile: () => tile(spec), shape: spec.shape || [1.85, 1.3, 2.7] };
    });
    MW.extend(add);
    return Object.keys(add);
  }
  return { draw, tile, full, mount, register, nice };
})();
