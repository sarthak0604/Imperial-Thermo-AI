#!/usr/bin/env python3
"""Serve the Omri website and the shared Thermo backend.

Run from the project environment. POST /api/ask uses request_planner.backend;
THERMO_PLANNER selects local Qwen, API inference, or retrieval-only planning.
HOST defaults to loopback locally; Cloud Run sets it to 0.0.0.0 and supplies PORT.
Secrets are read server-side from the environment or frontend/.env.local.
Legacy stand-in utilities below remain for their unit tests, not HTTP routing.
"""
from __future__ import annotations
import secrets
import urllib.parse
from http.cookies import SimpleCookie
import chart_facts
import thermo
import json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
from threading import BoundedSemaphore
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # frontend/
INFERENCE_SLOT = BoundedSemaphore(1)
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
    "general": "a curious, intelligent non-specialist. Plain words; explain any technical term the first time in a few words.",
    "student": "a physics or engineering student. Plain language, one concrete analogy where it helps, define each technical term once.",
    "professor": "a combustion researcher. Precise and technical; name the dimensionless numbers and regimes, compare investigations, point out where the evidence is thin.",
    "engineer": "an aerospace engineer making design decisions. Lead with what to do or watch for; give conditions, margins and limits; no background lectures.",
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
    # This website always uses the shared scientific backend, including when an
    # old .env.local still names the former Claude stand-in.
    env["AI_PROVIDER"] = "thermo"
    return env


