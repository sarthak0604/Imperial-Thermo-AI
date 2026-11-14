"""Compile semantic node scopes into fixed graph routes. SI assistance: OpenAI Codex."""
from collections import deque
from .query_plan import EDGES, FIELDS


def route(start, end, expression):
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        current, path = queue.popleft()
        if current == end:
            for edge, direction in reversed(path):
                expression = {'kind': 'relation', 'edge': edge, 'direction': direction, 'where': expression}
            return expression
        for edge, (source, target) in EDGES.items():
            for a, b, direction in ((source, target, 'out'), (target, source, 'in')):
                if current == a and b not in seen:
                    seen.add(b)
                    queue.append((b, path + [(edge, direction)]))
    raise ValueError(f'Unknown node type or route: {start} -> {end}')


def compile_expression(expr, current, depth=0):
    if depth > 12 or not isinstance(expr, dict):
        raise ValueError('Invalid or overly nested semantic expression.')
    kind = expr.get('kind')
    if kind == 'on':
        if set(expr) != {'kind', 'node_type', 'where'} or expr['node_type'] not in FIELDS:
            raise ValueError('on requires kind, node_type and where with a valid node type.')
        return route(current, expr['node_type'], compile_expression(expr['where'], expr['node_type'], depth + 1))
    if kind in {'all', 'any'}:
        if set(expr) != {'kind', 'items'} or not isinstance(expr['items'], list):
            raise ValueError('Boolean groups require items.')
        return {'kind': kind, 'items': [compile_expression(x, current, depth + 1) for x in expr['items']]}
    if kind == 'not':
        if set(expr) != {'kind', 'item'}:
            raise ValueError('not requires item.')
        return {'kind': kind, 'item': compile_expression(expr['item'], current, depth + 1)}
    if kind == 'filter':
        return dict(expr)
    raise ValueError('Use semantic on/filter/all/any/not expressions, never graph relations.')


def compile_plan(plan):
    result = dict(plan)
    queries = []
    for query in plan.get('queries', []):
        if 'criteria' not in query:
            queries.append(dict(query, where=compile_expression(query['where'], query['return_type'])))
            continue
        if set(query) != {'label', 'return_type', 'criteria'}:
            raise ValueError('Each query needs label, return_type and criteria only.')
        items, grouped = [], {}
        for criterion in query['criteria']:
            criterion = dict(criterion)
            node_type = criterion.pop('node_type')
            negate = criterion.pop('negated', False)
            if type(negate) is not bool or node_type not in FIELDS:
                raise ValueError('Invalid node_type or negated flag.')
            predicate = dict(criterion, kind='filter')
            if negate:
                items.append({'kind': 'not', 'item': route(query['return_type'], node_type, predicate)})
            elif node_type in {'Concept', 'Variable'}:
                items.append(route(query['return_type'], node_type, predicate))
            else:
                grouped.setdefault(node_type, []).append(predicate)
        for node_type, predicates in grouped.items():
            items.append(route(query['return_type'], node_type, {'kind': 'all', 'items': predicates}))
        queries.append({'label': query['label'], 'return_type': query['return_type'], 'where': {'kind': 'all', 'items': items}})
    result['queries'] = queries
    return result
