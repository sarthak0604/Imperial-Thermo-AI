// AI client.
// - Requires the HTTP backend. Errors are displayed without invented answers.
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
  status: { mode: location.protocol.startsWith("http") ? "live" : "unavailable", provider: null, model: null, graph_id: null, planner: null, error: null },

  async health() {
    if (this.status.mode !== "live") return this.status;
    try {
      const r = await fetch("/api/health");
      const j = await r.json();
      Object.assign(this.status, { provider: j.provider, model: j.model, graph_id: j.graph_id || null, planner: j.planner || null,
        error: r.ok && j.ok && j.provider === "thermo" ? null : (j.error || "Thermo backend is unavailable") });
    } catch (e) { Object.assign(this.status, { error: "backend server not reachable" }); }
    return this.status;
  },

  describe() {
    const s = this.status;
    if (s.mode === "live" && s.provider && !s.error) return `live — ${s.provider} / ${s.model}${s.graph_id ? ` · ${s.graph_id}` : " · no reviewed graph reported"}`;
    return "backend unavailable" + (s.error ? ` (${s.error})` : " (start the backend server)");
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
          meta: { source: "live", provider: "thermo", status: "error" } });   // never leave the user with nothing
      }
    }
    return this.normalise({ summary: "Start the backend server and open its HTTP address to ask a question.",
      meta: { source: "live", provider: "thermo", status: "error" } });
  },

  // Make any answer safe to render, whatever the backend sends
  normalise(a) {
    return {
      conversation_id: a.conversation_id, state_revision: a.state_revision,
      function_pipeline: a.function_pipeline || [],
      clarifications: a.clarifications || [], model_decisions: a.model_decisions || [],
      title: a.title || "", summary: a.summary || a.answer || "", key_facts: Array.isArray(a.key_facts) ? a.key_facts : [],
      answer: String(a.answer || a.summary || ""), evidence: Array.isArray(a.evidence) ? a.evidence : [],
      blocks: Array.isArray(a.blocks) ? a.blocks : [], crosslinks: Array.isArray(a.crosslinks) ? a.crosslinks : [], fulfilment: a.fulfilment || [],
      widgets: Array.isArray(a.widgets) ? a.widgets : [], points: Array.isArray(a.points) ? a.points : [], limitations: a.limitations || "",
      follow_ups: Array.isArray(a.follow_ups) ? a.follow_ups : [], dropped: a.dropped || [], meta: a.meta || { source: "live" }
    };
  }
};
