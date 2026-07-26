# Studio — local website-builder prototype

This is a local-only prototype for proposing Svelte website changes through a
chat interface. Gemini creates concise draft proposals; the app does not read
or modify a website repository, create commits, upload files, or deploy.

## What it includes

- Svelte UI with page selection, chat, a concept preview, and a local-draft list
- FastAPI endpoint at `POST /api/drafts`
- Google ADK agent powered by Gemini Enterprise Agent Platform
- Application Default Credentials (ADC) only; no API-key code path
- Explicit draft-only guardrails in the agent instruction
- ZIP import for local, read-only Svelte/SvelteKit project inspection

## Configure ADC

Create `.env` from `.env.example` in the project root and use real values:

```dotenv
GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_ENTERPRISE=True
GEMINI_MODEL=gemini-3.5-flash
```

Authenticate locally once:

```sh
gcloud auth application-default login
gcloud config set project your-google-cloud-project-id
```

The `.env` file is ignored by Git. Stop and restart the API after changing it.

## Run locally

Install Python dependencies:

```sh
agents-cli install
```

In terminal one, start the API:

```sh
uv run uvicorn app.fast_api_app:app --reload --port 8000
```

In terminal two, start the Svelte UI:

```sh
cd frontend
npm install
npm run dev
```

Open the displayed Vite URL, normally `http://localhost:5173`. Vite proxies
`/api/drafts` to the local FastAPI service.

## Import a Svelte site

Use **Import a project** in the left sidebar and select a ZIP archive. Imports
are extracted only into `.local-imports/`, which is ignored by Git. The
prototype validates archive paths and size, detects the Svelte framework and
routes, then builds only that extracted copy and displays the generated static
site automatically in the right-hand preview. It never edits the uploaded
source archive or an original local project.

Try the supplied sample archive:

```text
../outputs/sample-svelte-site.zip
```

It contains a small SvelteKit site named `northstar-sample` with `/`, `/about`,
and `/contact` routes.

## Verify

These commands validate the code without sending a Gemini request:

```sh
uv run pytest tests/unit tests/integration
cd frontend && npm run build
```

Once ADC is configured, run the behavioral evaluation:

```sh
agents-cli eval run --evalset tests/eval/evalsets/basic.evalset.json
```

## Boundaries

This prototype intentionally does not include GitHub, Cloud Storage, site-file
tools, preview deployments, or a publish button. Those integrations can be
added in a later, separately approved phase.
