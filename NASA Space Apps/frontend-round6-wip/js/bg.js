// BACKGROUND — sparse stars, and a faint dot grid that lights up under the cursor and fades behind it (design 3).
// Under it: a soft gradient and fine film grain (CSS, the grain texture is made here once), so the frosted widgets
// stand out. Also turns the prompt box's rim light: slowly at rest, faster while the AI is thinking. The angle is set
// on the prompt box itself, not the page, so only that box restyles each frame.
// One canvas behind everything; pauses when the tab is hidden; a still frame with reduced motion.
window.BG = (() => {
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches, TAU = Math.PI * 2, SP = 28, R = 130, SIG = 60;
  const cv = document.getElementById("bg"), x = cv.getContext("2d"), pb = document.getElementById("ask-form");
  // film grain: a small tile of soft noise, drawn once and repeated by CSS (body::after)
  (() => { try {
    const n = 140, g = document.createElement("canvas"); g.width = g.height = n; const c = g.getContext("2d"), im = c.createImageData(n, n), r = rng(7);
    for (let i = 0; i < n * n; i++) { const v = 128 + (r() + r() + r() - 1.5) * 150; im.data[i * 4] = im.data[i * 4 + 1] = im.data[i * 4 + 2] = v < 0 ? 0 : v > 255 ? 255 : v; im.data[i * 4 + 3] = 255; }
    c.putImageData(im, 0, 0); document.documentElement.style.setProperty("--grain", `url(${g.toDataURL("image/png")})`);
  } catch (e) {} })();
  let w = 1, h = 1, dpr = 1, stars = [], cols = 0, rows = 0, heat = new Float32Array(0), raf = 0, last = 0, T = 0;
  let mx = -9999, my = -9999, sx = -9999, sy = -9999, k = 0, kT = 0, ang = 0;
  function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2); w = innerWidth; h = innerHeight; cv.width = w * dpr | 0; cv.height = h * dpr | 0;
    const r = rng(20261115), n = Math.round(60 * Math.max(.4, Math.min(1.8, w * h / (1280 * 720))));
    stars = Array.from({ length: n }, () => { const q = r(); return { x: r() * w, y: r() * h, s: q < .82 ? .45 + r() * .45 : q < .985 ? .9 + r() * .5 : 1.45 + r() * .4, a: .3 + r() * .6, f: .25 + r() * 1.1, p: r() * TAU, d: .3 + r() * .7, c: r() < .09 ? 1 : r() < .08 ? 2 : 0 }; });
    cols = Math.ceil(w / SP) + 1; rows = Math.ceil(h / SP) + 1; heat = new Float32Array(cols * rows);
    draw(0);
  }
  const STC = { dark: [[255, 255, 255], [205, 222, 255], [255, 226, 186]], light: [[18, 18, 26], [44, 95, 224], [221, 95, 10]] };
  function draw(dt) {
    const L = document.documentElement.dataset.theme === "light", ink = L ? "12,12,16" : "255,255,255";
    x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, w, h);
    // stars, with a few pixels of parallax toward the pointer
    const ox = sx > -999 ? -(sx - w / 2) * .008 : 0, oy = sy > -999 ? -(sy - h / 2) * .008 : 0, C = STC[L ? "light" : "dark"];
    for (const s of stars) {
      const al = s.a * (.62 + .38 * Math.sin(T * s.f + s.p)) * (L ? .42 : 1), c = C[s.c], px = s.x + ox * s.d, py = s.y + oy * s.d;
      x.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${al.toFixed(3)})`;
      if (s.s < 1) { const z = s.s * (L ? 1.5 : 1.7); x.fillRect(px - z / 2, py - z / 2, z, z); }
      else { x.beginPath(); x.arc(px, py, s.s * (L ? .8 : 1), 0, TAU); x.fill(); }
    }
    // the cursor's dots: light up near the pointer, then fade out over about a second once it has passed
    if (sx > -999 && dt) {
      const c0 = Math.max(0, Math.floor((sx - R) / SP)), c1 = Math.min(cols - 1, Math.ceil((sx + R) / SP)), r0 = Math.max(0, Math.floor((sy - R) / SP)), r1 = Math.min(rows - 1, Math.ceil((sy + R) / SP));
      for (let j = r0; j <= r1; j++) for (let i = c0; i <= c1; i++) {
        const X = SP / 2 + i * SP, Y = SP / 2 + j * SP, d2 = (X - sx) ** 2 + (Y - sy) ** 2; if (d2 > R * R) continue;
        const a = .46 * Math.exp(-d2 / (2 * SIG * SIG)), q = j * cols + i; if (a > heat[q]) heat[q] = a;
      }
    }
    const fade = dt ? Math.exp(-dt / .55) : 1;
    x.fillStyle = `rgb(${ink})`;
    for (let q = 0; q < heat.length; q++) {
      const v = heat[q]; if (v < .012) { heat[q] = 0; continue; }
      x.globalAlpha = v * (L ? .85 : 1); const i = q % cols, j = (q / cols) | 0;
      x.beginPath(); x.arc(SP / 2 + i * SP, SP / 2 + j * SP, 1.1, 0, TAU); x.fill();
      heat[q] = v * fade;
    }
    x.globalAlpha = 1;
    // the ask box rim: angle eased between a slow drift and a faster turn while thinking
    k += (kT - k) * (1 - Math.exp(-dt * 1.8)); ang += dt * (.22 + 1.1 * k);
    if (pb) pb.style.setProperty("--ra", (ang * 180 / Math.PI % 360).toFixed(1) + "deg");
  }
  function loop(now) { const dt = last ? Math.min(.05, (now - last) / 1000) : 1 / 60; last = now; T += dt;
    if (mx > -999) { if (sx < -999) { sx = mx; sy = my; } else { const f = 1 - Math.exp(-dt * 14); sx += (mx - sx) * f; sy += (my - sy) * f; } } else sx = sy = -9999;
    draw(dt); raf = requestAnimationFrame(loop); }
  function start() { if (RM || raf) return; last = 0; raf = requestAnimationFrame(loop); }
  function stop() { cancelAnimationFrame(raf); raf = 0; }
  addEventListener("pointermove", e => { if (e.pointerType === "touch") return; mx = e.clientX; my = e.clientY; }, { passive: true });
  document.addEventListener("pointerleave", () => { mx = my = -9999; });
  addEventListener("blur", () => { mx = my = -9999; });
  document.addEventListener("visibilitychange", () => document.hidden ? stop() : start());
  addEventListener("resize", resize);
  resize(); start();
  return { thinking(on) { kT = on ? 1 : 0; }, redraw: () => { if (!raf) draw(0); } };
})();
