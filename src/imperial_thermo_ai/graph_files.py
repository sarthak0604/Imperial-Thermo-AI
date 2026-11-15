"""Shared graph-to-file contract mapping. SI assistance: OpenAI Codex."""
from urllib.parse import parse_qs, urlsplit


def nasa_download_url(node):
    """Recognize a recorded PSI file resolver; never promote an arbitrary landing URL."""
    props = node['properties']
    url = props.get('source_url') or ''
    parsed = urlsplit(url)
    parts = parsed.path.split('/')
    query = parse_qs(parsed.query)
    if (parsed.scheme == 'https' and parsed.netloc == 'psi.nasa.gov'
            and len(parts) == 6 and parts[:4] == ['', 'geode-py', 'ws', 'studies']
            and parts[-1] == 'download' and node['id'].startswith(f'res:{parts[4]}:')
            and len(query.get('file', [])) == 1 and query['file'][0]
            and len(query.get('version', [])) == 1 and query['version'][0].isdigit()
            and props.get('access_status') not in {'citation_only', 'download_failed', 'downloaded_failed'}):
        return url
    return None


def file_kind(props):
    fmt = str(props.get('file_format', '')).lower().lstrip('.')
    mime = props.get('media_type') or {
        'csv': 'text/csv', 'tsv': 'text/tab-separated-values', 'pdf': 'application/pdf',
        'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif',
        'mp4': 'video/mp4', 'webm': 'video/webm', 'mpg': 'video/mpeg', 'avi': 'video/x-msvideo',
        'tif': 'image/tiff', 'txt': 'text/plain', 'json': 'application/json',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }.get(fmt, 'application/octet-stream')
    role = ('video' if mime.startswith('video/') else 'image' if mime.startswith('image/') else
            'documentation' if mime == 'application/pdf' else
            'documentation' if props.get('resource_type', '').lower() in {'paper', 'reports', 'science documents', 'engineering documents', 'presentations'} else
            'measurement' if props.get('resource_type', '').lower() in {'dataset', 'experimental table', 'analyzed data', 'raw data', 'calibration', 'reference data'} else 'other')
    return mime, role


class GraphFileRecords:
    """Requires a validated GraphIndex in self.graph; does not inspect file contents."""

    def _provenance(self, file_id):
        experiments = [e['source'] for e in self.graph.incoming[file_id] if e['type'] == 'HAS_RESOURCE']
        investigations = {e['source'] for exp in experiments for e in self.graph.incoming[exp] if e['type'] == 'CONTAINS'}
        if len(investigations) != 1:
            return None
        return next(iter(investigations)), experiments

    def _record(self, file_id, reason):
        node = self.graph.nodes[file_id]
        props = node['properties']
        inv_id, experiments = self._provenance(file_id)
        inv = self.graph.nodes[inv_id]['properties']
        mime, role = file_kind(props)
        notes = list(props.get('data_notes') or [])
        url = props.get('retrieval_url') or props.get('download_url') or nasa_download_url(node)
        status = props.get('access_status')
        if status:
            notes.append(f'Source review status: {status}. Availability does not establish content review.')
        if props.get('summary'):
            notes.append('Source summary: ' + props['summary'])
        if not url:
            notes.append('Download URL unknown; a landing page is not a file download. Planner cannot select this file yet.')
        if not props.get('columns_verified'):
            variables = None
        else:
            variables = props.get('column_metadata')
        # Never promote graph Variable names or Resource.variables tags to inspected column headers.
        if variables is None:
            notes.append('Column headers, units and numeric suitability have not been verified.')
        # Only explicitly file-level facts are exported, never inherited run conditions.
        conditions = props.get('file_conditions') or {}
        run_ids = props.get('run_ids', []) if props.get('run_ids_verified') else []
        path_edges = [e for exp in experiments for e in self.graph.incoming[exp] + self.graph.outgoing[exp]
                      if e['type'] == 'CONTAINS' or e['target'] == file_id]
        if any(e.get('properties', {}).get('origin') == 'illustrative' or
               e.get('properties', {}).get('verification_status') == 'needs_review' for e in path_edges):
            notes.append('Graph provenance is illustrative or needs review; this is not verified experimental evidence.')
        return {'file_id': file_id, 'investigation_id': inv.get('investigation_id') or inv_id.removeprefix('inv:'),
                'title': props.get('title') or props.get('filename') or file_id,
                'role': role, 'media_type': mime, 'retrieval_url': url,
                'source_page_url': props.get('source_page_url') or (inv.get('source_url') if nasa_download_url(node) else props.get('source_url')) or inv.get('source_url'),
                'size_bytes': props.get('size_bytes'), 'run_ids': run_ids, 'variables': variables,
                'encoding': props.get('encoding'), 'conditions': conditions, 'data_notes': notes,
                'related_file_ids': props.get('related_file_ids') or [], 'match_reason': reason}

