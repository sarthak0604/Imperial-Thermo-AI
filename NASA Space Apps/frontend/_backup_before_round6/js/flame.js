// FLAME — the AI's presence (design 2): a microgravity flame drawn as a ring of light (the flame sheet) with a dark
// core, and a belt of fine dust orbiting it in 3D, dimming as it passes behind. Thinking: the ring brightens,
// the dust speeds up and a faint ripple travels outward. Used large on the home screen and small as the loader.
// setGlyph(env) cross-fades the flame into a line drawing of the chosen environment (ISS, Moon, spacesuit, Earth);
// the dust belt keeps orbiting it. setGlyph(null) brings the flame back.
window.FLAME = (() => {
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches, TAU = Math.PI * 2;
  const hex = h => { const n = parseInt(h.slice(1), 16); return [n >> 16, n >> 8 & 255, n & 255]; };
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a < 0 ? 0 : a > 1 ? 1 : a.toFixed(3)})`;
  const F = { blu: hex("#4A7DFF"), org: hex("#FF8A1F"), pale: hex("#D6E2FF"), bluL: hex("#2C5FE0"), orgL: hex("#DD5F0A") };
  const cl = (v, a, b) => v < a ? a : v > b ? b : v;
  function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  // environment glyphs, 24 x 24 line drawings (canvas Path2D)
  const circ = (cx, cy, r) => `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
  const GLYPH = {
    iss: "M1.5 12h21M2.5 4.5h5v6h-5zM2.5 13.5h5v6h-5zM16.5 4.5h5v6h-5zM16.5 13.5h5v6h-5zM5 4.5v6M5 13.5v6M19 4.5v6M19 13.5v6M2.5 7.5h5M2.5 16.5h5M16.5 7.5h5M16.5 16.5h5M5 10.5v3M19 10.5v3M9 10.2h6v3.6h-6zM10.9 6.8h2.2v3.4h-2.2zM10.9 13.8h2.2v3.4h-2.2z",
    lunar_habitat: "M1.8 18.8c3.2-1.5 6.6-2.2 10.2-2.2s7 .7 10.2 2.2M5.9 17.1a6.1 6.1 0 0 1 12.2 0M6.9 13.9h10.2M12 11v2.9M11 17v-1.9h2V17M4 21.3h2.4M16.2 21.5h3" + circ(18.6, 5.4, 2.4) + "M17.5 3.3a3.4 3.4 0 0 0 0 4.2M5.2 6.8h.01M9.4 4.4h.01",
    spacesuit: circ(12, 10.3, 7) + "M7.3 9.6c0-2.6 2.1-4.3 4.7-4.3s4.7 1.7 4.7 4.3c0 2.3-2.1 3.6-4.7 3.6s-4.7-1.3-4.7-3.6zM9.4 8.3c.6-.9 1.5-1.4 2.6-1.5M7.8 16.6h8.4M3.6 22.5c0-3.1 2.1-5.1 4.9-5.8M20.4 22.5c0-3.1-2.1-5.1-4.9-5.8",
    earth: circ(12, 12, 8.5) + "M12 3.5c-2.6 2.4-3.9 5.2-3.9 8.5s1.3 6.1 3.9 8.5M12 3.5c2.6 2.4 3.9 5.2 3.9 8.5s-1.3 6.1-3.9 8.5M3.5 12h17M4.7 7.9h14.6M4.7 16.1h14.6"
  };
  const P2D = {}; const path = g => P2D[g] || (P2D[g] = new Path2D(GLYPH[g]));
  function glyph(x, L, g, cx, cy, R, t, k, a) {
    if (!GLYPH[g] || a <= 0) return;
    const S = R * 2.9, sc = S / 24, f = flick(t);
    x.save(); x.globalAlpha = a;
    // a soft glow behind the drawing: the flame's colours, faint
    const hg = x.createRadialGradient(cx, cy, 0, cx, cy, S * .75), B = L ? F.bluL : F.blu, O = L ? F.orgL : F.org;
    hg.addColorStop(0, rgba(O, (L ? .06 : .10) * (1 + k))); hg.addColorStop(.55, rgba(B, (L ? .05 : .09) * (1 + k))); hg.addColorStop(1, rgba(B, 0));
    x.fillStyle = hg; x.beginPath(); x.arc(cx, cy, S * .75, 0, TAU); x.fill();
    x.translate(cx - S / 2 * f, cy - S / 2 * f); x.scale(sc * f, sc * f);
    x.lineCap = "round"; x.lineJoin = "round";
    x.shadowColor = rgba(O, L ? .35 : .75); x.shadowBlur = (8 + 10 * k) * sc;
    x.strokeStyle = rgba(L ? [12, 12, 16] : F.pale, .35); x.lineWidth = 1.6; x.stroke(path(g));
    x.shadowColor = rgba(B, L ? .3 : .6); x.shadowBlur = 4 * sc;
    x.strokeStyle = L ? "rgba(12,12,16,.88)" : "rgba(246,247,255,.95)"; x.lineWidth = 1.05; x.stroke(path(g));
    x.restore();
  }
  const flick = t => 1 + .018 * Math.sin(9.1 * t) + .012 * Math.sin(13.7 * t + 1.3) + .008 * Math.sin(23.3 * t + 2.1);

  function ring(x, L, cx, cy, R, t, k) {
    const f = flick(t), Rf = R * (1 + .07 * k) * f, a = (.93 + .07 * Math.sin(t * 7.7 + .5)) * (1 + .25 * k);
    x.save(); x.globalCompositeOperation = L ? "source-over" : "lighter";
    const g = x.createRadialGradient(cx, cy, 0, cx, cy, Rf * 2.5), B = L ? F.bluL : F.blu, O = L ? F.orgL : F.org, W = L ? F.bluL : F.pale;
    [[0, O, 0], [.3, O, 0], [.37, O, L ? .35 : .42], [.41, W, L ? .75 : .95], [.45, B, L ? .45 : .55], [.56, B, .14], [.75, B, .04], [1, B, 0]].forEach(([p, c, al]) => g.addColorStop(p, rgba(c, al * a)));
    x.fillStyle = g; x.beginPath(); x.arc(cx, cy, Rf * 2.5, 0, TAU); x.fill();
    x.globalCompositeOperation = "source-over";
    const cg = x.createRadialGradient(cx, cy, 0, cx, cy, Rf * .9);
    cg.addColorStop(0, L ? "rgba(255,255,255,.95)" : "rgba(4,5,8,.92)"); cg.addColorStop(1, L ? "rgba(255,255,255,0)" : "rgba(4,5,8,0)");
    x.fillStyle = cg; x.beginPath(); x.arc(cx, cy, Rf * .9, 0, TAU); x.fill();
    x.fillStyle = L ? "rgba(12,12,16,.55)" : "rgba(255,240,210,.55)"; x.beginPath(); x.arc(cx, cy, Math.max(1, Rf * .08), 0, TAU); x.fill();
    x.restore();
  }

  function mount(cv, o = {}) {
    const x = cv.getContext("2d"), n = o.n || 90, R0 = o.R || 28, r = rng(o.seed || 7);
    const P = Array.from({ length: n }, () => ({ rad: 1.4 + Math.pow(r(), .85) * 2.1, inc: (63 + r() * 17) * Math.PI / 180, node: (r() - .5) * .55, ph: r() * TAU, sp: .6 + r() * .4, s: .5 + r() * .9, c: r() < .18 ? 1 : r() < .12 ? 2 : 0 }));
    let w = 1, h = 1, dpr = 1, raf = 0, last = 0, T = o.t0 || 3, k = 0, kT = 0, mx = -9999, my = -9999, lx = 0, ly = 0, on = true;
    let gCur = GLYPH[o.glyph] ? o.glyph : null, gOld = null, gm = 1;                 // glyph now, glyph fading out, mix 0..1
    const resize = () => { const b = cv.getBoundingClientRect(); w = Math.max(4, b.width); h = Math.max(4, b.height); dpr = Math.min(devicePixelRatio || 1, 2); cv.width = w * dpr | 0; cv.height = h * dpr | 0; draw(0); };
    function dust(L, cx, cy, R, front) {
      const C = [L ? [12, 12, 16] : [255, 255, 255], L ? F.bluL : F.pale, L ? F.orgL : F.org];
      for (const p of P) {
        const X0 = Math.cos(p.ph) * p.rad * R, Y0 = Math.sin(p.ph) * p.rad * R * Math.cos(p.inc), Z = Math.sin(p.ph) * Math.sin(p.inc);
        if ((Z >= 0) !== front) continue;
        const X = X0 * Math.cos(p.node) - Y0 * Math.sin(p.node), Y = X0 * Math.sin(p.node) + Y0 * Math.cos(p.node);
        if (Z < 0 && Math.hypot(X, Y) < R * .95) continue;                                    // hidden behind the flame
        const px = cx + X + lx * (Z + 1) / 2, py = cy + Y + ly * (Z + 1) / 2, dz = (Z + 1) / 2;
        const edge = Math.min(px, py, w - px, h - py), fe = cl(edge / 14, 0, 1); if (fe <= 0) continue;
        x.fillStyle = rgba(C[p.c], (.3 + .6 * dz) * fe * (L ? .8 : 1)); x.beginPath(); x.arc(px, py, p.s * (.7 + .5 * dz) * (o.dotScale || 1), 0, TAU); x.fill();
      }
    }
    function draw(dt) {
      const L = document.documentElement.dataset.theme === "light", cx = w / 2, cy = h / 2, R = Math.min(R0, w / 8, h / 3.2);
      k += (kT - k) * (1 - Math.exp(-dt * 2.2));
      for (const p of P) p.ph += dt * .5 * p.sp * Math.pow(1.4 / p.rad, 1.5) * (1 + 1.3 * k);
      if (o.lean !== false && mx > -999) { const b = cv.getBoundingClientRect(), tx = cl((mx - b.left - cx) * .025, -8, 8), ty = cl((my - b.top - cy) * .025, -6, 6); lx += (tx - lx) * (1 - Math.exp(-dt * 6)); ly += (ty - ly) * (1 - Math.exp(-dt * 6)); }
      else { lx *= Math.exp(-dt * 4); ly *= Math.exp(-dt * 4); }
      x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, w, h);
      if (gm < 1) gm = Math.min(1, gm + dt / .55);
      const e = gm * gm * (3 - 2 * gm);
      dust(L, cx, cy, R, false);
      const core = (g, a) => { if (a <= 0) return; if (g) glyph(x, L, g, cx + lx * .35, cy + ly * .35, R, T, k, a); else { x.save(); x.globalAlpha = a; ring(x, L, cx, cy, R, T, k); x.restore(); } };
      core(gOld, 1 - e); core(gCur, gm < 1 ? e : 1);
      dust(L, cx, cy, R, true);
      if (k > .04) { const q = (T % 2.3) / 2.3; x.strokeStyle = rgba(L ? F.bluL : F.pale, (1 - q) * .32 * k); x.lineWidth = 1; x.beginPath(); x.arc(cx, cy, R * (1.05 + q * 2.6), 0, TAU); x.stroke(); }
    }
    function loop(now) { if (!on) return; const dt = last ? Math.min(.05, (now - last) / 1000) : 1 / 60; last = now; T += dt; draw(dt); raf = requestAnimationFrame(loop); }
    const move = e => { mx = e.clientX; my = e.clientY; };
    addEventListener("pointermove", move, { passive: true });
    const ro = new ResizeObserver(resize); ro.observe(cv);
    let inView = false;
    const go = () => { if (inView && !RM && !document.hidden) { if (!raf) { on = true; last = 0; raf = requestAnimationFrame(loop); } } else { on = false; cancelAnimationFrame(raf); raf = 0; } };
    const io = new IntersectionObserver(es => { inView = es[0].isIntersecting; go(); });
    io.observe(cv);
    const vis = () => go();
    document.addEventListener("visibilitychange", vis);
    resize();
    if (RM) { for (let i = 0; i < 30; i++) { T += 1 / 30; draw(1 / 30); } }
    return { think(v) { kT = v ? 1 : 0; }, redraw: () => draw(0),
      setGlyph(g) { g = GLYPH[g] ? g : null; if (g === gCur) return; gOld = gCur; gCur = g; gm = RM || !raf ? 1 : 0; if (gm === 1) draw(0); },
      stop() { on = false; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); removeEventListener("pointermove", move); document.removeEventListener("visibilitychange", vis); } };
  }
  return { mount, has: g => !!GLYPH[g] };
})();
