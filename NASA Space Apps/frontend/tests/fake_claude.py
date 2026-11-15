#!/usr/bin/env python3
# Fake Claude Code CLI for tests: answers like `claude -p --output-format json` would, with a fixed answer
# (one made-up investigation, PSI-999, which the server must drop). No real Claude call, no plan usage.
import json, re, sys, time
prompt = sys.stdin.read()
if "--system-prompt-file" in sys.argv:                       # the chart list is in the system prompt
    prompt += open(sys.argv[sys.argv.index("--system-prompt-file") + 1], encoding="utf-8").read()
# the page's generated figures for this question, if it sent any (round 6): attach them like a real answer would
FIGS = re.findall(r"^- (f[0-9a-z]+_[a-z]+): ", prompt, re.M)
time.sleep(float(__import__("os").environ.get("FAKE_DELAY", "2.5")))
ans = {
 "title": "Fabric flammability in a lunar habitat",
 "summary": "Yes. Cotton-fiberglass (SIBAL) fabric can burn in a lunar habitat, and more readily than on the ISS: the richer 30% oxygen raises the flame temperature, while the Moon's weak gravity still drives a buoyant flow that feeds the flame. NASA's Saffire tests show the same fabric already sustains spreading flames in microgravity at 21% oxygen.",
 "points": [
  {"text": "NASA's Saffire experiments burned large SIBAL fabric samples aboard uncrewed Cygnus vehicles and saw flames spread steadily along the fabric in microgravity. The concurrent-spread model shows the flame front speeding up as it grows along the sample.", "psi_ids": ["PSI-98", "PSI-99"], "charts": ["thm06_rate"]},
  {"text": "Raising oxygen from 21% to 30% at lower pressure lifts the hottest possible flame temperature, so the lunar habitat atmosphere makes fabric easier to ignite and faster to burn than ISS air.", "psi_ids": ["PSI-20"], "charts": ["thm01_flame_temp", "thm17_limiting_oxygen"]},
  {"text": "On the Moon, 0.16 g is weak but not zero: buoyancy still outweighs normal cabin airflow, so a lunar fabric fire behaves more like a slow Earth fire than an ISS flame. This is a theoretical bound; PSI has no partial-gravity data.", "psi_ids": ["PSI-25"], "charts": ["thm08_richardson"]},
  {"text": "BASS-II measured how airflow controls whether thin solid fuels keep burning; slow ventilation that would starve a flame on the ISS is not needed on the Moon, where buoyancy supplies the oxygen.", "psi_ids": ["PSI-25", "PSI-26"], "charts": []}
 ],
 "key_facts": [
  {"label": "Lunar habitat oxygen", "value": "≥ 30% O₂ at ≤ 10.2 psi", "psi_id": None, "source": "Challenge brief", "tag": "direct_psi"},
  {"label": "Fabric tested in orbit", "value": "SIBAL cotton-fiberglass", "psi_id": "PSI-98", "source": "Saffire-I", "tag": "direct_psi"},
  {"label": "Lunar gravity", "value": "0.16 g", "psi_id": None, "source": "Challenge brief", "tag": "theoretical_bound"}
 ],
 "evidence": [
  {"psi_id": "PSI-98", "tag": "direct_psi", "note": "Large-scale fabric flame spread in microgravity aboard Cygnus."},
  {"psi_id": "PSI-99", "tag": "direct_psi", "note": "Repeat flame-spread tests on fabric and acrylic samples."},
  {"psi_id": "PSI-25", "tag": "direct_psi", "note": "Flame spread and extinction over thin solids in controlled airflow."},
  {"psi_id": "PSI-20", "tag": "semi_empirical", "note": "Burning-rate emulator used to relate gaseous fuels to solid burning."},
  {"psi_id": "PSI-999", "tag": "direct_psi", "note": "made up"}
 ],
 "limitations": "PSI holds no partial-gravity combustion data, so every statement about the Moon is a theoretical bound from the buoyancy scaling, not a measurement.",
 "follow_ups": ["How fast would a fire spread along habitat fabric at 30% oxygen?", "Which suppressant works best at 10.2 psi?", "Would a spacesuit's pure oxygen make fabric ignite instantly?"]
}
if FIGS:
    for pt, f in zip(ans["points"], FIGS):
        pt["charts"] = [f]
print(json.dumps({"type": "result", "is_error": False, "result": json.dumps(ans)}))
