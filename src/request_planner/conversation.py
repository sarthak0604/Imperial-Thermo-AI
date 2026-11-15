"""Transactional, session-isolated short conversation memory and continuations."""

import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class ConversationError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


class ConversationStore:
    def __init__(self, path, ttl=86400):
        self.path, self.ttl = str(path), ttl
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, owner TEXT NOT NULL, revision INTEGER NOT NULL, updated REAL NOT NULL, state TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS replies (conversation TEXT, request TEXT, response TEXT NOT NULL, PRIMARY KEY(conversation,request))"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def load(self, owner, cid=None):
        if not cid:
            cid = secrets.token_urlsafe(24)
            state = {
                "turns": [],
                "pending": [],
                "active_question": "",
                "facts": [],
                "sources": [],
            }
            with self.connect() as db:
                db.execute(
                    "INSERT INTO conversations VALUES (?,?,0,?,?)",
                    (cid, owner, time.time(), json.dumps(state)),
                )
            return cid, 0, state
        with self.connect() as db:
            row = db.execute(
                "SELECT revision,updated,state FROM conversations WHERE id=? AND owner=?",
                (cid, owner),
            ).fetchone()
        if not row:
            raise ConversationError("Conversation not found for this session.", 404)
        if time.time() - row[1] > self.ttl:
            self.delete(owner, cid)
            raise ConversationError(
                "Conversation expired; start a new conversation.", 410
            )
        return cid, row[0], json.loads(row[2])

    def cached(self, owner, cid, rid):
        self.load(owner, cid)
        with self.connect() as db:
            row = db.execute(
                "SELECT response FROM replies WHERE conversation=? AND request=?",
                (cid, rid),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def commit(self, owner, cid, revision, state, rid, response):
        with self.connect() as db:
            changed = db.execute(
                "UPDATE conversations SET revision=revision+1,updated=?,state=? WHERE id=? AND owner=? AND revision=?",
                (time.time(), json.dumps(state), cid, owner, revision),
            ).rowcount
            if not changed:
                raise ConversationError(
                    "Conversation changed in another request. Reload before retrying."
                )
            db.execute(
                "INSERT INTO replies VALUES (?,?,?)", (cid, rid, json.dumps(response))
            )
            # Bounded response snapshots; retain active typed state independently.
            db.execute(
                "DELETE FROM replies WHERE conversation=? AND rowid NOT IN (SELECT rowid FROM replies WHERE conversation=? ORDER BY rowid DESC LIMIT 12)",
                (cid, cid),
            )

    def delete(self, owner, cid):
        with self.connect() as db:
            if db.execute(
                "DELETE FROM conversations WHERE id=? AND owner=?", (cid, owner)
            ).rowcount:
                db.execute("DELETE FROM replies WHERE conversation=?", (cid,))


def ask_conversation(question, env, owner, request):
    from .backend import answer
    from .context_resolution import resolve
    from .providers import configure
    from .task_router import route

    store = ConversationStore(
        env.get("THERMO_CONVERSATION_DB", "/tmp/thermo-conversations.sqlite3")
    )
    cid, rev, state = store.load(owner, request.get("conversation_id"))
    rid = request.get("client_request_id")
    if not isinstance(rid, str) or not 1 <= len(rid) <= 200:
        raise ConversationError("A client_request_id is required.", 400)
    cached = store.cached(owner, cid, rid)
    if cached:
        return cached
    if request.get("expected_state_revision", rev) != rev:
        raise ConversationError(
            "Conversation revision is stale. Reload before retrying."
        )
    options = configure(env)
    generator = options.get("program_generator")
    options.pop("routing_generator", None)
    started = time.monotonic()
    if generator:
        original = generator
        calls = [0]

        def bounded(messages, max_time=120):
            import inspect

            from .model_worker import InferenceError

            calls[0] += 1
            left = 120 - (time.monotonic() - started)
            if left <= 0 or calls[0] > 6:
                raise InferenceError("Conversation inference budget exceeded.")
            return (
                original(messages, max_time=min(left, max_time))
                if "max_time" in inspect.signature(original).parameters
                else original(messages)
            )

        generator = bounded
        for key in ("program_generator", "answer_generator", "semantic_generator"):
            if options.get(key):
                options[key] = generator
    resolved = resolve(
        question, state, generator, request.get("clarification_answers", [])
    )
    decision = route(
        question,
        generator,
        {"resolved_task": resolved["question"], "pending": state.get("pending", [])},
    )
    turn_id = secrets.token_urlsafe(18)
    context = {
        "history": state["turns"][-4:],
        "resolved_values": resolved["facts"],
        "routing": decision.model_dump(),
        "persona": request.get("persona"),
        "scenario": request.get("scenario"),
    }
    if (
        resolved.get("continuation")
        and decision.intent == "explanation"
        and re.search(
            r"\b(why|explain|result|changed|previous)\b", question, re.IGNORECASE
        )
    ):
        context["previous_results"] = state.get("results", [])
        context["explain_previous"] = bool(context["previous_results"])
    result = answer(
        resolved["question"],
        graph_path=env.get("THERMO_GRAPH"),
        evidence_path=env.get("THERMO_EVIDENCE_INDEX"),
        context=context,
        routing_decision=decision,
        deadline_seconds=max(1, 120 - (time.monotonic() - started)),
        **options,
    )
    response = result.frontend()
    response["meta"]["original_question"] = question
    pending = [s.model_dump() for s in decision.missing]
    pending += [
        {"id": f"backend-{i}", "question": q, "reason_code": "missing_evidence"}
        for i, q in enumerate(result.request.clarifications)
        if q not in {s.question for s in decision.missing}
    ]
    response.update(
        conversation_id=cid,
        turn_id=turn_id,
        state_revision=rev + 1,
        clarifications=pending,
        model_decisions=[decision.model_dump()],
        resolved_inputs_summary=resolved["facts"],
    )
    response["meta"]["conversation_state"] = (
        "awaiting_user" if pending else result.status
    )
    state["turns"] = (
        state["turns"]
        + [
            {
                "id": turn_id,
                "q": question,
                "a": response["summary"],
                "source_file_ids": [
                    e["file_id"] for e in response["evidence"] if e.get("file_id")
                ],
            }
        ]
    )[-4:]
    computed = [b for b in result.result.blocks if b["type"] == "calculation"]
    if computed and len(json.dumps(computed)) < 64000:
        state["results"] = computed[-4:]
    elif not resolved["facts"]:
        state.pop("results", None)
    state.update(
        active_question=resolved["question"], facts=resolved["facts"], pending=pending
    )
    store.commit(owner, cid, rev, state, rid, response)
    return response
