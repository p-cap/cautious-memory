"""Vertex AI Gemini client for local website draft proposals."""

import asyncio
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

GOOGLE_CLOUD_PROJECT = getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = getenv("GOOGLE_CLOUD_LOCATION", "global")
GEMINI_MODEL = getenv("GEMINI_MODEL", "gemini-2.5-flash")


def agent_label() -> str:
    """Return a non-secret identifier suitable for health checks and logs."""
    return f"vertex-ai:{GEMINI_MODEL}"


def _create_response(prompt: str) -> str:
    """Run a blocking Gemini request using Application Default Credentials."""
    if not GOOGLE_CLOUD_PROJECT:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT in .env.")

    # Keep imports inside the request path so API contract tests do not require
    # the SDK, credentials, or a live Vertex AI project.
    from google import genai
    from google.genai.types import HttpOptions

    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION,
        http_options=HttpOptions(api_version="v1"),
    )
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return str(response.text or "").strip()


async def generate_draft(prompt: str) -> str:
    """Send a bounded site snapshot to Gemini through Vertex AI."""
    proposal = await asyncio.to_thread(_create_response, prompt)
    if not proposal:
        raise RuntimeError("Gemini returned an empty draft proposal.")
    return proposal
