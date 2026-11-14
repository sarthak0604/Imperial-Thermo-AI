#!/usr/bin/env python3
"""STAND-IN AI BACKEND for local testing — replaced by the backend team's knowledge-graph service later.

Serves the website at http://localhost:8000 and answers POST /api/ask in the agreed answer contract.
It does a simple keyword search over standin/context.json (NASA PSI data + our model catalogue),
sends the best matches to an OpenAI-style chat API, then checks the reply before the site sees it.

Keys are read from environment variables or from frontend/.env.local (git-ignored), never from website code:
  GROQ_API_KEY   Groq, console.groq.com (free plan, rate-limited)
  XAI_API_KEY    xAI Grok, console.x.ai (paid per use)
Optional: AI_PROVIDER=groq|xai, AI_MODEL=<model id>, PORT=8000

Run from the frontend folder:   python3 standin/server.py
Standard library only — nothing to install.
"""
from __future__ import annotations
import json, os, re, sys, time, urllib.error, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # frontend/
CTX = json.loads((Path(__file__).parent / "context.json").read_text(encoding="utf-8"))

PROVIDERS = {  # name: (key env var, chat-completions URL, default model)  — same set-up as Bot Tracker's old ask.py
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b"),
    "xai": ("XAI_API_KEY", "https://api.x.ai/v1/chat/completions", "grok-4.7"),
}
WIDGETS = {  # type: params — must match js/model_widgets.js (thermo-model widgets, outputs pre-computed)
    "thm02_lewis_gauge": '{}  THM-02: where H2, CH4, n-heptane flames sit on the Lewis-number stability scale',
    "thm02_gas_mixer": '{}  THM-02 interactive: fuel, diluent, pressure, O2 slider -> transport properties and Lewis number',
    "thm02_atmospheres": '{}  THM-02: heat and O2 diffusion in ISS vs lunar habitat vs spacesuit air',
    "thm02_diluents": '{}  THM-02: nitrogen vs CO2 vs helium conductivity and Lewis number',
    "thm11_droplet": '{}  THM-11 interactive: n-decane droplet hot -> cool flame, FLEX runs R377/R379',
    "thm11_held_out": '{}  THM-11: model vs NASA observation for FLEX R379 (11 s late)',
    "thm11_facts": '{}  THM-11: droplet burn key times for R377',
    "thm16_heating": '{}  THM-16 interactive (SYNTHETIC material): surface heating to ignition vs heat flux',
    "thm16_heatmap": '{}  THM-16 (SYNTHETIC material): temperature through the slab over time',
    "thm16_ignition_vs_flux": '{}  THM-16 (SYNTHETIC material): time to ignition vs heat flux',
    "thm16_fact": '{}  THM-16 (SYNTHETIC material): time to ignition at 35 kW/m2',
    "thm04_hrr": '{}  THM-04: heat release rate and total energy of a burning sample, reduced from a measured oxygen-calorimetry burn (ground-based reference test)',
    "thm05_spread": '{}  THM-05: flame spread speed against sheet thickness, flame moving against the airflow, checked against two measured points',
    "thm06_rate": '{}  THM-06 (ILLUSTRATIVE inputs): how the concurrent spread rate grows as the flame lengthens, versus its limit',
    "thm06_front": '{}  THM-06 (ILLUSTRATIVE inputs): flame front, base and tip position over time until the sample edge',
    "thm15_soot": '{}  THM-15 (screening, ILLUSTRATIVE inputs): flame temperature against the soot-inception threshold',
    "thm17_limiting_oxygen": '{}  THM-17: lowest oxygen that still burns against airflow speed (quench and blow-off limits)',
    "thm18_dilution": '{}  THM-18 (thermal budget, ILLUSTRATIVE inputs): oxygen left and heat per m3 as CO2 is added to air',
    "thm18_mist": '{}  THM-18 (thermal budget, ILLUSTRATIVE inputs): heat a small water-mist dose absorbs, heating versus evaporating',
    "thm19_cabin": '{}  THM-19 (ILLUSTRATIVE inputs): pressure and temperature rise in a sealed cabin after a fire',
    "thm01_flame_temp": '{}  THM-01: hottest possible flame temperature for methane, hydrogen and propane in ISS air, lunar habitat air and a spacesuit',
    "thm03_zst": '{}  THM-03: where a microgravity methane flame sits around a burner and how that changes with the oxygen supplied',
    "thm07_blowoff": '{}  THM-07: how ventilation speed pushes a flame towards blow-off, ISS air vs lunar habitat air',
    "thm08_richardson": '{}  THM-08 (theoretical bound for Moon/Mars): whether buoyancy or forced airflow dominates on the ISS, Moon, Mars and Earth',
    "thm09_bnumber": '{}  THM-09: how oxygen level changes the burn rate of a plastic (PMMA) surface, B-number',
    "thm20_smoke": '{}  THM-20 (ILLUSTRATIVE inputs): smoke particle count and size drifting along a duct to a detector',
}
TAGS = {"direct_psi", "semi_empirical", "theoretical_bound"}
PERSONA = {
    "general": "a mixed audience of students, researchers and engineers: clear and direct, technically accurate, define jargon briefly.",
    "student": "an undergraduate or school student: plain language, one analogy, define any technical term, 120-200 words.",
    "professor": "a professor or researcher: technical and precise, compare investigations, note open questions and data gaps, 150-280 words.",
    "engineer": "an aerospace engineer making design decisions: short and decision-focused, state conditions, margins and limits, 100-200 words.",
}
INV_IDS = {i["id"] for i in CTX["investigations"]}
STOP = set("the a an of in on for to and or is are be can what which how why does do with from at by it its this that as about into than vs".split())


