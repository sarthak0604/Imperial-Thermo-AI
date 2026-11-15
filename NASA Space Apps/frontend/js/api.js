// AI client.
// - Opened as a file (double-click index.html): MOCK answers from data/mock_answers.js.
// - Served by standin/server.py: LIVE answers from the configured backend.
// - The integrated Thermo provider reports its active reviewed graph at /api/health.
window.API = {
  ENDPOINT: "/api/ask",
  conversation: null,
  resetConversation() {
    const id = this.conversation?.id;
    if (id) fetch('/api/conversation?id='+encodeURIComponent(id), {method:'DELETE'}).catch(() => {});
    this.conversation = null; sessionStorage.removeItem('thermo-conversation');
  },
  status: { mode: location.protocol.startsWith("http") ? "live" : "mock", provider: null, model: null, graph_id: null, planner: null, error: null },

  async health() {
    if (this.status.mode !== "live") return this.status;
    try {
      const r = await fetch("/api/health");
      const j = await r.json();
      Object.assign(this.status, { provider: j.provider, model: j.model, graph_id: j.graph_id || null, planner: j.planner || null,
        error: j.provider ? null : (j.error || "no AI provider is active") });
    } catch (e) { Object.assign(this.status, { error: "backend server not reachable" }); }
    return this.status;
  },

  describe() {
    const s = this.status;
    if (s.mode === "live" && s.provider) return `live — ${s.provider} / ${s.model}${s.graph_id ? ` · ${s.graph_id}` : " · no reviewed graph reported"}`;
    return "mock" + (s.error ? ` (${s.error})` : " (open via standin/server.py for live answers)");
  },

  async ask({ question, persona, scenario, history, signal }) {
    if (this.status.mode === "live") {
      try {
        if (!this.conversation) {
          try { this.conversation = JSON.parse(sessionStorage.getItem('thermo-conversation')); } catch (_) {}
        }
        const conversation = this.conversation || {};
        const requestId = crypto.randomUUID();
        const r = await fetch(this.ENDPOINT, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, persona, scenario, history,
            conversation_id: conversation.id, expected_state_revision: conversation.revision,
            client_request_id: requestId }), signal
        });
        const j = await r.json();
        if (!r.ok) {
          if ([404,410].includes(r.status)) this.resetConversation();
          if (r.status === 409 && conversation.id) {
            const current = await fetch('/api/conversation?id='+encodeURIComponent(conversation.id)).then(r => r.json());
            if (current.state_revision !== undefined) {
              this.conversation = {id: conversation.id, revision: current.state_revision};
              sessionStorage.setItem('thermo-conversation', JSON.stringify(this.conversation));
            }
          }
          throw new Error(j.error || "server error " + r.status);
        }
        if (j.conversation_id) {
          this.conversation = { id: j.conversation_id, revision: j.state_revision };
          sessionStorage.setItem('thermo-conversation', JSON.stringify(this.conversation));
        }
        return this.normalise(j);
      } catch (e) {
        if (e.name === "AbortError") return { meta: { aborted: true } };   // the user pressed stop
        return this.normalise({ summary: e.message, limitations: "The request failed. Try again or check the backend configuration.",
          meta: { source: "live", provider: this.status.provider || "backend", status: "error" } });   // never leave the user with nothing
      }
    }
    return this.mock({ question, persona, scenario, signal });
  },

  async mock({ question, persona, scenario, signal }, error) {
    await new Promise(res => setTimeout(res, error ? 0 : 1400));
    if (signal && signal.aborted) return { meta: { aborted: true } };
    const a = window.MOCKGEN ? MOCKGEN.answer(question, persona) : JSON.parse(JSON.stringify(DATA.mockAnswers[persona] || DATA.mockAnswers.student));
    a.meta = { ...a.meta, source: error ? "fallback-mock" : "mock", error: error || null, echo_question: question, scenario };
    return a;
  },

  // Make any answer safe to render, whatever the backend sends
  normalise(a) {
    return {
      conversation_id: a.conversation_id, state_revision: a.state_revision,
      clarifications: a.clarifications || [], model_decisions: a.model_decisions || [],
      title: a.title || "", summary: a.summary || a.answer || "", key_facts: Array.isArray(a.key_facts) ? a.key_facts : [],
      answer: String(a.answer || a.summary || ""), evidence: Array.isArray(a.evidence) ? a.evidence : [],
      blocks: Array.isArray(a.blocks) ? a.blocks : [], crosslinks: Array.isArray(a.crosslinks) ? a.crosslinks : [], fulfilment: a.fulfilment || [],
      widgets: Array.isArray(a.widgets) ? a.widgets : [], points: Array.isArray(a.points) ? a.points : [], limitations: a.limitations || "",
      follow_ups: Array.isArray(a.follow_ups) ? a.follow_ups : [], dropped: a.dropped || [], meta: a.meta || { source: "live" }
    };
  }
};
