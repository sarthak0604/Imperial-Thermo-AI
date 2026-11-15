// REPORT — "Download PDF": a summary of everything the AI wrote for this answer — overview, key facts, every finding
// with its charts (drawn in light ink), what the data can't say, next questions and the full reference list with links.
// jsPDF and the Inter font are loaded only when a PDF is asked for (vendor/). Works offline and from file://.
window.REPORT = (() => {
  let loading = null;
  const load = src => new Promise((res, rej) => { const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = () => rej(new Error("could not load " + src)); document.head.appendChild(s); });
  const ready = () => loading || (loading = Promise.all([window.jspdf ? 0 : load("vendor/jspdf.umd.min.js"), window.PDF_FONTS ? 0 : load("vendor/inter-pdf.js")]).catch(e => { loading = null; throw e; }));
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const plain = s => String(s ?? "").replace(/\*\*/g, "").replace(/[ \t]+/g, " ").trim();
  const STATUS = t => ANS.STATUS_LABEL[(W.def(t) || {}).status] || "";
  const figCap = (n, t, extra = "") => { const d = W.def(t); return [`Figure ${n}`, d.title, d.model, STATUS(t)].filter(Boolean).join("  ·  ") + extra; };
  const fit = (im, maxW, maxH = 82) => { let iw = Math.min(maxW, 150), ih = iw / im.aspect; if (ih > maxH) { ih = maxH; iw = ih * im.aspect; } return { iw, ih }; };

  // ---------- a chart as a PNG, drawn off-screen in the light theme ----------
  const PROPS = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity", "font-family", "font-size", "font-weight", "letter-spacing", "paint-order", "text-anchor", "rx", "ry"];
  async function chartPNG(t, wpx = 760, block = null) {
    const [aspect] = block ? [2] : MW.shape(t), a = Math.max(1.3, Math.min(2.6, aspect)), hpx = Math.round(wpx / a);
    const stage = document.createElement("div"); stage.className = "pdf-stage";
    stage.innerHTML = block ? `<div style="width:${wpx}px">${WORKFLOW.render(block)}</div>` : `<div style="width:${wpx}px;height:${hpx}px;display:flex">${MW.tile(t)}</div>`;
    document.body.appendChild(stage);
    try {
      await frame();
      const svg = stage.querySelector("svg.vc"); if (!svg) return null;
      const clone = svg.cloneNode(true), src = [svg, ...svg.querySelectorAll("*")], dst = [clone, ...clone.querySelectorAll("*")];
      src.forEach((el, i) => { const cs = getComputedStyle(el); dst[i].setAttribute("style", PROPS.map(p => `${p}:${cs.getPropertyValue(p)}`).filter(x => !/:\s*$/.test(x)).join(";")); });
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const PADX = 14, PADY = 8, w0 = +svg.getAttribute("width"), h0 = +svg.getAttribute("height"), w = w0 + 2 * PADX, h = h0 + 2 * PADY;   // room for labels that overhang the plot
      clone.setAttribute("viewBox", `${-PADX} ${-PADY} ${w} ${h}`); clone.setAttribute("width", w); clone.setAttribute("height", h);
      const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(clone));
      const img = new Image(); await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = url; });
      const c = document.createElement("canvas"), k = 2; c.width = w * k; c.height = h * k;
      const x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height);
      return { png: c.toDataURL("image/png"), aspect: w / h };
    } catch (e) { console.error(e); return null; }
    finally { stage.remove(); }
  }
  // widgets that are numbers, not charts (the "facts" tiles): their readings as text
  function factsText(t) { const d = document.createElement("div"); d.innerHTML = MW.tile(t); const fs = [...d.querySelectorAll(".facts > div")]; return fs.map(f => [...f.children].map(c => c.textContent.trim()).join(" ")).join(" · "); }

  async function download(M) {
    UI.toast("Preparing the PDF…");
    await ready();
    const { jsPDF } = window.jspdf, doc = new jsPDF({ unit: "mm", format: "a4", compress: true });
    doc.addFileToVFS("Inter-Regular.ttf", PDF_FONTS.regular); doc.addFont("Inter-Regular.ttf", "Inter", "normal");
    doc.addFileToVFS("Inter-SemiBold.ttf", PDF_FONTS.semibold); doc.addFont("Inter-SemiBold.ttf", "Inter", "bold");
    const PW = 210, PH = 297, ML = 18, CW = PW - 2 * ML, TOP = 18, BOT = PH - 18, INK = [11, 11, 13], MUTED = [95, 95, 103], FAINT = [150, 150, 158], ACC = [217, 88, 10];
    let y = TOP;
    const pt = s => s * 0.3528;
    const need = h => { if (y + h > BOT) { doc.addPage(); y = TOP; } };
    function text(s, o = {}) {
      const size = o.size || 10, lh = pt(size) * (o.lh || 1.45), ind = o.indent || 0;
      doc.setFont("Inter", o.bold ? "bold" : "normal"); doc.setFontSize(size); doc.setTextColor(...(o.color || INK));
      const lines = doc.splitTextToSize(plain(s), CW - ind - (o.right || 0));
      lines.forEach(l => { need(lh); doc.text(l, ML + ind, y + pt(size) * .82); y += lh; });
      y += o.gap ?? 1.5;
    }
    function label(s, o = {}) { need(9 + (o.keep || 0)); y += o.before ?? 5; doc.setFont("Inter", "bold"); doc.setFontSize(7.2); doc.setTextColor(...MUTED); doc.text(String(s).toUpperCase(), ML, y, { charSpace: .35 }); y += 2.2; doc.setDrawColor(225, 225, 228); doc.setLineWidth(.2); doc.line(ML, y, ML + CW, y); y += 4; }
    const refsOf = ns => { const u = [...new Set((ns || []).filter(Boolean))].sort((a, b) => a - b); return u.length ? " [" + u.join(", ") + "]" : ""; };

    // header
    doc.setFont("Inter", "bold"); doc.setFontSize(7.2); doc.setTextColor(...MUTED);
    doc.text("FLAME IN FREEFALL  ·  ANSWER REPORT", ML, y, { charSpace: .35 });
    doc.setFont("Inter", "normal"); doc.text(new Date(M.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }), ML + CW, y, { align: "right" });
    y += 3; doc.setDrawColor(...ACC); doc.setLineWidth(.6); doc.line(ML, y, ML + 14, y); y += 8;
    text(M.q, { size: 17, bold: true, lh: 1.25, gap: 2 });
    text(`${ANS.forWho(M)}  ·  ${M.live ? `AI: ${M.meta.provider || ""}${M.meta.model ? " / " + M.meta.model : ""}` : "Preview without the AI"}`, { size: 8.5, color: MUTED, gap: 2 });

    label("AI overview");
    text(M.title, { size: 13, bold: true, lh: 1.3, gap: 2 });
    if (M.summary) String(M.summary).split(/\n{2,}/).forEach(p => text(p, { size: 10.5, lh: 1.55, gap: 2.2 }));
    if (M.note) text(M.note, { size: 9.5, color: MUTED });

    if (M.facts.length) {
      label("Key facts");
      M.facts.forEach(f => { need(12); text(f.value, { size: 12.5, bold: true, gap: .4 }); text(f.label + refsOf(f.refs) + (f.source ? "  ·  " + f.source : ""), { size: 9, color: MUTED, gap: 2.6 }); });
    }

    let fig = 0;
    if (M.blocks?.length) {
      label("Computed results");
      for (const block of M.blocks) {
        WORKFLOW.text(block).split('\n').forEach(line => text(line, { size: 9.5 }));
        if (block.type === 'chart' && block.chart_type !== 'bar') {
          for (const series of block.series) {
            const im = await chartPNG(null, 760, { ...block, series: [series] });
            if (im) {
              const { iw, ih } = fit(im, CW); need(ih + 9);
              doc.addImage(im.png, "PNG", ML, y, iw, ih, undefined, "FAST"); y += ih + 1.5;
              text(`${block.title || 'Computed chart'} · ${series.label}`, { size: 8, color: MUTED, gap: 4 });
            }
          }
        }
      }
    }
    if (M.finds.length) {
      label("Findings");
      for (const f of M.finds) {
        const ims = []; for (const t of f.charts) ims.push(await chartPNG(t));
        doc.setFont("Inter", "normal"); doc.setFontSize(10.5);
        const textH = doc.splitTextToSize(plain(f.text), CW - 9).length * pt(10.5) * 1.5 + 2.4, first = ims[0] ? fit(ims[0], CW - 9).ih + 9 : 0;
        need(Math.min(textH + first, BOT - TOP));                       // keep a finding with its first chart
        need(16);
        doc.setFont("Inter", "bold"); doc.setFontSize(8); doc.setTextColor(...ACC); doc.text(String(f.n).padStart(2, "0"), ML, y + 3);
        text(f.text + refsOf(f.refs), { size: 10.5, lh: 1.5, indent: 9, gap: 2.4 });
        for (const [k, t] of f.charts.entries()) {
          const im = ims[k];
          if (im) { const { iw, ih } = fit(im, CW - 9); need(ih + 9); doc.addImage(im.png, "PNG", ML + 9, y, iw, ih, undefined, "FAST"); y += ih + 1.5; }
          else { const ft = factsText(t); if (ft) text(ft, { size: 10, bold: true, indent: 9 }); }
          fig++; text(figCap(fig, t), { size: 8, color: MUTED, indent: 9, gap: 4 });
        }
        y += 1.5;
      }
    }
    if (M.extra.length) {
      label("Other charts");
      for (const c of M.extra) { const im = await chartPNG(c.type);
        if (im) { const { iw, ih } = fit(im, CW); need(ih + 9); doc.addImage(im.png, "PNG", ML, y, iw, ih, undefined, "FAST"); y += ih + 1.5; }
        fig++; text(figCap(fig, c.type, refsOf(c.refs)), { size: 8, color: MUTED, gap: 4 }); }
    }
    if (M.limitations) { label("What the data can't say"); text(M.limitations, { size: 10, lh: 1.5 }); }
    if (M.exps.length) {
      label("NASA experiments behind the answer");
      M.exps.forEach(e => { const i = U.inv(e.psi); if (!i) return; need(12); text(`${i.acronym ? i.acronym + ": " : ""}${i.title}${refsOf(e.refs)}`, { size: 9.5, bold: true, gap: .4 }); text([i.id, i.projectType, i.platform].filter(Boolean).join("  ·  "), { size: 8.5, color: MUTED, gap: 2.4 }); });
    }
    if (M.follow_ups.length) { label("Questions to ask next"); M.follow_ups.forEach(q => text("→  " + q, { size: 9.5, gap: 1.2 })); }

    if (M.refs.length) {
      label("References");
      M.refs.forEach(r => {
        need(14);
        doc.setFont("Inter", "normal"); doc.setFontSize(8.5); doc.setTextColor(...MUTED); doc.text(`[${r.n}]`, ML, y + 3);
        text(r.title, { size: 9.5, bold: true, indent: 9, gap: .5 });
        text(`${r.kind}  ·  ${r.desc}`, { size: 8.3, color: MUTED, indent: 9, gap: .6 });
        (r.notes || []).forEach(n => text(n.text, { size: 8.3, color: MUTED, indent: 9, gap: .5 }));
        if (r.url) { need(4); doc.setFont("Inter", "normal"); doc.setFontSize(8.3); doc.setTextColor(...ACC); doc.textWithLink(r.url.length > 110 ? r.url.slice(0, 108) + "…" : r.url, ML + 9, y + 2.4, { url: r.url }); y += 4.2; }
        (r.sub || []).forEach(s => { text("·  " + s.text, { size: 8, color: MUTED, indent: 12, gap: .3 }); if (s.url) { need(4); doc.setFontSize(8); doc.setTextColor(...ACC); doc.textWithLink(s.url, ML + 15, y + 2.3, { url: s.url }); y += 4; } });
        if (r.boundary) text("Evidence boundary: " + r.boundary, { size: 8, color: FAINT, indent: 9, gap: .3 });
        y += 2.4;
      });
    }
    label("How this answer was made");
    text(ANS.madeLine(M), { size: 8.5, color: MUTED, lh: 1.5 });

    const n = doc.getNumberOfPages();
    for (let i = 1; i <= n; i++) {
      doc.setPage(i); doc.setFont("Inter", "normal"); doc.setFontSize(7.2); doc.setTextColor(...FAINT);
      doc.text("Flame in Freefall · NASA Space Apps 2026 · research support only, not safety certification", ML, PH - 9);
      doc.text(`${i} / ${n}`, ML + CW, PH - 9, { align: "right" });
    }
    const slug = String(M.title || M.q).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "answer";
    doc.setProperties({ title: `Flame in Freefall — ${M.title}`, subject: M.q, creator: "Flame in Freefall (NASA Space Apps 2026)" });
    doc.save(`flame-in-freefall-${slug}.pdf`);
    UI.toast("PDF downloaded");
    return doc;
  }
  return { download, chartPNG };
})();
