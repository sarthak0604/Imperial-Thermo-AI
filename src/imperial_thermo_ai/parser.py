"""LLM interpretation + validated graph plans. SI assistance: OpenAI Codex.

This replaces the six-field parser. Embeddings are not a JSON-generating LLM.
The model interprets language; query_plan validates routes; graph_search executes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .query_plan import FIELDS, validate_plan

from .semantic_plan import compile_plan
SYSTEM_PROMPT = Path(__file__).with_name('flat_prompt.txt').read_text(encoding='utf-8')
DEFAULT_MODEL = 'Qwen/Qwen3-4B-Instruct-2507'


class ParserError(ValueError):
    def __init__(self, message, attempts=None):
        super().__init__(message)
        self.attempts = attempts or []


def graph_catalogue(graph):
    """Bounded vocabulary hints, never put the entire graph in the context."""
    if graph is None:
        return {'fields': {key: sorted(value) for key, value in FIELDS.items()},
                'note': 'No graph supplied. Node availability is unknown.'}
    fields = {key: set(value) for key, value in FIELDS.items()}
    names = []

    def add_paths(kind, value, prefix=''):
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            path = f'{prefix}.{key}' if prefix else key
            fields[kind].add(path)
            if isinstance(child, dict) and not {'value', 'unit'} & child.keys():
                add_paths(kind, child, path)
    for node in graph.get('nodes', []):
        kind = node.get('type')
        if kind not in fields:
            continue
        props = node.get('properties', {})
        add_paths(kind, props)
        if kind in {'Concept', 'Variable', 'Investigation'} and len(names) < 80:
            names.append({'type': kind, 'name': str(props.get('name', props.get('title', '')))[:120],
                          'synonyms': [str(x)[:80] for x in props.get('synonyms', [])[:6]]})
    return {'fields': {key: sorted(value)[:100] for key, value in fields.items()},
            'vocabulary_sample': names, 'note': 'Vocabulary is a sample, not an exhaustive list.'}


def _json_object(text):
    if not isinstance(text, str):
        raise ValueError('Model response must be JSON text.')
    stripped = text.strip()
    if stripped.startswith('```') and stripped.endswith('```'):
        stripped = stripped.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    def pairs(items):
        value = {}
        for key, child in items:
            if key in value:
                raise ValueError(f'Duplicate JSON key: {key}')
            value[key] = child
        return value
    parsed = json.loads(stripped, object_pairs_hook=pairs)
    if not isinstance(parsed, dict):
        raise ValueError('Expected one JSON object.')
    return parsed


def parse_question(question, generate, graph=None, repair_attempts=1):
    """Use an injected generator for tests, or QuestionParser for local inference."""
    if not isinstance(question, str) or not question.strip():
        raise ParserError('Enter a question.')
    if len(question) > 12000:
        raise ParserError('Question exceeds 12,000 characters; split it into smaller questions.')
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': json.dumps(
            {'question': question, 'graph_catalogue': graph_catalogue(graph)}, ensure_ascii=False)},
    ]
    failures = []
    for attempt in range(repair_attempts + 1):
        raw = generate(messages)
        try:
            candidate = compile_plan(_json_object(raw))
            # These are owned by the application, not generated scientific content.
            candidate['schema_version'] = '2.0'
            candidate['original_question'] = question
            plan = validate_plan(candidate, question=question, graph=graph)
            return plan
        except (ValueError, TypeError) as exc:
            failures.append({'attempt': attempt + 1, 'error': str(exc), 'raw_output': raw})
            if attempt < repair_attempts:
                messages += [
                    {'role': 'assistant', 'content': raw},
                    {'role': 'user', 'content': 'Repair ONLY the invalid JSON plan. Keep all the original request. '
                     'Return the complete corrected object. Validation errors: ' + str(exc)[:2500]},
                ]
    raise ParserError('The model could not produce a valid search plan after bounded repair.', failures)


class QuestionParser:
    """Load one local instruction model and reuse it across questions."""
    def __init__(self, model_id=None, *, generate=None, local_files_only=True,
                 max_new_tokens=2400, repair_attempts=1):
        self.model_id = model_id or os.environ.get('PSI_PARSER_MODEL', DEFAULT_MODEL)
        self._generator = generate
        self.local_files_only = local_files_only
        self.max_new_tokens = max_new_tokens
        self.repair_attempts = repair_attempts
        self.model = None
        self.tokenizer = None

    def _load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        kwargs = {'local_files_only': self.local_files_only}
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, **kwargs)
        if torch.cuda.is_available():
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            kwargs.update(device_map='auto', dtype=dtype, quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=dtype))
        else:
            # Preserve checkpoint precision: the 4B model needs about 8 GB in
            # BF16, whereas expanding to FP32 can exhaust a 16 GB CPU machine.
            kwargs.update(device_map='cpu', dtype='auto')
        self.model = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs).eval()

    def generate(self, messages, *, max_time=None):
        if self._generator is not None:
            return self._generator(messages)
        import torch
        if self.model is None:
            self._load()
        inputs = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, enable_thinking=False,
            return_dict=True, return_tensors='pt',
        ).to(self.model.device)
        if inputs.input_ids.shape[1] > 16000:
            raise ParserError('Question and graph vocabulary exceed the configured input limit.')
        with torch.inference_mode():
            tokens = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens,
                                         do_sample=False, pad_token_id=self.tokenizer.eos_token_id, max_time=max_time)
        return self.tokenizer.decode(tokens[0, inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

    def parse(self, question, graph=None):
        return parse_question(question, self.generate, graph=graph, repair_attempts=self.repair_attempts)


def search_graph(graph, query, limit=20):
    """Kept as an import-compatible name; only version 2 plans are accepted."""
    from .graph_search import search_graph as execute
    return execute(graph, validate_plan(query, graph=graph), limit=limit)
