"""Persistent request requirements and conservative deterministic output checks."""

import re

from .backend_models import RequestSpec, Requirement


def interpret(prompt, *, aliases=None, context=None):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
        raise ValueError(
            "Question must contain 1 to 12,000 characters; split longer requests."
        )
    kinds = []
    patterns = {
        "calculation": r"\b(calculate|calculating|compute|estimate|predict)\b",
        "chart": r"\b(plot|chart|graph)\b",
        "inspection": r"\b(inspect|columns|headers)\b",
        "explanation": r"\b(why|explain|compare|contrast|difference|summari[sz]e|summar[yi])\b|^how\b",
    }
    for kind, pattern in patterns.items():
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match and not re.search(
            r"(?:do not|don.t|without)\s*$", prompt[: match.start()], re.IGNORECASE
        ):
            kinds.append((kind, match.group()))
    # A numerical before/after question asks for a computed comparison even when
    # the user does not say "calculate". Keep an explicit chart requirement so
    # a prose answer or a single scalar cannot silently satisfy the request.
    quantitative_change = re.search(
        r"\b(?:increas\w*|decreas\w*|chang\w*|vary\w*)\b"
        r".{0,120}\bfrom\s+\d+(?:\.\d+)?(?:\s*(?:mm|cm|m|%|kPa|K))?"
        r"\s+to\s+\d+(?:\.\d+)?\b",
        prompt, re.IGNORECASE | re.DOTALL,
    )
    if quantitative_change and re.search(
        r"\b(?:affect|impact|spread|rate|temperature|number|burn|ignit)\w*\b",
        prompt, re.IGNORECASE,
    ):
        if not any(kind == "calculation" for kind, _ in kinds):
            kinds.append(("calculation", quantitative_change.group()))
        if not any(kind == "chart" for kind, _ in kinds):
            kinds.append(("chart", quantitative_change.group()))
    if re.search(r"\blewis number\b.{0,100}\b(?:for|given|in)\b", prompt, re.IGNORECASE):
        if not any(kind == "calculation" for kind, _ in kinds):
            kinds.append(("calculation", "Lewis number"))
    asks_flame_temperature = re.search(
        r"\bhow hot\b.{0,100}\bflame\b", prompt, re.I
    )
    if asks_flame_temperature and not any(k == "calculation" for k, _ in kinds):
        kinds.append(("calculation", asks_flame_temperature.group()))
    if not any(k in {"calculation", "inspection", "explanation"} for k, _ in kinds):
        for kind, pattern in [
            ("video", r"\bvideos?\b"),
            ("document", r"\b(pdf|reports?|papers?)\b"),
            ("image", r"\b(images?|photos?)\b"),
        ]:
            if m := re.search(pattern, prompt, re.IGNORECASE):
                kinds.append((kind, m.group()))
    if not kinds:
        question = re.match(
            r"^\s*(?:can|could|does|do|is|are|would|will|what|which)\b", prompt, re.I
        )
        kinds = [("explanation", question.group())] if question else [("discovery", prompt)]
    positive, negative = set(), set()
    for m in re.finditer(r"\bPSI\s*-\s*\d+\b", prompt, re.IGNORECASE):
        target = (
            negative
            if re.search(
                r"(?:excluding|except|without|not)\s*$",
                prompt[: m.start()],
                re.IGNORECASE,
            )
            else positive
        )
        target.add(re.sub(r"\s+", "", m.group().upper()))
    remaining = prompt
    for alias, study in sorted((aliases or {}).items(), key=lambda x: -len(x[0])):
        pattern = r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])"
        if m := re.search(pattern, remaining, re.IGNORECASE):
            (
                negative
                if re.search(
                    r"(?:excluding|except|without|not)\s*$",
                    remaining[: m.start()],
                    re.IGNORECASE,
                )
                else positive
            ).add(study)
            remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE)
    clarifications = []
    if positive & negative:
        clarifications.append(
            "The requested investigation is also excluded: "
            + ", ".join(sorted(positive & negative))
        )
    if re.search(r"\b(that|previous)\b", prompt, re.IGNORECASE) and not (
        context or {}
    ).get("history"):
        clarifications.append(
            "Specify the experiment or conditions referred to by the follow-up."
        )
    requirements = [
        Requirement(id=f"task-{i + 1}", kind=k, source_text=t)
        for i, (k, t) in enumerate(kinds)
    ]
    models = list(
        dict.fromkeys(re.findall(r"\bTHM-(?:0[1-9]|1[0-9]|20)\b", prompt.upper()))
    )
    # Naming a THM function in a plot request asks for its calculated output.
    if models and any(k == "chart" for k, _ in kinds) and not any(
        k == "calculation" for k, _ in kinds
    ):
        kinds.append(("calculation", "THM model plot"))
        requirements.append(
            Requirement(id=f"task-{len(requirements) + 1}", kind="calculation",
                        source_text="THM model plot")
        )
    if not models and any(k in {"calculation", "chart"} for k, _ in kinds):
        if re.search(r"\blewis number\b", prompt, re.IGNORECASE):
            models = ["THM-02"]
        elif (re.search(r"\b(?:flame spread|spread rate)\b", prompt, re.IGNORECASE)
              and re.search(r"\b(?:thickness|thick|sheet)\b", prompt, re.IGNORECASE)
              and re.search(r"\b(?:against (?:the )?airflow|opposed[ -]flow|opposite.*airflow|airflow opposing)\b", prompt, re.IGNORECASE)):
            models = ["THM-05"]
        elif asks_flame_temperature or re.search(r"\badiabatic flame temperature\b", prompt, re.IGNORECASE):
            models = ["THM-01"]
    if models and any(k in {"calculation", "chart"} for k, _ in kinds):
        requirements = [r for r in requirements if r.kind != "calculation"] + [
            Requirement(
                id="model-" + model,
                kind="calculation",
                source_text=model,
                model_id=model,
            )
            for model in models
        ]
    return RequestSpec(
        original_prompt=prompt,
        requirements=requirements,
        investigations=sorted(positive),
        excluded_investigations=sorted(negative),
        clarifications=clarifications,
        context=context or {},
        explicit_conditions=re.findall(
            r"\b\d+(?:\.\d+)?\s*(?:%|kPa|mmHg|atm|K\b|cm/s|m/s)|\b(?:lunar|martian|normal gravity)\b",
            prompt,
            re.IGNORECASE,
        ),
    )


