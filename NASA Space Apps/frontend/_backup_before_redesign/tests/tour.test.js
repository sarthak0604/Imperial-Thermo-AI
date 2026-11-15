const test = require("node:test"), assert = require("node:assert/strict");
const TOUR = require("../js/tour.js");

test("steps walks forward and back", () => {
  const t = TOUR.steps(3);
  assert.equal(t.total, 3); assert.equal(t.pos, 0); assert.equal(t.shown(), 1);
  assert.equal(t.back(), false);
  assert.equal(t.next(), true); assert.equal(t.shown(), 2); assert.equal(t.atEnd(), false);
  assert.equal(t.next(), true); assert.equal(t.atEnd(), true); assert.equal(t.shown(), 3);
  assert.equal(t.next(), false); assert.equal(t.pos, 2);
  assert.equal(t.back(), true); assert.equal(t.shown(), 2);
});

test("old API is gone", () => { assert.equal(TOUR.order, undefined); assert.equal(TOUR.caption, undefined); });

test("MIN_BOXES is 3", () => assert.equal(TOUR.MIN_BOXES, 3));

test("pref survives a throwing localStorage", () => {
  Object.defineProperty(global, "localStorage", { configurable: true, get() { throw new Error("denied"); } });
  assert.equal(TOUR.pref.off(), false);
  assert.doesNotThrow(() => TOUR.pref.set(true));
  const m = new Map();
  Object.defineProperty(global, "localStorage", { configurable: true, value: { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: k => m.delete(k) } });
  TOUR.pref.set(true); assert.equal(TOUR.pref.off(), true); assert.equal(m.get("tour-off"), "1");
  TOUR.pref.set(false); assert.equal(TOUR.pref.off(), false);
});
