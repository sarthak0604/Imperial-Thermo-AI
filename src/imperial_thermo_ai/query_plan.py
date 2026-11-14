"""Validated graph query language. SI-assisted implementation: OpenAI Codex."""
from __future__ import annotations

import math
import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

NodeType = Literal['Investigation', 'Experiment', 'Concept', 'Variable', 'Resource']
EdgeType = Literal['CONTAINS', 'STUDIES', 'MEASURES', 'HAS_RESOURCE']
Scalar = Union[str, int, float, bool, None]
EDGES = {
    'CONTAINS': ('Investigation', 'Experiment'),
    'STUDIES': ('Experiment', 'Concept'),
    'MEASURES': ('Experiment', 'Variable'),
    'HAS_RESOURCE': ('Experiment', 'Resource'),
}
FIELDS = {
    'Investigation': {'id', 'title', 'summary', 'keywords', 'doi', 'source_url'},
    'Experiment': {'id', 'title', 'summary', 'keywords', 'conditions.gravity',
                   'conditions.oxygen_concentration', 'methods', 'source_url'},
    'Concept': {'id', 'name', 'synonyms', 'description'},
    'Variable': {'id', 'name', 'symbol', 'unit', 'role'},
    'Resource': {'id', 'title', 'filename', 'resource_type', 'file_format', 'summary',
                 'keywords', 'variables', 'source_url', 'storage_uri', 'access_status', 'size_bytes'},
}
# These are requests, not assertions that the supplied graph contains these fields.
EVIDENCE_FIELDS = {'material', 'geometry', 'thickness', 'ignition_source',
                   'conditions.pressure', 'conditions.airflow', 'conditions.temperature',
                   'conditions.nitrogen_concentration', 'unmapped'}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Filter(StrictModel):
    kind: Literal['filter']
    field: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z_][A-Za-z0-9_.]*$')
    operator: Literal['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'contains', 'in', 'exists']
    value: Scalar | list[Scalar]
    unit: str | None = None
    basis: str | None = None
    stage: str | None = None
    scope: str | None = None
    source_text: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def check_value(self):
        values = self.value if isinstance(self.value, list) else [self.value]
        if any(isinstance(v, float) and not math.isfinite(v) for v in values):
            raise ValueError('Numeric values must be finite.')
        if self.operator in {'lt', 'lte', 'gt', 'gte'}:
            if type(self.value) not in (int, float):
                raise ValueError('Numeric comparisons require a number, not qualitative text.')
        if self.operator == 'in' and (not isinstance(self.value, list) or not self.value):
            raise ValueError('in requires a nonempty list.')
        if self.operator == 'exists' and type(self.value) is not bool:
            raise ValueError('exists requires true or false.')
        if self.operator not in {'in', 'exists'} and (self.value is None or isinstance(self.value, list)):
            raise ValueError('Use exists for missing values and in for lists.')
        if self.operator == 'contains' and not isinstance(self.value, str):
            raise ValueError('contains requires text.')
        return self


class Group(StrictModel):
    kind: Literal['all', 'any']
    items: list['Expression'] = Field(max_length=30)


class Not(StrictModel):
    kind: Literal['not']
    item: 'Expression'


class Relation(StrictModel):
    kind: Literal['relation']
    edge: EdgeType
    direction: Literal['in', 'out']
    where: 'Expression'


Expression = Annotated[Union[Filter, Group, Not, Relation], Field(discriminator='kind')]
for cls in (Group, Not, Relation):
    cls.model_rebuild()


class SearchQuery(StrictModel):
    label: str = Field(min_length=1, max_length=200)
    return_type: NodeType
    where: Expression


class RequestedField(StrictModel):
    node_type: NodeType
    field: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z_][A-Za-z0-9_.]*$')
    stage: str | None = None
    optional: bool = True


class Clarification(StrictModel):
    source_text: str
    reason: str
    question: str


class QueryPlan(StrictModel):
    schema_version: Literal['2.0'] = '2.0'
    original_question: str
    language: str = Field(min_length=2, max_length=40)
    normalized_question: str = Field(min_length=1, max_length=12000)
    intent: Literal['find', 'compare', 'explain', 'predict', 'out_of_scope']
    search_text: str = Field(max_length=3000)
    queries: list[SearchQuery] = Field(max_length=8)
    requested_fields: list[RequestedField] = Field(default_factory=list, max_length=30)
    clarifications: list[Clarification] = Field(default_factory=list, max_length=10)
    notes: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def check_plan(self):
        if self.intent == 'out_of_scope' and self.queries:
            raise ValueError('Out-of-scope plans must have no graph queries.')
        if self.intent != 'out_of_scope' and not self.queries and not self.clarifications:
            raise ValueError('Supply a graph query or a clarification.')
        if self.intent == 'compare' and len(self.queries) < 2 and not self.clarifications:
            raise ValueError('Comparisons need distinct queries for each group or clarification.')
        return self


def walk_filters(expression):
    """Yield predicates without flattening their Boolean or relationship scope."""
    if expression['kind'] == 'filter':
        yield expression
    elif expression['kind'] == 'relation':
        yield from walk_filters(expression['where'])
    elif expression['kind'] == 'not':
        yield from walk_filters(expression['item'])
    else:
        for item in expression['items']:
            yield from walk_filters(item)


def _compact(text):
    return re.sub(r'\s+', ' ', text).casefold().strip()


def validate_plan(raw, question=None, graph=None):
    """Reject invalid routes and invented quoted evidence before any search."""
    plan = QueryPlan.model_validate(raw).model_dump()
    if question is not None and plan['original_question'] != question:
        raise ValueError('original_question must exactly preserve the input.')
    observed = {key: set(value) for key, value in FIELDS.items()}

    def paths(value, prefix=''):
        if isinstance(value, dict):
            for key, child in value.items():
                path = f'{prefix}.{key}' if prefix else key
                yield path
                yield from paths(child, path)
    if graph:
        for node in graph.get('nodes', []):
            if node.get('type') in observed:
                observed[node['type']].update(paths(node.get('properties', {})))

    def check(expr, node_type, depth=0):
        if depth > 12:
            raise ValueError('Query is too deeply nested; split into smaller searches.')
        kind = expr['kind']
        if kind == 'filter':
            field = expr['field']
            allowed = observed[node_type] | (EVIDENCE_FIELDS if node_type == 'Experiment' else {'unmapped'})
            if field not in allowed:
                raise ValueError(f'{field} is not a field of {node_type}; use unmapped for an unrepresented requirement.')
            if _compact(expr['source_text']) not in _compact(plan['original_question']):
                raise ValueError(f'source_text must quote the ORIGINAL question, including its language and typos: {expr["source_text"]!r}')
        elif kind == 'relation':
            source, target = EDGES[expr['edge']]
            start, end = (source, target) if expr['direction'] == 'out' else (target, source)
            if start != node_type:
                raise ValueError(f'{node_type} cannot follow {expr["edge"]} {expr["direction"]}; valid start is {start}.')
            check(expr['where'], end, depth + 1)
        elif kind == 'not':
            check(expr['item'], node_type, depth + 1)
        else:
            if kind == 'any' and not expr['items']:
                raise ValueError('any must contain alternatives.')
            for item in expr['items']:
                check(item, node_type, depth + 1)
    for query in plan['queries']:
        check(query['where'], query['return_type'])
    return plan
