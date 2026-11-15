const test = require("node:test"), assert = require("node:assert/strict");
const STORY = require("../js/story.js");

const CHARTS = new Set(["thm02_diluents", "thm08_richardson", "thm01_flame_temp", "thm07_blowoff"]);
const env = {
  isChart: t => CHARTS.has(t), isPsi: id => ["PSI-20", "PSI-10", "PSI-25"].includes(id),
  linked: () => ["PSI-20", "PSI-10"], desc: t => "desc of " + t
};

test("points cleans AI output", () => {
  const a = { points: [
    { text: " one ", psi_ids: ["PSI-20", "PSI-999"], charts: ["thm02_diluents", "zzz", "thm08_richardson", "thm01_flame_temp"] },
    { text: "two", psi_ids: ["psi-10"], charts: ["thm02_diluents", "thm07_blowoff"] },
    { text: "   ", psi_ids: [], charts: [] },
    { text: "four", psi_ids: "PSI-20", charts: null },
    { text: "five" }, { text: "six" }, { text: "seven" }, { text: "eight" }
  ] };
  const p = STORY.points(a, env);
  assert.equal(p.length, 5);
  assert.deepEqual(p[0], { text: "one", psi_ids: ["PSI-20"], charts: ["thm02_diluents", "thm08_richardson"] });
  assert.deepEqual(p[1], { text: "two", psi_ids: ["PSI-10"], charts: ["thm07_blowoff"] });
  assert.deepEqual(p[2], { text: "four", psi_ids: [], charts: [] });
  assert.equal(p[4].text, "six");
});

test("points falls back to widgets", () => {
  assert.deepEqual(STORY.points({ widgets: [{ type: "thm02_diluents", why: "w" }, { type: "zzz" }] }, env),
    [{ text: "w", psi_ids: ["PSI-20"], charts: ["thm02_diluents"] }]);
  assert.equal(STORY.points({ widgets: [{ type: "thm07_blowoff" }] }, env)[0].text, "desc of thm07_blowoff");
  assert.deepEqual(STORY.points({}, env), []);
  assert.deepEqual(STORY.points(null, env), []);
});

test("rows builds header, points, close", () => {
  const a = { title: "T", summary: "S", key_facts: [{ label: "a", value: "1" }, { label: "b", value: "2" }, { label: "c", value: "3" }, { label: "d", value: "4" }],
    limitations: "lim", evidence: [{ psi_id: "PSI-20" }], follow_ups: ["q?"] };
  const pts = [{ text: "p1", psi_ids: ["PSI-20"], charts: ["thm02_diluents"] },
    { text: "p2", psi_ids: ["PSI-10"], charts: [] }, { text: "p3", psi_ids: [], charts: [] }];
  const r = STORY.rows(a, pts);
  assert.deepEqual(r.map(x => x.kind), ["header", "point", "point", "point", "close"]);
  assert.equal(r[0].items[0].type, "lead"); assert.equal(r[0].items.length, 4);
  assert.deepEqual(r[1].items.map(i => i.type), ["point", "thm02_diluents", "experiment"]);
  assert.deepEqual(r[2].items.map(i => i.type), ["experiment", "point"]);
  assert.equal(r[2].items[0].params.psi_id, "PSI-10");
  assert.deepEqual(r[3].items.map(i => i.type), ["point"]);
  assert.deepEqual(r[4].items.map(i => i.type), ["limitations", "evidence", "follow_ups"]);
  assert.equal(STORY.rows({ summary: "S" }, pts).at(-1).kind, "point");
  const twice = STORY.rows({}, [{ text: "a", psi_ids: ["PSI-20"], charts: [] }, { text: "b", psi_ids: ["PSI-20"], charts: [] }, { text: "c", psi_ids: ["PSI-20", "PSI-10"], charts: ["thm07_blowoff"] }]);
  assert.deepEqual(twice.slice(1).map(r => r.items.map(i => i.type)), [["point", "experiment"], ["point"], ["point", "thm07_blowoff", "experiment"]]);
  assert.equal(twice[3].items[2].params.psi_id, "PSI-10");
});

