// MODEL WIDGETS — real charts drawn from the thermo team's model outputs (data/model_outputs.js).
// Preview first (model-widgets.html); each is added to the main library once approved.
// Charts use the CH kit (js/charts.js): drawn at each box's real size, in the same ink / bone / mono style as the widgets.
// Monochrome: series told apart by solid / dashed / outline, never colour.
// Written with SI assistance (Claude, Anthropic).
window.MW = (() => {
  const { esc } = U;
  const { host, frame, line, dot, vref, href, chip, chipRows, hatchDef, caps, title, titleW, T, range, scale, r1, monoW, capsW, tkSize, CHIP_H } = CH;
  const M = () => DATA.modelOutputs;
  const sel = (name, opts, cur) => `<select name="${name}">${Object.entries(opts).map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
  const slider = (name, label, min, max, step, val, unit) =>
    `<label class="slider">${esc(label)} <input type="range" name="${name}" min="${min}" max="${max}" step="${step}" value="${val}"> <output>${val}</output> ${esc(unit)}</label>`;
  const STATUS = {
    physics: `<span class="badge" data-tag="semi_empirical">[Model calculation]</span>`,
    reconstruction: `<span class="badge" data-tag="direct_psi">[Reconstructs NASA FLEX run]</span>`,
    estimate: `<span class="badge" data-tag="semi_empirical">[Model estimate]</span>`,
    synthetic: `<span class="badge" data-tag="synthetic">[SYNTHETIC material]</span>`
  };

  // ---------- THM-02 ----------
  const regimeShort = le => le < 0.9 ? "unstable — cellular / flame-ball risk" : le <= 1.1 ? "neutral — smooth flame" : "damped — quench-prone";

  // A single log-scale strip: unstable | neutral | quench-prone, with each fuel marked on it
  function lewisGauge() {
    return host(sz => {
      const { w, h, compact: c, id } = sz, g = M().THM02.gauge_in_air, F = M().THM02.fuels, fs = tkSize(c);
      const sx = scale(0.2, 6, 2, w - 2, true), bh = c ? 24 : Math.round(Math.min(48, Math.max(30, h * 0.09))), step = CHIP_H + 6;
      const need = 18 + bh + fs + 12 + step * 2 + (c ? 0 : 18);
      const by0 = Math.max(18, Math.round((h - need) / 2) + 18), by1 = by0 + bh;
      const hid = id + "-h", seg = (a, b, attrs) => `<rect x="${r1(sx(a))}" y="${by0}" width="${r1(sx(b) - sx(a))}" height="${bh}" ${attrs}/>`;
      let s = hatchDef(hid) + seg(0.2, 0.9, `fill="url(#${hid})"`) + seg(0.9, 1.1, `class="paper"`) + seg(1.1, 6, `class="band"`);
      s += `<rect class="frame" x="${r1(sx(0.2))}" y="${by0}" width="${r1(sx(6) - sx(0.2))}" height="${bh}"/>` +
        [0.9, 1.1].map(v => `<line class="base" x1="${r1(sx(v))}" x2="${r1(sx(v))}" y1="${by0}" y2="${by1}"/>`).join("");
      s += caps(sx(Math.sqrt(0.2 * 0.9)), by0 - 7, "Unstable", "middle") + caps(sx(1), by0 - 7, "Neutral", "middle") + caps(sx(Math.sqrt(1.1 * 6)), by0 - 7, sx(6) - sx(1.1) > capsW("Quench-prone", 10.5) * 1.6 ? "Quench-prone" : "Quench", "middle");
      s += T(sx(0.9) - 4, by1 + fs + 3, "0.9", "tk", "end") + T(sx(1.1) + 4, by1 + fs + 3, "1.1", "tk");
      const fuels = Object.entries(g).sort((a, b) => a[1].Le - b[1].Le);
      s += fuels.map(([, v]) => `<line class="mk" x1="${r1(sx(v.Le))}" x2="${r1(sx(v.Le))}" y1="${by0 - 2}" y2="${by1 + 2}"/>`).join("");
      const rows = chipRows(fuels.map(([f, v]) => ({ x: sx(v.Le), anchor: "middle", text: `${F[f]} ${v.Le.toFixed(2)}`, leader: by1 + 2 })),
        by1 + fs + 12 + CHIP_H / 2, step, { compact: c, bounds: w });
      s += rows.svg;
      if (!c) s += title(w - 2, by1 + fs + 12 + rows.rows * step + 12, "Lewis number of the fuel", "log scale", "end");
      return s;
    }, { label: "Lewis number gauge" });
  }

  function mixerChart(f, d, p, o2) {
    const T2 = M().THM02, pts = T2.o2_values.map(o => [o, T2.grid[`${f}|${d}|${p}|${o}`]]).filter(([, v]) => v).map(([o, v]) => [o, v.Le]);
    const ys = pts.map(q => q[1]), lo = Math.min(...ys, 0.9), hi = Math.max(...ys, 1.1);
    const stp = hi - lo > 3 ? 1 : hi - lo > 1.2 ? 0.5 : 0.25;
    const y0 = Math.max(0, Math.floor(lo * 0.9 / stp) * stp), y1 = Math.ceil(hi * 1.12 / stp) * stp, cur = T2.grid[`${f}|${d}|${p}|${o2}`];
    const yt = []; for (let v = y0; v <= y1 + 1e-9; v += stp) yt.push(Math.round(v * 100) / 100);
    return host(sz => {
      const F = frame(sz, { x: [15, 100], y: [y0, y1], xticks: [15, 21, 30, 40, 50, 60, 75, 100], yticks: yt, xlabel: "Oxygen", xunit: "%", ylabel: "Lewis number" });
      const { sx, sy, X0, X1, Y0, Y1, c } = F, bt = sy(Math.min(1.1, y1)), bb = sy(Math.max(0.9, y0));
      let s = `<rect class="band" x="${X0}" y="${r1(bt)}" width="${r1(X1 - X0)}" height="${r1(bb - bt)}"/>` + F.axes;
      s += title(X1 - 4, bt - 5 < Y1 + 8 ? bb + 12 : bt - 5, "Neutral", "0.9–1.1", "end");
      s += line(pts, sx, sy);
      if (cur) {
        const x = sx(o2), y = sy(cur.Le), right = x > (X0 + X1) / 2, cy = y - 18 < Y1 + 9 ? y + 20 : y - 18;
        s += dot(x, y, { r: 5 }) + chip(right ? x - 8 : x + 8, cy, `Le ${cur.Le} at ${o2}% O₂`, { anchor: right ? "end" : "start", dark: true, compact: c, bounds: sz.w });
      }
      return s;
    }, { label: "Lewis number against oxygen" });
  }
  function mixerReadout(f, d, p, o2) {
    const v = M().THM02.grid[`${f}|${d}|${p}|${o2}`];
    if (!v) return `<p class="readout">No mixture: 2% fuel + ${o2}% O₂ exceeds 100%.</p>`;
    return `<div class="readout-grid">
      <div><b>${v.Le}</b><span>Lewis <em>Le</em></span></div><div><b>${v.Pr}</b><span>Prandtl <em>Pr</em></span></div><div><b>${v.Sc}</b><span>Schmidt <em>Sc</em></span></div>
      <div><b>${(v.k * 1000).toFixed(1)}</b><span>Conductivity <em>k · mW/m·K</em></span></div><div><b>${v.alpha.toExponential(2)}</b><span>Heat diffusivity <em>α · m²/s</em></span></div><div><b>${v.D.toExponential(2)}</b><span>O₂ diffusivity <em>D · m²/s</em></span></div></div>
      <p class="readout">${esc(regimeShort(v.Le))}</p>`;
  }

  // small legend key: solid / outline square + uppercase label, right-aligned on the title row
  function key(items, xr, y, c) {
    const fs = c ? 10 : 10.5; let x = xr, s = "";
    items.slice().reverse().forEach(([label, unit, cls]) => {
      x -= titleW(label, unit, fs);
      s += title(x, y, label, unit) + `<rect class="${cls}" x="${r1(x - 15)}" y="${r1(y - 9)}" width="10" height="10"/>`;
      x -= 28;
    });
    return s;
  }

  function lineKey(items, xr, y) {
    let x = xr, s = "";
    items.slice().reverse().forEach(([label, dashed]) => {
      x -= capsW(label, 10);
      s += caps(x, y, label) + `<path class="s${dashed ? " dash" : ""}" d="M${r1(x - 22)},${r1(y - 3.5)}h16"/>`;
      x -= 32;
    });
    return s;
  }

  function atmospheresChart() {
    return host(sz => {
      const A = M().THM02.atmospheres, keys = ["iss", "lunar_habitat", "spacesuit"], base = A.iss, c = sz.compact;
      const F = frame(sz, { x: [0, 3], y: [0, 4], yticks: [0, 1, 2, 3, 4], yfmt: v => "×" + v, ylabel: "Relative to ISS", bottom: c ? 2 : 16 });
      const { sy, X0, X1, Y0, fs } = F, gw = (X1 - X0) / 3, bw = Math.min(gw * 0.3, 52), gap = 4;
      let s = F.axes + key([["Heat", "α", "bar"], ["Oxygen", "D", "bar alt"]], X1, c ? 10 : 12, c);
      keys.forEach((k, i) => {
        const a = A[k], x0 = X0 + i * gw + (gw - 2 * bw - gap) / 2, mid = x0 + bw + gap / 2;
        [[a.alpha / base.alpha, "bar", "Heat diffusion"], [a.D / base.D, "bar alt", "Oxygen diffusion"]].forEach(([v, cls, n], j) => {
          const x = x0 + j * (bw + gap);
          s += `<rect class="${cls}" x="${r1(x)}" y="${r1(sy(v))}" width="${r1(bw)}" height="${r1(Y0 - sy(v))}"><title>${n} ×${v.toFixed(2)}</title></rect>`;
          if (bw >= 22) s += T(x + bw / 2, sy(v) - 6, v.toFixed(2), "val", "middle");
        });
        s += T(mid, Y0 + fs + 6, a.label, "gl", "middle");
        if (!c) s += T(mid, Y0 + fs + 21, `${a.o2_pct}% O₂ · ${a.pressure_kPa} kPa`, "tk", "middle");
      });
      return s;
    }, { label: "Heat and oxygen diffusion in each atmosphere, relative to the ISS" });
  }

  // two small bar panels side by side, values written on the bars (no y axis needed)
  function diluentCharts() {
    return host(sz => {
      const { w, h, compact: c } = sz, D = M().THM02.diluents_for_heptane, N = { N2: "N₂", CO2: "CO₂", HE: "He" }, order = ["N2", "CO2", "HE"], fs = tkSize(c);
      const gap = c ? 18 : 32, pw = (w - gap) / 2, Y0 = h - (c ? 20 : 24), top = c ? 34 : 44;
      const panel = (x0, name, unit, get, digits) => {
        const vals = order.map(k => get(D[k])), max = Math.max(...vals), sy = scale(0, max, Y0, top);
        const slot = pw / 3, bw = Math.min(slot * 0.56, 64);
        let s = title(x0, c ? 10 : 12, name, unit) + `<line class="base" x1="${r1(x0)}" x2="${r1(x0 + pw)}" y1="${Y0}" y2="${Y0}"/>`;
        order.forEach((k, i) => {
          const v = vals[i], x = x0 + i * slot + (slot - bw) / 2;
          s += `<rect class="bar" x="${r1(x)}" y="${r1(sy(v))}" width="${r1(bw)}" height="${r1(Y0 - sy(v))}"><title>${N[k]}: ${v.toFixed(digits)}</title></rect>` +
            T(x + bw / 2, sy(v) - 6, v.toFixed(digits), "val", "middle") + T(x + bw / 2, Y0 + fs + 6, N[k], "gl", "middle");
        });
        return s;
      };
      return panel(0, c ? "Conductivity" : "Heat conductivity", "mW/m·K", d => d.k * 1000, 1) +
        `<line class="grid-v" x1="${r1(pw + gap / 2)}" x2="${r1(pw + gap / 2)}" y1="0" y2="${Y0}"/>` +
        panel(pw + gap, c ? "Lewis no." : "Lewis number", "n-heptane", d => d.Le, 2);
    }, { label: "Nitrogen, carbon dioxide and helium compared" });
  }

  // ---------- THM-11 ----------
  function dropletChart(id) {
    return host(sz => {
      const R = M().THM11.runs[id], pts = R.time_s.map((t, i) => [t, R.d2_mm2[i]]), c = sz.compact;
      const hot = R.hot_extinction_time_s, tEnd = R.cool_extinction_time_s, obs = R.held_out_check && R.held_out_check.observed_cool_extinction_time_s;
      const xmax = Math.max(28, Math.ceil(tEnd + 2));
      const F = frame(sz, { x: [0, xmax], y: [0, 18], xticks: range(0, Math.floor(xmax / 5) * 5, Math.floor(xmax / 5)), yticks: [0, 5, 10, 15],
        xlabel: "Time since burning began", xunit: "s", ylabel: "Droplet diameter²", yunit: "mm²" });
      const { sx, sy, X0, Y0, Y1 } = F, hid = sz.id + "-h";
      let s = hatchDef(hid) + `<rect class="band" x="${X0}" y="${Y1}" width="${r1(sx(hot) - X0)}" height="${r1(Y0 - Y1)}"/>` +
        `<rect fill="url(#${hid})" x="${r1(sx(hot))}" y="${Y1}" width="${r1(sx(tEnd) - sx(hot))}" height="${r1(Y0 - Y1)}"/>` + F.axes;
      if (sx(hot) - X0 > 80) s += caps(X0 + 6, Y0 - 7, "Hot flame");
      if (sx(tEnd) - sx(hot) > 84) s += caps(sx(hot) + 6, Y0 - 7, "Cool flame");
      s += vref(sx(hot), Y0, Y1) + vref(sx(tEnd), Y0, Y1);
      const ci = R.phase.indexOf("cool_flame");
      s += line(pts.filter((_, i) => R.phase[i] === "hot_flame").concat([pts[ci]]), sx, sy) + line(pts.filter((_, i) => R.phase[i] === "cool_flame"), sx, sy, { dashed: true });
      const items = c ? [{ x: sx(tEnd) - 4, anchor: "end", text: `${hot.toFixed(1)} → ${tEnd.toFixed(1)} s` }]
        : [{ x: sx(hot) + 4, anchor: "start", text: `flame out ${hot.toFixed(1)} s` }, { x: sx(tEnd) - 4, anchor: "end", text: `burning ends ${tEnd.toFixed(1)} s · model` }];
      if (obs) {
        s += `<line class="mk" x1="${r1(sx(obs))}" x2="${r1(sx(obs))}" y1="${Y0}" y2="${r1(Y1 + (c ? 36 : 40))}"/>`;
        items.push({ x: sx(obs) - 4, anchor: "end", text: c ? `NASA ≈${obs} s` : `NASA observed ≈${obs} s`, dark: true });
      }
      s += chipRows(items, Y1 + 4 + CHIP_H / 2, CHIP_H + 5, { compact: c, bounds: sz.w }).svg;
      return s;
    }, { label: "Droplet diameter squared against time" });
  }

  function heldOutChart() {
    return host(sz => {
      const { w, h, compact: c } = sz, R = M().THM11.runs.R379, ho = R.held_out_check, fs = tkSize(c);
      const rows = c ? ["Model", "NASA"] : ["Model predicts", "NASA observed"], lw = Math.max(...rows.map(r => capsW(r, c ? 10 : 10.5)));
      const L = lw + 14, sx = scale(0, 30, L, w - (c ? 44 : 58)), bh = c ? 16 : Math.round(Math.min(36, Math.max(22, h * 0.07))), rg = c ? 10 : 14;
      const need = bh * 2 + rg + 34 + fs + 10 + (c ? 0 : 18), y0 = Math.max(6, Math.round((h - need) / 2));
      const yA = y0, yB = y0 + bh + rg, yBr = yB + bh + 14, yAx = yBr + 26;
      let s = [0, 10, 20, 30].map(v => `<line class="grid-v" x1="${r1(sx(v))}" x2="${r1(sx(v))}" y1="${yA - 4}" y2="${yAx}"/>` + T(sx(v), yAx + fs + 4, v + " s", "tk", "middle")).join("");
      const bar = (y, t, cls, label) => caps(L - 12, y + bh / 2 + 4, label, "end") +
        `<rect class="${cls}" x="${r1(sx(0))}" y="${y}" width="${r1(sx(t) - sx(0))}" height="${bh}"/>` + T(sx(t) + 8, y + bh / 2 + 4.5, t.toFixed(1) + " s", "val");
      s += bar(yA, R.cool_extinction_time_s, "bar", rows[0]) + bar(yB, ho.observed_cool_extinction_time_s, "bar alt dash", rows[1]);
      const a = sx(ho.observed_cool_extinction_time_s), b = sx(R.cool_extinction_time_s);
      s += `<path class="bracket" d="M${r1(a)},${yBr - 5}V${yBr}H${r1(b)}V${yBr - 5}"/>`;
      s += chip((a + b) / 2, yBr + 1, `+${ho.model_minus_observed_s.toFixed(1)} s late`, { anchor: "middle", dark: true, compact: c, bounds: w });
      if (!c) s += title(w - 2, yAx + fs + 26, "Cool-flame end", "FLEX R379 · 17% O₂ · 3.86 mm n-decane", "end");
      return s;
    }, { label: "Model prediction against NASA observation" });
  }

  // ---------- THM-16 ----------
  function heatingChart(flux) {
    return host(sz => {
      const T16 = M().THM16, R = T16.by_flux[String(flux)], crit = T16.ignition_criterion_K, c = sz.compact;
      const s1 = R.time_s.map((t, i) => [t, R.surface_K[i]]), s2 = R.time_s.map((t, i) => [t, R.back_K[i]]);
      const F = frame(sz, { x: [0, 90], y: [280, 700], xticks: [0, 15, 30, 45, 60, 75, 90], yticks: [300, 400, 500, 600, 700],
        xlabel: "Heating time", xunit: "s", ylabel: "Temperature", yunit: "K" });
      const { sx, sy, X0, X1, Y1 } = F;
      let s = F.axes + href(sy(crit), X0, X1) + title(X0 + 6, sy(crit) - 6, "Ignition point", crit + " K");
      s += line(s1, sx, sy) + line(s2, sx, sy, { dashed: true });
      const at = (arr, t) => arr.reduce((p, q) => Math.abs(q[0] - t) < Math.abs(p[0] - t) ? q : p);
      const tlast = R.time_s[R.time_s.length - 1], p1 = at(s1, tlast * 0.4), p2 = at(s2, tlast * 0.82);
      if (c) s += lineKey([["Surface", false], ["Back", true]], sz.w, 10);
      else s += caps(sx(p1[0]) + 6, sy(p1[1]) + 16, "Surface") + caps(sx(p2[0]), sy(p2[1]) - 9, "Back face", "end");
      if (R.time_to_ignition_s) {
        const x = sx(R.time_to_ignition_s), y = sy(crit), ts = R.time_to_ignition_s.toFixed(1), cy = Math.max(Y1 + 9, y - 18);
        let txt = ts + " s", side = "left";                                   // fallback: short text, kept clear of the axis
        for (const cand of [`ignites at ${ts} s`, ts + " s"]) {
          const wd = CH.chipBox(cand, c).w;
          if (x + 9 + wd < X1) { txt = cand; side = "right"; break; }
          if (x - 9 - wd > X0 + 2) { txt = cand; side = "left"; break; }
        }
        s += dot(x, y, { r: 5 }) + chip(side === "right" ? x + 9 : x - 9, cy, txt, { anchor: side === "right" ? "start" : "end", dark: true, compact: c, bounds: sz.w, min: X0 + 2 });
      } else s += chip(X1, Y1 + 9, `no ignition in 90 s`, { anchor: "end", compact: c, bounds: sz.w });
      return s;
    }, { label: "Surface and back-face temperature while heating" });
  }

  function heatmap() {
    return host(sz => {
      const H = M().THM16.heatmap_35kW, t = H.time_s, z = H.depth_mm, rows = H.T_K, c = sz.compact;
      const dt = t[1] - t[0], dz = z[1] - z[0], tmax = t[t.length - 1] + dt, zmax = z[z.length - 1] + dz;
      const lo = 295, hi = Math.max(...rows.flat());
      const F = frame(sz, { x: [0, tmax], y: [zmax, 0], xticks: [0, 10, 20, 30, 40], yticks: [0, 1, 2, 3, 4],
        xlabel: "Heating time", xunit: "s · at 35 kW/m²", ylabel: "Depth", yunit: "mm" });
      const { sx, sy, X1, Y1, fs } = F;
      const P = [250, 248, 243], K = [17, 17, 17], grey = f => `rgb(${P.map((p, i) => Math.round(p + (K[i] - p) * f)).join(",")})`;
      let s = F.axes;
      rows.forEach((row, i) => row.forEach((v, j) => {
        const x = sx(t[j]), y = sy(z[i]);
        s += `<rect x="${r1(x)}" y="${r1(y)}" width="${r1(sx(t[j] + dt) - x + 0.6)}" height="${r1(sy(z[i] + dz) - y + 0.6)}" fill="${grey((v - lo) / (hi - lo) * 0.92)}"/>`;
      }));
      const lw = c ? 48 : 80, ly = c ? 3 : 4, hiL = Math.round(hi) + " K", x1 = X1 - monoW(hiL, fs) - 6, x0 = x1 - lw;
      if (x0 - monoW(lo + " K", fs) - 6 > titleW("Depth", "mm", c ? 10 : 10.5) + 16) {
        s += range(0, 1, 15).slice(0, 15).map(f => `<rect x="${r1(x0 + f * lw)}" y="${ly}" width="${r1(lw / 15 + 0.5)}" height="9" fill="${grey(f * 0.92 + 0.03)}"/>`).join("") +
          `<rect class="frame" x="${r1(x0)}" y="${ly}" width="${lw}" height="9"/>` + T(x0 - 6, ly + 8.5, lo + " K", "tk", "end") + T(x1 + 6, ly + 8.5, hiL, "tk");
      }
      return s;
    }, { label: "Temperature through the slab over time" });
  }

  function ignitionVsFlux() {
    return host(sz => {
      const B = M().THM16.by_flux, pts = Object.entries(B).map(([f, v]) => [+f, v.time_to_ignition_s]), c = sz.compact;
      const F = frame(sz, { x: [5, 45], y: [0, 100], xticks: [10, 15, 20, 25, 30, 35, 40], yticks: [0, 30, 60, 90],
        xlabel: "Heat flux", xunit: "kW/m²", ylabel: "Time to ignition", yunit: "s" });
      const { sx, sy, X0, X1 } = F, ig = pts.filter(p => p[1]), no = pts.filter(p => !p[1]);
      let s = F.axes + href(sy(90), X0, X1);
      if (!c) s += title(X1, sy(90) + 15, "End of test", "90 s", "end");
      s += line(ig, sx, sy) + ig.map(([f, t]) => dot(sx(f), sy(t), { tip: `${f} kW/m²: ${t.toFixed(1)} s` }) + T(sx(f) + 8, sy(t) - 7, t.toFixed(0) + " s", "tk")).join("");
      s += no.map(([f]) => dot(sx(f), sy(96), { hollow: true, tip: `${f} kW/m²: no ignition within 90 s` })).join("");
      if (no.length) s += caps(sx(no[no.length - 1][0]) + 10, sy(96) + 4, c ? "No ignition" : "No ignition in 90 s");
      return s;
    }, { label: "Time to ignition against heat flux" });
  }

  // ---------- registry ----------
  const R = {
    thm02_lewis_gauge: { model: "THM-02", title: "Lewis number gauge", cat: "visual", status: "physics", size: "w",
      desc: "Where each fuel's flame sits between unstable (Le < 0.9), neutral and quench-prone (Le > 1.1). Fuel at 2% in air, 300 K, 1 atm.",
      render: () => lewisGauge() },
    thm02_gas_mixer: { model: "THM-02", title: "Gas mixer", cat: "interactive", status: "physics", size: "b",
      desc: "Pick a fuel, diluent and cabin pressure, then slide the oxygen level. Every number is from THM-02's kinetic-theory calculation (pre-computed grid, 300 K, 2% fuel).",
      render: () => `<div class="controls">${sel("fuel", M().THM02.fuels, "C7H16")}${sel("dil", M().THM02.diluents, "N2")}${sel("p", M().THM02.pressures, "70.3")}
          ${slider("o2", "O₂", 15, 95, 5, 30, "%")}</div><div class="chart-slot">${mixerChart("C7H16", "N2", "70.3", 30)}</div><div class="read-slot">${mixerReadout("C7H16", "N2", "70.3", 30)}</div>`,
      mount: el => { const f = el.querySelector("[name=fuel]"), d = el.querySelector("[name=dil]"), p = el.querySelector("[name=p]"), o = el.querySelector("[name=o2]");
        const draw = () => { el.querySelector("output").textContent = o.value; el.querySelector(".chart-slot").innerHTML = mixerChart(f.value, d.value, p.value, +o.value);
          el.querySelector(".read-slot").innerHTML = mixerReadout(f.value, d.value, p.value, +o.value); };
        [f, d, p, o].forEach(x => x.addEventListener("input", draw)); } },
    thm02_atmospheres: { model: "THM-02", title: "How gases move in each atmosphere", cat: "graph", status: "physics", size: "w",
      desc: "Heat and oxygen diffuse faster at low pressure: about 1.4× faster in a lunar habitat and 3.5× in a spacesuit than on the ISS. Their ratio (Lewis number ≈ 1.02) barely changes.",
      render: () => atmospheresChart() },
    thm02_diluents: { model: "THM-02", title: "Nitrogen vs CO₂ vs helium", cat: "graph", status: "physics", size: "w",
      desc: "Swapping nitrogen for helium makes the gas ~4× better at conducting heat and roughly doubles n-heptane's Lewis number — one reason helium behaves differently as a suppressant (FLEX).",
      render: () => diluentCharts() },
    thm11_droplet: { model: "THM-11", title: "Droplet burning: hot → cool flame", cat: "interactive", status: "reconstruction", size: "w",
      desc: "An n-decane droplet shrinks steadily while the visible flame burns, then keeps burning as an almost invisible cool flame. R377 reconstructs a real FLEX test; R379 is a model estimate checked against NASA's observation.",
      render: () => `<div class="controls">${sel("run", { R377: "FLEX run R377 · 21% O₂ · 4.03 mm", R379: "FLEX run R379 · 17% O₂ · 3.86 mm" }, "R377")}</div><div class="chart-slot">${dropletChart("R377")}</div>`,
      mount: el => { const s = el.querySelector("[name=run]"); s.addEventListener("input", () => { el.querySelector(".chart-slot").innerHTML = dropletChart(s.value);
        const b = el.querySelector("header .badge"); if (b) b.outerHTML = STATUS[s.value === "R377" ? "reconstruction" : "estimate"]; }); } },
    thm11_held_out: { model: "THM-11", title: "Model vs NASA observation", cat: "explanation", status: "estimate", size: "w",
      desc: "Honest check: for run R379 the model's cool-flame end comes about 11 s after the ≈13 s NASA observed. Shows where the model needs more evidence.",
      render: () => heldOutChart() },
    thm11_facts: { model: "THM-11", title: "Droplet key facts (R377)", cat: "data", status: "reconstruction", size: "w",
      desc: "Headline numbers for FLEX run R377 from THM-11.",
      render: () => { const R = M().THM11.runs.R377;
        return `<div class="facts"><div><span>Visible flame goes out</span><b>${R.hot_extinction_time_s.toFixed(1)} s</b></div><div><span>Cool flame lasts</span><b>${R.cool_stage_duration_s.toFixed(1)} s</b></div><div><span>Burning ends</span><b>${R.cool_extinction_time_s.toFixed(1)} s</b></div></div>`; } },
    thm16_heating: { model: "THM-16", title: "Heating to ignition", cat: "interactive", status: "synthetic", size: "w",
      desc: "How fast a solid's surface heats under a radiant heater, and when it reaches the ignition temperature. Slide the heat flux. Material is the thermo team's synthetic 4 mm demo slab.",
      render: () => `<div class="controls">${slider("flux", "Heat flux", 10, 40, 5, 35, "kW/m²")}</div><div class="chart-slot">${heatingChart(35)}</div>`,
      mount: el => { const s = el.querySelector("input"); s.addEventListener("input", () => { el.querySelector("output").textContent = s.value; el.querySelector(".chart-slot").innerHTML = heatingChart(+s.value); }); } },
    thm16_heatmap: { model: "THM-16", title: "Heat soaking into the material", cat: "visual", status: "synthetic", size: "w",
      desc: "Temperature through the slab's thickness over time (darker = hotter) until the surface ignites, at 35 kW/m².",
      render: () => heatmap() },
    thm16_ignition_vs_flux: { model: "THM-16", title: "Ignition time vs heat flux", cat: "graph", status: "synthetic", size: "w",
      desc: "Stronger heating ignites the material sooner; at 25 kW/m² and below it doesn't ignite within 90 s.",
      render: () => ignitionVsFlux() },
    thm16_fact: { model: "THM-16", title: "Time to ignition", cat: "data", status: "synthetic", size: "s",
      desc: "Headline number from THM-16 for the synthetic slab at 35 kW/m².",
      render: () => `<div class="facts one"><div><span>Ignites after</span><b>${M().THM16.by_flux["35"].time_to_ignition_s.toFixed(0)} s</b><span>at 35 kW/m² · synthetic slab</span></div></div>` }
  };

  // compact previews for dashboard tiles (default state, no controls)
  const TILE = {
    thm02_lewis_gauge: () => lewisGauge(), thm02_gas_mixer: () => mixerChart("C7H16", "N2", "70.3", 30),
    thm02_atmospheres: () => atmospheresChart(), thm02_diluents: () => diluentCharts(),
    thm11_droplet: () => dropletChart("R377"), thm11_held_out: () => heldOutChart(), thm11_facts: () => R.thm11_facts.render(),
    thm16_heating: () => heatingChart(35), thm16_heatmap: () => heatmap(), thm16_ignition_vs_flux: () => ignitionVsFlux(), thm16_fact: () => R.thm16_fact.render()
  };
  // Natural box shape of each chart, measured by rendering it at width:height 1.2 → 4.4 (see the contact sheet):
  // [best, narrowest that still reads well, widest that still reads well]. The tiler fits boxes to these.
  const SHAPE = { thm02_lewis_gauge: [2.8, 1.8, 3.6], thm02_gas_mixer: [1.7, 1.15, 2.5], thm02_atmospheres: [1.85, 1.3, 2.8], thm02_diluents: [1.9, 1.25, 3.0],
    thm11_droplet: [1.45, 1.05, 2.0], thm11_held_out: [2.5, 1.6, 4.0], thm11_facts: [2.6, 1.5, 4.5],
    thm16_heating: [1.8, 1.35, 2.5], thm16_heatmap: [1.8, 1.15, 2.8], thm16_ignition_vs_flux: [1.8, 1.25, 2.5], thm16_fact: [1.2, 0.8, 1.8] };

  function render(type) {
    const d = R[type];
    return `<section class="widget mw size-${d.size}" data-mw="${type}">
      <header><b>${esc(d.title)}</b><span class="kind">${esc(d.model)} · ${esc(d.cat)}</span>${STATUS[d.status]}</header>
      <p class="why">${esc(d.desc)}</p><div class="widget-body">${d.render()}</div></section>`;
  }
  function mountAll(root) { root.querySelectorAll("[data-mw]").forEach(el => { const d = R[el.dataset.mw]; if (d.mount) d.mount(el); }); }
  return { lib: R, types: () => Object.keys(R), render, mountAll, STATUS,
    tile: t => TILE[t](), shape: t => SHAPE[t] || [2, 1.4, 2.8], aspect: t => (SHAPE[t] || [2])[0], body: t => R[t].render(), mount: (el, t) => R[t] && R[t].mount && R[t].mount(el) };
})();
