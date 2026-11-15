"""Run from frontend/:  python3 -m unittest tests/test_server_nocache.py"""
import sys, threading, unittest, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "standin"))
import server


class NoCacheTests(unittest.TestCase):
    def test_site_files_are_not_cached(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            for path in ("/index.html", "/js/tour.js"):
                with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_port}{path}") as r:
                    self.assertEqual(r.status, 200)
                    self.assertIn("no-store", r.headers.get("Cache-Control", ""), path)
        finally:
            httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
