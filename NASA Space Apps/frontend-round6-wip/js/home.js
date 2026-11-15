// Minimal home page: one ask box. The answer appears underneath.
(() => {
  const form = document.getElementById("ask-form");
  const out = document.getElementById("answer");
  API.health();
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const q = form.elements.q.value.trim();
    if (!q) return;
    out.innerHTML = `<p class="muted">Thinking…</p>`;
    const a = await API.ask({ question: q, persona: "student", scenario: "iss", history: [] });
    const live = a.meta && a.meta.source === "live";
    out.innerHTML = (live ? "" : `<p class="muted">[${U.esc(a.meta.source)} answer — placeholder${a.meta.error ? ": " + U.esc(a.meta.error) : ""}]</p>`) + U.md(a.answer);
  });
})();
