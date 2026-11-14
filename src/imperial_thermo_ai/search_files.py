"""Search a graph and emit only the planner's file contract. SI: OpenAI Codex."""
import argparse
import gc
import json
import sys
from pathlib import Path
from .vector_search import MODEL_ID, QwenEmbedder, VectorGraphSearch, build_index, fingerprint


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('question', nargs='?')
    cli.add_argument('--graph', type=Path, required=True)
    cli.add_argument('--query-id', required=True)
    cli.add_argument('--mode', choices=['local', 'global'], default='local')
    cli.add_argument('--output', type=Path, default=Path('search-results.json'))
    cli.add_argument('--index', type=Path, default=Path('graph-embeddings.json'))
    cli.add_argument('--query-vector', type=Path, help='JSON {model_id, vector}; vector from the same embedding model.')
    cli.add_argument('--plan', type=Path, help='Existing validated parser plan or its CLI envelope.')
    cli.add_argument('--semantic-only', action='store_true', help='Skip LLM constraint extraction; vector relevance only.')
    cli.add_argument('--top-k', type=int, default=20)
    cli.add_argument('--min-score', type=float, default=0.3)
    cli.add_argument('--strict', action='store_true', help='Exclude candidates with unknown constraints.')
    args = cli.parse_args()
    try:
        if not args.question and not args.query_vector:
            raise ValueError('Supply a question or --query-vector.')
        if args.query_vector and not args.question and not args.plan and not args.semantic_only:
            raise ValueError('Vector-only search needs --plan for constraints or explicit --semantic-only.')
        graph = read(args.graph)
        plan = None
        if args.plan:
            plan = read(args.plan)
            plan = plan.get('plan', plan)
        elif not args.semantic_only:
            from .parser import QuestionParser
            parser = QuestionParser()
            plan = parser.parse(args.question, graph=graph)
            del parser
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        cached = read(args.index) if args.index.exists() else None
        embedder = None
        if cached is None or cached.get('graph_fingerprint') != fingerprint(graph) or cached.get('model_id') != MODEL_ID:
            embedder = QwenEmbedder()
            cached = build_index(graph, embedder)
            args.index.parent.mkdir(parents=True, exist_ok=True)
            args.index.write_text(json.dumps(cached, allow_nan=False), encoding='utf-8')
        service = VectorGraphSearch(graph, cached)
        if args.query_vector:
            vector = read(args.query_vector)
            query_vector, model_id = vector['vector'], vector['model_id']
        else:
            embedder = embedder or QwenEmbedder()
            text = plan['search_text'] if plan and plan['search_text'] else args.question
            query_vector = embedder.encode([text], query=True)[0]
            model_id = embedder.model_id
        search = service.local_search if args.mode == 'local' else service.global_search
        result = search(query_vector, query_id=args.query_id, model_id=model_id,
                        top_k=args.top_k, min_score=args.min_score, plan=plan, include_unknown=not args.strict)
        payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + '\n', encoding='utf-8')
        print(payload)
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
        print(f'Search failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
