# Signal Studio — Svelte website builder & tech blogger

Signal Studio is a local-first Svelte website builder and lightweight tech-blog
authoring app. Import a Svelte or SvelteKit ZIP, use Gemini through a chat
interface to propose changes, preview each change in an isolated local build,
and apply only the approved change to the imported local copy.

![Signal Studio interface](docs/studio-builder.svg)

## Demo video

<!-- Replace this placeholder with a short GIF that links to your full demo video. -->
[![Watch the Signal Studio demo](docs/video-placeholder.svg)](YOUR_DEMO_VIDEO_URL)

> Add your full demo-video URL in place of `YOUR_DEMO_VIDEO_URL`. A 30–45 second walkthrough showing import, chat, preview, and apply works well here.

## What it includes

- Svelte UI with navigation, Gemini chat, route detection, proposal review, and a resizable local preview
- ZIP import for local Svelte/SvelteKit project inspection and preview builds
- AI-assisted Svelte change proposals with disposable, isolated change previews
- A Posts CMS that creates local blog post drafts with title, slug, excerpt, body, and publication date/time
- Explicit **Preview change** then **Apply locally** workflow; no automatic publishing
- FastAPI backend and Gemini integration using Application Default Credentials (ADC) only

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
are extracted only into `.local-imports/`, which is ignored by Git. The app
validates archive paths and size, detects the Svelte framework and routes, then
builds the extracted copy and shows it in the right-hand preview.

If the imported project has an articles, posts, or blog route, select **Posts**
to create a blog draft. The resulting local source change can be previewed at
the articles route before it is applied.

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

This prototype intentionally does not include GitHub, Cloud Storage, remote
preview deployments, commits, pull requests, or a publish button. Applying a
change modifies only the local imported copy after a successful preview.
