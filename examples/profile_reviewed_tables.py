"""Reproduce runtime column profiles from reviewed PSI-25/69 source tables.

Downloads remain temporary. Exact header/unit mappings below are explicit;
unknown units stay null. This supplements, without rewriting, the reviewed graph.
SI assistance: OpenAI Codex.
"""
import hashlib
import json
from pathlib import Path
import tempfile

from imperial_thermo_ai.reviewed_graph import load_graph
from request_planner.execution import ExecutionSession, csv_columns
from request_planner.models import ExecutionLimits


UNITS = {
    'Ambient pressure; mmHg': 'mmHg',
    'O initial ambient composition; mole fraction': '1',
}


def main():
    graph = load_graph()
    records = {}
    for study in ('PSI-25', 'PSI-69'):
        file = next(f for f in graph.search(f'{study} experimental table').files
                    if f.title.startswith(study + '_Experimental table_'))
        with tempfile.TemporaryDirectory(prefix='psi-profile-') as directory:
            session = ExecutionSession(directory, ExecutionLimits())
            path = session.fetch(file)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            # Verify against the retained reviewed source, rather than silently
            # profiling a changed file behind an old resource ID.
            source = Path(__file__).resolve().parents[1] / 'src/reviewed_knowledge_graph/sources' / study / 'extracted'
            extracted = next(json.loads(p.read_text()) for p in source.glob('*.json')
                             if json.loads(p.read_text()).get('id') == file.file_id)
            if digest != extracted['sha256']:
                raise ValueError(f'Reviewed source checksum changed: {file.file_id}')
            file.variables = None
            for encoding in ('utf-8-sig', 'cp1252'):
                file.encoding = encoding
                try:
                    variables, content = csv_columns(path, file)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError('No supported decoder for ' + file.file_id)
            for variable in variables:
                variable.unit = UNITS.get(variable.name)
            records[file.file_id] = {
                'source_url': str(file.retrieval_url), 'size_bytes': file.size_bytes,
                'sha256': digest, 'encoding': file.encoding,
                'column_metadata': [v.model_dump() for v in variables],
                'data_notes': [
                    'Column numeric suitability profiled across all source rows; units supplied only for explicitly mapped headers.',
                    f'Decoded as {file.encoding}; this is an inspection choice, not a NASA-declared encoding.',
                    'Conditions vary between table rows; do not infer a shared run.',
                ] + (['The source header Burning rate; mm has an unresolved unit; it is not treated as mm²/s.'] if study == 'PSI-69' else []),
            }
            print(study, content['row_count'], 'rows,', len(variables), 'columns,', file.encoding)
    target = Path(__file__).resolve().parents[1] / 'src/imperial_thermo_ai/reviewed_file_metadata.json'
    target.write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
