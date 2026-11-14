"""Check numeric parsing and local plot execution. SI-assisted; see README.md."""

import hashlib
from pathlib import Path
import tempfile
import unittest

from request_planner.__main__ import ReplayPlanner
from request_planner.mini_graph import FileNode, MiniGraph, search_graph
from request_planner.planner import build_request
from request_planner.plotting import numeric_pairs, render_request


ROOT = Path(__file__).resolve().parents[1]


class ParsingTests(unittest.TestCase):
    def test_reads_exact_columns_and_keeps_all_rows(self):
        xs, ys = numeric_pairs(b"x,y\n1,2\n3,4\n", "utf-8", "x", "y")
        self.assertEqual(xs, [1.0, 3.0])
        self.assertEqual(ys, [2.0, 4.0])

    def test_missing_approximate_and_nonfinite_values_fail(self):
        for value in ["", "~6", "none", "NaN", "inf"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                numeric_pairs(f"x,y\n1,{value}\n".encode(), "utf-8", "x", "y")

    def test_rejects_wrong_headers_and_ragged_rows(self):
        for content in [b"x,x\n1,2\n", b"x,z\n1,2\n", b"x,y\n1,2,3\n"]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                numeric_pairs(content, "utf-8", "x", "y")


class LocalExecutorTests(unittest.TestCase):
    def setUp(self):
        self.graph = MiniGraph.model_validate_json((ROOT / "examples/psi_graph.json").read_text())
        self.request = build_request(
            "Plot the recorded FLEX pressure and initial ambient composition",
            search_graph(self.graph, "FLEX"), ReplayPlanner(ROOT / "examples/psi_plot_plan.json"),
        )

    def test_wrong_file_fails_before_creating_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "wrong.csv"
            csv_path.write_text("wrong content")
            with self.assertRaisesRegex(ValueError, "checksum"):
                render_request(self.request, self.graph, csv_path, root / "output")
            self.assertFalse((root / "output").exists())

    def test_executes_request_and_records_all_rows_and_source_hash(self):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            self.skipTest("Install plotting extra for image rendering test")
        payload = b"Ambient pressure; mmHg,O initial ambient composition; mole fraction\n760,0.21\n700,0.3\n"
        # Synthetic bytes are confined to this test; match their expected hash.
        node = next(node for node in self.graph.nodes
                    if isinstance(node, FileNode) and node.id == "psi69-experimental-table")
        node.verification.sha256 = hashlib.sha256(payload).hexdigest()
        node.verification.bytes = len(payload)
        node.record.size_bytes = len(payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "test.csv"
            csv_path.write_bytes(payload)
            manifest = render_request(self.request, self.graph, csv_path, root / "output")
            self.assertEqual(manifest["rows_plotted"], 2)
            self.assertEqual(manifest["rows_dropped"], 0)
            self.assertEqual(manifest["source_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual((root / "output/plot.png").read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertTrue((root / "output/manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
