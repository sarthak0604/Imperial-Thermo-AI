// LIBRARY ADAPTER — the main site's widgets: the thermo-model charts (js/model_widgets.js) plus the text boxes
// that fill the space around them (js/text_widgets.js). Gives dashboard.js / mockgen.js / tiler.js one small API.
window.W = (() => {
  const WEIGHT = { b: 4, w: 2.6, t: 2.2, s: 1.4 };
  const isText = t => TW.has(t);
  const def = t => MW.lib[t] || (TW.has(t) ? TW.def(t) : undefined);
  function sketch(type, opts = {}) {            // a dashboard tile: compact real chart (or text), click to open
    if (isText(type)) return TW.tile(type, opts);
    const d = def(type) || { title: type };
    return `<section class="widget sketch mtile" data-type="${U.esc(type)}" data-i="${opts.i || 0}" tabindex="0" role="button" aria-label="${U.esc(d.title)} — open"
      style="--i:${opts.i || 0};${opts.place || ""}"><span class="w-label">${U.esc(d.title)}</span><div class="tile-body">${def(type) ? MW.tile(type) : ""}</div></section>`;
  }
  return {
    types: () => MW.types(),                    // the charts (mockgen and the library page pick from these)
    isText, def,
    byCat: c => MW.types().filter(t => def(t).cat === c),
    cats: () => [...new Set(MW.types().map(t => def(t).cat))],
    size: t => (def(t) ? def(t).size : "s"),
    // what the tiler needs: charts have a rigid natural shape; text boxes are flexible
    shape: (t, params) => { if (isText(t)) return TW.shape(t, params);
      const [aspect, amin, amax] = MW.shape(t); return { aspect, amin, amax, weight: WEIGHT[def(t) ? def(t).size : "s"] || 1.5 }; },
    samples: Object.fromEntries(MW.types().map(t => [t, {}])),
    sketch,
    full: t => `<div class="mw-full" data-mw="${U.esc(t)}">${MW.body(t)}</div>`,
    mountFull: (el, t) => { if (!isText(t)) MW.mount(el, t); }
  };
})();