const sum = a => a.reduce((s, x) => s + x, 0);
test("solve fills the width", () => {
  const o = { gap: 10, minText: 0.3, hmin: 240, hmax: 560, hpref: 380 };
  const rows = [
    [{ flex: true, need: 90000 }, { aspect: 1.8, amin: 1.4, amax: 2.6 }, { flex: true, need: 70000 }],
    [{ flex: true, need: 90000 }, { aspect: 2.0, amin: 1.5, amax: 3.0 }],
    [{ flex: true, need: 90000 }, { aspect: 2.4, amin: 1.6, amax: 3.4 }, { aspect: 2.0, amin: 1.5, amax: 3.0 }],
    [{ aspect: 1.8, amin: 1.4, amax: 2.6 }, { flex: true, need: 40000 }]
  ];
  for (const W of [1200, 1440, 1920]) for (const items of rows) {
    const { h, widths } = STORY.solve(items, W, o);
    assert.ok(Math.abs(sum(widths) + o.gap * (items.length - 1) - W) <= 1, `${W} fill`);
    assert.ok(h >= o.hmin && h <= o.hmax, `${W} h=${h}`);
    const textW = sum(widths.filter((_, k) => items[k].flex));
    assert.ok(textW >= 0.3 * W - 1, `${W} text ${textW}`);
    items.forEach((it, k) => {
      if (it.flex) assert.ok(widths[k] >= 0.2 * W - 1, `${W} text box ${widths[k]}`);
      else assert.ok(widths[k] / h >= it.amin - 1e-6 && widths[k] / h <= it.amax + 1e-6, `${W} aspect ${widths[k] / h}`);
    });
  }
});

test("solve all-flex row", () => {
  const { h, widths } = STORY.solve([{ flex: true, need: 100 }, { flex: true, need: 200 }, { flex: true, need: 700 }], 1400, { gap: 10, minText: 0.3, hmin: 240, hmax: 560 });
  assert.ok(Math.abs(sum(widths) + 20 - 1400) <= 1);
  widths.forEach(w => assert.ok(w >= 0.2 * 1400 - 1));
  assert.ok(widths[2] > widths[1] && widths[1] >= widths[0]);
  assert.ok(h >= 240 && h <= 560);
});

test("solve keeps text readable", () => {
  const need = 600 * 400, o = { gap: 10, minText: 0.3, hmin: 240, hmax: 560 };
  const { h, widths } = STORY.solve([{ flex: true, need }, { aspect: 2.0, amin: 1.5, amax: 3.0 }], 1440, o);
  assert.ok(widths[0] * h >= 0.8 * need || h === o.hmax, `${widths[0]}x${h}`);
});

test("single flex item fills the row", () => {
  const { widths } = STORY.solve([{ flex: true, need: 5000 }], 1300, { gap: 10, minText: 0.3, hmin: 240, hmax: 560 });
  assert.equal(Math.round(widths[0]), 1300);
});


function loadWidgets() {
  const fs = require("node:fs"), vm = require("node:vm");
  const app = {
    document: { documentElement: {} },
    MutationObserver: class { observe() {} }
  };
  app.window = app;
  vm.createContext(app);
  for (const file of ["util.js", "charts.js", "text_widgets.js"])
    vm.runInContext(fs.readFileSync(require.resolve("../js/" + file), "utf8"), app);
  return app;
}

test("calculation cards render assumptions as text and retain calculation details", () => {
  const app = loadWidgets();
  const block = { type: "calculation", result_summary: "The droplet shrank by 0.546 mm.",
    data: { assumptions: ["Isolated <droplet>", "The curve uses 101 points."], regression_rate_mm2_s: 0.41 } };
  const teaser = app.TW.body("workflow_result", block);
  assert.match(teaser, /Model assumptions and defaults/);
  assert.match(teaser, /Isolated &lt;droplet&gt;/);
  assert.match(teaser, /0\.546 mm/);
  assert.match(app.TW.full("workflow_result", block), /regression_rate_mm2_s/);
});

test("close Lewis numbers get distinct chart labels", () => {
  const app = loadWidgets();
  app.CH.host = draw => draw({ w: 600, h: 188 });
  const html = app.TW.body("workflow_result", { type: "chart", chart_type: "scatter",
    x: { label: "Oxidizer oxygen", unit: "mol%", values: [21, 18, 15] },
    series: [{ label: "Methane Lewis number", values: [0.9497, 0.9494, 0.9490] }] });
  assert.match(html, />0\.9497<\/text>/);
  assert.match(html, />0\.9490<\/text>/);
});

test("a named NASA report links directly from the evidence card", () => {
  const app = loadWidgets();
  const html = app.TW.body("evidence", { items: [{ label: "NASA ISS cabin atmosphere",
    note: "Table 1-1", url: "https://ntrs.nasa.gov/citations/20050185597" }] });
  assert.match(html, /href="https:\/\/ntrs\.nasa\.gov\/citations\/20050185597"/);
  assert.match(html, /NASA ISS cabin atmosphere/);
  assert.doesNotMatch(html, /#\/investigation/);
});
