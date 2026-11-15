// Walkthrough helpers: a simple stepper (one row of the answer per step) and the "don't walk me through" preference.
const TOUR = (() => {
  const MIN_BOXES = 3;
  function steps(n) {
    const t = {
      total: n, pos: 0,
      shown() { return t.pos + 1; },
      atEnd() { return t.pos >= n - 1; },
      next() { if (t.atEnd()) return false; t.pos++; return true; },
      back() { if (t.pos <= 0) return false; t.pos--; return true; }
    };
    return t;
  }
  const KEY = "tour-off";
  const pref = {
    off() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } },
    set(v) { try { v ? localStorage.setItem(KEY, "1") : localStorage.removeItem(KEY); } catch (e) {} }
  };
  return { MIN_BOXES, steps, pref };
})();
if (typeof module !== "undefined") module.exports = TOUR;
