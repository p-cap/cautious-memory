"""Microsoft Foundry hosted-agent client for local website drafts."""

import asyncio
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

FOUNDRY_PROJECT_ENDPOINT = getenv("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")
FOUNDRY_AGENT_NAME = getenv("FOUNDRY_AGENT_NAME", "website-builder")
FOUNDRY_AGENT_VERSION = getenv("FOUNDRY_AGENT_VERSION", "2")


def agent_label() -> str:
    """Return a non-secret identifier suitable for health checks and logs."""
    return f"{FOUNDRY_AGENT_NAME}@{FOUNDRY_AGENT_VERSION}"


def _create_response(prompt: str) -> str:
    """Run the blocking Foundry SDK call with the local Azure CLI identity."""
    if not FOUNDRY_PROJECT_ENDPOINT:
        raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT in .env.")

    # Imports stay inside the request path so API contract tests do not require
    # Azure credentials or a live Foundry project.
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project_client = AIProjectClient(
        endpoint=FOUNDRY_PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )
    openai_client = project_client.get_openai_client()
    response = openai_client.responses.create(
        input=[{"role": "user", "content": prompt}],
        extra_body={
            "agent_reference": {
                "name": FOUNDRY_AGENT_NAME,
                "version": FOUNDRY_AGENT_VERSION,
                "type": "agent_reference",
            }
        },
    )
    return str(response.output_text).strip()


async def generate_draft(prompt: str) -> str:
    """Send a bounded site snapshot to the configured Foundry hosted agent."""
    proposal = await asyncio.to_thread(_create_response, prompt)
    if not proposal:
        raise RuntimeError("The Foundry agent returned an empty draft proposal.")
    return proposal
