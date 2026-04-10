"""
Chess Master - The main conversational agent.

Personality: Elegant, sharp-tongued chess player who reads opponents and doesn't go easy.
Always responds in JSON. Optional thinking section before response.

Inputs:
- System prompt (personality + dynamic context like time, username)
- Game state (odds, move history, elapsed time)
- Previous memories (injected by subconscious)
- User input (message, move, emotion, etc.)

Output:
- JSON with: [optional thinking], action (message/stop/emotion/etc), tone
"""

from typing import Optional, Dict, Any
import json


class ChessMaster:
    """
    Main agent for the Chess Master character.
    
    TODO:
    - Integrate Claude API client
    - Integrate Gemini API client
    - Implement tool calling for: send_message, save_memory, set_emotion, stop
    - Parse JSON responses consistently
    - Handle thinking blocks
    """
    
    def __init__(self, model: str = "claude", username: str = "Opponent"):
        self.model = model
        self.username = username
        self.response_history = []
    
    async def respond(
        self, 
        trigger_point: str,
        game_context: Dict[str, Any],
        memories: Optional[list] = None,
        user_input: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from the Chess Master.
        
        Args:
            trigger_point: When this is being called (before_match, on_user_input, etc)
            game_context: Current game state (odds, moves, time, etc)
            memories: Optional list of relevant memories from subconscious
            user_input: Optional user message or action
            
        Returns:
            Parsed JSON response with action and content
        """
        # TODO: Build system prompt with dynamic context
        # TODO: Build user prompt from trigger_point and game_context
        # TODO: Call LLM
        # TODO: Parse JSON response
        # TODO: Call any requested tools (save_memory, etc)
        # TODO: Return structured response
        pass
    
    def _build_system_prompt(self, game_context: Dict[str, Any]) -> str:
        """
        Construct the Chess Master's system prompt with dynamic context.
        Includes: personality, current time, username, behavioral guidelines.
        """
        # TODO: Load personality from personality.md
        # TODO: Inject current time, username, match stats
        # TODO: Include instructions about JSON format, thinking, tools
        pass
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the LLM response as JSON.
        Handles potential formatting issues.
        """
        # TODO: Extract JSON from response
        # TODO: Validate required fields
        pass
