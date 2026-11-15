"""Real NASA backend → Omri browser, offline except localhost. Uses retrieval mode."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main():
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    env={**os.environ,'AI_PROVIDER':'thermo','THERMO_PLANNER':'retrieval','PORT':str(port)}
    process=subprocess.Popen([sys.executable,str(ROOT/'standin/server.py')],env=env,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:urllib.request.urlopen(url+'/api/health',timeout=1);break
            except OSError:time.sleep(.1)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':900})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url)
            page.fill('#q','Show the PSI-39 CFI final science report PDF')
            page.keyboard.press('Enter')
            page.wait_for_selector('.workflow-result',timeout=30000)
            assert 'CFI Science Final Report' in page.inner_text('.workflow-result')
            assert page.locator('.workflow-result a[href*="psi.nasa.gov"]').count()==1
            assert 'completed' in page.locator('.box.ov').text_content(), page.locator('.box.ov').text_content()
            assert 'Preview' not in page.inner_text('.box.ov')
            page.route('**/api/ask',lambda route:route.fulfill(status=503,content_type='application/json',
                body=json.dumps({'provider':'thermo','error':'Test backend unavailable'})))
            page.fill('#q','Another question')
            page.keyboard.press('Enter')
            page.wait_for_function("document.querySelector('.box.ov')?.textContent.includes('Test backend unavailable')")
            assert 'error' in page.locator('.box.ov').text_content()
            assert not page.locator('.box.find').count()
            page.unroute('**/api/ask')
            fixture=json.loads((ROOT.parents[1]/'examples/thermo_frontend_response.json').read_text())
            page.route('**/api/ask',lambda route:route.fulfill(content_type='application/json',body=json.dumps({
                'summary':'Computed synthetic THM-04 test result', 'blocks':fixture['blocks'],
                'meta':{'source':'live','provider':'thermo','status':'completed'}})))
            page.fill('#q','Show computed synthetic chart')
            page.keyboard.press('Enter')
            page.wait_for_selector('.workflow-result svg',timeout=10000)
            assert 'Illustrative' in page.locator('.workflow-result').first.text_content()
            assert not errors,errors
            page.screenshot(path='/tmp/nasa-omri-backend.png',full_page=True)
            browser.close()
        print('PASS NASA backend report, result block, precise source link, and no mock fallback on errors')
    finally:
        process.terminate();process.wait(timeout=10)


if __name__=='__main__':main()
