// AI client.
// - Opened as a file (double-click index.html): MOCK answers from data/mock_answers.js.
// - Served by standin/server.py (http://localhost:8000): LIVE answers from POST /api/ask (Grok/Groq stand-in).
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

  async ask({ question, persona, scenario, history }) {
    if (this.status.mode === "live") {
      try {
        const r = await fetch(this.ENDPOINT, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, persona, scenario, history })
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error || "server error " + r.status);
        return this.normalise(j);
      } catch (e) {
        return this.mock({ question, persona, scenario }, e.message);   // never leave the user with nothing
      }
    }
    return this.mock({ question, persona, scenario });
  },

  async mock({ question, persona, scenario }, error) {
    await new Promise(res => setTimeout(res, 500));
    const a = window.MOCKGEN ? MOCKGEN.answer(question, persona) : JSON.parse(JSON.stringify(DATA.mockAnswers[persona] || DATA.mockAnswers.student));
    a.meta = { ...a.meta, source: error ? "fallback-mock" : "mock", error: error || null, echo_question: question, scenario };
    return a;
  },

  // Make any answer safe to render, whatever the backend sends
  normalise(a) {
    return {
      title: a.title || "", summary: a.summary || a.answer || "", key_facts: Array.isArray(a.key_facts) ? a.key_facts : [],
      answer: String(a.answer || a.summary || ""), evidence: Array.isArray(a.evidence) ? a.evidence : [],
      widgets: Array.isArray(a.widgets) ? a.widgets : [], points: Array.isArray(a.points) ? a.points : [], limitations: a.limitations || "",
      follow_ups: Array.isArray(a.follow_ups) ? a.follow_ups : [], dropped: a.dropped || [], meta: a.meta || { source: "live" }
    };
  }
};