def load_env():
    env = dict(os.environ)
    f = ROOT / ".env.local"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def pick_provider(env):
    order = [env["AI_PROVIDER"]] if env.get("AI_PROVIDER") in PROVIDERS else []
    order += [p for p in PROVIDERS if p not in order]
    for name in order:
        key_var, url, model = PROVIDERS[name]
        if env.get(key_var):
            return {"name": name, "key": env[key_var], "url": env.get("AI_URL") or url, "model": env.get("AI_MODEL") or model}
    return None


def search(question, k=4):
    """Keyword retrieval — a crude stand-in for the knowledge-graph search."""
    words = {w for w in re.findall(r"[a-z0-9\-]+", question.lower()) if w not in STOP and len(w) > 1}
    scored = []
    for inv in CTX["investigations"]:
        hay = " ".join([inv["id"], inv["acronym"], inv["title"], inv["keywords"], inv["objectives"], " ".join(inv["briefNotes"]),
                        " ".join(inv["hardware"]), inv["draftTags"]["fuelPhase"], " ".join(inv["draftTags"]["roles"])]).lower()
        s = sum(hay.count(w) for w in words)
        if inv["acronym"] and inv["acronym"].lower() in question.lower():
            s += 50
        if inv["draftTags"]["relevance"] == "high":
            s += 1
        if inv["draftTags"]["relevance"] == "low":
            s -= 5
        scored.append((s, inv))
    scored.sort(key=lambda x: -x[0])
    return [slim(inv) for _, inv in scored[:k]]


def slim(inv):
    """Keep the prompt small (Groq's free plan allows about 8K tokens a minute): the fields the answer needs, shortened."""
    out = {"id": inv["id"], "acronym": inv["acronym"], "title": inv["title"], "objectives": str(inv.get("objectives", ""))[:320],
           "notes": [str(n)[:160] for n in (inv.get("briefNotes") or [])[:2]], "hardware": (inv.get("hardware") or [])[:4]}
    return out


