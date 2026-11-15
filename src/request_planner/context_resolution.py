"""Resolve follow-ups using exact historical user spans, never assistant prose."""

import json

from pydantic import Field

from imperial_thermo_ai.parser import _json_object

from .models import Contract


class FactRef(Contract):
    turn: int
    quote: str = Field(min_length=1, max_length=2000)


class Resolution(Contract):
    continuation: bool
    references: list[FactRef] = Field(default_factory=list, max_length=30)


def resolve(question, state, generate=None, answers=()):
    if answers:
        slots = {x["id"]: x for x in state.get("pending", [])}
        parts = []
        for item in answers:
            if not isinstance(item, dict) or item.get("slot_id") not in slots:
                raise ValueError("Unknown clarification slot.")
            parts.append(
                slots[item["slot_id"]]["question"]
                + " User answer: "
                + json.dumps(item.get("value"))
                + " "
                + str(item.get("unit", ""))
                + " "
                + str(item.get("basis", ""))
            )
        question += "\n" + "\n".join(parts)
    turns = state.get("turns", [])
    if not turns:
        return {"question": question, "facts": [], "continuation": False}
    if generate is None:
        # No semantic guessing for an ambiguous context-dependent reply.
        return {"question": question, "facts": [], "continuation": False}
    retained = list(
        dict.fromkeys(f["quote"] for f in state.get("facts", []) if f.get("quote"))
    )
    user_turns = [x["q"] for x in turns] + retained + [question]
    raw = generate(
        [
            {
                "role": "system",
                "content": "Resolve whether the latest question continues the active task or starts a new topic. "
                "Return JSON matching "
                + json.dumps(Resolution.model_json_schema())
                + " References select exact quotes from USER turns (zero based), containing unchanged inputs, "
                "task goal or source names needed to answer the current turn. Never retain a value the user "
                "corrected, a previous species when they changed species, or constraints from an unrelated task. "
                "A short answer to a pending question is a continuation. Include original task wording if still "
                "needed, excluding corrected clauses. Do not cite assistant output as user evidence.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_turns": user_turns,
                        "pending": state.get("pending", []),
                        "active_facts": state.get("facts", []),
                    }
                ),
            },
        ]
    )
    decision = Resolution.model_validate(_json_object(raw))
    facts = []
    if decision.continuation:
        for ref in decision.references:
            if (
                not 0 <= ref.turn < len(user_turns)
                or ref.quote not in user_turns[ref.turn]
            ):
                raise ValueError(
                    "Context resolution invented historical input provenance."
                )
            facts.append({"turn": ref.turn, "quote": ref.quote})
    # Original quotes remain literal so existing parameter provenance checks work.
    text = question
    if facts:
        text = "\n".join(x["quote"] for x in facts) + "\nCurrent request: " + question
    if len(text) > 12000:
        raise ValueError(
            "Resolved task exceeds the input limit; narrow this conversation."
        )
    return {"question": text, "facts": facts, "continuation": decision.continuation}
