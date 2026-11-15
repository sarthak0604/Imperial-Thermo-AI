"""Browser checks for the answer page (story rows + walkthrough). Run:  python3 -I tests/tour_e2e.py   (needs playwright + /usr/bin/google-chrome)"""
import json, sys, traceback
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = "file://" + str(ROOT / "index.html")
LIVE = {"title": "Flames on the Moon", "summary": "A lunar flame sits **between** an Earth flame and an ISS flame.",
        "key_facts": [{"label": "Lunar gravity", "value": "1/6 of Earth", "source": "brief"}],
        "points": [{"text": "Buoyancy pulls air into flames on Earth but not in orbit.", "psi_ids": ["PSI-25"], "charts": ["thm08_richardson", "thm02_atmospheres"]},
                   {"text": "ISS tests found slow-spreading flames.", "psi_ids": ["PSI-25", "PSI-26"], "charts": []},
                   {"text": "Nothing has been measured at lunar gravity.", "psi_ids": [], "charts": ["zzz"]},
                   {"text": "Oxygen-rich habitat air changes blow-off. " * 16, "psi_ids": ["PSI-20"], "charts": ["thm07_blowoff"]}],
        "evidence": [{"psi_id": "PSI-25"}], "limitations": "No partial-g data.", "follow_ups": ["What does oxygen do to a flame?"], "widgets": [], "meta": {"source": "live"}}
STUB = ("let _a; Object.defineProperty(window,'API',{configurable:true,get(){return _a},set(v){ v.ask = async () => (" + json.dumps(LIVE) + "); _a = v; }});")


def page(pw, w=1440, h=900, url=None, init=None):
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files", "--no-sandbox"])
    p = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce").new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    if init:
        p.add_init_script(init)
    p.goto(url or URL + "#q=" + quote("What happens to a flame on the Moon?"))
    p.wait_for_timeout(900)
    return b, p, errs


ROWS = """[...document.querySelectorAll('.srow:not([hidden])')].map(r => { const bs = [...r.children].map(c => c.getBoundingClientRect());
  return { gap: bs.reduce((s, x) => s + x.width, 0) + 10 * (bs.length - 1) - r.getBoundingClientRect().width, n: bs.length, h: r.offsetHeight }; })"""
visible = lambda p: p.locator(".srow:not([hidden])").count()
locked = lambda p: p.evaluate("document.body.classList.contains('focus-open')")


def test_rows_fill_width(pw):
    for w in (1200, 1440, 1920):
        b, p, errs = page(pw, w=w, init=STUB)
        p.click('[data-tour="skip"]'); p.wait_for_timeout(300)
        for r in p.evaluate(ROWS):
            assert abs(r["gap"]) <= 2, (w, r)
        assert p.evaluate("document.documentElement.scrollWidth") <= w
        assert not errs, errs
        b.close()


def test_charts_keep_shape(pw):
    b, p, _ = page(pw, init=STUB)
    p.click('[data-tour="skip"]'); p.wait_for_timeout(300)
    bad = p.evaluate("""[...document.querySelectorAll('.srow .mtile')].filter(el => { const [a, lo, hi] = MW.shape(el.dataset.type), r = el.getBoundingClientRect();
      const x = r.width / r.height; return x < lo * 0.95 || x > hi * 1.05; }).map(el => el.dataset.type)""")
    assert not bad, bad
    b.close()


def test_ai_points_page(pw):
    b, p, _ = page(pw, init=STUB)
    p.click('[data-tour="skip"]'); p.wait_for_timeout(300)
    rows = p.evaluate("[...document.querySelectorAll('.srow')].map(r => [...r.children].map(c => c.dataset.type || 'lead'))")
    assert rows[1] == ["point", "thm08_richardson", "thm02_atmospheres"], rows[1]
    assert "experiment" in rows[2], rows[2]
    assert rows[3] == ["point"], rows[3]                                    # unknown chart dropped, no PSI → text alone
    long = p.locator(".srow[data-row='4'] .t-point .t-body")
    assert p.evaluate("e => e.scrollHeight <= e.clientHeight + 2 || e.classList.contains('clipped')", long.element_handle())
    assert "undefined" not in p.inner_text(".story")
    b.close()