def find_claude(env):
    """The Claude Code command on this computer (Finder-launched scripts may not have it on PATH)."""
    for c in [env.get("CLAUDE_BIN"), shutil.which("claude"), *(str(Path.home() / p) for p in (".local/bin/claude", ".claude/local/claude", ".npm-global/bin/claude")),
              "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return None


def pick_provider(env):
    if str(env.get("AI_PROVIDER", "")).lower() == "claude":          # Claude via your own Claude Code login (Pro/Max plan), no API key
        exe = find_claude(env)
        return {"name": "claude", "bin": exe, "model": env.get("AI_MODEL") or "haiku"} if exe else None
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


def rich():
    """Claude (your plan) has room for more context than Groq's free plan (about 8K tokens a minute)."""
    return str(os.environ.get("AI_PROVIDER", "")).lower() == "claude"


def slim(inv):
    """The fields the answer needs, shortened (more of them when the provider has room)."""
    big = rich()
    out = {"id": inv["id"], "acronym": inv["acronym"], "title": inv["title"], "type": inv.get("type", ""), "platform": inv.get("platform", ""),
           "objectives": str(inv.get("objectives", ""))[:700 if big else 320],
           "notes": [str(n)[:240 if big else 160] for n in (inv.get("briefNotes") or [])[:3 if big else 2]], "hardware": (inv.get("hardware") or [])[:4]}
    if big:
        out["approach"] = str(inv.get("approach", ""))[:400]
        out["impacts"] = str(inv.get("impacts", ""))[:300]
    return out


def build_messages(question, persona, scenario, history):
    hits = search(question, k=int(os.environ.get("AI_CONTEXT_K", 4)))
    index = [f'{i["id"]} {i["acronym"] or ""}: {i["title"][:38]}' for i in CTX["investigations"]]
    models = [f'{m["id"]} [{m["evidence"]}] {m["description"][:55]} (PSI: {", ".join(m["linkedInvestigations"])})' for m in CTX["models"]]
    sc = CTX["scenarios"].get(scenario, CTX["scenarios"]["iss"])
    data = {
        "facts": CTX["facts"], "selected_scenario": {"id": scenario, **sc},
        "most_relevant_investigations": hits, "all_investigations_index": index,
        "hardware": [{"name": h["name"], "investigations": h["investigations"]} for h in CTX["hardware"]],
        "thermo_models_catalogue": models,
    }
    charts = chart_facts.facts(compact=not rich(), linked={m["id"]: m["linkedInvestigations"] for m in CTX["models"]})
    system = f"""You answer questions on a NASA Space Apps 2026 website ({CTX["challenge"]["name"]}) about fire safety in crewed spacecraft and habitats.
Your sources: NASA PSI microgravity combustion investigations (in <data>) and the thermo team's model charts (CHARTS below).
Reader: {PERSONA.get(persona, PERSONA["general"])}

WHAT A GOOD ANSWER LOOKS LIKE
The page shows your summary and key facts first, then your points as boxes in order, each with the charts you attach, then the NASA investigations you cite and a numbered reference list.
It must read like a clear explanation from an expert who knows this data, not a list of caveats.
1. summary: answer the question directly in 1-2 sentences: the conclusion first (yes/no, which, how much, what happens), then the main reason. If the honest answer is uncertain, still give the best-supported answer and say what it rests on.
2. points: 3-5 steps that build to that conclusion, in reading order:
   - each point makes ONE concrete claim, then gives its support (what an investigation in <data> studied or found, or what a chart shows, with its numbers), then says what that means for THIS question;
   - go from what is known/measured, to the mechanism (why), to the consequence for the question;
   - quote numbers from a chart's "Shows:" line when they make the point (they are exactly what the reader sees on the chart); never quote numbers from charts marked ILLUSTRATIVE; never state a number, ratio or comparison ("half", "twice") that is not written in <data>, a "Shows:" line or a "Means:" line;
   - attach 0-2 charts to a point ONLY if that chart directly shows the claim; each chart in one point at most; no chart beats a loosely related one;
   - readers see the first points and charts first: put the chart that most directly answers the question on the earliest point it supports;
   - each chart's "Means:" line is the correct reading of it: never contradict it; if it disagrees with what you expected, the chart wins and your claim changes;
   - when a point rests on a chart, also cite in psi_ids the NASA investigations in its "Built on:" line that are relevant to the point;
   - when a point explains WHY something happens, you may name the chart's method and one source from its "Method:" line, e.g. "Richardson-number scaling (Sacksteder 1990)"; never cite a paper that is not on a "Method:" line;
   - 1-3 sentences per point; no filler ("it is important to note"), no restating the question, no point that only says data is missing.
3. Every point cites at least one NASA investigation in psi_ids (from <data>, or a relevant one from its chart's "Built on:" line). Investigations: say only what <data> says about them. If <data> gives only objectives, write "was designed to study ..." rather than inventing a result. Cite the PSI ids a point relies on in its psi_ids.
4. Gaps and caveats go in "limitations" (1-2 sentences), unless the question is about the gap itself. Moon/Mars: PSI has no partial-gravity data, so those statements are theoretical bounds; say it once. Lunar and Martian gravity is weak but NOT zero: buoyancy still beats normal cabin airflow there (see the buoyancy chart), so never describe lunar flames as if they were ISS microgravity flames, and don't apply a microgravity-only chart to the Moon without saying it was measured in microgravity.
5. Research support only, not safety certification. Refer to charts by what they show, never by THM number.
6. Before replying, check each point: is the claim supported by <data> or a chart? is every number written there? does it contradict any chart's "Means:" line, including charts you did not attach? Fix it if so.

CHARTS (type: what it shows)
{chr(10).join(f"- {t}: {d}" for t, d in charts.items())}

OTHER FIELDS
- title: max 8 words, names the answer's subject (not "Dashboard").
- key_facts: 2-3 tiles; "value" max 6 words, copied from <data> or a chart's "Shows:" line; label says what it is; source names where it came from; psi_id if it comes from one investigation, else null.
- evidence: every investigation you cite, tag direct_psi (its own data), semi_empirical (a model/correlation) or theoretical_bound (theory or partial-g estimate), with a one-line note on what it contributes.
- follow_ups: 2-3 natural next questions this answer raises.

Reply with ONE JSON object and nothing else:
{{"title": "...", "summary": "...",
 "points": [{{"text": "...", "psi_ids": ["PSI-xx"], "charts": ["chart type"]}}],
 "key_facts": [{{"label": "...", "value": "...", "psi_id": "PSI-xx or null", "source": "...", "tag": "direct_psi"}}],
 "evidence": [{{"psi_id": "PSI-xx", "tag": "direct_psi", "note": "..."}}],
 "limitations": "...", "follow_ups": ["..."]}}"""
    msgs = [{"role": "system", "content": system}]
    for h in (history or [])[-3:]:
        msgs += [{"role": "user", "content": str(h.get("q", ""))[:500]}, {"role": "assistant", "content": str(h.get("a", ""))[:1200]}]
    msgs.append({"role": "user", "content": f"<data>\n{json.dumps(data, ensure_ascii=False)}\n</data>\n\nQuestion: {question}"})
    return msgs


def call_claude(provider, messages):
    """Ask Claude through the Claude Code CLI in print mode, signed in with the user's own plan.
    Runs in an empty temp folder with no tools, so it can't read or change anything on the computer."""
    system = messages[0]["content"]
    convo = "\n\n".join(("Earlier question: " if m["role"] == "user" else "Earlier answer: ") + m["content"] for m in messages[1:-1])
    prompt = (convo + "\n\n" if convo else "") + messages[-1]["content"]
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}   # use the plan login, never API billing
    with tempfile.TemporaryDirectory(prefix="fif-claude-") as tmp:
        sp = Path(tmp) / "system.txt"
        sp.write_text(system, encoding="utf-8")
        cmd = [provider["bin"], "-p", "--model", provider["model"], "--output-format", "json", "--system-prompt-file", str(sp),
               "--tools", "", "--strict-mcp-config", "--no-session-persistence"]
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tmp, env=env, timeout=180)
        except subprocess.TimeoutExpired:
            raise RuntimeError("claude: no answer within 3 minutes")
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    except ValueError:
        out = {}
    text = str(out.get("result") or "")
    if r.returncode != 0 or out.get("is_error") or not text:
        why = (text or r.stderr or r.stdout or "no output").strip().splitlines()
        hint = " — open Terminal, run `claude`, and sign in with your Claude account" if any(w in " ".join(why).lower() for w in ("login", "log in", "auth", "sign in")) else ""
        raise RuntimeError(f"claude: {(why[-1] if why else 'failed')[:200]}{hint}")
    return text


