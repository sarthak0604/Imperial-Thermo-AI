// AI client.
// Every question first goes through the demo pipeline (js/pipeline.js): it runs the thermo models on the question's
// conditions with synthetic data and draws the figures. Then:
// - Served by standin/server.py (http://localhost:8000): LIVE answers from POST /api/ask. The request carries the
//   figures' readings (`figures`), so the AI writes about exactly what the figures show and attaches them by id.
// - Opened as a file, or no AI key: the pipeline's own write-up of the figures (meta.source "demo").
// - Later: point ENDPOINT at the backend team's service. The API key always stays server-side.
window.API = {
  ENDPOINT: "/api/ask",
  status: { mode: location.protocol.startsWith("http") ? "live" : "mock", provider: null, model: null, error: null },

  async health() {
    if (this.status.mode !== "live") return this.status;
    try {
      const r = await fetch("/api/health");
      const j = await r.json();
      Object.assign(this.status, { provider: j.provider, model: j.model, error: j.provider ? null : "no AI key on the server" });
    } catch (e) { Object.assign(this.status, { mode: "mock", error: "stand-in server not reachable" }); }
    return this.status;
  },

  describe() {
    const s = this.status;
    if (s.mode === "live" && s.provider) return `live — ${s.provider} / ${s.model} (stand-in)`;
    return "mock" + (s.error ? ` (${s.error})` : " (open via standin/server.py for live answers)");
  },

  async ask({ question, persona, scenario, history, signal, run }) {
    run = run || PIPE.run(question, persona, scenario);
    if (this.status.mode === "live" && this.status.provider) {
      try {
        const r = await fetch(this.ENDPOINT, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, persona, scenario, history, figures: run.brief }), signal
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error || "server error " + r.status);
        const a = this.normalise(j);
        a.figures = run.figures;                                            // the server only names them; the page has the data
        if (!a.method) a.method = run.answer.method;
        a.meta = { ...a.meta, models: run.answer.meta.models };
        return a;
      } catch (e) {
        if (e.name === "AbortError") return { meta: { aborted: true } };   // the user pressed stop
        return this.mock({ question, persona, scenario, run }, e.message);   // never leave the user with nothing
      }
    }
    return this.mock({ question, persona, scenario, signal, run });
  },

  // no AI: the pipeline's own answer, written from the figures (after a pause the length of a short think)
  async mock({ question, persona, scenario, signal, run }, error) {
    await new Promise(res => setTimeout(res, error ? 0 : 2600));
    if (signal && signal.aborted) return { meta: { aborted: true } };
    const a = JSON.parse(JSON.stringify((run || PIPE.run(question, persona, scenario)).answer));
    a.meta = { ...a.meta, source: "demo", error: error || null, echo_question: question, scenario };
    return a;
  },

  // Make any answer safe to render, whatever the backend sends
  normalise(a) {
    return {
      title: a.title || "", summary: a.summary || a.answer || "", key_facts: Array.isArray(a.key_facts) ? a.key_facts : [],
      answer: String(a.answer || a.summary || ""), evidence: Array.isArray(a.evidence) ? a.evidence : [],
      widgets: Array.isArray(a.widgets) ? a.widgets : [], points: Array.isArray(a.points) ? a.points : [], limitations: a.limitations || "",
      follow_ups: Array.isArray(a.follow_ups) ? a.follow_ups : [], dropped: a.dropped || [], meta: a.meta || { source: "live" },
      method: a.method || null, figures: a.figures && typeof a.figures === "object" ? a.figures : null
    };
  }
};
