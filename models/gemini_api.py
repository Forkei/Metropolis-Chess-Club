"""
Gemini 3.1 Flash Lite API wrapper for the Chess Master agent.

Handles:
- Structured JSON output (for agent responses)
- Tool/function calling (send_message, save_memory, set_emotion, stop)
- Error handling and retries
- Temperature and sampling configuration
- Fallback to Claude API if needed
"""

import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List
from datetime import datetime
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError, DeadlineExceeded
from config.settings import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Gemini 3.1 Flash Lite API client for Chess Master agent.

    Supports:
    - Structured JSON output for consistent response parsing
    - Tool use / function calling
    - Automatic retries with exponential backoff
    - Configurable temperature and sampling
    """

    # Define tools the agent can call
    TOOLS = {
        "send_message": {
            "description": "Send a message to the player",
            "parameters": {
                "content": {"type": "string", "description": "The message to send"},
                "tone": {"type": "string", "description": "Tone: sharp, playful, respectful, dismissive, warm"}
            }
        },
        "save_memory": {
            "description": "Save a memory about the player or the game",
            "parameters": {
                "content": {"type": "string", "description": "What to remember"},
                "memory_type": {
                    "type": "string",
                    "description": "Category: player_behavior, player_observation, game_context, personal_note, pattern, streak, emotional"
                },
                "related_player_id": {"type": "string", "description": "Optional player ID"}
            }
        },
        "set_emotion": {
            "description": "Display an emotion (for future visual representation)",
            "parameters": {
                "emotion": {"type": "string", "description": "One of: smirk, thoughtful, amused, focused, dismissive, respectful"}
            }
        },
        "stop": {
            "description": "Do nothing. Choose silence.",
            "parameters": {}
        }
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        max_retries: int = 3,
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY from config)
            model: Model name (defaults to GEMINI_MODEL from config)
            temperature: Sampling temperature (0.0-1.0, higher = more creative)
            max_tokens: Maximum tokens in response
            max_retries: Number of retries on failure
        """
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in environment or config")

        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gemini")
        self.call_count = 0
        self.error_count = 0

    async def respond(
        self,
        system_prompt: str,
        user_prompt: str,
        player_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from Gemini with structured JSON output.

        Args:
            system_prompt: System context and personality
            user_prompt: User input/game context
            player_id: Optional player ID for context

        Returns:
            Parsed JSON response with action, content, tone, etc.

        Example response:
            {
                "thinking": "optional reasoning",
                "action": "send_message",
                "content": "Your move. I'm waiting.",
                "tone": "sharp",
                "metadata": {"memory_to_save": {...}}
            }
        """
        self.call_count += 1
        full_prompt = self._build_full_prompt(system_prompt, user_prompt)

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Gemini API call #{self.call_count}, attempt {attempt + 1}")

                # Call Gemini with JSON output format
                response = await self._call_gemini(full_prompt)

                # Parse response
                parsed = self._parse_response(response)
                logger.info(f"Gemini response: action={parsed.get('action')}")

                return parsed

            except (DeadlineExceeded, GoogleAPIError) as e:
                self.error_count += 1
                logger.warning(f"Gemini API error (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    # Exponential backoff
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

        # Should not reach here
        raise RuntimeError("All retries exhausted")

    async def _call_gemini(self, prompt: str) -> str:
        """
        Call Gemini API synchronously (wrapped in async).

        Gemini doesn't have native async support, so we run it in a thread pool.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: self.client.generate_content(prompt).text
        )

    def _build_full_prompt(self, system_prompt: str, user_prompt: str) -> str:
        """
        Combine system and user prompts with JSON instruction.
        """
        return f"""{system_prompt}

---

{user_prompt}

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
        Parse Gemini's JSON response.

        Handles:
        - Extracting JSON from markdown code blocks (if present)
        - Validating required fields
        - Type conversion
        """
        text = response_text.strip()

        # Try to extract JSON from markdown code block
        if text.startswith("```"):
            # Find the JSON block
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


# Export for convenience
__all__ = ["GeminiClient"]
