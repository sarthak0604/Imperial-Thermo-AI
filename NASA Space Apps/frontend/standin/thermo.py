"""Thin Omri HTTP adapter for the shared version 2 backend."""
class ModelLoadError(RuntimeError):
    pass


def model_id(env):
    if env.get('THERMO_PLANNER') == 'retrieval':
        return 'source retrieval'
    from imperial_thermo_ai.parser import DEFAULT_MODEL
    return env.get('OPENAI_MODEL') if env.get('THERMO_PLANNER') == 'api' else env.get('PSI_PARSER_MODEL') or DEFAULT_MODEL


def health(env):
    from imperial_thermo_ai.reviewed_graph import load_graph
    graph = load_graph(env.get('THERMO_GRAPH'))
    return {
        'ok': True,
        'provider': 'thermo',
        'model': model_id(env),
        'planner': env.get('THERMO_PLANNER', 'local'),
        'graph_id': graph.graph.graph.get('graph_id', 'unknown'),
        'investigation_count': len(graph.investigations),
    }


def ask(question, env, context=None):
    from request_planner.backend import answer
    from request_planner.providers import configure
    result = answer(question, graph_path=env.get('THERMO_GRAPH'), context=context,
                    evidence_path=env.get('THERMO_EVIDENCE_INDEX'), **configure(env))
    response = result.frontend()
    response['meta']['model'] = 'source retrieval' if env.get('THERMO_PLANNER') == 'retrieval' else model_id(env)
    return response


def ask_session(question, env, owner, request):
    from request_planner.conversation import ask_conversation
    return ask_conversation(question, env, owner, request)
