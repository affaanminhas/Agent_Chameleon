"""
Shared LLM config for all tools.
Path: src/function_schema/llm_config.py

All tools import from here instead of reading env vars directly.
To switch LLM provider, just update .env — no tool files need changing.

Supported providers (set in .env):
    Groq:          GROQ_API_KEY=gsk_...   HF_API_BASE=https://api.groq.com/openai/v1
    HuggingFace:   HF_TOKEN=hf_...        HF_API_BASE=https://router.huggingface.co/v1
    OpenAI:        OPENAI_API_KEY=sk_...  HF_API_BASE=https://api.openai.com/v1
    Anthropic:     ANTHROPIC_API_KEY=...  HF_API_BASE=https://api.anthropic.com/v1
    Ollama:        HF_TOKEN=ollama        HF_API_BASE=http://localhost:11434/v1
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root — works regardless of where Python is run from
_here = Path(__file__).resolve().parent          # src/function_schema/
_root = _here.parent.parent                      # project root
load_dotenv(_root / ".env", override=False)


def get_api_key() -> str:
    """Return whichever API key is set in .env, in priority order."""
    return (
        os.getenv("GROQ_API_KEY") or
        os.getenv("HF_TOKEN") or
        os.getenv("OPENAI_API_KEY") or
        os.getenv("ANTHROPIC_API_KEY") or
        ""
    )


def get_base_url() -> str:
    return os.getenv("HF_API_BASE", "https://api.groq.com/openai/v1")


def get_model() -> str:
    return os.getenv("HF_MODEL", "llama-3.3-70b-versatile")


def get_client():
    """Return a ready-to-use OpenAI-compatible client."""
    from openai import OpenAI
    return OpenAI(api_key=get_api_key(), base_url=get_base_url())