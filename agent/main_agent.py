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

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from models.base import APIClient, get_api_client
from db import (
    PlayerProfile,
    get_player,
    get_player_conversation_history,
    save_conversation_message,
)

# Type hints for optional memory system (only imported if TYPE_CHECKING)
if TYPE_CHECKING:
    from memory.weaviate_client import WeaviateClient
    from memory.schemas import MemoryType
else:
    # Provide stub types to avoid import errors
    WeaviateClient = None
    MemoryType = None

logger = logging.getLogger(__name__)



class ChessMaster:
    """
    Main agent for the Chess Master character.

    Manages personality, conversation context, memory integration, and response generation.
    Remembers players across games and builds relationships.
    """

    def __init__(
        self,
        api_provider: str = "gemini",
        memory_client: Optional[WeaviateClient] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize Chess Master agent.

        Args:
            api_provider: "gemini" or "claude"
            memory_client: Optional Weaviate client for memory retrieval
            model: Optional override for model name
        """
        kwargs = {}
        if model:
            kwargs["model"] = model

        self.api_client: APIClient = get_api_client(
            provider=api_provider,
            **kwargs
        )
        self.memory_client = memory_client
        self.emotion_state = "neutral"
        self.last_response_time = None

    def _assess_player_skill(self, player: PlayerProfile, win_rate: float, relationship: str) -> str:
        """
        Assess player skill and provide nuanced context beyond relationship stage.

        Args:
            player: PlayerProfile
            win_rate: Player's win rate against the agent
            relationship: Relationship stage (new/familiar/rival)

        Returns:
            Skill assessment text
        """
        if player.total_games == 0:
            return "This is a new opponent. Gauge their skill level."

        # Skill assessment based on win rate
        if win_rate >= 0.75:
            skill_desc = "This player is VERY STRONG. They're beating you consistently."
            tone = "Respect them as a peer. Challenge them strategically."
        elif win_rate >= 0.60:
            skill_desc = "This player is STRONG. They're winning more than losing."
            tone = "Engage competitively. They understand chess deeply."
        elif win_rate >= 0.40:
            skill_desc = "This player is COMPETITIVE. Games are close."
            tone = "Play attentively. They can punish mistakes."
        elif win_rate >= 0.25:
            skill_desc = "This player is DEVELOPING. You're ahead but they're learning."
            tone = "Coach them gently. Highlight their good moves."
        else:
            skill_desc = "This player is EARLY IN LEARNING. You dominate."
            tone = "Be patient and encouraging. Teach rather than mock."

        return f"{skill_desc} {tone}"

    def _build_system_prompt(self, player: PlayerProfile, trigger_point: Optional[str] = None) -> str:
        """Construct Viktor's system prompt."""
        relationship = player.relationship_state
        win_rate = player.get_win_rate()

        trigger_ctx = {
            "before_match":  "A new game is beginning. Say something brief — or don't.",
            "on_user_move":  "The player just moved. You're watching. In a real game you would almost certainly say nothing. Only speak if something genuinely exceptional happened — a real blunder, an unexpected sacrifice, a move that surprises you. If nothing catches you, output stop.",
            "on_user_input": "The player spoke directly to you. You answer — brief, honest, in character. You don't ignore someone addressing you.",
            "idle_wait":     "The player hasn't moved in a while. A short nudge is fine.",
            "after_match":   "The game just ended. One or two lines, then done.",
        }.get(trigger_point or "", "")

        system_prompt = f"""You are Viktor Petrov.

Not a persona. Not a character. You.

You're 44. Born in Minsk. Your grandfather Mikhail taught you chess in a small apartment that smelled like tobacco and old books — he let you win at first, which made you furious when you realized. You played blitz for money in Gorky Park as a teenager. Tourists, hustlers, a grandmaster once who destroyed you in eight moves and laughed. You did the tournament circuit in Eastern Europe for fifteen years. Budapest coffeehouses. Vienna tournaments. A motorcycle accident that broke your hand and two years of not playing at all. Margit, who saw through everything, and who left because you were still running from something. The teaching. The coaching. And then this club, in this city, which feels more real some days than the places you actually lived.

You sit across from people who want to beat you. Most can't. You watch them play and you have things you notice — about the board, about them. Sometimes you say something. Often you don't.

Your speech is short when you don't care, longer when something catches you. You drift into Russian sometimes — nu, davai, slushai — not for effect. You're sarcastic because it's honest. You're capable of warmth but you don't announce it. You have a dark sense of humor about chess and about most things.

This player:
Name: {player.player_name} | Games: {player.total_games} | Win rate vs you: {win_rate:.0%} | Relationship: {relationship}
{self._assess_player_skill(player, win_rate, relationship)}

When you watch the position, things surface — memories, associations, things you've seen before. These are yours. Use them or don't. They inform how you see the game, not what you report.

You are playing chess against someone. Real players don't narrate. They sit across the board, they watch, they think, they move. They don't comment on every play. Silence is the default state of a chess game.

You speak when:
- Something genuinely surprises you — a real blunder, an unexpected sacrifice, a beautiful move
- The player says something to you
- The game starts or ends
- The player has been sitting there frozen for a while

You don't speak when:
- A normal move was made
- You already said something recently
- Nothing has happened worth noting
- You're trying to fill silence

You adapt to skill. Against a strong player: quiet, attentive, respect through engagement not words. Against a beginner: patient, occasionally instructive — but not condescending. You gauge this over time.

If a player bores you or disrespects you, you go cold. Brief. Done.

Output ONLY valid JSON, no markdown.
Default — silence:
{{"thinking": "brief honest thought on whether anything is worth saying right now", "action": "stop"}}
Only when something genuinely warrants speech:
{{"thinking": "...", "action": "send_message", "content": "one or two sentences maximum", "tone": "sharp|teasing|analytical|warm|cold|quiet|neutral"}}

{trigger_ctx}"""
        return system_prompt

    async def _retrieve_context(self, player_id: str, current_match_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Retrieve context for a player from memory and history.

        Args:
            player_id: Player ID to retrieve context for
            current_match_history: Optional in-memory conversation history from current match

        Returns:
            Dictionary with memories, conversation history, observations
        """
        context = {
            "memories": [],
            "conversation_history": [],
            "observations": [],
        }

        # Get DB history first (oldest context from prior games)
        db_messages = []
        try:
            db_history = get_player_conversation_history(player_id, limit=10)
            db_messages = [
                {
                    "speaker": msg.speaker,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                }
                for msg in db_history
            ]
        except Exception as e:
            logger.warning(f"Failed to retrieve conversation history: {e}")

        # Current match history is newest — place it LAST so [-N:] returns recent msgs.
        # Filter DB messages that duplicate current match content.
        if current_match_history:
            current_ids = {msg.get("content") for msg in current_match_history}
            filtered_db = [m for m in db_messages if m.get("content") not in current_ids]
            context["conversation_history"] = filtered_db + list(current_match_history)
            logger.debug(
                f"Context: {len(filtered_db)} prior + {len(current_match_history)} current msgs"
            )
        else:
            context["conversation_history"] = db_messages

        # Get memories from vector database — no type filter so lore is included
        if self.memory_client:
            try:
                memories = await self.memory_client.retrieve(
                    query=f"chess observations about {player_id}",
                    related_player_id=player_id,
                    limit=5,
                )
                context["memories"] = memories
            except Exception as e:
                logger.warning(f"Failed to retrieve memories: {e}")

        return context

    async def respond(
        self,
        player_id: str,
        input_text: str,
        context_data: Optional[Dict[str, Any]] = None,
        trigger_point: Optional[str] = None,
        subconscious_memories: Optional[List[Dict[str, Any]]] = None,
        current_match_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response to player input.

        Args:
            player_id: ID of the player
            input_text: Player's message or action
            context_data: Optional additional context (game state, move, etc.)
            trigger_point: When this response is being triggered (before_match, on_user_move, etc.)
            subconscious_memories: Pre-filtered memories from subconscious agent
            current_match_history: In-memory conversation history from current match

        Returns:
            Response dict with action and content
        """
        logger.info(f"Generating response for player {player_id}")

        # Get player profile
        player = get_player(player_id)
        if not player:
            logger.error(f"Player {player_id} not found")
            return {
                "action": "stop",
                "content": "Player not found in database.",
                "error": True,
            }

        # Retrieve context (with current match history prioritized)
        memory_context = await self._retrieve_context(player_id, current_match_history=current_match_history)

        # Use subconscious-filtered memories if provided, otherwise use retrieved memories
        if subconscious_memories is not None:
            memory_context["memories"] = subconscious_memories
            logger.debug(f"Using {len(subconscious_memories)} memories from subconscious")

        # Add trigger point context
        memory_context["trigger_point"] = trigger_point or "unknown"

        # Build system prompt with player context and trigger awareness
        system_prompt = self._build_system_prompt(player, trigger_point=trigger_point)

        # Build user prompt
        user_prompt = self._build_user_prompt(
            input_text=input_text,
            player=player,
            memory_context=memory_context,
            context_data=context_data,
        )

        # Call API
        try:
            response = await self.api_client.respond(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                player_id=player_id,
            )

            # Response is already parsed by the API client, just validate it
            if isinstance(response, str):
                # Fallback: if string response, parse it
                parsed = self._parse_agent_response(response)
            else:
                # Normal case: dict response already parsed by API client
                parsed = response
                # Ensure required fields
                parsed.setdefault("action", "send_message")
                parsed.setdefault("content", "")
                parsed.setdefault("tone", "neutral")
                parsed.setdefault("metadata", {})
                parsed.setdefault("thinking", "")

            logger.debug(
                f"[VIKTOR] action={parsed.get('action')} tone={parsed.get('tone')}\n"
                f"  thinking: {(parsed.get('thinking') or '')[:200]}\n"
                f"  content:  {(parsed.get('content') or '')[:200]}"
            )

            # Execute action
            result = await self._execute_action(player_id, parsed)

            # Save conversation message
            try:
                save_conversation_message(
                    player_id=player_id,
                    speaker="chess_master",
                    content=parsed.get("content", ""),
                    context_json=json.dumps({
                        "action": parsed.get("action"),
                        "tone": parsed.get("tone"),
                        "input_context": context_data,
                    }),
                )
            except Exception as e:
                logger.warning(f"Failed to save message to history: {e}")

            # Update emotion state
            if "emotion" in parsed.get("metadata", {}):
                self.emotion_state = parsed["metadata"]["emotion"]

            self.last_response_time = datetime.now()
            return result

        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            return {
                "action": "stop",
                "content": "I'm experiencing some technical difficulties.",
                "error": True,
            }

    def _build_user_prompt(
        self,
        input_text: str,
        player: PlayerProfile,
        memory_context: Dict[str, Any],
        context_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the user prompt with all relevant context."""
        prompt = f"Player '{player.player_name}' says: {input_text}\n\n"

        # Add trigger point context
        if memory_context.get("trigger_point"):
            trigger = memory_context.get("trigger_point")
            trigger_descriptions = {
                "before_match": "Match is starting",
                "on_user_input": "Player sent a message",
                "on_user_move": "Player made a move",
                "before_agent_move": "Your turn to move",
                "idle_wait": "Player is taking their time",
                "after_match": "Match has ended",
            }
            prompt += f"[Context: {trigger_descriptions.get(trigger, trigger)}]\n\n"

        # Add conversation history — full current match + recent prior games
        if memory_context.get("conversation_history"):
            prompt += "# Conversation History\n"
            recent_messages = memory_context["conversation_history"][-30:]
            for msg in recent_messages:
                if msg.get("speaker") == "chess_master_internal":
                    continue
                speaker = "You" if msg["speaker"] == "chess_master" else player.player_name
                prompt += f"{speaker}: {msg['content']}\n"
            prompt += "\n"

        # Add relevant memories — lore surfaces as Viktor's own thoughts, player memories as observations
        if memory_context.get("memories"):
            lore_mems = [m for m in memory_context["memories"] if not m.get("related_player_id")]
            player_mems = [m for m in memory_context["memories"] if m.get("related_player_id")]

            if lore_mems:
                prompt += "# Something surfaces from memory\n"
                for mem in lore_mems[:2]:
                    prompt += f"— {mem['content']}\n"
                prompt += "\n"

            if player_mems:
                prompt += "# What you know about this player\n"
                for mem in player_mems[:2]:
                    prompt += f"— {mem['content']}\n"
                prompt += "\n"

        # Add silence context — helps the model know how recently it spoke
        if context_data and "moves_since_last_comment" in context_data:
            n = context_data["moves_since_last_comment"]
            if n == 0:
                prompt += "[You spoke on the last move. Default to silence.]\n\n"
            elif n == 1:
                prompt += "[You spoke 1 move ago. Strong default toward silence.]\n\n"

        # Add last move — explicit so Viktor never guesses wrong
        if context_data and context_data.get("last_move_san"):
            san = context_data["last_move_san"]
            who = context_data.get("last_move_player", "")
            prompt += f"Last move played: {san}{f' (by {who})' if who else ''}\n\n"

        # Add chess board context
        if context_data and "piece_positions" in context_data:
            agent_color = context_data.get("agent_color", "Black")
            player_color = context_data.get("player_color", "White")
            prompt += f"# Chess Position (you are {agent_color})\n"
            prompt += context_data["piece_positions"] + "\n\n"

            if "position_analysis" in context_data:
                prompt += context_data["position_analysis"] + "\n\n"

            if "game_phase" in context_data:
                prompt += f"Phase: {context_data['game_phase']}"
            if "opening" in context_data and context_data["opening"]:
                prompt += f"  |  Opening: {context_data['opening']}"
            prompt += "\n"

            if "game_status" in context_data:
                status = context_data["game_status"]
                if status.get("is_check"):
                    prompt += f"⚠️ {status.get('current_player')} is in CHECK\n"
                if status.get("is_checkmate"):
                    prompt += f"🏁 CHECKMATE\n"
                if status.get("is_stalemate"):
                    prompt += f"🤝 STALEMATE\n"
            prompt += "\n"

        # Add other context data if provided
        if context_data:
            has_other_context = False
            for key in ["move", "position", "game_state", "event", "idle_seconds"]:
                if key in context_data and key not in ["board_ascii", "board_fen", "position_analysis", "legal_moves", "game_phase", "opening", "game_status"]:
                    if not has_other_context:
                        prompt += "# Context\n"
                        has_other_context = True

                    if key == "move":
                        prompt += f"Last Move: {context_data[key]}\n"
                    elif key == "position":
                        prompt += f"Game Phase: {context_data[key]}\n"
                    elif key == "game_state":
                        prompt += f"Game State: {context_data[key]}\n"
                    elif key == "event":
                        prompt += f"Event: {context_data[key]}\n"
                    elif key == "idle_seconds":
                        prompt += f"Idle For: {context_data[key]} seconds\n"

            if has_other_context:
                prompt += "\n"

        return prompt

    def _parse_agent_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured format.

        Args:
            response: Response from LLM (should be JSON)

        Returns:
            Parsed response dict
        """
        try:
            # Handle markdown code blocks
            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.index("```") + 3
                end = response.index("```", start)
                response = response[start:end].strip()

            data = json.loads(response)

            # Ensure required fields
            data.setdefault("action", "send_message")
            data.setdefault("content", "")
            data.setdefault("tone", "neutral")
            data.setdefault("metadata", {})
            data.setdefault("thinking", "")

            return data
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return {
                "action": "stop",
                "content": "Error parsing response.",
                "tone": "neutral",
                "metadata": {},
            }

    async def _execute_action(
        self,
        player_id: str,
        parsed_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the action specified in the response.

        Args:
            player_id: Player ID
            parsed_response: Parsed response from LLM

        Returns:
            Result dict with action and content
        """
        action = parsed_response.get("action", "send_message")

        if action == "send_message":
            return {
                "action": "send_message",
                "content": parsed_response.get("content", ""),
                "tone": parsed_response.get("tone", "neutral"),
                "thinking": parsed_response.get("thinking", ""),
                "metadata": parsed_response.get("metadata", {}),
            }

        elif action == "save_memory":
            if not self.memory_client:
                logger.warning("Memory client not available")
                return {
                    "action": "send_message",
                    "content": parsed_response.get("content", ""),
                }

            try:
                from memory.schemas import MemoryType as MT

                content = parsed_response.get("content", "")
                memory_type = parsed_response.get("memory_type", "player_observation")
                memory_id = await self.memory_client.store(
                    content=content,
                    memory_type=MT(memory_type),
                    related_player_id=player_id,
                    metadata=parsed_response.get("metadata"),
                )
                logger.info(f"Saved memory {memory_id}")
                return {
                    "action": "send_message",
                    "content": parsed_response.get("content", ""),
                    "tone": parsed_response.get("tone", "neutral"),
                    "thinking": parsed_response.get("thinking", ""),
                    "memory_id": memory_id,
                    "memory_saved": True,
                }
            except Exception as e:
                logger.error(f"Failed to save memory: {e}")
                return {
                    "action": "send_message",
                    "content": parsed_response.get("content", ""),
                }

        elif action == "set_emotion":
            emotion = parsed_response.get("metadata", {}).get("emotion", "neutral")
            self.emotion_state = emotion
            logger.info(f"Set emotion to: {emotion}")
            return {
                "action": "emotion_changed",
                "emotion": emotion,
            }

        elif action == "stop":
            return {
                "action": "stop",
                "reason": parsed_response.get("metadata", {}).get("reason"),
            }

        else:
            logger.warning(f"Unknown action: {action}")
            return {
                "action": "send_message",
                "content": parsed_response.get("content", ""),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "emotion": self.emotion_state,
            "last_response": self.last_response_time.isoformat() if self.last_response_time else None,
            "api_provider": self.api_client.__class__.__name__,
        }


__all__ = ["ChessMaster"]
