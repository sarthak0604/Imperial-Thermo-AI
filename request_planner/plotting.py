"""Execute one plot operation on a verified local CSV. SI-assisted; see README.md."""

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys

from pydantic import ValidationError

from .mini_graph import FileNode, InvestigationNode, MiniGraph
from .models import SearchResults, ServiceRequest
from .planner import PlanningError, validate_plan


def numeric_pairs(payload: bytes, encoding: str, x: str, y: str) -> tuple[list[float], list[float]]:
    """Reject ambiguous/missing values instead of silently dropping data rows."""
    reader = csv.reader(io.StringIO(payload.decode(encoding)))
    header = next(reader, [])
    if len(header) != len(set(header)) or x not in header or y not in header:
        raise ValueError("CSV must have unique headers and both requested columns")
    x_index, y_index = header.index(x), header.index(y)
    xs, ys = [], []
    for row_number, row in enumerate(reader, start=2):
        if len(row) != len(header):
            raise ValueError(f"CSV row {row_number} has the wrong number of cells")
        try:
            xv, yv = float(row[x_index]), float(row[y_index])
        except ValueError as exc:
            raise ValueError(f"CSV row {row_number} needs inspection: non-numeric or missing value") from exc
        if not math.isfinite(xv) or not math.isfinite(yv):
            raise ValueError(f"CSV row {row_number} contains a non-finite value")
        xs.append(xv)
        ys.append(yv)
    if not xs:
        raise ValueError("CSV contains no data rows")
    return xs, ys


def render_request(request: ServiceRequest, graph: MiniGraph, csv_path: Path, output_dir: Path) -> dict:
    """The local example executor: no network, cleaning, conversions, or aggregation."""
    if request.plan.action != "calculate" or request.plan.requested_asset_ids:
        raise ValueError("This example executor accepts a calculation without additional assets")
    files = [node for node in graph.nodes if isinstance(node, FileNode)]
    validate_plan(request.plan, SearchResults(query_id=request.query_id,
                                             files=[node.record for node in files]), request.limits)
    operation = request.plan.operation
    node = next(node for node in files if node.id == operation.file_id)
    source = next(item for item in graph.nodes if isinstance(item, InvestigationNode)
                  and item.id == node.record.investigation_id)
    with csv_path.open("rb") as handle:
        payload = handle.read(min(request.limits.max_download_bytes, 100_000_000) + 1)
    if len(payload) > min(request.limits.max_download_bytes, 100_000_000):
        raise ValueError("Local CSV exceeds the input byte limit")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != node.verification.sha256:
        raise ValueError("CSV checksum differs from the graph snapshot; inspect and refresh metadata first")
    params = operation.parameters
    xs, ys = numeric_pairs(payload, node.record.encoding or "utf-8-sig", params.x, params.y)

    # Lazy import: planning and graph search do not need the plotting extra.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(9, 6), facecolor="white")
    FigureCanvasAgg(figure)
    axes = figure.add_subplot()
    axes.scatter(xs, ys, s=42, alpha=0.55, color="#187d91", edgecolors="white", linewidths=0.5)
    axes.set_facecolor("#f5f8fa")
    axes.set_axisbelow(True)
    axes.grid(color="#dde5e9", linewidth=0.7)
    for spine in axes.spines.values():
        spine.set_visible(False)
    variables = {variable.name: variable for variable in node.record.variables or []}

    def label(name):
        if "; " in name:
            title, unit = name.rsplit("; ", 1)
            return f"{title}\n({unit})"
        return f"{name.strip()}\n({variables[name].unit})"

    axes.set_xlabel(label(params.x), labelpad=12)
    axes.set_ylabel(label(params.y), labelpad=12)
    title = f"{source.acronym}: recorded CSV values"
    figure.suptitle(title, x=0.17, y=0.95, ha="left", fontsize=19, fontweight="bold", color="#153848")
    axes.set_title(f"{len(xs)} table rows plotted; repeated points may overlap", loc="left",
                   fontsize=10, color="#526672", pad=18)
    figure.subplots_adjust(left=0.17, right=0.96, top=0.82, bottom=0.27)
    figure.text(0.17, 0.12, f"Source: NASA {source.id}  |  DOI: {source.doi}", fontsize=9, color="#526672")
    figure.text(0.17, 0.075, "Different experimental conditions; no causal relationship or safety limit inferred.",
                fontsize=8, color="#526672")
    figure.text(0.17, 0.035, "SI-assisted visualization of source data; no generated measurements.",
                fontsize=8, color="#526672")
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "plot.png"
    figure.savefig(plot_path, dpi=160, metadata={
        "Title": title,
        "Description": f"SI-assisted visualization of NASA PSI data; source SHA-256: {digest}",
        "Source": str(source.source_page_url),
    })
    manifest = {
        "schema_version": "1.0", "status": "completed", "query_id": request.query_id,
        "rows_plotted": len(xs), "rows_dropped": 0,
        "source_sha256": digest,
        "artifacts": [{
            "artifact_id": "plot-" + hashlib.sha256(plot_path.read_bytes()).hexdigest()[:12],
            "kind": "plot", "title": title, "media_type": "image/png", "path": "plot.png",
            "evidence_type": "derived_visualization", "source_file_ids": [node.id],
            "source_page_url": str(source.source_page_url), "source_doi": source.doi,
            "operation": operation.model_dump(),
        }],
        "warnings": [*request.plan.warnings, "Different test conditions; no causal inference or safety limit.",
                     "Repeated points overlap; a marker need not represent a unique test condition."],
        "generated_by": "SI-assisted Python plotter; source measurements are from NASA PSI",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot a verified local PSI CSV using a service request")
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path, help="Previously downloaded original CSV")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        graph = MiniGraph.model_validate_json(args.graph.read_text())
        request = ServiceRequest.model_validate_json(args.request.read_text())
        manifest = render_request(request, graph, args.csv, args.output_dir)
        print(json.dumps(manifest, indent=2))
    except ModuleNotFoundError as exc:
        if exc.name != "matplotlib":
            raise
        print("Plotting requires: uv sync --extra plotting", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, csv.Error, ValidationError, PlanningError, ValueError) as exc:
        print(f"Plot failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

