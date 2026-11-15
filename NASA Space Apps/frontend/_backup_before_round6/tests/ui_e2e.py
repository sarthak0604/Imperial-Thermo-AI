"""Browser checks for the interface (home, environment picker, ask flow, question tab, full-screen overview, answer boxes,
References/Method drop-downs, PDF, share, data display settings, experiments and All questions file managers, mock mode, phone). Runs the real stand-in server with a FAKE `claude` (tests/fake_claude.py), so the live
path is tested without using your Claude plan.
Run from frontend/:  python3 -I tests/ui_e2e.py      (needs: pip install playwright && python3 -m playwright install chromium)"""
import json, os, socket, subprocess, sys, time, traceback, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/usr/bin/google-chrome" if Path("/usr/bin/google-chrome").exists() else None   # else Playwright's own Chromium


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def start_server():
    port = free_port()
    env = {**os.environ, "AI_PROVIDER": "claude", "CLAUDE_BIN": str(ROOT / "tests" / "fake_claude.py"), "AI_MODEL": "haiku", "PORT": str(port), "FAKE_DELAY": "1"}
    proc = subprocess.Popen([sys.executable, str(ROOT / "standin" / "server.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except Exception:
            time.sleep(.1)
    return proc, f"http://127.0.0.1:{port}/index.html"


def browser(pw):
    kw = {"args": ["--no-sandbox", "--allow-file-access-from-files"]}
    if CHROME: kw["executable_path"] = CHROME
    return pw.chromium.launch(**kw)


def new_page(b, w=1440, h=900, **ctx):
    p = b.new_context(viewport={"width": w, "height": h}, accept_downloads=True, **ctx).new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    return p, errs


def pick_env(p, env="lunar_habitat"):
    """The environment starts empty: asking without one opens the menu; picking one goes on with the question."""
    p.wait_for_selector("#env-pop.open", timeout=3000)
    p.click(f"[data-env={env}]")


def test_live_answer(b, url):
    p, errs = new_page(b)
    p.goto(url); p.wait_for_timeout(500)
    assert "Live AI" in p.inner_text("#ai-status"), p.inner_text("#ai-status")
    assert p.is_visible("#home .pb"), "prompt bar on the home screen"
    assert p.locator(".greet, #sugg, .home-note").count() == 0, "no greeting, suggestions or source note on home"
    assert "Environment" in p.inner_text("#env-pop > button"), "environment starts empty"
    assert p.evaluate("document.getElementById('persona-dd').nextElementSibling.classList.contains('send')"), "persona picker sits just left of send"
    p.fill("#q", "Can fabric catch fire in a lunar habitat?"); p.keyboard.press("Enter"); p.wait_for_timeout(300)
    assert p.locator(".qtab").count() == 0, "nothing asked before an environment is chosen"
    pick_env(p); p.wait_for_timeout(400)
    assert p.is_visible(".qtab .steps"), "question + thinking steps in the tab above the prompt bar"
    assert p.locator(".astage canvas").count() == 1, "the environment, thinking, in the centre"
    p.wait_for_selector(".box.ov h1", timeout=15000); p.wait_for_timeout(1500)
    assert p.inner_text(".box.ov h1") == "Fabric flammability in a lunar habitat"
    assert p.evaluate("!document.querySelector('.qtab').classList.contains('open')"), "the tab shrinks once the answer lands"
    assert p.evaluate("document.getElementById('ask-form').classList.contains('flat')"), "prompt bar flattened under an answer"
    ov = p.evaluate("(() => { const b = document.querySelector('.box.ov').getBoundingClientRect(); return [b.height, innerHeight]; })()")
    assert ov[0] > ov[1] * .6, f"overview fills the screen {ov}"
    assert p.locator(".fcell").count() == 3, "three key facts"
    assert p.locator(".box.find").count() == 4, "four findings"
    assert p.locator(".box.find.s12").count() >= 1, "the two-chart finding is full width"
    assert p.locator("#answer .fups").count() == 0, "no suggested questions on the page"
    assert not p.evaluate("document.getElementById('references').open") and not p.evaluate("document.getElementById('method').open"), "References and Method start closed"
    refs = p.locator(".refs > li").count()
    assert refs >= 6, refs
    assert "PSI-999" not in p.text_content(".refs"), "made-up investigation removed by the server"
    assert "PSI-999" in p.text_content(".made"), "and the Method says what was removed"
    assert p.locator(".hist .hi").count() == 1, "question saved in Recent"
    nums = p.eval_on_selector_all(".cite a", "as => as.map(a => +a.dataset.ref)")
    assert nums and max(nums) <= refs, nums
    p.locator(".box.find .cite a").first.click(); p.wait_for_timeout(700)
    assert p.evaluate("document.getElementById('references').open"), "a citation opens References"
    assert not errs, errs
    return p


def test_expand(p):
    p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
    p.click(".box.ov h1"); p.wait_for_timeout(800)
    assert "ask next" in p.inner_text(".fx").lower() and p.locator(".fx [data-followup]").count() >= 1, "the overview opens full screen, with the follow-up questions"
    p.keyboard.press("Escape"); p.wait_for_timeout(600)
    box = p.locator(".box.find").nth(1); box.scroll_into_view_if_needed(); p.wait_for_timeout(600)
    box.click(position={"x": 30, "y": 30}); p.wait_for_timeout(700)
    r = p.evaluate("(() => { const b = document.querySelector('.fx').getBoundingClientRect(); return [b.width, b.height, innerWidth, innerHeight]; })()")
    assert r[0] > r[2] * .95 and r[1] > r[3] * .95, f"box fills the screen {r}"
    assert p.locator(".fx .mw-full").count() == 1, "full interactive chart inside"
    if p.locator(".fx .tabs button").count() == 2:
        p.click(".fx .tabs button >> nth=1"); p.wait_for_timeout(300)
        assert p.locator(".fx .tabs button[aria-selected=true]").inner_text() == p.locator(".fx .tabs button").nth(1).inner_text()
    p.keyboard.press("Escape"); p.wait_for_timeout(600)
    assert not p.evaluate("document.body.classList.contains('focus-open')"), "Esc closes"
    assert p.evaluate("getComputedStyle(document.querySelectorAll('.box.find')[1]).visibility") == "visible", "box back on the page"
    p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
    p.click(".fcell >> nth=1"); p.wait_for_timeout(700)
    assert "SIBAL" in p.inner_text(".fx"); p.click(".fx-head [data-fx-close]"); p.wait_for_timeout(600)


def test_pdf_and_share(p):
    p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(200)
    with p.expect_download(timeout=30000) as dl:
        p.click(".acts-top > [data-pdf]")
    path = dl.value.path(); data = Path(path).read_bytes()
    assert data[:5] == b"%PDF-" and len(data) > 50000, len(data)
    assert dl.value.suggested_filename.startswith("flame-in-freefall-"), dl.value.suggested_filename
    p.click("#share-pop > button"); p.wait_for_timeout(250)
    assert p.is_visible("[data-share=link]"); p.keyboard.press("Escape")


def test_pages(p):
    p.click("text=Data display settings"); p.wait_for_timeout(900)
    n = p.locator(".fm-it").count(); assert n >= 20, n
    sw = p.locator("[data-ds-chart]").first; sw.click(); p.wait_for_timeout(200)
    assert sw.get_attribute("aria-checked") == "false" and "off" in (p.locator(".fm-it").first.get_attribute("class") or "")
    assert p.evaluate("JSON.parse(localStorage.getItem('fif-display')).off.length") == 1, "switched-off chart is remembered"
    sw.click(); p.wait_for_timeout(200)
    p.fill(".fm-search input", "flame"); p.wait_for_timeout(200)
    assert 0 < p.locator(".fm-it").count() < n
    p.goto(p.url.split("#")[0] + "#library"); p.wait_for_timeout(700)
    assert p.evaluate("location.hash") == "#display", "the old #library link lands on the settings"
    p.click("text=NASA experiments"); p.wait_for_timeout(900)
    assert p.locator(".fm-it").count() >= 20
    p.fill(".fm-search input", "saffire"); p.wait_for_timeout(200)
    k = p.locator(".fm-it").count(); assert 3 <= k < 10, k
    p.fill(".fm-search input", ""); p.click("[data-fm-view=details]"); p.wait_for_timeout(200)
    p.click("[data-fm-sort=years]"); p.wait_for_timeout(200)
    assert p.get_attribute(".fm-th [aria-sort=ascending] button", "data-fm-sort") == "years", "column headers sort"
    p.click("[data-fm-sort=years]"); p.wait_for_timeout(200)
    assert p.locator(".fm-th [aria-sort=descending]").count() == 1
    p.click("[data-fm-view=list]"); p.click("[data-fm-size=l]"); p.wait_for_timeout(200)
    assert p.locator(".fm-list.sz-l .fm-row").count() >= 20, "list view, large items"
    p.click("text=All questions"); p.wait_for_timeout(700)
    assert p.locator(".fm-it").count() == 1
    p.click("[data-qf-new]"); p.wait_for_timeout(150); p.keyboard.press("Control+a"); p.keyboard.type("Moon"); p.keyboard.press("Enter"); p.wait_for_timeout(300)
    p.click("[data-qf=all]"); p.wait_for_timeout(200)
    p.drag_and_drop(".fm-it >> nth=0", ".qf[data-drop^=f]"); p.wait_for_timeout(300)
    assert p.inner_text(".qf[data-drop^=f] .qf-c") == "1", "dragged into the folder"
    p.click(".hist .hi a"); p.wait_for_timeout(1200)
    assert "Saved answer" in p.inner_text(".qtab"), "reopened from Recent, without asking again"


def test_mock_and_phone(b):
    p, errs = new_page(b)
    p.goto("file://" + str(ROOT / "index.html")); p.wait_for_timeout(400)
    p.fill("#q", "How long does a heptane droplet burn?"); p.keyboard.press("Enter"); pick_env(p, "iss"); p.wait_for_timeout(2600)
    assert "preview" in p.inner_text(".box.ov .pill").lower() and p.locator(".box.find").count() >= 2
    assert not errs, errs
    m, errs = new_page(b, 390, 844)
    m.goto("file://" + str(ROOT / "index.html")); m.wait_for_timeout(300)
    m.fill("#q", "Why is a flame in microgravity a sphere?"); m.keyboard.press("Enter"); pick_env(m, "iss"); m.wait_for_timeout(2600)
    wide = m.evaluate("Math.max(...[...document.querySelectorAll('.box, .qtab, .pb')].map(b => b.getBoundingClientRect().right))")
    assert wide <= 391, f"nothing wider than the phone ({wide})"
    assert not errs, errs


if __name__ == "__main__":
    proc, url = start_server(); bad = 0
    try:
        with sync_playwright() as pw:
            b = browser(pw)
            p = None
            for name, fn in [("live answer", lambda: test_live_answer(b, url)), ("full-screen boxes", lambda: test_expand(p)), ("PDF + share", lambda: test_pdf_and_share(p)),
                             ("settings, experiments, all questions, Recent", lambda: test_pages(p)), ("mock mode + phone", lambda: test_mock_and_phone(b))]:
                try:
                    r = fn(); p = r or p; print("ok  ", name)
                except Exception:
                    bad += 1; print("FAIL", name); traceback.print_exc()
            b.close()
    finally:
        proc.terminate()
    print("all passed" if not bad else f"{bad} failed"); sys.exit(1 if bad else 0)