def fulfilment(spec, response, *, claims=(), files=()):
    blocks = response.blocks
    rows = []
    for req in spec.requirements:
        if req.kind == "explanation":
            okay = any(c.get("kind") == "supported_summary" for c in claims)
        elif req.kind == "discovery":
            okay = bool(files or blocks)
        elif req.kind == "inspection":
            okay = any(
                b["type"] == "inspection" and b["kind"] != "unsupported" for b in blocks
            )
        else:
            okay = any(
                b["type"] == req.kind
                and (req.model_id is None or b.get("model_id") == req.model_id)
                for b in blocks
            )
        rows.append(
            {
                "id": req.id,
                "kind": req.kind,
                "satisfied": okay,
                "missing": None
                if okay
                else "No supported " + req.kind + " was produced.",
            }
        )
    return rows


def summarize_result(response):
    """Use actual worker results rather than pre-execution planner promises."""
    messages = []
    for block in response.blocks:
        if block["type"] == "calculation":
            data = block["data"]
            if block["model_id"] == "THM-01" and "outputs" in data:
                i, o = data["inputs"], data["outputs"]
                messages.append(
                    f"THM-01 estimates {o['adiabatic_flame_temp_k']:,.2f} K for {i['fuel_species']} "
                    f"at oxygen mole fraction {i['o2_mole_frac']:g}, {i['pressure_kpa']:g} kPa and {i['t_init_k']:g} K."
                )
            else:
                metric = data.get("frontend_summary", {}).get("headline_metric", {})
                if metric.get("value") is not None and metric.get("label"):
                    messages.append(
                        f"{block['model_id']}: {metric['label']} = {metric['value']} "
                        f"{metric.get('unit', '')}. This is a model estimate."
                    )
                else:
                    outputs = data.get("outputs", {})
                    numeric = [
                        (key, val)
                        for key, val in outputs.items()
                        if type(val) in (int, float)
                    ]
                    messages.append(
                        f"{block['model_id']} completed. "
                        + "; ".join(
                            f"{key.replace('_', ' ')}: {val}"
                            for key, val in numeric[:3]
                        )
                    )
        elif block["type"] == "inspection" and block["kind"] == "table":
            messages.append(
                f"Inspected {block['row_count']} rows. Columns: "
                + ", ".join(c["name"] for c in block["columns"])
                + "."
            )
        elif block["type"] == "chart":
            messages.append(
                f"Produced a {block['chart_type']} chart with {len(block['x']['values'])} points."
            )
        elif block["type"] in {"document", "video", "image"}:
            messages.append("Source link: " + block["title"] + ".")
    return "\n\n".join(messages) or response.message


def validate_action(spec, plan, results):
    """Reject known task/scope mismatches before transfers and computations."""
    from .planner import PlanningError

    kinds = {r.kind for r in spec.requirements}
    if plan.action == "calculate":
        operation = plan.operation
        requested = {r.model_id for r in spec.requirements if r.model_id}
        selected_model = getattr(
            getattr(operation, "parameters", None), "model_id", None
        )
        if requested and selected_model not in requested:
            raise PlanningError(
                "Selected calculation does not match the requested THM model."
            )
        if not kinds & {"calculation", "chart"}:
            raise PlanningError("The prompt did not request a calculation or chart.")
    selected = set(plan.selected_file_ids + plan.requested_asset_ids)
    for file in results.files:
        if file.file_id in selected and (
            file.investigation_id in spec.excluded_investigations
            or spec.investigations
            and file.investigation_id not in spec.investigations
        ):
            raise PlanningError(
                "Selected file conflicts with the requested investigation scope."
            )
