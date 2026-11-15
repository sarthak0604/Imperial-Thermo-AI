// FM — a small file manager, after Windows Explorer / macOS Finder: search, view (grid · list · details),
// item size (S · M · L), sort (menu, or click a column header in details), group by, and a status bar.
// Used by the NASA experiments page, All questions and the data display settings. The view, size, sort and group
// are remembered per page. Written with SI assistance (Claude, Anthropic).
//
// FM.mount(root, {
//   key,                          remembers the view settings under "fm-<key>"
//   items, id: it => string,      the things to show
//   cols: [{ k, label, get: it => sortable value, cell: it => html, w: "css grid track", name: true }],
//   search: it => text,           what the search box matches
//   card: (it, size) => html,     the grid tile          line: (it, size) => html   the list row's text
//   icon: it => html,             list / details icon    actions: it => html        controls on every item (switch, ⋯ menu)
//   groups: [{ k, label, get: it => string }], defaults: { view, size, sort: { k, dir }, group },
//   tools: html (extra toolbar controls), noun: ["experiment", "experiments"], empty: "text",
//   onOpen: (it, el) => …, drag: true (items can be dragged; dataTransfer "text/plain" = id), cls: extra class
// }) → { render(items?), items: () => visible items, state }
window.FM = (() => {
  const { esc } = U, ic = (...a) => UI.ic(...a);
  const VIEWS = [["grid", "Grid", "grid"], ["list", "List", "list"], ["details", "Details", "table"]], SIZES = [["s", "Small"], ["m", "Medium"], ["l", "Large"]];
  const cmp = (a, b) => {
    if (a == null || a === "") return b == null || b === "" ? 0 : 1;
    if (b == null || b === "") return -1;
    return typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
  };

  function mount(root, o) {
    const KEY = "fm-" + o.key, d = o.defaults || {};
    const saved = UI.store.json(KEY, {});
    const st = { view: saved.view || d.view || "grid", size: saved.size || d.size || "m", sort: saved.sort && o.cols.some(c => c.k === saved.sort.k) ? saved.sort : (d.sort || { k: o.cols[0].k, dir: 1 }),
      group: saved.group !== undefined && (saved.group === "" || (o.groups || []).some(g => g.k === saved.group)) ? saved.group : (d.group || ""), q: "", shut: new Set() };
    let items = o.items || [], shown = [];
    const persist = () => UI.store.setJson(KEY, { view: st.view, size: st.size, sort: st.sort, group: st.group });
    const col = k => o.cols.find(c => c.k === k) || o.cols[0];
    const noun = o.noun || ["item", "items"];
    const nameCol = o.cols.find(c => c.name) || o.cols[0];

    root.classList.add("fm"); if (o.cls) root.classList.add(o.cls);
    root.innerHTML = `<div class="fm-bar" role="toolbar" aria-label="View options">
        <label class="fm-search">${ic("search")}<span class="visually-hidden">Search</span><input type="search" placeholder="Search ${items.length} ${esc(noun[items.length === 1 ? 0 : 1])}" autocomplete="off"></label>
        ${o.tools || ""}<span class="sp"></span>
        <div class="pop fm-sort"></div>${o.groups && o.groups.length ? `<div class="pop fm-group"></div>` : ""}
        <div class="seg fm-view" role="group" aria-label="View">${VIEWS.map(([k, l, i]) => `<button type="button" data-fm-view="${k}" aria-pressed="false" title="${l}" aria-label="${l} view">${ic(i)}</button>`).join("")}</div>
        <div class="seg fm-size" role="group" aria-label="Item size">${SIZES.map(([k, l]) => `<button type="button" data-fm-size="${k}" aria-pressed="false" title="${l} items" aria-label="${l} items">${k.toUpperCase()}</button>`).join("")}</div>
      </div><div class="fm-body"></div><p class="fm-status" role="status"></p>`;
    const body = root.querySelector(".fm-body"), status = root.querySelector(".fm-status"), input = root.querySelector(".fm-search input");

    function tools() {
      root.querySelectorAll("[data-fm-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.fmView === st.view)));
      root.querySelectorAll("[data-fm-size]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.fmSize === st.size)));
      const sc = col(st.sort.k);
      root.querySelector(".fm-sort").innerHTML = `<button type="button" class="btn sm" aria-haspopup="menu" aria-expanded="false">${ic("sort")}<span>Sort: ${esc(sc.label)} ${st.sort.dir > 0 ? "↑" : "↓"}</span></button>
        <div class="menu right" role="menu"><p class="menu-h">Sort by</p>${o.cols.filter(c => c.get).map(c => `<button type="button" class="mi" role="menuitemradio" data-fm-sortk="${c.k}" aria-checked="${c.k === st.sort.k}"><span><b>${esc(c.label)}</b></span>${ic("check", "tk")}</button>`).join("")}
        <p class="menu-h">Order</p><button type="button" class="mi" role="menuitemradio" data-fm-dir="1" aria-checked="${st.sort.dir > 0}"><span><b>Ascending</b><small>A → Z, oldest or smallest first</small></span>${ic("check", "tk")}</button><button type="button" class="mi" role="menuitemradio" data-fm-dir="-1" aria-checked="${st.sort.dir < 0}"><span><b>Descending</b><small>Z → A, newest or largest first</small></span>${ic("check", "tk")}</button></div>`;
      const gp = root.querySelector(".fm-group");
      if (gp) { const g = (o.groups || []).find(x => x.k === st.group);
        gp.innerHTML = `<button type="button" class="btn sm" aria-haspopup="menu" aria-expanded="false">${ic("group")}<span>Group: ${esc(g ? g.label : "None")}</span></button>
          <div class="menu right" role="menu"><p class="menu-h">Group by</p>${[{ k: "", label: "None" }, ...o.groups].map(x => `<button type="button" class="mi" role="menuitemradio" data-fm-group="${x.k}" aria-checked="${x.k === st.group}"><span><b>${esc(x.label)}</b></span>${ic("check", "tk")}</button>`).join("")}</div>`; }
    }

    const itemAttrs = it => `data-fm-id="${esc(o.id(it))}" tabindex="0" role="button"${o.label ? ` aria-label="${esc(o.label(it))}"` : ""}${o.drag ? ' draggable="true"' : ""}`;
    const xc = it => o.itemCls ? " " + o.itemCls(it) : "";
    function itemHTML(it) {
      if (st.view === "grid") return `<div class="fm-it fm-card${xc(it)}" ${itemAttrs(it)}>${o.card(it, st.size)}${o.actions ? `<div class="fm-act">${o.actions(it)}</div>` : ""}</div>`;
      if (st.view === "list") return `<div class="fm-it fm-row${xc(it)}" ${itemAttrs(it)}><span class="fm-ic">${o.icon ? o.icon(it) : ""}</span><div class="fm-txt">${o.line(it, st.size)}</div>${o.actions ? `<div class="fm-act">${o.actions(it)}</div>` : ""}</div>`;
      return `<div class="fm-it fm-tr${xc(it)}" role="row" ${itemAttrs(it)}>${o.cols.map((c, i) => `<span class="fm-td${c === nameCol ? " fm-nm" : ""}" role="cell">${i === 0 && o.icon ? `<span class="fm-ic">${o.icon(it)}</span>` : ""}${c.cell ? c.cell(it) : esc(c.get(it) ?? "")}</span>`).join("")}${o.actions ? `<span class="fm-td fm-act" role="cell">${o.actions(it)}</span>` : ""}</div>`;
    }
    function render(next) {
      if (next) items = next;
      const q = st.q.trim().toLowerCase(), sc = col(st.sort.k);
      shown = items.filter(it => !q || (o.search ? o.search(it) : o.cols.map(c => c.get ? c.get(it) : "").join(" ")).toLowerCase().includes(q));
      shown.sort((a, b) => cmp(sc.get(a), sc.get(b)) * st.sort.dir || cmp(nameCol.get(a), nameCol.get(b)));
      const g = (o.groups || []).find(x => x.k === st.group);
      const groups = g ? [...shown.reduce((m, it) => { const k = g.get(it) || "—"; (m.get(k) || m.set(k, []).get(k)).push(it); return m; }, new Map())].sort((a, b) => cmp(a[0], b[0])) : [["", shown]];
      const tracks = `${o.cols.map(c => c.w || "minmax(0,1fr)").join(" ")}${o.actions ? " max-content" : ""}`;
      const head = st.view === "details" ? `<div class="fm-tr fm-th" role="row">${o.cols.map(c => `<span class="fm-td" role="columnheader" aria-sort="${c.k === st.sort.k ? (st.sort.dir > 0 ? "ascending" : "descending") : "none"}">${c.get ? `<button type="button" data-fm-sort="${c.k}">${esc(c.label)}${c.k === st.sort.k ? ic(st.sort.dir > 0 ? "up" : "down") : ""}</button>` : esc(c.label)}</span>`).join("")}${o.actions ? `<span class="fm-td"></span>` : ""}</div>` : "";
      const wrap = list => st.view === "grid" ? `<div class="fm-grid sz-${st.size}">${list.map(itemHTML).join("")}</div>`
        : st.view === "list" ? `<div class="fm-list sz-${st.size}">${list.map(itemHTML).join("")}</div>`
        : `<div class="fm-rows">${list.map(itemHTML).join("")}</div>`;
      const inner = !shown.length ? `<p class="fm-empty">${esc(q ? `Nothing matches “${st.q.trim()}”.` : ((typeof o.empty === "function" ? o.empty() : o.empty) || "Nothing here yet."))}</p>`
        : groups.map(([k, list]) => g ? `<section class="fm-g${st.shut.has(k) ? " shut" : ""}"><button type="button" class="fm-gh" data-fm-gh="${esc(k)}" aria-expanded="${!st.shut.has(k)}">${ic("chev", "cv")}<b>${esc(k)}</b><span>${list.length}</span></button>${st.shut.has(k) ? "" : wrap(list)}</section>` : wrap(list)).join("");
      body.className = `fm-body v-${st.view} sz-${st.size}`;
      body.style.setProperty("--fm-cols", tracks);
      body.innerHTML = st.view === "details" ? `<div class="fm-table" role="table" aria-label="${esc(noun[1])}">${head}${inner}</div>` : inner;
      const n = items.length;
      status.textContent = `${n} ${noun[n === 1 ? 0 : 1]}${shown.length !== n ? ` · ${shown.length} shown` : ""} · sorted by ${sc.label.toLowerCase()} (${st.sort.dir > 0 ? "ascending" : "descending"})${g ? ` · grouped by ${g.label.toLowerCase()}` : ""}`;
      tools();
      if (o.after) o.after(body);
    }

    input.addEventListener("input", () => { st.q = input.value; render(); });
    root.addEventListener("click", e => {
      const t = e.target;
      const v = t.closest("[data-fm-view]"); if (v) { st.view = v.dataset.fmView; persist(); return render(); }
      const z = t.closest("[data-fm-size]"); if (z) { st.size = z.dataset.fmSize; persist(); return render(); }
      const hs = t.closest("[data-fm-sort]"); if (hs) { const k = hs.dataset.fmSort; st.sort = { k, dir: st.sort.k === k ? -st.sort.dir : 1 }; persist(); render(); root.querySelector(`[data-fm-sort="${k}"]`)?.focus(); return; }
      const sk = t.closest("[data-fm-sortk]"); if (sk) { st.sort = { k: sk.dataset.fmSortk, dir: st.sort.dir }; persist(); UI.closeMenus(); return render(); }
      const dr = t.closest("[data-fm-dir]"); if (dr) { st.sort = { k: st.sort.k, dir: +dr.dataset.fmDir }; persist(); UI.closeMenus(); return render(); }
      const gr = t.closest("[data-fm-group]"); if (gr) { st.group = gr.dataset.fmGroup; st.shut.clear(); persist(); UI.closeMenus(); return render(); }
      const gh = t.closest("[data-fm-gh]"); if (gh) { const k = gh.dataset.fmGh; st.shut.has(k) ? st.shut.delete(k) : st.shut.add(k); return render(); }
      const it = t.closest(".fm-it[data-fm-id]");
      if (it && !t.closest("a, button, input, select, textarea, label, .fm-act, .menu") && o.onOpen) { const x = items.find(y => o.id(y) === it.dataset.fmId); if (x) o.onOpen(x, it); }
    });
    root.addEventListener("keydown", e => {
      const it = e.target.closest && e.target.closest(".fm-it[data-fm-id]");
      if (it && e.target === it && (e.key === "Enter" || e.key === " ") && o.onOpen) { e.preventDefault(); const x = items.find(y => o.id(y) === it.dataset.fmId); if (x) o.onOpen(x, it); }
    });
    if (o.drag) {
      root.addEventListener("dragstart", e => { const it = e.target.closest && e.target.closest(".fm-it[data-fm-id]"); if (!it) return; e.dataTransfer.setData("text/plain", it.dataset.fmId); e.dataTransfer.effectAllowed = "move"; it.classList.add("dragging"); document.body.classList.add("fm-dragging"); });
      const end = () => { root.querySelectorAll(".dragging").forEach(x => x.classList.remove("dragging")); document.body.classList.remove("fm-dragging"); };
      root.addEventListener("dragend", end); document.addEventListener("drop", end);   // a drop can re-render the list, so the dragged item may be gone by dragend
    }
    render();
    return { render, items: () => shown, state: st, find: id => items.find(y => o.id(y) === id) };
  }
  return { mount };
})();
