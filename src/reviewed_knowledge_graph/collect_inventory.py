"""Retrieve the public NASA PSI inventory; no model or cloud service is used."""
import concurrent.futures
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'psi_kg'))
from psi_graph.nasa_access import get_metadata, list_files

STUDIES = [25,26,117,10,159,101,98,39,102,106,99,107,100,21,20,68,22,23,69]

def collect(number):
    accession = f'PSI-{number}'
    target = ROOT / 'sources' / accession
    target.mkdir(parents=True, exist_ok=True)
    metadata = get_metadata(accession)
    files = list_files(accession, metadata['version'])
    (target / 'metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    (target / 'files.json').write_text(json.dumps(files, indent=2, ensure_ascii=False))
    return {'accession': accession, 'title': metadata.get('title'), 'version': metadata['version'], 'files': len(files), 'bytes': sum(int(f.get('bytes_size') or 0) for f in files)}

if __name__ == '__main__':
    result = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(collect, n): n for n in STUDIES}
        for future in concurrent.futures.as_completed(jobs):
            try:
                row = future.result()
            except Exception as error:
                row = {'accession': f'PSI-{jobs[future]}', 'error': str(error)}
            result.append(row)
            print(json.dumps(row), flush=True)
    (ROOT / 'inventory.json').write_text(json.dumps(result, indent=2))
