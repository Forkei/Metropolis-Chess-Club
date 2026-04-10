"""
Chess Master - The main conversational agent.

A real human chess player with personality, lore, and the ability to remember opponents.

Model: Gemini 3.1 Flash Lite Preview (primary), Claude Opus (fallback)

Personality: Sharp, respectful, sarcastic, with personal history. Builds relationships
across games. Respects good play, taunts weak play (but not cruelly).

Always responds in JSON. Optional thinking section before response.

Inputs:
- System prompt (personality + dynamic context like time, username, player relationship)
- Game state (odds, move history, elapsed time, match difficulty)
- Previous memories (injected by subconscious)
- Conversation history (recent messages with this player)
- Player profile (if returning player)
- User input (message, move, emotion, etc.)

Output:
- JSON with: [optional thinking], action (message/stop/save_memory/set_emotion), content, tone
"""

from typing import Optional, Dict, Any, List
import json


class ChessMaster:
    """
    Main agent for the Chess Master character.

    Manages personality, conversation context, memory integration, and response generation.
    Remembers players across games and builds relationships.

    TODO:
    - Implement Gemini API client with structured output (JSON)
    - Implement Claude API client (fallback)
    - Tool calling for: send_message, save_memory, set_emotion, stop
    - Parse JSON responses consistently
    - Handle thinking blocks
    - Load and inject player conversation history
    - Load and inject player profile
    """

    def __init__(
        self,
        model: str = "gemini",
        player_id: str = "anonymous",
        player_name: str = "Opponent"
    ):
        self.model = model  # "gemini" or "claude"
        self.player_id = player_id
        self.player_name = player_name
        self.response_history = []
        self.conversation_history: List[Dict[str, str]] = []
    
    async def respond(
        self,
        trigger_point: str,
        game_context: Dict[str, Any],
        memories: Optional[List[Dict[str, Any]]] = None,
        user_input: Optional[str] = None,
        player_profile: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from the Chess Master.

        The agent considers:
        - Its personality and voice
        - The player's relationship state (new/familiar/rival)
        - Recent conversation history
        - Relevant memories from the subconscious
        - Current game context (odds, moves, time)
        - The trigger point (before_match, on_user_move, etc.)

        Args:
            trigger_point: When called (before_match, on_user_input, on_user_move, etc)
            game_context: Current game state (odds, moves, time, difficulty)
            memories: Optional list of relevant memories from subconscious
            user_input: Optional user message or action
            player_profile: Optional player profile (relationship, history, elo)
            conversation_history: Optional recent messages with this player

        Returns:
            Parsed JSON response with action, content, and optional thinking
            Example: {
                "thinking": "optional reasoning",
                "action": "send_message",
                "content": "Your move. I'm waiting.",
                "tone": "sharp",
                "metadata": {"memory_to_save": {...}}
            }
        """
        if conversation_history:
            self.conversation_history = conversation_history

        # TODO: Build system prompt with personality, player context
        # TODO: Build user prompt from trigger_point, game_context, memories
        # TODO: Call Gemini API with structured JSON output
        # TODO: Parse JSON response
        # TODO: Execute tool requests (save_memory, etc.)
        # TODO: Log message to conversation history
        # TODO: Return structured response
        pass
    
    def _build_system_prompt(
        self,
        game_context: Dict[str, Any],
        player_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Construct the Chess Master's system prompt with dynamic context.

        Includes:
        - Personality & voice (from personality.md)
        - Player relationship context (new? returning? rival?)
        - Current time, opponent name, match stats
        - Behavioral guidelines (JSON format, thinking, tools)
        - Instructions about memory saving and conversation

        Args:
            game_context: Current game state (time, odds, moves, etc.)
            player_profile: Optional player profile (relationship, history, elo)

        Returns:
            Complete system prompt string
        """
        # TODO: Load personality from personality.md
        # TODO: Inject player relationship context
        # TODO: Inject current time, username, match stats
        # TODO: Include instructions about JSON format, thinking, tools, memories
        pass
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the LLM response as JSON.
        Handles potential formatting issues.
        """
        # TODO: Extract JSON from response
        # TODO: Validate required fields
        pass
