# IMPER-ai-L — Omri interface with Hayk2 backend

This is Omri's new interface (`4bb5afe`): environment selection, persona selection,
question management, data display settings, animated flame and rocket, expanded
answers and PDF export. Its design assets come from Omri. Live answers are returned
by the complete Hayk2 backend (`23e17ea`) through `/api/ask`.

The API and result adapters preserve conversation IDs, backend calculation blocks,
charts, reference inputs, method details and JSON downloads. Browser demo
calculations are not used to answer live questions. Errors are displayed without
falling back to synthetic answers. Old saved responses are not replayed on navigation.

From the repository root:

```bash
uv sync --locked
THERMO_PLANNER=retrieval PORT=8015 uv run python 'NASA Space Apps/frontend/standin/server.py'
```

Open http://localhost:8015. Retrieval mode runs supported deterministic models
without downloading an LLM. Local Qwen additionally requires the search extra and
model weights. For GPU hosting, use the Cloud Run build path:

```bash
uv run google-website --project nasa26 --region europe-west1 --service ic-dynamics --public
```

See `docs/cloud-website.md` for prerequisites and deployment options. Cloud Build
installs GPU dependencies and downloads Qwen weights remotely. The deployment
includes the frontend, the reviewed graph and Hayk2's thermo-reference package.
