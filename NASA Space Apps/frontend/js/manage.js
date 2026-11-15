// MANAGE — the three management pages, each built on the file manager (js/fm.js):
//   #experiments  the 26 NASA PSI investigations: grid / list / details, item size, sortable headers, group by
//   #questions    every question asked, with its saved answer: folders (drag a question onto one), pin, rename, delete
//   #display      data display settings: switch answer sections and individual charts on or off
// Written with SI assistance (Claude, Anthropic).
window.MANAGE = (() => {
  const { esc } = U, ic = (...a) => UI.ic(...a);
  const year = d => { const m = String(d || "").match(/(\d{4})/); return m ? m[1] : ""; };
  const when = i => { const y = [year(i.start), year(i.end)].filter(Boolean); return y.length ? (y.length === 1 || y[0] === y[1] ? y[0] : y.join("–")) : ""; };
  const platform = i => !i.platform || i.platform === "Not Applicable" ? (i.projectType === "Ground Investigation" ? "Ground" : "Not stated") : i.platform.replace("International Space Station (ISS)", "ISS");
  const center = i => String(i.center || "").replace(/\s*\(.*\)/, "") || "Not stated";
  const short = (t, n) => { t = String(t || ""); return t.length > n ? t.slice(0, n - 1) + "…" : t; };
  const head = (h, p, extra = "") => `<div class="page-h"><div><h1>${h}</h1><p>${p}</p></div><span class="sp"></span>${extra}</div>`;

  // ---------- NASA experiments ----------
  function experiments(page) {
    const inv = DATA.investigations;
    page.innerHTML = head("NASA experiments", `The ${inv.length} microgravity combustion investigations from NASA's Physical Sciences Informatics database that the answers draw on. Open one for its full record.`) + `<div class="fmh"></div>`;
    FM.mount(page.querySelector(".fmh"), {
      key: "experiments", items: inv, id: i => i.id, noun: ["experiment", "experiments"], label: i => `${i.acronym || i.id}: ${i.title}`,
      cols: [
        { k: "name", label: "Name", name: true, get: i => i.acronym || i.id, cell: i => `<b>${esc(i.acronym || i.id)}</b>`, w: "minmax(150px,1fr)" },
        { k: "title", label: "Title", get: i => i.title, cell: i => `<span class="fm-clamp">${esc(i.title)}</span>`, w: "minmax(220px,3fr)" },
        { k: "id", label: "PSI ID", get: i => +String(i.id).replace(/\D/g, "") || 0, cell: i => `<span class="t-id">${esc(i.id)}</span>`, w: "78px" },
        { k: "platform", label: "Platform", get: platform, w: "minmax(90px,.9fr)" },
        { k: "type", label: "Type", get: i => (i.projectType || "").replace(" Investigation", ""), w: "minmax(96px,.8fr)" },
        { k: "years", label: "Years", get: i => +year(i.start) || 0, cell: i => esc(when(i) || "—"), w: "88px" },
        { k: "center", label: "NASA center", get: center, w: "minmax(110px,1fr)" }
      ],
      search: i => [i.id, i.acronym, i.title, i.keywords, i.platform, i.projectType, i.center, i.objectives].join(" "),
      groups: [{ k: "platform", label: "Platform", get: platform }, { k: "type", label: "Type", get: i => i.projectType || "Not stated" },
        { k: "center", label: "NASA center", get: center }, { k: "decade", label: "Start decade", get: i => year(i.start) ? year(i.start).slice(0, 3) + "0s" : "No date" }],
      defaults: { view: "grid", size: "m", sort: { k: "name", dir: 1 } },
      icon: () => ic("beaker"),
      card: (i, sz) => `<div class="fc-h"><span class="lab">${esc(i.id)}</span>${sz !== "s" ? `<span class="fc-tag">${esc(platform(i))}</span>` : ""}</div>
        <b class="fc-n">${esc(i.acronym || i.id)}</b>${sz === "s" ? `<span class="fc-t s">${esc(short(i.title, 64))}</span>` : `<p class="fc-t">${esc(i.title)}</p>`}
        ${sz !== "s" ? `<p class="fc-m">${esc([(i.projectType || "").replace(" Investigation", ""), when(i), center(i)].filter(Boolean).join(" · "))}</p>` : ""}
        ${sz === "l" ? `<p class="fc-o">${esc(i.objectives || "")}</p>` : ""}`,
      line: (i, sz) => `<b>${esc(i.acronym || i.id)}</b><span class="fm-sub">${esc(i.title)}</span>${sz !== "s" ? `<span class="fm-meta">${esc([i.id, platform(i), when(i)].filter(Boolean).join(" · "))}</span>` : ""}${sz === "l" ? `<span class="fm-more">${esc(short(i.objectives, 260))}</span>` : ""}`,
      onOpen: (i, el) => EXPAND.open(el, EXPAND.spec({ kind: "exp", e: { psi: i.id } }, null))
    });
  }

  // ---------- data display settings ----------
  function display(page) {
    // one preview per kind of figure the pipeline can generate, drawn for the environment you have chosen;
    // switching one off hides that kind of figure from every answer (stored under its thermo model's chart type)
    const D = UI.display, env = UI.env() || "iss", figs = {};
    Object.keys(PIPE.CONTROLS).forEach(k => { const sp = PIPE.rerun(k, { q: "", s: env }, {}); figs["pv_" + k] = { ...sp, cat: sp.kind === "bar" ? "visual" : "graph" }; });
    const types = FIG.register(figs), def = t => W.def(t), key = t => def(t).lib || t;
    const counts = () => { const off = types.filter(t => !D.chart(key(t))).length, so = D.SECTIONS.filter(s => !D.section(s.k)).length;
      return `${types.length - off} of ${types.length} kinds of figure shown${so ? ` · ${so} section${so > 1 ? "s" : ""} off` : " · every section on"}`; };
    page.innerHTML = head("Data display settings", "Choose what an answer shows. Anything switched off is left out of every answer, including saved ones, until you switch it back on. You can still open it here to preview.",
      `<div class="ds-hr"><p class="ds-count" role="status">${counts()}</p><button type="button" class="btn sm" data-ds-reset>${ic("refresh")}Reset to defaults</button></div>`) +
      `<div class="sec-h"><h2>Answer sections</h2><p>The AI overview, the findings and the References and Method drop-downs are always shown.</p></div>
      <div class="ds-secs">${D.SECTIONS.map(s => `<div class="ds-sec${D.section(s.k) ? "" : " off"}"><div><b>${esc(s.label)}</b><p>${esc(s.d)}</p></div>${UI.sw(D.section(s.k), `data-ds-sec="${s.k}"`, s.label)}</div>`).join("")}</div>
      <div class="sec-h"><h2>Figures</h2><p>What the pipeline can generate from a question, one kind per thermo model. Previews use the defaults for ${esc(UI.envLabel(env))}; open one to re-run its model.</p></div><div class="fmh"></div>`;
    const fm = FM.mount(page.querySelector(".fmh"), {
      key: "display", items: types, id: t => t, noun: ["figure", "figures"], label: t => def(t).title, cls: "fm-charts",
      itemCls: t => D.chart(key(t)) ? "" : "off",
      tools: `<button type="button" class="btn sm" data-ds-all="1">${ic("check")}Show all</button><button type="button" class="btn sm" data-ds-all="0">${ic("x")}Hide all</button>`,
      cols: [
        { k: "title", label: "Figure", name: true, get: t => def(t).title, cell: t => `<b>${esc(def(t).title)}</b>`, w: "minmax(200px,2.2fr)" },
        { k: "model", label: "Model", get: t => def(t).model || "", cell: t => `<span class="t-id">${esc(def(t).model || "")}</span>`, w: "84px" },
        { k: "cat", label: "Kind", get: t => cap(def(t).cat), w: "minmax(80px,.7fr)" },
        { k: "status", label: "Basis", get: t => ANS.STATUS_LABEL[def(t).status] || "", w: "minmax(140px,1.2fr)" },
        { k: "shown", label: "Shown", get: t => D.chart(key(t)) ? 0 : 1, cell: t => `<span class="ds-st">${D.chart(key(t)) ? "Shown" : "Hidden"}</span>`, w: "72px" }
      ],
      search: t => [def(t).title, def(t).model, def(t).cat, def(t).desc].join(" "),
      groups: [{ k: "cat", label: "Kind", get: t => cap(def(t).cat) }, { k: "model", label: "Model", get: t => def(t).model || "" }, { k: "status", label: "Basis", get: t => ANS.STATUS_LABEL[def(t).status] || "Other" }],
      defaults: { view: "grid", size: "m", sort: { k: "model", dir: 1 } },
      icon: () => ic("layers"),
      actions: t => UI.sw(D.chart(key(t)), `data-ds-chart="${esc(key(t))}"`, `Show ${def(t).title} in answers`),
      card: (t, sz) => `<div class="fc-h"><span class="lab">${esc(cap(def(t).cat))} · ${esc(def(t).model || "")}</span></div>
        ${sz === "s" ? `<b class="fc-n sm">${esc(def(t).title)}</b>` : `${ANS.chartArea(t, sz === "l" ? 320 : 190)}<b class="fc-n sm">${esc(def(t).title)}</b>`}
        ${sz === "l" ? `<p class="fc-o">${esc(ANS.firstSentence(def(t).desc || ""))}</p>` : ""}`,
      line: (t, sz) => `<b>${esc(def(t).title)}</b><span class="fm-sub">${esc(def(t).model || "")} · ${esc(cap(def(t).cat))}</span>${sz !== "s" ? `<span class="fm-meta">${esc(ANS.STATUS_LABEL[def(t).status] || "")}</span>` : ""}${sz === "l" ? `<span class="fm-more">${esc(ANS.firstSentence(def(t).desc || ""))}</span>` : ""}`,
      onOpen: (t, el) => EXPAND.open(el, EXPAND.spec({ kind: "chart", c: { type: t } }, null))
    });
    const sync = () => {
      page.querySelector(".ds-count").textContent = counts();
      page.querySelectorAll("[data-ds-chart]").forEach(b => { const on = D.chart(b.dataset.dsChart); b.setAttribute("aria-checked", String(on)); const it = b.closest(".fm-it"); if (it) { it.classList.toggle("off", !on); const st = it.querySelector(".ds-st"); if (st) st.textContent = on ? "Shown" : "Hidden"; } });
      page.querySelectorAll("[data-ds-sec]").forEach(b => { const on = D.section(b.dataset.dsSec); b.setAttribute("aria-checked", String(on)); b.closest(".ds-sec").classList.toggle("off", !on); });
    };
    page.onclick = e => {
      const c = e.target.closest("[data-ds-chart]"); if (c) { D.setChart(c.dataset.dsChart, !D.chart(c.dataset.dsChart)); return sync(); }
      const s = e.target.closest("[data-ds-sec]"); if (s) { D.setSection(s.dataset.dsSec, !D.section(s.dataset.dsSec)); return sync(); }
      const a = e.target.closest("[data-ds-all]"); if (a) { D.setCharts(fm.items().map(key), a.dataset.dsAll === "1"); UI.toast(a.dataset.dsAll === "1" ? `${fm.items().length} kinds of figure shown` : `${fm.items().length} kinds of figure hidden from answers`); return sync(); }
      if (e.target.closest("[data-ds-reset]")) { D.reset(); sync(); UI.toast("Every section and chart is back on"); }
    };
  }
  const cap = s => s ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : "Other";

  // ---------- all questions: a file manager for what you've asked ----------
  let qmRefresh = null;
  UI.onHist(() => { if (qmRefresh) qmRefresh(); });
  function questions(page) {
    let where = UI.store.get("fif-qm-folder", "all");
    const ago = t => { const d = new Date(t), n = new Date(), day = 864e5, s0 = new Date(n.getFullYear(), n.getMonth(), n.getDate()).getTime();
      return t >= s0 ? "Today" : t >= s0 - day ? "Yesterday" : t >= s0 - 6 * day ? "Earlier this week" : d.toLocaleDateString([], { month: "long", year: "numeric" }); };
    const fmt = t => new Date(t).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const fname = id => { const f = UI.folders().find(x => x.id === id); return f ? f.name : ""; };
    const pick = () => { const H = UI.hist(); return where === "all" ? H : where === "pinned" ? H.filter(h => h.pin) : where === "none" ? H.filter(h => !h.folder || !fname(h.folder)) : H.filter(h => h.folder === where); };
    const threadName = h => { const t = UI.thread(h.th || h.id); return t.length > 1 ? UI.label(t[0]) : "Single questions"; };

    page.innerHTML = head("All questions", "Every question you've asked, with its answer saved in this browser. Open, pin, rename or delete one from its ⋯ menu, and sort them into folders: drag a question onto a folder, or use Move to.") +
      `<div class="qm"><nav class="qm-nav" aria-label="Folders"></nav><div class="qm-main fmh"></div></div>`;
    const nav = page.querySelector(".qm-nav");
    function renderNav() {
      const H = UI.hist(), F = UI.folders();
      if (where !== "all" && where !== "pinned" && where !== "none" && !F.some(f => f.id === where)) where = "all";
      const row = (k, label, n, icon, extra = "") => `<div class="qf${where === k ? " on" : ""}" data-drop="${k}"><button type="button" class="qf-b" data-qf="${k}" aria-pressed="${where === k}">${ic(icon)}<span class="qf-n">${esc(label)}</span><span class="qf-c">${n}</span></button>${extra}</div>`;
      nav.innerHTML = row("all", "All questions", H.length, "layers") + row("pinned", "Pinned", H.filter(h => h.pin).length, "pin") + row("none", "Not in a folder", H.filter(h => !h.folder || !fname(h.folder)).length, "doc") +
        `<p class="lab qm-fl">Folders</p>` + F.map(f => row(f.id, f.name, H.filter(h => h.folder === f.id).length, "folder",
          `<div class="pop qf-more"><button type="button" class="ib sm" aria-haspopup="menu" aria-expanded="false" aria-label="Folder options for ${esc(f.name)}">${ic("more")}</button><div class="menu right" role="menu"><button type="button" class="mi" data-qf-rename="${f.id}">${ic("edit")}<span><b>Rename</b></span></button><button type="button" class="mi" data-qf-del="${f.id}">${ic("trash")}<span><b>Delete folder</b><small>Its questions move to “Not in a folder”</small></span></button></div></div>`)).join("") +
        `<button type="button" class="qf-new" data-qf-new>${ic("folderPlus")}<span>New folder</span></button>`;
    }
    const actions = h => `<button type="button" class="ib sm qm-pin${h.pin ? " on" : ""}" data-qm-pin="${esc(h.id)}" aria-pressed="${!!h.pin}" aria-label="${h.pin ? "Unpin" : "Pin"}" title="${h.pin ? "Unpin" : "Pin"}">${ic("pin")}</button>
      <div class="pop"><button type="button" class="ib sm" aria-haspopup="menu" aria-expanded="false" aria-label="More for this question" title="More">${ic("more")}</button><div class="menu right" role="menu">
        <button type="button" class="mi" data-qm-open="${esc(h.id)}">${ic("open")}<span><b>Open</b><small>Instantly, from the saved answer</small></span></button>
        <button type="button" class="mi" data-qm-rename="${esc(h.id)}">${ic("edit")}<span><b>Rename</b></span></button>
        <p class="menu-h">Move to</p>
        <button type="button" class="mi" role="menuitemradio" data-qm-move="${esc(h.id)}" data-to="" aria-checked="${!h.folder || !fname(h.folder)}">${ic("doc")}<span><b>Not in a folder</b></span>${ic("check", "tk")}</button>
        ${UI.folders().map(f => `<button type="button" class="mi" role="menuitemradio" data-qm-move="${esc(h.id)}" data-to="${f.id}" aria-checked="${h.folder === f.id}">${ic("folder")}<span><b>${esc(f.name)}</b></span>${ic("check", "tk")}</button>`).join("")}
        <button type="button" class="mi" data-qm-move-new="${esc(h.id)}">${ic("folderPlus")}<span><b>New folder…</b></span></button>
        <p class="menu-h"></p><button type="button" class="mi danger" data-qm-del="${esc(h.id)}">${ic("trash")}<span><b>Delete</b><small>Removes the question and its saved answer</small></span></button></div></div>`;
    const chips = h => `<span class="qchip">${ic(UI.personaIcon(h.p))}${esc(UI.personaLabel(h.p))}</span><span class="qchip">${ic(UI.envIcon(h.s || "iss"))}${esc(UI.envLabel(h.s || "iss"))}</span>`;
    const fm = FM.mount(page.querySelector(".fmh"), {
      key: "questions", items: pick(), id: h => h.id, noun: ["question", "questions"], label: h => UI.label(h), drag: true,
      empty: () => where === "all" ? "Your questions will appear here." : where === "pinned" ? "Nothing pinned yet. Pin a question with its pin button." : "No questions here. Drag one onto this folder, or use Move to in its ⋯ menu.",
      cols: [
        { k: "q", label: "Question", name: true, get: h => UI.label(h), cell: h => `<span class="fm-clamp" data-nm>${h.pin ? ic("pin", "pn") : ""}${esc(UI.label(h))}</span>`, w: "minmax(190px,2.4fr)" },
        { k: "title", label: "Answer", get: h => (h.a && h.a.title) || "", cell: h => `<span class="fm-clamp muted">${esc((h.a && h.a.title) || "")}</span>`, w: "minmax(130px,1.5fr)" },
        { k: "p", label: "For", get: h => UI.personaLabel(h.p), w: "78px" },
        { k: "s", label: "Environment", get: h => UI.envLabel(h.s || "iss"), w: "minmax(88px,.8fr)" },
        { k: "folder", label: "Folder", get: h => fname(h.folder), w: "minmax(76px,.7fr)" },
        { k: "t", label: "Asked", get: h => h.t, cell: h => `<span class="t-id">${esc(fmt(h.t))}</span>`, w: "104px" }
      ],
      search: h => [h.q, h.name, h.a && h.a.title, h.a && h.a.summary, UI.personaLabel(h.p), UI.envLabel(h.s || "iss"), fname(h.folder)].join(" "),
      groups: [{ k: "date", label: "Date asked", get: h => ago(h.t) }, { k: "th", label: "Thread", get: threadName }, { k: "p", label: "For", get: h => UI.personaLabel(h.p) },
        { k: "s", label: "Environment", get: h => UI.envLabel(h.s || "iss") }, { k: "folder", label: "Folder", get: h => fname(h.folder) || "Not in a folder" }],
      defaults: { view: "details", size: "m", sort: { k: "t", dir: -1 } },
      icon: h => ic(h.pin ? "pin" : "doc"),
      actions,
      card: (h, sz) => `<div class="fc-h"><span class="lab">${esc(ago(h.t))}</span>${h.folder && fname(h.folder) ? `<span class="fc-tag">${ic("folder")}${esc(fname(h.folder))}</span>` : ""}</div>
        <b class="fc-n sm" data-nm>${h.pin ? ic("pin", "pn") : ""}${esc(UI.label(h))}</b>${sz !== "s" && h.a && h.a.title ? `<p class="fc-t">${esc(h.a.title)}</p>` : ""}
        ${sz === "l" && h.a && h.a.summary ? `<p class="fc-o">${esc(short(ANS.plain(h.a.summary), 220))}</p>` : ""}${sz !== "s" ? `<p class="fc-chips">${chips(h)}</p>` : ""}`,
      line: (h, sz) => `<b data-nm>${esc(UI.label(h))}</b><span class="fm-sub">${esc((h.a && h.a.title) || "")}</span>${sz !== "s" ? `<span class="fm-meta">${esc([UI.personaLabel(h.p), UI.envLabel(h.s || "iss"), fmt(h.t), fname(h.folder)].filter(Boolean).join(" · "))}</span>` : ""}${sz === "l" && h.a && h.a.summary ? `<span class="fm-more">${esc(short(ANS.plain(h.a.summary), 240))}</span>` : ""}`,
      onOpen: h => { location.hash = UI.href(h.q, h.p, h.s).slice(1); }
    });
    const refresh = () => { if (!page.isConnected || page.hidden || !page.querySelector(".qm")) { qmRefresh = null; return; } renderNav(); fm.render(pick()); };
    qmRefresh = refresh;
    renderNav();

    function inline(el, value, done) {           // swap a label for a text box; Enter saves, Esc cancels
      const inp = document.createElement("input"); inp.type = "text"; inp.className = "qm-in"; inp.value = value; inp.setAttribute("aria-label", "Name");
      el.replaceWith(inp); inp.focus(); inp.select();
      let over = false; const end = ok => { if (over) return; over = true; done(ok ? inp.value.trim() : null); };
      inp.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); end(true); } if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); end(false); } });
      inp.addEventListener("blur", () => end(true));
      inp.addEventListener("click", e => e.stopPropagation());
    }
    page.onclick = e => {
      const t = e.target;
      const qf = t.closest("[data-qf]"); if (qf) { where = qf.dataset.qf; UI.store.set("fif-qm-folder", where); return refresh(); }
      if (t.closest("[data-qf-new]")) { const b = t.closest("[data-qf-new]"); return inline(b, "New folder", v => { if (v) { const f = UI.addFolder(v); where = f.id; UI.store.set("fif-qm-folder", where); } refresh(); }); }
      const fr = t.closest("[data-qf-rename]"); if (fr) { UI.closeMenus(); const n = nav.querySelector(`[data-qf="${fr.dataset.qfRename}"] .qf-n`); return inline(n, n.textContent, v => { if (v) UI.renameFolder(fr.dataset.qfRename, v); else refresh(); }); }
      const fd = t.closest("[data-qf-del]"); if (fd) { UI.closeMenus(); const name = fname(fd.dataset.qfDel); UI.removeFolder(fd.dataset.qfDel); UI.toast(`Folder “${name}” deleted; its questions are still in All questions`); return; }
      const pn = t.closest("[data-qm-pin]"); if (pn) { const h = UI.get(pn.dataset.qmPin); if (h) UI.update(h.id, { pin: !h.pin }); return; }
      const op = t.closest("[data-qm-open]"); if (op) { UI.closeMenus(); const h = UI.get(op.dataset.qmOpen); if (h) location.hash = UI.href(h.q, h.p, h.s).slice(1); return; }
      const rn = t.closest("[data-qm-rename]"); if (rn) { UI.closeMenus(); const id = rn.dataset.qmRename, it = page.querySelector(`.fm-it[data-fm-id="${CSS.escape(id)}"] [data-nm]`), h = UI.get(id); if (!it || !h) return;
        return inline(it, UI.label(h), v => { if (v === null) return refresh(); UI.update(id, { name: v && v !== h.q ? v : null }); }); }
      const mv = t.closest("[data-qm-move]"); if (mv) { UI.closeMenus(); UI.update(mv.dataset.qmMove, { folder: mv.dataset.to || null }); return; }
      const mn = t.closest("[data-qm-move-new]"); if (mn) { UI.closeMenus(); const b = nav.querySelector("[data-qf-new]"), id = mn.dataset.qmMoveNew;
        return inline(b, "New folder", v => { if (v) { const f = UI.addFolder(v); UI.update(id, { folder: f.id }); UI.toast(`Moved to “${f.name}”`); } refresh(); }); }
      const dl = t.closest("[data-qm-del]"); if (dl) { UI.closeMenus(); const h = UI.get(dl.dataset.qmDel); if (h) { UI.remove(h.id); UI.toast("Question deleted"); } return; }
    };
    // drag a question onto a folder
    nav.addEventListener("dragover", e => { const d = e.target.closest("[data-drop]"); if (!d || d.dataset.drop === "all") return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; nav.querySelectorAll(".drop-on").forEach(x => x !== d && x.classList.remove("drop-on")); d.classList.add("drop-on"); });
    nav.addEventListener("dragleave", e => { const d = e.target.closest("[data-drop]"); if (d && !d.contains(e.relatedTarget)) d.classList.remove("drop-on"); });
    nav.addEventListener("drop", e => {
      const d = e.target.closest("[data-drop]"); if (!d) return; e.preventDefault(); d.classList.remove("drop-on");
      const id = e.dataTransfer.getData("text/plain"), h = UI.get(id), k = d.dataset.drop; if (!h) return;
      if (k === "pinned") { UI.update(id, { pin: true }); UI.toast("Pinned"); }
      else if (k === "none") { UI.update(id, { folder: null }); UI.toast("Moved out of its folder"); }
      else { UI.update(id, { folder: k }); UI.toast(`Moved to “${fname(k)}”`); }
    });
  }

  return { experiments, display, questions };
})();
