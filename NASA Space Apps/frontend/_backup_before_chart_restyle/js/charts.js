// CHART KIT — tiny monochrome SVG charts, no libraries (works offline / from file://).
// Series are told apart by dash pattern, never colour.
window.CH = (() => {
  const esc = s => U.esc(s);
  const DASH = ["", "6 4", "2 3", "10 3 2 3"];
  const r2 = n => Math.round(n * 100) / 100;

  function scale(d0, d1, r0, r1, log) {
    if (log) { const a = Math.log10(d0), b = Math.log10(d1); return v => r0 + (Math.log10(v) - a) / (b - a) * (r1 - r0); }
    return v => r0 + (v - d0) / (d1 - d0) * (r1 - r0);
  }
  const fmt = v => (Math.abs(v) >= 1e5 || (Math.abs(v) < 0.01 && v !== 0)) ? v.toExponential(0).replace("e+", "e") : String(r2(v));

  // Generic XY chart. o: {w,h,x:[a,b],y:[a,b],xlog,ylog,xticks,yticks,xlabel,ylabel,legend:[{label,dash}],draw(ctx)->svg}
  function xy(o) {
    const w = o.w || 520, h = o.h || 260, m = { l: 48, r: 14, t: 14, b: 38, ...(o.m || {}) };
    const sx = scale(o.x[0], o.x[1], m.l, w - m.r, o.xlog), sy = scale(o.y[0], o.y[1], h - m.b, m.t, o.ylog);
    const xt = o.xticks || [], yt = o.yticks || [];
    let g = `<g class="grid">${yt.map(v => `<line x1="${m.l}" x2="${w - m.r}" y1="${r2(sy(v))}" y2="${r2(sy(v))}"/>`).join("")}</g>`;
    g += `<g class="ax"><line x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/><line x1="${m.l}" x2="${m.l}" y1="${m.t}" y2="${h - m.b}"/>`;
    g += xt.map(v => `<line x1="${r2(sx(v))}" x2="${r2(sx(v))}" y1="${h - m.b}" y2="${h - m.b + 4}"/><text x="${r2(sx(v))}" y="${h - m.b + 15}" text-anchor="middle">${esc(o.xfmt ? o.xfmt(v) : fmt(v))}</text>`).join("");
    g += yt.map(v => `<line x1="${m.l - 4}" x2="${m.l}" y1="${r2(sy(v))}" y2="${r2(sy(v))}"/><text x="${m.l - 6}" y="${r2(sy(v)) + 3}" text-anchor="end">${esc(o.yfmt ? o.yfmt(v) : fmt(v))}</text>`).join("");
    g += `<text class="lab" x="${(m.l + w - m.r) / 2}" y="${h - 4}" text-anchor="middle">${esc(o.xlabel || "")}</text>`;
    g += `<text class="lab" transform="translate(12 ${(m.t + h - m.b) / 2}) rotate(-90)" text-anchor="middle">${esc(o.ylabel || "")}</text></g>`;
    const body = o.draw ? o.draw({ sx, sy, w, h, m }) : "";
    const lw = Math.max(0, ...(o.legend || []).map(s => s.label.length)) * 5.4 + 30;
    const lx = o.legendAt === "left" ? m.l + 10 : w - m.r - Math.max(130, lw);
    const legend = (o.legend || []).map((s, i) => `<g transform="translate(${lx} ${m.t + 6 + i * 14})"><line x1="0" x2="18" y1="0" y2="0" class="series" stroke-dasharray="${s.dash ?? DASH[i]}"/><text x="24" y="3">${esc(s.label)}</text></g>`).join("");
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(o.aria || o.ylabel || "chart")}">${g}${body}<g class="legend">${legend}</g></svg>`;
  }

  const path = (pts, sx, sy) => "M" + pts.map(([x, y]) => `${r2(sx(x))},${r2(sy(y))}`).join("L");
  const line = (pts, sx, sy, i = 0, extra = "") => `<path class="series" d="${path(pts, sx, sy)}" stroke-dasharray="${DASH[i % DASH.length]}" ${extra}/>`;
  const dots = (pts, sx, sy, tip) => pts.map(([x, y], k) => `<circle class="dot" cx="${r2(sx(x))}" cy="${r2(sy(y))}" r="3"><title>${esc(tip ? tip(x, y, k) : `${fmt(x)}, ${fmt(y)}`)}</title></circle>`).join("");
  const range = (a, b, n) => Array.from({ length: n + 1 }, (_, k) => a + (b - a) * k / n);

  function bars(items, o = {}) {   // items: [{label, value, note}]
    const w = o.w || 300, h = o.h || 200, m = { l: 40, r: 10, t: 12, b: 34 };
    const max = o.max || Math.max(...items.map(i => i.value)) * 1.15;
    const sy = scale(0, max, h - m.b, m.t), bw = (w - m.l - m.r) / items.length;
    const yt = o.yticks || [0, max / 2, max].map(v => r2(v));
    let s = `<g class="grid">${yt.map(v => `<line x1="${m.l}" x2="${w - m.r}" y1="${r2(sy(v))}" y2="${r2(sy(v))}"/>`).join("")}</g>`;
    s += `<g class="ax"><line x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>${yt.map(v => `<text x="${m.l - 6}" y="${r2(sy(v)) + 3}" text-anchor="end">${fmt(v)}</text>`).join("")}`;
    s += `<text class="lab" transform="translate(11 ${(m.t + h - m.b) / 2}) rotate(-90)" text-anchor="middle">${esc(o.ylabel || "")}</text></g>`;
    s += items.map((it, k) => { const x = m.l + k * bw + bw * 0.2, y = sy(it.value);
      return `<rect class="bar" x="${r2(x)}" y="${r2(y)}" width="${r2(bw * 0.6)}" height="${r2(h - m.b - y)}"><title>${esc(it.label)}: ${fmt(it.value)}${it.note ? " — " + esc(it.note) : ""}</title></rect>
        <text class="ax-t" x="${r2(x + bw * 0.3)}" y="${h - m.b + 14}" text-anchor="middle">${esc(it.label)}</text>
        <text class="val" x="${r2(x + bw * 0.3)}" y="${r2(y) - 4}" text-anchor="middle">${fmt(it.value)}</text>`; }).join("");
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(o.ylabel || "bar chart")}">${s}</svg>`;
  }

  return { xy, line, dots, path, bars, range, scale, fmt, r2, DASH };
})();
