"""Parse a human question, optionally search a graph, and ALWAYS write JSON.

SI-assisted implementation: OpenAI Codex. No generated scientific predictions.
"""
import argparse
import json
import sys
from pathlib import Path

from .parser import DEFAULT_MODEL, ParserError, QuestionParser, search_graph


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('question')
    cli.add_argument('--output', type=Path, default=Path('query.json'))
    cli.add_argument('--graph', type=Path, help='A JSON graph with nodes and edges.')
    cli.add_argument('--model', default=DEFAULT_MODEL)
    cli.add_argument('--download-model', action='store_true', help='Allow an uncached model download.')
    cli.add_argument('--limit', type=int, default=20)
    args = cli.parse_args()
    code = 0
    try:
        if not 1 <= args.limit <= 1000:
            raise ValueError('--limit must be between 1 and 1000.')
        graph = json.loads(args.graph.read_text(encoding='utf-8-sig')) if args.graph else None
        if graph is not None:
            from .graph_search import GraphIndex
            GraphIndex(graph)
        parser = QuestionParser(model_id=args.model, local_files_only=not args.download_model)
        plan = parser.parse(args.question, graph=graph)
        status = 'out_of_scope' if plan['intent'] == 'out_of_scope' else (
            'needs_clarification' if plan['clarifications'] else 'ready')
        output = {'status': status, 'plan': plan,
                  'metadata': {'parser_version': '2.0', 'model': parser.model_id,
                               'si_assisted': True, 'purpose': 'Evidence discovery; no scientific prediction.'}}
        if graph is not None:
            output['search'] = search_graph(graph, plan, limit=args.limit)
        else:
            output['message'] = 'Plan created. Supply --graph to retrieve graph records.'
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        code = 2
        output = {'status': 'error', 'original_question': args.question,
                  'error': str(exc), 'attempts': getattr(exc, 'attempts', [])}
    formatted = json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted + '\n', encoding='utf-8')
    except OSError as exc:
        print(f'Could not write {args.output}: {exc}', file=sys.stderr)
        return 2
    print(formatted)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
