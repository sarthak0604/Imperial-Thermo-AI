"""The step-by-step walkthrough was replaced by the progressive answer page (Nov 15). Its browser checks now live in
tests/ui_e2e.py; this file just runs those so old commands still work."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name("ui_e2e.py")), run_name="__main__")