def call_llm(provider, messages):
    if provider["name"] == "claude":
        return call_claude(provider, messages)
    body = {"model": provider["model"], "messages": messages, "temperature": 0.2, "max_tokens": 1400,
            "response_format": {"type": "json_object"}}
    if provider["name"] == "groq" and "gpt-oss" in provider["model"]:
        body["reasoning_effort"] = "medium"      # "low" contradicted the charts too often; reasoning tokens count towards max_tokens
        body["max_tokens"] = 2200
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


def fix_chart(t):
    """A slightly mistyped chart name ("thm08_bnumber") becomes the right one when its model number has only one chart."""
    if not isinstance(t, str) or t in WIDGETS:
        return t
    m = re.match(r"(thm\d\d)_", t.strip().lower())
    same = [w for w in WIDGETS if m and w.startswith(m.group(1) + "_")]
    return same[0] if len(same) == 1 else t


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
                item = {"type": w["type"], "params": p, "why": str(w.get("why", ""))[:200]}
                widgets.append(item); continue
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
    points, used = [], set()
    for p in obj.get("points") or []:
        if not isinstance(p, dict) or len(points) >= 5:
            continue
        text = str(p.get("text") or "").strip()[:700]
        if not text:
            continue
        psi = []
        for i in p.get("psi_ids") if isinstance(p.get("psi_ids"), list) else []:
            i = str(i).upper().strip()
            if i in INV_IDS and i not in psi:
                psi.append(i)
            elif i not in INV_IDS:
                dropped.append(f"point evidence {i}")
        charts = []
        for t in p.get("charts") if isinstance(p.get("charts"), list) else []:
            t = fix_chart(t)
            if t in WIDGETS and t not in used and len(charts) < 2:
                charts.append(t); used.add(t)
            elif t not in WIDGETS:
                dropped.append(f"chart {t}")
        points.append({"text": text, "psi_ids": psi[:3], "charts": charts})
    if points:   # the charts the page shows are the ones attached to points
        widgets = [{"type": t, "params": {}, "why": p["text"][:200]} for p in points for t in p["charts"]]
    summary = str(obj.get("summary") or obj.get("answer") or "The model returned no answer.")[:4000]
    return {
        "title": str(obj.get("title") or "")[:90], "summary": summary, "answer": summary, "key_facts": facts[:4],
        "evidence": ev, "widgets": widgets[:10], "points": points,
        "limitations": str(obj.get("limitations") or "")[:800],
        "follow_ups": [str(f)[:200] for f in (obj.get("follow_ups") or [])][:3],
        "dropped": dropped,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def end_headers(self):                                       # always serve the latest files (no stale page after an update)
        self.send_header("Cache-Control", "no-store")
        if getattr(self, 'session_cookie', None):
            self.send_header('Set-Cookie', 'thermo_session='+self.session_cookie+'; HttpOnly; SameSite=Strict; Path=/')
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  " + (fmt % args) + "\n")

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def send_head(self):
        try:
            path = Path(self.translate_path(self.path)).resolve().relative_to(ROOT)
        except (OSError, ValueError):
            self.send_error(404)
            return None
        if any(part.startswith(".") or part == "standin" for part in path.parts):
            self.send_error(404)
            return None
        return super().send_head()

    def do_DELETE(self):
        if not self.path.startswith('/api/conversation?'):
            return self._json(404, {'error':'not found'})
        origin = self.headers.get('Origin')
        if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get('Host'):
            return self._json(403, {'error':'Cross-origin mutation rejected.'})
        from request_planner.conversation import ConversationStore
        cookie = SimpleCookie(self.headers.get('Cookie',''))
        if 'thermo_session' not in cookie:
            return self._json(403, {'error':'Session required.'})
        cid = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
        ConversationStore(load_env().get('THERMO_CONVERSATION_DB','/tmp/thermo-conversations.sqlite3')).delete(cookie['thermo_session'].value,cid)
        return self._json(200, {'deleted':True})

    def do_GET(self):
        if self.path.startswith('/api/conversation?'):
            from request_planner.conversation import ConversationStore, ConversationError
            cookie = SimpleCookie(self.headers.get('Cookie',''))
            if 'thermo_session' not in cookie:
                return self._json(403, {'error':'Session required.'})
            cid = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
            if not cid:
                return self._json(400, {'error':'Conversation ID required.'})
            try:
                _,revision,state = ConversationStore(load_env().get('THERMO_CONVERSATION_DB','/tmp/thermo-conversations.sqlite3')).load(cookie['thermo_session'].value,cid)
                return self._json(200, {'conversation_id':cid,'state_revision':revision,'turns':state['turns'],'clarifications':state['pending']})
            except ConversationError as exc:
                return self._json(exc.status, {'error':str(exc)})
        if self.path == "/api/health":
            env = load_env()
            if env.get("AI_PROVIDER") == "thermo":
                try:
                    return self._json(200, thermo.health(env))
                except ImportError:
                    return self._json(503, {"ok": False, "provider": "thermo",
                                            "error": "Start the server from the project environment."})
            p = pick_provider(env)
            return self._json(200, {"ok": True, "provider": p and p["name"], "model": p and p["model"]})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/ask":
            return self._json(404, {"error": "not found"})
        if not INFERENCE_SLOT.acquire(blocking=False):
            return self._json(503, {"provider": "thermo", "code": "model_busy",
                                    "error": "The model is processing another request. Try again shortly."})
        try:
            return self._handle_post()
        finally:
            INFERENCE_SLOT.release()

    def _handle_post(self):
        if self.path != "/api/ask":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= 100000:
                return self._json(413, {"error": "Request body too large"})
            req = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._json(400, {"error": "bad JSON"})
        if not isinstance(req, dict) or not isinstance(req.get("question"), str):
            return self._json(400, {"error": "question must be text"})
        q = req["question"].strip()
        if len(q) > 12000:
            return self._json(400, {"provider": "thermo", "error": "Question exceeds 12,000 characters. Split it into smaller questions."})
        if not q:
            return self._json(400, {"error": "empty question"})
        env = load_env()
        if env.get("AI_PROVIDER") == "thermo":
            try:
                if req.get('client_request_id'):
                    from request_planner.conversation import ConversationError
                    origin = self.headers.get('Origin')
                    if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get('Host'):
                        return self._json(403, {'error':'Cross-origin conversation request rejected.'})
                    cookie = SimpleCookie(self.headers.get('Cookie', ''))
                    owner = cookie['thermo_session'].value if 'thermo_session' in cookie else secrets.token_urlsafe(32)
                    self.session_cookie = owner
                    try:
                        out = thermo.ask_session(q, env, owner, req)
                    except ConversationError as exc:
                        return self._json(exc.status, {'error':str(exc)})
                else:
                    out = thermo.ask(q, env, context={k: req[k] for k in ("history", "persona", "scenario") if k in req})
            except ImportError:
                return self._json(503, {"provider": "thermo", "error": "Start the server from the project environment with the search extra."})
            except thermo.ModelLoadError:
                return self._json(503, {"provider": "thermo", "error": "Could not load the local Qwen model. Check the model cache and GPU setup."})
            except (OSError, ValueError, KeyError):
                return self._json(500, {"provider": "thermo", "error": "The Thermo workflow could not load its PSI graph or results."})
            return self._json(200, out)
        provider = pick_provider(env)
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
    # Build the shared graph once before accepting concurrent health checks and
    # questions. lru_cache alone allows concurrent cold loads of the 83 MB graph.
    thermo.health(env)
    print(f"Thermo website: http://localhost:{port}")
    print("  Thermo backend · " + env.get("THERMO_PLANNER", "local") + " planning")
    ThreadingHTTPServer((env.get("HOST", "127.0.0.1"), port), Handler).serve_forever()
