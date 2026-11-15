#!/usr/bin/env python3
"""Build data/literature.js from the thermo team's thm_literature_map.py (Imperial-Thermo-AI, main branch,
src/Functions/thm_literature_map.py): for each model, the method, governing equations, up to 3 literature sources and
the PSI investigations it aligns with. The site shows these under each point and in the enlarged chart view.

  python3 standin/build_literature.py --map ~/Documents/Imperial-Thermo-AI/src/Functions/thm_literature_map.py

Without --map it reads the file straight from the repo's origin/main (needs `git fetch` first):
  python3 standin/build_literature.py --repo ~/Documents/Imperial-Thermo-AI
"""
from __future__ import annotations
import argparse, importlib.util, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Short names for the method, shown as "Method: …" next to the charts. Edit freely.
METHOD = {
    "THM-01": "chemical-equilibrium flame temperature", "THM-02": "kinetic-theory gas transport and Lewis number",
    "THM-03": "Burke–Schumann mixture-fraction flame position", "THM-04": "oxygen-consumption calorimetry",
    "THM-05": "de Ris opposed-flow flame spread", "THM-06": "concurrent-flow flame spread",
    "THM-07": "Damköhler-number blow-off", "THM-08": "Richardson-number buoyancy scaling",
    "THM-09": "Spalding B-number burning", "THM-10": "droplet d²-law burning", "THM-11": "two-stage (hot/cool flame) droplet burning",
    "THM-12": "flame-ball radiative balance", "THM-13": "radiative heat loss", "THM-14": "smoke and soot yield",
    "THM-15": "soot-inception screening", "THM-16": "solid ignition by radiant heating", "THM-17": "limiting oxygen against airflow",
    "THM-18": "suppressant thermal budget", "THM-19": "sealed-cabin pressure and temperature rise", "THM-20": "smoke ageing in ducts",
}


def short_cite(c: str) -> str:
    """'Olson, S. L., Ferkul, P. V., & T'ien, J. S. (1988). …' -> 'Olson et al. 1988'."""
    m = re.search(r"\((\d{4}[a-z]?)\)", c)
    year = m.group(1) if m else ""
    authors = c[: m.start()] if m else c
    names = re.findall(r"(?:^|,\s*&?\s*|&\s*)((?:[a-z]+\s)?[A-Z][A-Za-z'’\-]+(?:\s[A-Z][a-z]+)?),\s*(?:[A-Z]\.\s*-?)+", authors)
    if not names:
        return (authors.strip().rstrip(",. ")[:40] + (" " + year if year else "")).strip()
    who = names[0] if len(names) == 1 else f"{names[0]} & {names[1]}" if len(names) == 2 else f"{names[0]} et al."
    return f"{who} {year}".strip()


def link(ident: str) -> str | None:
    i = ident or ""
    m = re.search(r"10\.\d{4,9}/\S+", i)
    if m:
        return "https://doi.org/" + m.group(0).rstrip(".,;)")
    m = re.search(r"ISBN[:\s]*([\d\-Xx]{10,17})", i)
    if m:
        return "https://openlibrary.org/isbn/" + m.group(1).replace("-", "")
    if re.search(r"NASA|NTRS|TM-|TP-|CR-|RP-", i):
        return "https://ntrs.nasa.gov/search?q=" + re.sub(r"[^A-Za-z0-9\-/.]+", "+", i.replace("NASA/", "NASA ")).strip("+")
    m = re.search(r"https?://\S+", i)
    return m.group(0) if m else None


def load(path: Path) -> dict:
    spec = importlib.util.spec_from_file_location("thm_literature_map", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.THM_LITERATURE_MAP


def build(raw: dict) -> dict:
    out = {}
    for mid, e in sorted(raw.items()):
        out[mid] = {
            "method": METHOD.get(mid, str(e.get("domain", "")).split(". ", 1)[-1].lower()),
            "summary": e.get("scientific_method_summary", ""),
            "equations": list(e.get("governing_equations") or [])[:4],
            "sources": [{"short": short_cite(s.get("citation", "")), "citation": s.get("citation", ""), "id": s.get("identifier", ""),
                         "url": link(s.get("identifier", "")), "relevance": s.get("relevance", "")} for s in (e.get("literature_sources") or [])[:3]],
            "boundary": e.get("evidence_boundary", ""),
            "psi": list(e.get("psi_investigations") or []),
            "file": e.get("file_name", ""),
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", type=Path, help="path to thm_literature_map.py")
    ap.add_argument("--repo", type=Path, help="Imperial-Thermo-AI checkout: read the file from origin/main")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "literature.js")
    a = ap.parse_args()
    if a.map:
        path = a.map.expanduser()
    elif a.repo:
        src = subprocess.run(["git", "-C", str(a.repo.expanduser()), "show", "origin/main:src/Functions/thm_literature_map.py"],
                             capture_output=True, text=True, check=True).stdout
        path = Path(tempfile.mkdtemp()) / "thm_literature_map.py"; path.write_text(src, encoding="utf-8")
    else:
        sys.exit("give --map path/to/thm_literature_map.py or --repo path/to/Imperial-Thermo-AI")
    data = build(load(path))
    a.out.write_text("// GENERATED by standin/build_literature.py from the thermo team's thm_literature_map.py (Imperial-Thermo-AI main).\n"
                     "// Method, equations and literature behind each thermo model. Do not hand-edit; rebuild instead.\n"
                     "window.DATA = window.DATA || {};\nwindow.DATA.literature = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print(f"wrote {a.out} ({len(data)} models, {sum(len(v['sources']) for v in data.values())} sources)")


if __name__ == "__main__":
    main()
