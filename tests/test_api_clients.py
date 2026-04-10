"""
Tests for API clients (Gemini, Claude).
"""

import json
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from models.gemini_api import GeminiClient
from models.claude_api import ClaudeClient
from models.base import get_api_client


class TestGeminiClient:
    """Test Gemini API client."""

    @pytest.fixture
    def client(self):
        """Create a Gemini client for testing."""
        return GeminiClient(
            api_key="test_key",
            model="gemini-3.1-flash-lite-preview",
        )

    def test_initialization(self, client):
        """Test client initialization."""
        assert client.api_key == "test_key"
        assert client.model == "gemini-3.1-flash-lite-preview"
        assert client.temperature == 0.8
        assert client.max_tokens == 1024

    def test_parse_response_valid_json(self, client):
        """Test parsing valid JSON response."""
        response = json.dumps({
            "action": "send_message",
            "content": "Hello, opponent.",
            "tone": "sharp"
        })

        parsed = client._parse_response(response)
        assert parsed["action"] == "send_message"
        assert parsed["content"] == "Hello, opponent."
        assert parsed["tone"] == "sharp"

    def test_parse_response_with_markdown(self, client):
        """Test parsing JSON from markdown code block."""
        response = '''```json
{
    "action": "send_message",
    "content": "Nice move.",
    "tone": "respectful"
}
```'''

        parsed = client._parse_response(response)
        assert parsed["action"] == "send_message"
        assert parsed["content"] == "Nice move."

    def test_parse_response_missing_action(self, client):
        """Test that missing action field raises error."""
        response = json.dumps({
            "content": "Hello",
            "tone": "sharp"
        })

        with pytest.raises(ValueError, match="Missing 'action' field"):
            client._parse_response(response)

    def test_parse_response_missing_content(self, client):
        """Test that missing content field raises error (except for stop)."""
        response = json.dumps({
            "action": "send_message"
        })

        with pytest.raises(ValueError, match="Missing 'content' field"):
            client._parse_response(response)

    def test_parse_response_stop_no_content(self, client):
        """Test that stop action doesn't require content."""
        response = json.dumps({
            "action": "stop"
        })

        parsed = client._parse_response(response)
        assert parsed["action"] == "stop"

    def test_parse_response_invalid_action(self, client):
        """Test that invalid action raises error."""
        response = json.dumps({
            "action": "invalid_action",
            "content": "test"
        })

        with pytest.raises(ValueError, match="Invalid action"):
            client._parse_response(response)

    def test_parse_response_save_memory(self, client):
        """Test parsing save_memory action."""
        response = json.dumps({
            "action": "save_memory",
            "content": "Alice plays aggressively",
            "memory_type": "player_behavior"
        })

        parsed = client._parse_response(response)
        assert parsed["action"] == "save_memory"
        assert parsed["content"] == "Alice plays aggressively"

    def test_parse_response_set_emotion(self, client):
        """Test parsing set_emotion action."""
        response = json.dumps({
            "action": "set_emotion",
            "content": "smirk"
        })

        parsed = client._parse_response(response)
        assert parsed["action"] == "set_emotion"
        assert parsed["content"] == "smirk"

    def test_parse_response_defaults_metadata(self, client):
        """Test that missing metadata defaults to empty dict."""
        response = json.dumps({
            "action": "send_message",
            "content": "test"
        })

        parsed = client._parse_response(response)
        assert parsed["metadata"] == {}

    def test_build_full_prompt(self, client):
        """Test prompt building."""
        system = "You are a chess master."
        user = "What do you think of my move?"

        prompt = client._build_full_prompt(system, user)
        assert system in prompt
        assert user in prompt
        assert "JSON" in prompt
        assert "action" in prompt

    def test_get_stats(self, client):
        """Test statistics tracking."""
        stats = client.get_stats()
        assert stats["total_calls"] == 0
        assert stats["total_errors"] == 0
        assert stats["error_rate"] == 0

        client.call_count = 10
        client.error_count = 2

        stats = client.get_stats()
        assert stats["total_calls"] == 10
        assert stats["total_errors"] == 2
        assert stats["error_rate"] == 0.2

    def test_reset_stats(self, client):
        """Test statistics reset."""
        client.call_count = 10
        client.error_count = 2

        client.reset_stats()
        assert client.call_count == 0
        assert client.error_count == 0


class TestClaudeClient:
    """Test Claude API client."""

    @pytest.fixture
    def client(self):
        """Create a Claude client for testing."""
        return ClaudeClient(
            api_key="test_key",
            model="claude-opus-4-20250514",
        )

    def test_initialization(self, client):
        """Test client initialization."""
        assert client.api_key == "test_key"
        assert client.model == "claude-opus-4-20250514"

    def test_parse_response_valid_json(self, client):
        """Test parsing valid JSON response."""
        response = json.dumps({
            "action": "send_message",
            "content": "Hello, opponent.",
            "tone": "respectful"
        })

        parsed = client._parse_response(response)
        assert parsed["action"] == "send_message"
        assert parsed["content"] == "Hello, opponent."


class TestAPIFactory:
    """Test API client factory."""

    def test_get_gemini_client(self):
        """Test getting Gemini client."""
        client = get_api_client(
            provider="gemini",
            api_key="test_key"
        )
        assert isinstance(client, GeminiClient)

    def test_get_claude_client(self):
        """Test getting Claude client."""
        client = get_api_client(
            provider="claude",
            api_key="test_key"
        )
        assert isinstance(client, ClaudeClient)

    def test_get_invalid_provider(self):
        """Test that invalid provider raises error."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_api_client(provider="invalid")


# Integration test (requires actual API keys)
@pytest.mark.skipif(
    True,  # Skip by default, enable with API keys
    reason="Requires actual API credentials"
)
class TestGeminiIntegration:
    """Integration tests with real Gemini API."""

    @pytest.mark.asyncio
    async def test_respond_real_api(self):
        """Test actual API call to Gemini."""
        client = GeminiClient()
        response = await client.respond(
            system_prompt="You are a helpful chess player.",
            user_prompt="How are you?"
        )

        assert "action" in response
        assert "content" in response
        assert response["action"] in ["send_message", "stop", "save_memory", "set_emotion"]
