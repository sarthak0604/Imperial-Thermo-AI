// LIBRARY ADAPTER — the main site's widget library is now the thermo-model widgets (js/model_widgets.js).
// Gives dashboard.js / mockgen.js / tiler.js the same small API the old sketch library had.
window.W = (() => {
  const WEIGHT = { b: 4, w: 2.6, t: 2.2, s: 1.4 };
  const def = t => MW.lib[t];
  function sketch(type, opts = {}) {            // a dashboard tile: compact real chart, click to open
    const d = def(type) || { title: type };
    return `<section class="widget sketch mtile" data-type="${U.esc(type)}" data-i="${opts.i || 0}" tabindex="0" role="button" aria-label="${U.esc(d.title)} — open"
      style="--i:${opts.i || 0};${opts.place || ""}"><span class="w-label">${U.esc(d.title)}</span><div class="tile-body">${def(type) ? MW.tile(type) : ""}</div></section>`;
  }
  return {
    types: () => MW.types(),
    def,
    byCat: c => MW.types().filter(t => def(t).cat === c),
    cats: () => [...new Set(MW.types().map(t => def(t).cat))],
    size: t => (def(t) ? def(t).size : "s"),
    shape: t => ({ aspect: MW.aspect(t), weight: WEIGHT[def(t) ? def(t).size : "s"] || 1.5 }),
    samples: Object.fromEntries(MW.types().map(t => [t, {}])),
    sketch,
    full: t => `<div class="mw-full" data-mw="${U.esc(t)}">${MW.body(t)}</div>`,
    mountFull: (el, t) => MW.mount(el, t)
  };
})();
