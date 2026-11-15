"""Exercise the final website with the actual Hayk2 calculation backend."""
import importlib.util
import json
import threading
import urllib.request
from pathlib import Path


def test_new_frontend_calls_hayk2_backend(monkeypatch, tmp_path):
    frontend = Path(__file__).resolve().parents[1] / 'NASA Space Apps/frontend'
    monkeypatch.syspath_prepend(str(frontend / 'standin'))
    monkeypatch.setenv('THERMO_PLANNER', 'retrieval')
    monkeypatch.setenv('THERMO_CONVERSATION_DB', str(tmp_path / 'state.sqlite'))
    spec = importlib.util.spec_from_file_location('final_http_server', frontend / 'standin/server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urllib.request.urlopen(base, timeout=10) as response:
            html = response.read().decode()
        assert '<title>IMPER-ai-L</title>' in html
        assert 'js/workflow.js' in html
        assert 'data/mock_answers.js' not in html
        assert 'js/mockgen.js' not in html
        with urllib.request.urlopen(base + '/api/health', timeout=60) as response:
            assert json.load(response)['provider'] == 'thermo'
        results = []
        for mass in (250, 500):
            body = {'question': f'How much heat could {mass} grams of water mist absorb if it warms from 20 °C to 100 °C and half of it evaporates?',
                    'client_request_id': f'mist-{mass}', 'scenario': 'iss'}
            request = urllib.request.Request(base + '/api/ask', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=60) as response:
                reply = json.load(response)
            assert reply['meta']['provider'] == 'thermo'
            assert reply['meta']['status'] == 'completed'
            assert not reply.get('widgets') and not reply.get('figures')
            result = next(b for b in reply['blocks'] if b['type'] == 'calculation')
            assert result['model_id'] == 'THM-18'
            results.append(result['data']['total_water_heat_sink_kJ'])
        assert abs(results[1] - 2 * results[0]) < 1e-8
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