def build_messages(question, persona, scenario, history):
    hits = search(question)
    index = [f'{i["id"]} {i["acronym"] or ""}: {i["title"][:38]}' for i in CTX["investigations"]]
    models = [f'{m["id"]} [{m["evidence"]}] {m["description"][:55]} (PSI: {", ".join(m["linkedInvestigations"])})' for m in CTX["models"]]
    sc = CTX["scenarios"].get(scenario, CTX["scenarios"]["iss"])
    data = {
        "facts": CTX["facts"], "selected_scenario": {"id": scenario, **sc},
        "most_relevant_investigations": hits, "all_investigations_index": index,
        "hardware": [{"name": h["name"], "investigations": h["investigations"]} for h in CTX["hardware"]],
        "thermo_models_catalogue": models,
    }
    system = f"""You are the assistant on a NASA Space Apps 2026 website (challenge: {CTX["challenge"]["name"]}).
You help people understand fire safety for crewed spacecraft and habitats using NASA PSI microgravity combustion data.
Reader: {PERSONA.get(persona, PERSONA["student"])}

RULES
- Use ONLY the data in <data>. If it does not answer the question, say so plainly and suggest what data would.
- Every factual claim about an experiment must come from an investigation you list in "evidence".
- Never invent numbers, results, measurements or DOIs. The widgets below show real outputs of the thermo models, but you are NOT given their numbers: describe what a widget shows, never quote a number, range or result from a model, and refer to a widget by what it shows, never by its THM number.
- Lunar/Martian (partial-gravity) statements are theoretical bounds: PSI has no partial-gravity data. Say this whenever the question involves the Moon or Mars.
- Research support only, not safety certification.
- Pick 5-8 widgets that genuinely help, from this list only (they show real thermo-model outputs), only from this list (type: params  [data] what it shows). SYNTHETIC widgets show illustrative shapes only: never quote numbers from them.
{chr(10).join(f"  {t}: {p}" for t, p in WIDGETS.items())}
- Evidence tags: direct_psi (an investigation's own data), semi_empirical (a model/correlation), theoretical_bound (theory or partial-g estimate).

You are NOT chatting. You are designing a one-page DASHBOARD that answers the request.
- title: a short dashboard title (max 8 words).
- summary: the direct answer in 2-4 sentences (markdown, **bold** allowed). Point the reader to the charts you chose by what they show (e.g. "the nitrogen-vs-helium chart"), so text and charts connect.
- key_facts: 2-4 stat tiles. "value" must be SHORT (max 6 words) and copied from <data> (a count you can verify from the data, a condition, a platform, a date range, a facility). Give its psi_id when it comes from one investigation, else null, and name the source.
- widgets: 5-8 items from the list, most important first, mixing real-data and model visuals where useful, each with a one-line "why" saying what it shows for THIS request.
- evidence: every investigation you relied on.

Reply with ONE JSON object, no other text:
{{"title": "...",
 "summary": "...",
 "key_facts": [{{"label": "...", "value": "...", "psi_id": "PSI-xx or null", "source": "e.g. PSI, challenge brief", "tag": "direct_psi"}}],
 "widgets": [{{"type": "...", "params": {{}}, "why": "..."}}],
 "evidence": [{{"psi_id": "PSI-xx", "tag": "direct_psi", "note": "one line: why it is relevant"}}],
 "limitations": "one or two sentences on what the data cannot say",
 "follow_ups": ["2-3 short follow-up requests that would make useful next dashboards"]}}"""
    msgs = [{"role": "system", "content": system}]
    for h in (history or [])[-3:]:
        msgs += [{"role": "user", "content": str(h.get("q", ""))[:500]}, {"role": "assistant", "content": str(h.get("a", ""))[:1200]}]
    msgs.append({"role": "user", "content": f"<data>\n{json.dumps(data, ensure_ascii=False)}\n</data>\n\nQuestion: {question}"})
    return msgs


