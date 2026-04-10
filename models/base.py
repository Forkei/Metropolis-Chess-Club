"""
Base API client interface and factory for selecting between Gemini and Claude.
"""

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from config.settings import LLM_PROVIDER


class APIClient(ABC):
    """Abstract base class for LLM API clients."""

    @abstractmethod
    async def respond(
        self,
        system_prompt: str,
        user_prompt: str,
        player_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get API call statistics."""
        pass

    @abstractmethod
    def reset_stats(self) -> None:
        """Reset statistics."""
        pass


def get_api_client(
    provider: Optional[str] = None,
    **kwargs
) -> APIClient:
    """
    Factory function to get the appropriate API client.

    Args:
        provider: "gemini" or "claude" (defaults to config.LLM_PROVIDER)
        **kwargs: Additional arguments to pass to the client

    Returns:
        Initialized API client (GeminiClient or ClaudeClient)

    Raises:
        ValueError: If provider is invalid or API key is not set
    """
    provider = provider or LLM_PROVIDER

    if provider == "gemini":
        from models.gemini_api import GeminiClient
        return GeminiClient(**kwargs)

    elif provider == "claude":
        from models.claude_api import ClaudeClient
        return ClaudeClient(**kwargs)

    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. Must be 'gemini' or 'claude'."
        )


__all__ = ["APIClient", "get_api_client"]
