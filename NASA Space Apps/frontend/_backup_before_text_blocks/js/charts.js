// CHART KIT — monochrome SVG charts, no libraries (works offline / from file://).
// Every chart is drawn at the real pixel size of the box it sits in (and redrawn when the box
// resizes), so text stays the same size as the rest of the site instead of being scaled like an image.
// Look matches the widget boxes: ink lines, flat bone fills, mono numbers, uppercase small labels,
// square "chip" call-outs styled like the evidence badges. Series are told apart by solid / dashed / outline, never colour.
// Usage: CH.host(sz => svgInnerString, { label }) returns a placeholder <div>; it paints itself once it is on the page.
window.CH = (() => {
  const esc = s => U.esc(s);
  const r1 = n => Math.round(n * 10) / 10;
  const r2 = n => Math.round(n * 100) / 100;
  const fmt = v => (Math.abs(v) >= 1e5 || (Math.abs(v) < 0.01 && v !== 0)) ? v.toExponential(0).replace("e+", "e") : String(r2(v));
  const range = (a, b, n) => Array.from({ length: n + 1 }, (_, k) => a + (b - a) * k / n);
  function scale(d0, d1, p0, p1, log) {
    if (log) { const a = Math.log10(d0), b = Math.log10(d1); return v => p0 + (Math.log10(v) - a) / (b - a) * (p1 - p0); }
    return v => p0 + (v - d0) / (d1 - d0) * (p1 - p0);
  }

  // ---------- sizing: placeholder → painted SVG ----------
  const reg = new Map(); let seq = 0;
  function host(draw, o = {}) {
    const id = "vc" + (++seq); reg.set(id, { draw, label: o.label || "chart" });
    return `<div class="vc-host${o.cls ? " " + o.cls : ""}" data-vc="${id}"></div>`;
  }
  function paint(el) {
    const job = el._vc; if (!job) return;
    const w = Math.floor(el.clientWidth), h = Math.floor(el.clientHeight);
    if (w < 60 || h < 60 || (el._w === w && el._h === h)) return;
    el._w = w; el._h = h;
    const compact = !!el.closest(".mtile") || h < 190 || w < 330;
    let inner;
    try { inner = job.draw({ w, h, compact, id: el.dataset.vc }); }
    catch (e) { console.error(e); inner = `<text class="tk" x="8" y="18">chart error</text>`; }
    el.innerHTML = `<svg class="vc${compact ? " compact" : ""}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(job.label)}">${inner}</svg>`;
  }
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(es => es.forEach(e => paint(e.target))) : null;
  const live = new Set();
  function mount(root = document) {
    live.forEach(el => { if (!el.isConnected) { live.delete(el); if (ro) ro.unobserve(el); } });
    root.querySelectorAll("[data-vc]").forEach(el => {
      if (el._vc) return;
      const job = reg.get(el.dataset.vc); if (!job) return;
      reg.delete(el.dataset.vc); el._vc = job; paint(el); live.add(el); if (ro) ro.observe(el);
    });
  }
  new MutationObserver(() => mount()).observe(document.documentElement, { childList: true, subtree: true });

  // ---------- text metrics (approximate, for layout) ----------
  const tkSize = c => c ? 10 : 11;                       // mono tick numbers
  const monoW = (s, fs) => String(s).length * fs * 0.6;
  const capsW = (s, fs) => String(s).length * fs * 0.72;  // uppercase sans + letter-spacing

  // ---------- primitives ----------
  const T = (x, y, s, cls, anchor = "start", extra = "") => `<text class="${cls}" x="${r1(x)}" y="${r1(y)}" text-anchor="${anchor}" ${extra}>${esc(s)}</text>`;
  const caps = (x, y, s, anchor, extra) => T(x, y, String(s).toUpperCase(), "vt", anchor, extra);
  // uppercase label + optional unit kept in normal case (mono), e.g. "CONDUCTIVITY mW/m·K"
  const title = (x, y, s, unit, anchor = "start") => `<text class="vt" x="${r1(x)}" y="${r1(y)}" text-anchor="${anchor}">${esc(String(s).toUpperCase())}${unit ? `<tspan class="u"> ${esc(unit)}</tspan>` : ""}</text>`;
  const titleW = (s, unit, fs) => capsW(s, fs) + (unit ? monoW(" " + unit, fs) : 0);
  const path = (pts, sx, sy) => "M" + pts.map(([x, y]) => `${r1(sx(x))},${r1(sy(y))}`).join("L");
  const line = (pts, sx, sy, o = {}) => `<path class="s${o.dashed ? " dash" : ""}${o.thin ? " thin" : ""}" d="${path(pts, sx, sy)}"/>`;
  const dot = (x, y, o = {}) => `<circle class="${o.hollow ? "pt hollow" : "pt"}" cx="${r1(x)}" cy="${r1(y)}" r="${o.r || 4}">${o.tip ? `<title>${esc(o.tip)}</title>` : ""}</circle>`;
  const vref = (x, y0, y1) => `<line class="ref" x1="${r1(x)}" x2="${r1(x)}" y1="${r1(y0)}" y2="${r1(y1)}"/>`;
  const href = (y, x0, x1) => `<line class="ref" x1="${r1(x0)}" x2="${r1(x1)}" y1="${r1(y)}" y2="${r1(y)}"/>`;
  const hatchDef = id => `<defs><pattern id="${id}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line class="hatch" x1="0" y1="0" x2="0" y2="6"/></pattern></defs>`;

  // Chip = a small boxed call-out, same look as the evidence badges. dark = inverted (the key reading).
  const CHIP_H = 18;
  function chipBox(text, c) { const fs = c ? 10 : 10.5; return { w: monoW(text, fs) + 12, fs }; }
  function chip(x, y, text, o = {}) {      // (x, y) = anchor point on the chip's vertical centre
    const c = !!o.compact, { w } = chipBox(text, c), anchor = o.anchor || "start";
    let x0 = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
    if (o.bounds) x0 = Math.max(1, Math.min(o.bounds - w - 1, x0));
    return `<g class="chip${o.dark ? " dark" : ""}"><rect x="${r1(x0)}" y="${r1(y - CHIP_H / 2)}" width="${r1(w)}" height="${CHIP_H}"/>` +
      `<text x="${r1(x0 + 6)}" y="${r1(y + 3.6)}">${esc(text)}</text></g>`;
  }
  // Place chips in the first row (top → down) where they don't overlap. items: {x, anchor, text, dark}
  function chipRows(items, y0, step, o = {}) {
    const rows = []; let out = "";
    items.forEach(it => {
      const { w } = chipBox(it.text, o.compact);
      let x0 = it.anchor === "middle" ? it.x - w / 2 : it.anchor === "end" ? it.x - w : it.x;
      if (o.bounds) x0 = Math.max(1, Math.min(o.bounds - w - 1, x0));
      let r = 0; while ((rows[r] || []).some(([a, b]) => x0 < b + 6 && x0 + w > a - 6)) r++;
      (rows[r] = rows[r] || []).push([x0, x0 + w]);
      const y = y0 + r * step;
      if (it.leader) out += `<line class="lead" x1="${r1(it.x)}" x2="${r1(it.x)}" y1="${r1(it.leader)}" y2="${r1(y + (step > 0 ? -CHIP_H / 2 : CHIP_H / 2))}"/>`;
      out += chip(x0, y, it.text, { dark: it.dark, compact: o.compact });
    });
    return { svg: out, rows: rows.length };
  }

  // keep every k-th tick so labels don't collide
  function thin(ticks, pos, minGap) {
    if (ticks.length < 3) return ticks;
    for (let k = 1; k < ticks.length; k++) {
      const kept = ticks.filter((_, i) => i % k === 0);
      if (kept.every((v, i) => i === 0 || Math.abs(pos(v) - pos(kept[i - 1])) >= minGap)) return kept;
    }
    return [ticks[0], ticks[ticks.length - 1]];
  }

  // ---------- XY frame: light horizontal grid, solid baseline, mono ticks, uppercase axis titles (never rotated) ----------
  // o: { x:[a,b], y:[a,b], xlog, xticks, yticks, xfmt, yfmt, xlabel, ylabel, top (extra px above plot), right, bottom }
  function frame(sz, o) {
    const { w, h, compact: c } = sz, fs = tkSize(c), yf = o.yfmt || fmt, xf = o.xfmt || fmt;
    const ylabW = Math.max(0, ...(o.yticks || []).map(v => monoW(yf(v), fs)));
    const m = {
      l: o.yticks && o.yticks.length ? Math.ceil(ylabW) + 10 : 4,
      r: Math.max(o.right ?? (c ? 6 : 12), o.xticks && o.xticks.length ? Math.ceil(monoW(xf(o.xticks[o.xticks.length - 1]), fs) / 2) + 2 : 0),
      t: (o.ylabel ? (c ? 20 : 26) : 8) + (o.top || 0),
      b: (c ? 18 : 22) + (o.xlabel ? (c ? 14 : 18) : 0) + (o.bottom || 0)
    };
    const X0 = m.l, X1 = w - m.r, Y0 = h - m.b, Y1 = m.t;
    const sx = scale(o.x[0], o.x[1], X0, X1, o.xlog), sy = scale(o.y[0], o.y[1], Y0, Y1);
    const yt = thin(o.yticks || [], sy, fs + 8), xt = thin(o.xticks || [], sx, Math.max(...(o.xticks || [0]).map(v => monoW(xf(v), fs))) + 14);
    let g = `<g class="grid">${yt.filter(v => r1(sy(v)) !== r1(Y0)).map(v => `<line x1="${X0}" x2="${X1}" y1="${r1(sy(v))}" y2="${r1(sy(v))}"/>`).join("")}</g>`;
    g += `<line class="base" x1="${X0}" x2="${X1}" y1="${Y0}" y2="${Y0}"/>`;
    g += yt.map(v => T(X0 - 8, sy(v) + fs * 0.35, yf(v), "tk", "end")).join("");
    g += xt.map(v => `<line class="tick" x1="${r1(sx(v))}" x2="${r1(sx(v))}" y1="${Y0}" y2="${Y0 + 4}"/>` + T(sx(v), Y0 + fs + 5, xf(v), "tk", "middle")).join("");
    if (o.ylabel) g += title(0, c ? 10 : 12, o.ylabel, o.yunit);
    if (o.xlabel) g += title(X1, h - 3, o.xlabel, o.xunit, "end");
    return { sx, sy, m, X0, X1, Y0, Y1, w, h, c, fs, axes: g };
  }

  return { host, mount, frame, line, dot, vref, href, chip, chipRows, chipBox, hatchDef, caps, title, titleW, T, thin, path, range, scale, fmt, r1, r2, monoW, capsW, tkSize, CHIP_H };
})();