def call_llm(provider, messages):
    body = {"model": provider["model"], "messages": messages, "temperature": 0.2, "max_tokens": 1000,
            "response_format": {"type": "json_object"}}
    if provider["name"] == "groq" and "gpt-oss" in provider["model"]:
        body["reasoning_effort"] = "low"
    for attempt in range(4):
        req = urllib.request.Request(provider["url"], data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {provider['key']}", "Content-Type": "application/json",
                                              "User-Agent": "flame-in-freefall-standin/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")[:400]
            if e.code == 429 and attempt < 3:
                m = re.search(r"try again in ([0-9.]+)\s*(ms|s|m)", text)
                wait = float(m.group(1)) * {"ms": 0.001, "s": 1, "m": 60}[m.group(2)] if m else float(e.headers.get("retry-after") or 8)
                if wait <= 45:                                   # free-plan rate limit: wait it out instead of failing
                    time.sleep(wait + 0.5); continue
            if e.code == 400 and "response_format" in text and attempt == 0:
                body.pop("response_format"); continue          # provider/model without JSON mode: retry once without
            hint = {401: "key refused — check .env.local", 403: "key refused — check .env.local", 429: "rate limit hit — wait a minute",
                    404: f"model '{provider['model']}' not found — set AI_MODEL", 413: "request too large for this plan"}.get(e.code, text)
            raise RuntimeError(f"{provider['name']} HTTP {e.code}: {hint}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"couldn't reach {provider['name']}: {e.reason}")
    raise RuntimeError("no answer")


def parse_and_check(raw):
    """Never trust model output: keep only known widget types, known PSI ids and known tags."""
    m = re.search(r"\{.*\}", raw, re.S)
    obj = json.loads(m.group(0)) if m else {}
    dropped = []
    ev = []
    for e in obj.get("evidence") or []:
        pid = str(e.get("psi_id", "")).upper().strip()
        if pid in INV_IDS:
            ev.append({"psi_id": pid, "tag": e.get("tag") if e.get("tag") in TAGS else "direct_psi", "note": str(e.get("note", ""))[:300]})
        else:
            dropped.append(f"evidence {pid or '?'}")
    widgets = []
    for w in obj.get("widgets") or []:
        if isinstance(w, dict) and w.get("type") in WIDGETS:
            p = w.get("params") if isinstance(w.get("params"), dict) else {}
            for key in ("id", "node"):
                if key in p and str(p[key]).upper() not in INV_IDS:
                    p = None; break
            if p is not None and "ids" in p:
                p["ids"] = [i for i in p["ids"] if str(i).upper() in INV_IDS][:4]
            if p is not None and "psi_ids" in p:
                p["psi_ids"] = [i for i in p["psi_ids"] if str(i).upper() in INV_IDS][:6]
            if p is not None and "items" in p:
                p["items"] = [it for it in p["items"] if isinstance(it, dict) and str(it.get("id", "")).upper() in INV_IDS]
            if p is not None:
                widgets.append({"type": w["type"], "params": p, "why": str(w.get("why", ""))[:200]}); continue
        dropped.append(f"widget {w.get('type') if isinstance(w, dict) else '?'}")
    facts = []
    for f in obj.get("key_facts") or []:
        if not isinstance(f, dict) or not f.get("label") or not f.get("value"):
            continue
        pid = str(f.get("psi_id") or "").upper().strip()
        if pid and pid not in ("NULL", "NONE") and pid not in INV_IDS:
            dropped.append(f"key fact citing {pid}"); continue
        facts.append({"label": str(f["label"])[:60], "value": str(f["value"])[:60], "psi_id": pid if pid in INV_IDS else None,
                      "source": str(f.get("source") or "")[:60], "tag": f.get("tag") if f.get("tag") in TAGS else None})
    summary = str(obj.get("summary") or obj.get("answer") or "The model returned no answer.")[:4000]
    return {
        "title": str(obj.get("title") or "")[:90], "summary": summary, "answer": summary, "key_facts": facts[:4],
        "evidence": ev, "widgets": widgets[:10],
        "limitations": str(obj.get("limitations") or "")[:800],
        "follow_ups": [str(f)[:200] for f in (obj.get("follow_ups") or [])][:3],
        "dropped": dropped,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, fmt, *args):
        sys.stderr.write("  " + (fmt % args) + "\n")

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/.env") or "standin" in self.path:   # never serve secrets or server code
            return self._json(404, {"error": "not found"})
        if self.path == "/api/health":
            p = pick_provider(load_env())
            return self._json(200, {"ok": True, "provider": p and p["name"], "model": p and p["model"]})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/ask":
            return self._json(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        except ValueError:
            return self._json(400, {"error": "bad JSON"})
        q = str(req.get("question", "")).strip()[:600]
        if not q:
            return self._json(400, {"error": "empty question"})
        provider = pick_provider(load_env())
        if not provider:
            return self._json(503, {"error": "No AI key found. Add GROQ_API_KEY or XAI_API_KEY to frontend/.env.local, then restart."})
        t0 = time.time()
        try:
            raw = call_llm(provider, build_messages(q, req.get("persona"), req.get("scenario"), req.get("history")))
            out = parse_and_check(raw)
        except (RuntimeError, ValueError) as e:
            return self._json(502, {"error": str(e)})
        out["meta"] = {"source": "live", "si_generated": True, "provider": provider["name"], "model": provider["model"],
                       "stand_in": True, "seconds": round(time.time() - t0, 1)}
        print(f"  ask [{req.get('persona')}] {q[:60]!r} -> {len(out['evidence'])} evidence, {len(out['widgets'])} widgets, dropped {out['dropped']}")
        return self._json(200, out)


if __name__ == "__main__":
    env = load_env()
    port = int(env.get("PORT", 8000))
    p = pick_provider(env)
    print(f"Stand-in AI server: http://localhost:{port}")
    print(f"  AI: {p['name']} / {p['model']}" if p else "  AI: NO KEY FOUND — add GROQ_API_KEY or XAI_API_KEY to frontend/.env.local (site will use mock answers)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
