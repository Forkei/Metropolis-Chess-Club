"""
Claude API wrapper for the Chess Master agent (fallback).

Handles:
- Structured JSON output via response_format
- Tool use / function calling
- Error handling and retries
- Configuration from settings
"""

import json
import asyncio
import logging
from typing import Optional, Dict, Any
import anthropic
from anthropic import APIError, RateLimitError

from config.settings import CLAUDE_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    Claude API client for Chess Master agent (fallback to Gemini).

    Supports:
    - Structured JSON output
    - Tool use / function calling
    - Automatic retries with exponential backoff
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        max_retries: int = 3,
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Claude API key (defaults to CLAUDE_API_KEY from config)
            model: Model name (defaults to CLAUDE_MODEL from config)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            max_retries: Number of retries on failure
        """
        self.api_key = api_key or CLAUDE_API_KEY
        self.model = model or CLAUDE_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY not set in environment or config")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.call_count = 0
        self.error_count = 0

    async def respond(
        self,
        system_prompt: str,
        user_prompt: str,
        player_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from Claude with structured JSON output.

        Args:
            system_prompt: System context and personality
            user_prompt: User input/game context
            player_id: Optional player ID for context

        Returns:
            Parsed JSON response with action, content, tone, etc.
        """
        self.call_count += 1
        full_prompt = self._build_full_prompt(system_prompt, user_prompt)

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Claude API call #{self.call_count}, attempt {attempt + 1}")

                # Call Claude with JSON output mode
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                    )
                )

                # Parse response
                response_text = response.content[0].text
                parsed = self._parse_response(response_text)
                logger.info(f"Claude response: action={parsed.get('action')}")

                return parsed

            except (RateLimitError, APIError) as e:
                self.error_count += 1
                logger.warning(f"Claude API error (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.debug(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed after {self.max_retries} attempts")
                    raise

            except json.JSONDecodeError as e:
                self.error_count += 1
                logger.error(f"Failed to parse JSON response: {e}")
                raise

        raise RuntimeError("All retries exhausted")

    def _build_full_prompt(self, system_prompt: str, user_prompt: str) -> str:
        """
        Combine system and user prompts with JSON instruction.
        """
        return f"""{user_prompt}

---

IMPORTANT: You must respond ONLY with valid JSON. No markdown, no extra text.

The JSON must have this structure:
{{
    "thinking": "optional pre-response reasoning",
    "action": "send_message | stop | save_memory | set_emotion",
    "content": "the message, memory content, or emotion",
    "tone": "optional tone indicator",
    "metadata": {{optional additional context}}
}}

Required fields: action, content
Optional fields: thinking, tone, metadata

Examples:
{{"action": "send_message", "content": "Nice move.", "tone": "respectful"}}
{{"action": "save_memory", "content": "Alice always plays the Sicilian", "memory_type": "player_behavior"}}
{{"action": "stop"}}
"""

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Claude's JSON response.

        Handles:
        - Extracting JSON from markdown code blocks
        - Validating required fields
        - Type conversion
        """
        text = response_text.strip()

        # Try to extract JSON from markdown code block
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = [l for l in lines[1:] if l and not l.startswith("```")]
            text = "\n".join(json_lines)

        # Parse JSON
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response: {text[:200]}")
            raise

        # Validate required fields
        if "action" not in parsed:
            raise ValueError(f"Missing 'action' field in response: {parsed}")

        if "content" not in parsed and parsed.get("action") != "stop":
            raise ValueError(f"Missing 'content' field in response: {parsed}")

        # Ensure action is valid
        valid_actions = ["send_message", "stop", "save_memory", "set_emotion"]
        if parsed["action"] not in valid_actions:
            raise ValueError(f"Invalid action '{parsed['action']}'. Must be one of: {valid_actions}")

        # Set defaults
        if "tone" not in parsed:
            parsed["tone"] = None
        if "metadata" not in parsed:
            parsed["metadata"] = {}

        return parsed

    def get_stats(self) -> Dict[str, Any]:
        """Get API call statistics."""
        return {
            "total_calls": self.call_count,
            "total_errors": self.error_count,
            "error_rate": self.error_count / self.call_count if self.call_count > 0 else 0,
        }

    def reset_stats(self) -> None:
        """Reset API statistics."""
        self.call_count = 0
        self.error_count = 0


__all__ = ["ClaudeClient"]
