"""
LLM API clients for Chess Master agent.

Supports:
- Gemini 3.1 Flash Lite (primary)
- Claude Opus (fallback)

Both support structured JSON output and tool calling.
"""

from models.base import APIClient, get_api_client
from models.gemini_api import GeminiClient
from models.claude_api import ClaudeClient

__all__ = ["APIClient", "get_api_client", "GeminiClient", "ClaudeClient"]
