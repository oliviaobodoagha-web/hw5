"""Model and path configuration shared by every agent.

Every agent uses the same single model, gpt-6-luna, through Portkey's
OpenAI-compatible gateway. The model name is a constant on purpose: no other
model may appear in this code or in any run.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER_PATH = PROJECT_DIR / "mcp_server" / "server.py"
# The backend never opens the database. All shop data goes through the MCP server,
# which uses data/campus_customs_new.db (working copy) and only reads data/campus_customs.db on reset.

# .env in this project (copy .env.example). Locally it can also live two folders up.
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(PROJECT_DIR.parent.parent / ".env")

MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Delegation guardrails: multi-agent chats burn tokens fast.
MAX_DELEGATION_DEPTH = 3


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Add it to the root .env file.")
    return key


# A model call that hangs must not stall a ticket: give up after 2 minutes and retry twice.
MODEL_TIMEOUT_SECONDS = 120
MODEL_MAX_RETRIES = 2


def build_model() -> OpenAIResponsesModel:
    client = AsyncOpenAI(
        api_key=require_api_key(),
        base_url=PORTKEY_BASE_URL,
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_MAX_RETRIES,
        # Every run must be a real run: never serve a cached answer from an earlier one.
        default_headers={"x-portkey-cache-force-refresh": "true"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def load_prompt(agent_name: str) -> str:
    path = PROMPTS_DIR / f"{agent_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt file for {agent_name}: {path}")
    return path.read_text()
