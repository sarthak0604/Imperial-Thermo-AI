// TILER — splits the screen into a bento grid around the centred question.
// Tries many random tilings (seeded, so the same question → same layout) and keeps the one
// whose box shapes best fit what each widget contains (its natural width:height).
window.TILER = (() => {
  const C = 8, R = 5, CENTRE = { r: 2, c: 2, rs: 1, cs: 4 };   // 8×5 grid, question across the middle row

  function hash(s) { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  // Random partition of the screen into the centre + k rectangles (guillotine cuts — always succeeds)
  // Starting regions around a centre {r, c, cs}: 4 schemes (side columns, full bands, pinwheel, mirrored pinwheel)
  function bases(ce) {
    const L = ce.c, Rw = C - ce.c - ce.cs, r = ce.r, below = R - r - 1, out = [];
    const keep = list => list.filter(x => x.rs > 0 && x.cs > 0);
    out.push(keep([{ r: 0, c: 0, rs: R, cs: L }, { r: 0, c: ce.c + ce.cs, rs: R, cs: Rw }, { r: 0, c: ce.c, rs: r, cs: ce.cs }, { r: r + 1, c: ce.c, rs: below, cs: ce.cs }]));
    out.push(keep([{ r: 0, c: 0, rs: r, cs: C }, { r: r + 1, c: 0, rs: below, cs: C }, { r, c: 0, rs: 1, cs: L }, { r, c: ce.c + ce.cs, rs: 1, cs: Rw }]));
    out.push(keep([{ r: 0, c: 0, rs: r + 1, cs: L }, { r: 0, c: L, rs: r, cs: C - L }, { r, c: ce.c + ce.cs, rs: below + 1, cs: Rw }, { r: r + 1, c: 0, rs: below, cs: C - Rw }]));
    out.push(keep([{ r: 0, c: 0, rs: r, cs: C - Rw }, { r: 0, c: ce.c + ce.cs, rs: r + 1, cs: Rw }, { r: r + 1, c: L, rs: below, cs: C - L }, { r, c: 0, rs: below + 1, cs: L }]));
    return out;
  }
  const CENTRES = [{ r: 2, c: 2, rs: 1, cs: 4 }];   // always dead centre: middle row, middle 4 of 8 columns

  function partition(k, rand) {
    let centre = CENTRE, rects;
    if (k >= 4) { centre = CENTRES[Math.floor(rand() * CENTRES.length)]; const bs = bases(centre); rects = bs[Math.floor(rand() * bs.length)].map(x => ({ ...x })); }
    else if (k >= 2) { centre = { r: 2, c: 0, rs: 1, cs: C }; rects = [{ r: 0, c: 0, rs: 2, cs: C }, { r: 3, c: 0, rs: 2, cs: C }]; }
    else { centre = { r: 2, c: 0, rs: 3, cs: C }; rects = [{ r: 0, c: 0, rs: 2, cs: C }]; }
    while (rects.length < k) {
      const cand = rects.filter(x => x.rs * x.cs > 1);
      if (!cand.length) break;
      const tot = cand.reduce((s, x) => s + x.rs * x.cs, 0); let pick = rand() * tot, a = cand[0];
      for (const x of cand) { if ((pick -= x.rs * x.cs) <= 0) { a = x; break; } }
      const vertical = a.cs > 1 && (a.rs === 1 || rand() < a.cs / (a.cs + a.rs));
      const n = vertical ? a.cs : a.rs, cut = 1 + Math.floor(rand() * (n - 1));
      const p1 = vertical ? { ...a, cs: cut } : { ...a, rs: cut };
      const p2 = vertical ? { ...a, c: a.c + cut, cs: a.cs - cut } : { ...a, r: a.r + cut, rs: a.rs - cut };
      rects = rects.filter(x => x !== a).concat([p1, p2]);
    }
    return rects.length === k ? { centre, rects } : null;
  }

  // cost of putting widget w (aspect, weight) into rect
  function fit(rect, w, cell, totalArea, totalWeight) {
    const pw = rect.cs * cell.w + (rect.cs - 1) * cell.gap, ph = rect.rs * cell.h + (rect.rs - 1) * cell.gap;
    const shape = Math.log((pw / ph) / w.aspect) ** 2;
    const area = Math.log((rect.rs * rect.cs / totalArea) / (w.weight / totalWeight)) ** 2;
    return 2.2 * shape + 0.6 * area;
  }

  function solve(rects, ws, cell) {
    const totalArea = rects.reduce((s, r) => s + r.rs * r.cs, 0), totalW = ws.reduce((s, w) => s + w.weight, 0);
    // greedy by area/weight, then improve with pairwise swaps
    const rs = rects.slice().sort((a, b) => b.rs * b.cs - a.rs * a.cs);
    const order = ws.map((w, i) => i).sort((a, b) => ws[b].weight - ws[a].weight);
    const asg = []; order.forEach((wi, n) => { asg[wi] = rs[n]; });
    const cost = i => fit(asg[i], ws[i], cell, totalArea, totalW);
    for (let pass = 0; pass < 4; pass++) for (let i = 0; i < ws.length; i++) for (let j = i + 1; j < ws.length; j++) {
      const before = cost(i) + cost(j); [asg[i], asg[j]] = [asg[j], asg[i]];
      if (cost(i) + cost(j) >= before) [asg[i], asg[j]] = [asg[j], asg[i]];
    }
    return { asg, total: ws.reduce((s, _, i) => s + cost(i), 0) };
  }

  // widgets: [{aspect, weight}] → {C, R, centre, rects:[rect per widget]}
  function layout(widgets, seed, viewport) {
    const k = Math.min(widgets.length, 26);
    const gap = 10, cell = { w: (viewport.w - gap * (C + 1)) / C, h: (viewport.h - gap * (R + 1)) / R, gap };
    if (!k) return { C, R, centre: { r: 0, c: 0, rs: R, cs: C }, rects: [] };
    const rand = rng(seed);
    let best = null;
    for (let t = 0; t < 220; t++) {
      const p = partition(k, rand); if (!p) continue;
      const s = solve(p.rects, widgets.slice(0, k), cell);
      const jitter = rand() * 0.35;                      // a little randomness so similar questions still differ
      if (!best || s.total + jitter < best.score) best = { score: s.total + jitter, rects: s.asg, centre: p.centre };
    }
    return { C, R, centre: best ? best.centre : CENTRE, rects: best ? best.rects : [] };
  }

  return { layout, hash, rng };
})();
