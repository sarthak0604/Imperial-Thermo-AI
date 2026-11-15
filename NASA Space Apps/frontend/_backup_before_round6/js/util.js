// Small helpers shared by every file.
window.U = {
  esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  },
  // Minimal markdown: paragraphs + **bold**. Everything escaped first.
  md(text) {
    return String(text ?? "").split(/\n{2,}/).map(p =>
      "<p>" + U.esc(p).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>") + "</p>").join("");
  },
  inv(id) { return DATA.investigations.find(i => i.id === id); },
  model(id) { return DATA.models.find(m => m.id === id); },
  badge(tag) {
    const t = DATA.evidenceTags[tag] || { label: tag || "untagged" };
    return `<span class="badge" data-tag="${U.esc(tag)}">[${U.esc(t.label)}]</span>`;
  },
  short(text, n = 180) { const s = String(text ?? ""); return s.length > n ? s.slice(0, n) + "…" : s; },
  // Marker for facts we don't know yet
  unknown(label) { return `<span class="unknown">[UNKNOWN: ${U.esc(label)}]</span>`; },
  pv(value, label) { return value ? U.esc(value) : U.unknown(label); },
  projectName() { return PROJECT.name || "[Project name]"; },
  hardwareFor(id) { return DATA.hardware.filter(h => h.investigations.includes(id)); },
  modelsFor(id) { return Object.entries(DATA.modelInvestigations).filter(([, ids]) => ids.includes(id)).map(([m]) => m); },
  // Where links to an investigation / model go. The dashboard overrides these to generate a new dashboard.
  invHref(id) { return "#/investigation/" + id; },
  modelHref(id) { return "#/model/" + id; },
  link(href, label) { return `<a href="${U.esc(href)}">${U.esc(label)}</a>`; },
  invLabel(i) { return i ? (i.acronym || i.id) : "?"; },
  // "BASS-II — PSI-25", or just "PSI-117" when there is no acronym
  invTitle(i) { return i ? (i.acronym ? i.acronym + " — " + i.id : i.id) : "?"; }
};
