"""Noninteractive graph generation; all run output lives on mounted cloud storage."""

import sys
from pathlib import Path

from psi_graph.manage import main

if "--mode" not in sys.argv or "--graph" not in sys.argv:
    raise SystemExit(
        "Cloud execution requires --mode create/update and --graph /data/graphs/NAME.json"
    )
for option in ("--graph", "--runs"):
    if option in sys.argv:
        value = Path(sys.argv[sys.argv.index(option) + 1]).resolve()
        if not value.is_relative_to(Path("/data")):
            raise SystemExit(option + " must be inside persistent /data")
if __name__ == "__main__":
    raise SystemExit(main())
