// TILER — splits the screen into a bento grid around the centred question.
// Charts decide the shape of their boxes: each chart has a natural width:height and a range it still looks good in
// (measured, see MW.shape in model_widgets.js), so the tiler fits boxes to the charts, never the other way round.
// Text blocks (answer, facts, explanations…) are flexible: they take whatever space is left, as long as they get
// enough room for their words. Tries many random tilings (seeded, so the same question → same layout) and keeps
// the best-scoring one.
// An item is { aspect, amin, amax, weight }                  for a chart (rigid shape), or
//             { flex: true, amin, amax, need }               for a text block (need = pixels² its text wants).
window.TILER = (() => {
  const C = 8, R = 5, GAP = 10, CENTRE = { r: 2, c: 2, rs: 1, cs: 4 };   // 8×5 grid, question across the middle row
  const TRIES = 900, MAX_ITEMS = 18;
  const L = Math.log;

  function hash(s) { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  const px = (rect, cell) => ({ w: rect.cs * cell.w + (rect.cs - 1) * cell.gap, h: rect.rs * cell.h + (rect.rs - 1) * cell.gap });
  const cellsFor = viewport => ({ w: (viewport.w - GAP * (C + 1)) / C, h: (viewport.h - GAP * (R + 1)) / R, gap: GAP });

  // Starting regions around a centre {r, c, cs}: 4 schemes (side columns, full bands, pinwheel, mirrored pinwheel)
  function bases(ce) {
    const Lc = ce.c, Rw = C - ce.c - ce.cs, r = ce.r, below = R - r - 1, out = [];
    const keep = list => list.filter(x => x.rs > 0 && x.cs > 0);
    out.push(keep([{ r: 0, c: 0, rs: R, cs: Lc }, { r: 0, c: ce.c + ce.cs, rs: R, cs: Rw }, { r: 0, c: ce.c, rs: r, cs: ce.cs }, { r: r + 1, c: ce.c, rs: below, cs: ce.cs }]));
    out.push(keep([{ r: 0, c: 0, rs: r, cs: C }, { r: r + 1, c: 0, rs: below, cs: C }, { r, c: 0, rs: 1, cs: Lc }, { r, c: ce.c + ce.cs, rs: 1, cs: Rw }]));
    out.push(keep([{ r: 0, c: 0, rs: r + 1, cs: Lc }, { r: 0, c: Lc, rs: r, cs: C - Lc }, { r, c: ce.c + ce.cs, rs: below + 1, cs: Rw }, { r: r + 1, c: 0, rs: below, cs: C - Rw }]));
    out.push(keep([{ r: 0, c: 0, rs: r, cs: C - Rw }, { r: 0, c: ce.c + ce.cs, rs: r + 1, cs: Rw }, { r: r + 1, c: Lc, rs: below, cs: C - Lc }, { r, c: 0, rs: below + 1, cs: Lc }]));
    return out;
  }
  const CENTRES = [{ r: 2, c: 2, rs: 1, cs: 4 }];   // always dead centre: middle row, middle 4 of 8 columns

  // Which way to cut a rectangle: wide boxes are cut across, tall/square ones along, so the pieces land near the
  // 1.4–2.4 shapes the charts like (still random, so layouts vary).
  function cutVertical(a, cell, rand) {
    if (a.cs === 1) return false;
    if (a.rs === 1) return true;
    const p = px(a, cell), ar = p.w / p.h;
    return rand() < (ar > 2.4 ? 0.85 : ar < 1.3 ? 0.15 : 0.5);
  }

  // Random partition of the screen into the centre + k rectangles (guillotine cuts — always succeeds)
  function partition(k, rand, cell) {
    let centre = CENTRE, rects;
    if (k >= 4) { centre = CENTRES[Math.floor(rand() * CENTRES.length)]; const bs = bases(centre); rects = bs[Math.floor(rand() * bs.length)].map(x => ({ ...x })); }
    else if (k >= 2) { centre = { r: 2, c: 0, rs: 1, cs: C }; rects = [{ r: 0, c: 0, rs: 2, cs: C }, { r: 3, c: 0, rs: 2, cs: C }]; }
    else { centre = { r: 2, c: 0, rs: 3, cs: C }; rects = [{ r: 0, c: 0, rs: 2, cs: C }]; }
    while (rects.length < k) {
      const cand = rects.filter(x => x.rs * x.cs > 1);
      if (!cand.length) break;
      const tot = cand.reduce((s, x) => s + x.rs * x.cs, 0); let pick = rand() * tot, a = cand[0];
      for (const x of cand) { if ((pick -= x.rs * x.cs) <= 0) { a = x; break; } }
      const vertical = cutVertical(a, cell, rand);
      const n = vertical ? a.cs : a.rs, cut = 1 + Math.floor(rand() * (n - 1));
      const p1 = vertical ? { ...a, cs: cut } : { ...a, rs: cut };
      const p2 = vertical ? { ...a, c: a.c + cut, cs: a.cs - cut } : { ...a, r: a.r + cut, rs: a.rs - cut };
      rects = rects.filter(x => x !== a).concat([p1, p2]);
    }
    return rects.length === k ? { centre, rects } : null;
  }

  const tooSmall = (w, h, mw, mh) => 3 * (Math.max(0, mw - w) / 80) ** 2 + 3 * (Math.max(0, mh - h) / 50) ** 2;

  // cost of putting item `it` into `rect` (lower is better)
  function fit(rect, it, cell, ctx) {
    const { w, h } = px(rect, cell), area = w * h, la = L(w / h);
    const lo = L(it.amin), hi = L(it.amax), ex = la < lo ? lo - la : la > hi ? la - hi : 0;   // log-distance outside its range
    if (it.flex) {
      const r = area / it.need;
      return 0.8 * ex * ex + (r < 1 ? 5 : 0.35) * L(r) ** 2 + tooSmall(w, h, 150, 90);
    }
    const dev = la - L(it.aspect), want = ctx.chartBudget * it.weight / ctx.chartW;
    return 2.5 * dev * dev + 16 * ex * ex + 0.7 * L(area / want) ** 2 + tooSmall(w, h, 250, 140);
  }

  function solve(rects, its, cell) {
    const totalPx = rects.reduce((s, r) => { const p = px(r, cell); return s + p.w * p.h; }, 0);
    const textNeed = its.reduce((s, it) => s + (it.flex ? it.need : 0), 0);
    const chartW = its.reduce((s, it) => s + (it.flex ? 0 : it.weight), 0) || 1;
    const ctx = { chartBudget: Math.max(totalPx - textNeed, 0.35 * totalPx), chartW };
    // greedy: biggest wants → biggest rectangles, then improve with pairwise swaps
    const want = it => it.flex ? it.need : ctx.chartBudget * it.weight / chartW;
    const rs = rects.slice().sort((a, b) => b.rs * b.cs - a.rs * a.cs);
    const order = its.map((_, i) => i).sort((a, b) => want(its[b]) - want(its[a]));
    const asg = []; order.forEach((wi, n) => { asg[wi] = rs[n]; });
    const cost = i => fit(asg[i], its[i], cell, ctx);
    for (let pass = 0; pass < 6; pass++) {
      let moved = false;
      for (let i = 0; i < its.length; i++) for (let j = i + 1; j < its.length; j++) {
        const before = cost(i) + cost(j); [asg[i], asg[j]] = [asg[j], asg[i]];
        if (cost(i) + cost(j) >= before - 1e-9) [asg[i], asg[j]] = [asg[j], asg[i]]; else moved = true;
      }
      if (!moved) break;
    }
    return { asg, total: its.reduce((s, _, i) => s + cost(i), 0) };
  }

  const norm = it => it.flex
    ? { flex: true, amin: it.amin || 0.7, amax: it.amax || 2.5, need: it.need || 30000 }
    : { aspect: it.aspect || 2, amin: it.amin || (it.aspect || 2) / 1.4, amax: it.amax || (it.aspect || 2) * 1.4, weight: it.weight || 2 };

  // items → { C, R, centre, rects:[rect per item], fits:[{ar, dev, inRange}] }
  function layout(items, seed, viewport) {
    const k = Math.min(items.length, MAX_ITEMS), cell = cellsFor(viewport);
    if (!k) return { C, R, centre: { r: 0, c: 0, rs: R, cs: C }, rects: [], fits: [] };
    const its = items.slice(0, k).map(norm), rand = rng(seed);
    let best = null;
    for (let t = 0; t < TRIES; t++) {
      const p = partition(k, rand, cell); if (!p) continue;
      const s = solve(p.rects, its, cell);
      const score = s.total + rand() * 0.3;              // a little randomness so similar questions still differ
      if (!best || score < best.score) best = { score, rects: s.asg, centre: p.centre };
    }
    const rects = best ? best.rects : [];
    const fits = rects.map((r, i) => { const { w, h } = px(r, cell), ar = w / h, it = its[i];
      return { w: Math.round(w), h: Math.round(h), ar, flex: !!it.flex, dev: it.flex ? 0 : Math.abs(L(ar / it.aspect)), inRange: ar >= it.amin && ar <= it.amax }; });
    return { C, R, centre: best ? best.centre : CENTRE, rects, fits };
  }

  return { layout, hash, rng, px, cellsFor };
})();