def test_walkthrough(pw):
    b, p, _ = page(pw, init=STUB)
    total = p.locator(".srow").count()
    assert visible(p) == 1 and "Step 1 of" in p.text_content("#tour-bar")
    p.click('[data-tour="next"]'); p.wait_for_timeout(200)
    assert visible(p) == 2
    top = p.evaluate("document.querySelector('.srow[data-row=\"1\"]').getBoundingClientRect().top")
    assert 0 <= top < 900, top
    p.click('[data-tour="back"]'); p.wait_for_timeout(200)
    assert visible(p) == 1
    p.keyboard.press("ArrowRight"); p.keyboard.press("ArrowRight"); p.wait_for_timeout(200)
    assert visible(p) == 3
    for _ in range(total):
        if p.locator("#tour-bar").is_hidden():
            break
        p.click('[data-tour="next"]'); p.wait_for_timeout(100)
    assert p.locator("#tour-bar").is_hidden() and visible(p) == total and not locked(p)
    b.close()


def test_escape_skip_pref_replay(pw):
    b, p, _ = page(pw, init=STUB)
    p.keyboard.press("Escape"); p.wait_for_timeout(200)
    assert p.locator("#tour-bar").is_hidden() and visible(p) == p.locator(".srow").count()
    p.click("[data-replay]"); p.wait_for_timeout(200)
    assert visible(p) == 1
    p.check('[data-tour="off"]'); p.click('[data-tour="skip"]')
    p.evaluate("location.hash = '#q=' + encodeURIComponent('Why do flames go blue?')"); p.wait_for_timeout(900)
    assert p.locator("#tour-bar").is_hidden() and visible(p) == p.locator(".srow").count()
    b.close()


def test_resize_keeps_revealed(pw):
    b, p, _ = page(pw, init=STUB)
    p.click('[data-tour="next"]'); p.click('[data-tour="next"]')
    p.set_viewport_size({"width": 1200, "height": 800}); p.wait_for_timeout(600)
    assert visible(p) == 3
    for r in p.evaluate(ROWS):
        assert abs(r["gap"]) <= 2, r
    b.close()


def test_library_still_bento(pw):
    b, p, _ = page(pw, url=URL + "#library")
    assert p.locator(".bento").count() >= 1 and p.locator(".story").count() == 0 and p.locator("#tour-bar").is_hidden()
    b.close()


def test_new_question_and_library_reset(pw):
    b, p, _ = page(pw, init=STUB)
    p.click('[data-tour="next"]')
    p.evaluate("location.hash = '#library'"); p.wait_for_timeout(500)
    assert p.locator("#tour-bar").is_hidden() and not locked(p)
    p.evaluate("location.hash = '#q=' + encodeURIComponent('Again?')"); p.wait_for_timeout(900)
    assert visible(p) == 1 and not p.locator("#tour-bar").is_hidden()
    b.close()


def test_phone(pw):
    b, p, _ = page(pw, w=390, h=800, init=STUB)
    assert p.evaluate("document.documentElement.scrollWidth") <= 390
    for sel in ('[data-tour="back"]', '[data-tour="next"]', '[data-tour="skip"]'):
        bx = p.locator(sel).bounding_box()
        assert bx and bx["x"] >= 0 and bx["x"] + bx["width"] <= 390 and bx["y"] + bx["height"] <= 800, (sel, bx)
    p.click('[data-tour="skip"]'); p.wait_for_timeout(300)
    assert p.evaluate("document.documentElement.scrollWidth") <= 390
    b.close()


def test_click_opens_focus(pw):
    b, p, _ = page(pw, init=STUB)
    p.click('[data-tour="skip"]'); p.wait_for_timeout(200)
    p.click(".srow .mtile >> nth=0"); p.wait_for_timeout(150)
    assert not p.evaluate("document.getElementById('focus').hidden")
    p.keyboard.press("Escape"); p.wait_for_timeout(100)
    assert p.evaluate("document.getElementById('focus').hidden") and not locked(p)
    b.close()


def test_mock_mode(pw):
    b, p, errs = page(pw)
    assert p.locator(".srow.point").count() >= 2 and not errs, errs
    b.close()


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    with sync_playwright() as pw:
        for name, fn in tests:
            try:
                fn(pw); print("PASS", name)
            except Exception:
                fails += 1; print("FAIL", name); traceback.print_exc(limit=2)
    print(f"{len(tests) - fails}/{len(tests)} passed")
    sys.exit(1 if fails else 0)
