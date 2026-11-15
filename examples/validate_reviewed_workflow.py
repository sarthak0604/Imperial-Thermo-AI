"""Exercise real reviewed-graph prompts with a live planner and NASA downloads.

Run with --live to permit provider calls and bounded source downloads. Results
contain the actual plans, frontend blocks, diagnostics and source checksums.
SI assistance: OpenAI Codex.
"""

import argparse
import json
from pathlib import Path
import time

from imperial_thermo_ai.reviewed_graph import load_graph
from request_planner.planner import OpenAIPlanner
from request_planner.service import run_workflow


CASES = [
    ("cfi-report", "Show me the PSI-39 CFI final science report as a PDF.", "document"),
    ("bass-video", "Show the PSI-25 BASS-II T23 still sequence video.", "video"),
    ("same-report", "Show the PSI-102 SAME final science report PDF about smoke detectors.", "document"),
    ("bass-inspection", "Inspect the PSI-25 BASS-II experimental CSV table and list its columns. Do not calculate.", "inspection"),
    ("flex-plot", "Plot Ambient pressure; mmHg against O initial ambient composition; mole fraction from the PSI-69 FLEX experimental table.", "chart"),
    ("flex-thm01", "Estimate the adiabatic flame temperature for CH4 at 101.325 kPa and 298.15 K, using the oxygen mole fraction from the first test of the PSI-69 FLEX experimental table. State the scenario assumptions.", "calculation"),
    ("missing-evidence", "Calculate heat release with THM-04 from the PSI-117 Kavg burning-rate table.", "no_calculation"),
    ("unknown-study", "Find the experimental table for PSI-99999.", "empty"),
]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--live', action='store_true', required=True)
    cli.add_argument('--model', default='gpt-4.1-mini')
    cli.add_argument('--output', type=Path, default=Path('/tmp/reviewed-workflow-validation.json'))
    args = cli.parse_args()
    started = time.monotonic()
    graph = load_graph()
    rows = []
    for name, prompt, expected in CASES:
        begin = time.monotonic()
        results = graph.search(prompt)
        response = run_workflow(prompt, results, OpenAIPlanner(args.model), planning_seconds=60)
        kinds = {block['type'] for block in response.blocks}
        if expected == 'no_calculation':
            passed = 'calculation' not in kinds and response.status in {'no_match', 'needs_input'}
        elif expected == 'empty':
            passed = not results.files and response.status == 'no_match'
        else:
            passed = expected in kinds and response.status != 'error'
        if name == 'cfi-report':
            passed = passed and any('CFI Science Final Report' in source['title'] for source in response.sources)
        if name == 'flex-plot':
            charts = [b for b in response.blocks if b['type'] == 'chart']
            passed = passed and bool(charts) and len(charts[0]['x']['values']) == 274
        if name == 'flex-thm01':
            calculations = [b for b in response.blocks if b['type'] == 'calculation']
            if calculations:
                data = calculations[0]['data']
                passed = passed and (data['inputs']['o2_mole_frac'] == 0.21
                    and data['inputs']['fuel_species'] == 'CH4'
                    and data['inputs']['pressure_kpa'] == 101.325
                    and data['inputs']['t_init_k'] == 298.15
                    and 2200 < data['outputs']['adiabatic_flame_temp_k'] < 2250)
        row = {'case': name, 'prompt': prompt, 'expected': expected, 'passed': passed,
               'seconds': round(time.monotonic() - begin, 2),
               'retrieved_file_ids': [f.file_id for f in results.files],
               'response': response.model_dump(mode='json')}
        rows.append(row)
        print(f'{name}: {response.status}, blocks={sorted(kinds)}, passed={passed}', flush=True)
        print(response.message[:300], flush=True)
        args.output.write_text(json.dumps({'graph_id': graph.graph.graph.get('graph_id'),
            'model': args.model, 'seconds': round(time.monotonic()-started, 2), 'cases': rows}, indent=2) + '\n')
    return 0 if all(row['passed'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
