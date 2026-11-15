"""Real HTTP backend + browser checks; no mocked scientific responses.

Run from the repository root with the project environment and Playwright installed.
Uses retrieval planning (no LLM), actual THM solvers, and the bundled reviewed graph.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TEMPERATURE = ('Calculate adiabatic flame temperature for methane with {oxygen}% oxygen '
               'in nitrogen at 101.325 kPa and 298.15 K, with equivalence ratio 1')
COMPARISON = ('How does increasing acrylic sheet thickness from 0.20 to 0.30 mm affect '
              'flame spread against airflow in microgravity with 3 cm/s opposed airflow, '
              '20.7% oxygen, 101.325 kPa pressure, and 20 mm sheet width?')


def main():
    with tempfile.TemporaryDirectory(prefix='thermo-final-e2e-') as temp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, 'AI_PROVIDER': 'claude', 'THERMO_PLANNER': 'retrieval',
               'HOST': '127.0.0.1', 'PORT': str(port),
               'THERMO_CONVERSATION_DB': str(Path(temp) / 'conversations.sqlite3')}
        with (Path(temp) / 'server.log').open('w') as log:
            process = subprocess.Popen([sys.executable, str(ROOT / 'standin/server.py')],
                                       env=env, stdout=log, stderr=log)
            url = f'http://127.0.0.1:{port}'
            try:
                for _ in range(150):
                    try:
                        with urllib.request.urlopen(url + '/api/health', timeout=60) as response:
                            health = json.load(response)
                        break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise AssertionError('Server did not become ready')
                assert health['provider'] == 'thermo', health
                assert health['planner'] == 'retrieval'
                with sync_playwright() as pw:
                    options = {'args': ['--no-sandbox']}
                    chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
                    if chrome.exists():
                        options['executable_path'] = str(chrome)
                    browser = pw.chromium.launch(**options)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(url)
                    page.wait_for_function('API.status.provider === "thermo"')

                    def ask(question):
                        page.fill('#q', question)
                        with page.expect_response(lambda r: r.url.endswith('/api/ask')) as response:
                            page.keyboard.press('Enter')
                        reply = response.value.json()
                        assert response.value.ok, reply
                        page.wait_for_selector('.think.done', timeout=15000)
                        assert reply['meta']['provider'] == 'thermo'
                        assert not reply.get('widgets'), 'Live answers must not choose precomputed demo widgets'
                        return reply

                    first = ask(TEMPERATURE.format(oxygen=21))
                    second = ask(TEMPERATURE.format(oxygen=30))
                    def temperature(reply):
                        return next(b['data']['outputs']['adiabatic_flame_temp_k']
                                    for b in reply['blocks'] if b['type'] == 'calculation')
                    assert temperature(second) > temperature(first), (temperature(first), temperature(second))
                    assert first['meta']['trace_id'] != second['meta']['trace_id']
                    assert page.locator('a[download$="-output.json"]').count()
                    print('PASS different inputs produce different actual solver outputs', flush=True)

                    chart_reply = ask(COMPARISON)
                    assert any(b['type'] == 'chart' for b in chart_reply['blocks']), chart_reply['summary']
                    chart = next(b for b in chart_reply['blocks'] if b['type'] == 'chart')
                    page.wait_for_selector('.workflow-result svg circle.pt')
                    assert page.locator('.workflow-result svg circle.pt').count() == len(chart['x']['values'])
                    assert all(v > 0 for v in chart['series'][0]['values'])
                    assert page.locator('.workflow-result svg').evaluate_all(
                        'nodes => nodes.every(n => !/NaN|Infinity/.test(n.outerHTML))')
                    page.screenshot(path='/tmp/thermo-final-chart-desktop.png', full_page=True)
                    with page.expect_download(timeout=30000) as download:
                        page.locator('#acts-top > [data-pdf]').click()
                    pdf = Path(download.value.path()).read_bytes()
                    assert pdf.startswith(b'%PDF-') and b'/Subtype /Image' in pdf
                    print('PASS PDF export includes the computed chart', flush=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Mobile overflow'
                    page.screenshot(path='/tmp/thermo-final-chart-mobile.png', full_page=True)
                    print('PASS actual backend scatter chart, downloaded outputs, mobile layout', flush=True)

                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    reply = ask('Plot adiabatic flame temperatures for methane, hydrogen and propane in ordinary air at room temperature and sea-level pressure')
                    assert any(b.get('chart_type') == 'bar' for b in reply['blocks'])
                    assert page.locator('.workflow-result meter').count() == 3
                    print('PASS actual backend bar chart', flush=True)

                    page.goto(url)
                    reply = ask('Plot THM-05 flame spread against acrylic sheet thickness')
                    assert reply['meta']['status'] in ('needs_input', 'partial')
                    assert not any(b['type'] in ('calculation', 'chart') for b in reply['blocks'])
                    print('PASS missing inputs produce no invented calculation', flush=True)

                    page.goto(url)
                    reply = ask('Show the PSI-39 CFI final science report PDF')
                    assert page.locator('.workflow-result a[href*="psi.nasa.gov"]').count()
                    print('PASS reviewed NASA source retrieval and links', flush=True)

                    page.goto(url + '/#library')
                    page.wait_for_selector('.box.chart')
                    count = page.locator('.box.chart').count()
                    assert count >= 20
                    # Mount and expand every existing Omri widget, including slider views.
                    for i in range(count):
                        card = page.locator('.box.chart').nth(i)
                        card.scroll_into_view_if_needed()
                        card.click(position={'x': 30, 'y': 30})
                        page.wait_for_selector('.fx .mw-full')
                        sliders = page.locator('.fx input[type=range]')
                        for slider in sliders.all():
                            slider.evaluate("e => { e.value = e.max; e.dispatchEvent(new Event('input', {bubbles: true})); }")
                        page.keyboard.press('Escape')
                    print(f'PASS all {count} Omri library widgets and their slider interactions', flush=True)

                    # An actual broken connection, not a substituted scientific response.
                    page.goto(url)
                    process.terminate()
                    process.wait(timeout=10)
                    page.fill('#q', 'Calculate something while the backend is offline')
                    page.keyboard.press('Enter')
                    page.wait_for_selector('.think.done')
                    assert 'error' in page.locator('.box.ov').inner_text().lower()
                    assert page.locator('.box.find, .workflow-result').count() == 0
                    assert page.evaluate('typeof MOCKGEN === "undefined"')
                    print('PASS backend outage displays an error without mock answers', flush=True)
                    assert not errors, errors
                    browser.close()
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)


if __name__ == '__main__':
    main()
