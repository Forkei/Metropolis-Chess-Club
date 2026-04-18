"""
Async scheduler for triggering the Chess Master agent at different points in a game.

Manages dispatch and coordination of agent responses across trigger points.

Trigger points:
- before_match: Game setup, greeting
- on_user_input: Message/emotion/action from user
- on_user_move: After opponent makes a chess move
- before_agent_move: Just before the agent moves
- idle_wait: Player is taking too long (fired by app-level idle monitor)
- after_match: Match concludes, reflect/save
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from chess_engine import ChessGame, PositionAnalysis

logger = logging.getLogger(__name__)


class TriggerPoint(str, Enum):
    """When the agent should be triggered."""

    BEFORE_MATCH      = "before_match"
    ON_USER_INPUT     = "on_user_input"
    ON_USER_MOVE      = "on_user_move"
    BEFORE_AGENT_MOVE = "before_agent_move"
    IDLE_WAIT         = "idle_wait"
    AFTER_MATCH       = "after_match"


class MatchScheduler:
    """
    Async scheduler for agent triggers during a chess match.

    Handles:
    - Event-driven triggers (user input, moves, etc.)
    - Player persistence — loads player profile, conversation history
    - Conversation logging — appends to persistent conversation history
    - Chattiness control — silence gate for ON_USER_MOVE triggers
    - Idle monitoring — asyncio task that nudges the agent when the player stalls
    """

    def __init__(
        self,
        match_id: str,
        player_id: str,
        main_agent=None,
        subconscious_agent=None,
        player_name: str = "Player",
        agent_name: str = "Chess Master",
    ):
        self.match_id = match_id
        self.player_id = player_id
        self.main_agent = main_agent
        self.subconscious_agent = subconscious_agent
        self.conversation_history: List[Dict[str, Any]] = []
        self.trigger_history: List[Dict[str, Any]] = []
        self.match_start_time = None
        self.last_user_activity = None

        # Chess game state
        self.chess_game: Optional[ChessGame] = None
        self.player_name = player_name
        self.agent_name = agent_name

        # Chattiness control: track ON_USER_MOVE events and when Viktor last spoke
        self.on_user_move_count: int = 0
        self.viktor_last_spoke_at_move: int = -99
        self.MIN_MOVES_BETWEEN_COMMENTS: int = 4

        # Idle monitoring
        self.idle_monitoring_active: bool = False
        self.scheduler = None  # asyncio.Task for the idle monitoring loop

        # Cached player relationship (set in start_match to avoid sync DB calls in async context)
        self._cached_relationship: str = "new"

    async def trigger(
        self,
        point: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Trigger the agent for a given event.

        Args:
            point: TriggerPoint value
            context: Game state, messages, move history, etc.

        Returns:
            Agent response dict or None if agent chooses to do nothing
        """
        if not self.main_agent:
            logger.warning("Main agent not available")
            return None

        context = context or {}
        self.last_user_activity = datetime.now()

        logger.info(f"Trigger {point} for player {self.player_id}")

        self.trigger_history.append({
            "timestamp": datetime.now().isoformat(),
            "trigger_point": point,
            "context_keys": list(context.keys()),
        })

        try:
            # ── Chattiness gate (ON_USER_MOVE only) ──────────────────────────
            if point == TriggerPoint.ON_USER_MOVE:
                self.on_user_move_count += 1
                moves_since_spoke = self.on_user_move_count - self.viktor_last_spoke_at_move
                context["moves_since_last_comment"] = moves_since_spoke - 1
                if moves_since_spoke < self.MIN_MOVES_BETWEEN_COMMENTS:
                    logger.debug(
                        f"Silence gate: Viktor spoke {moves_since_spoke - 1} moves ago, staying quiet"
                    )
                    return {"action": "stop"}

            # ── Inject board state ────────────────────────────────────────────
            if self.chess_game:
                context.setdefault("board_fen", self.chess_game.get_fen())
                context.setdefault("game_phase", self.chess_game.get_game_phase())
                context.setdefault("opening", self.chess_game.get_opening_name())
                context.setdefault("legal_moves", self.chess_game.get_legal_moves())
                context.setdefault("game_status", self.chess_game.get_game_status())
                context.setdefault(
                    "position_analysis",
                    PositionAnalysis.describe_position_for_agent(self.chess_game.board),
                )
                context.setdefault(
                    "piece_positions",
                    self.chess_game.get_piece_positions(
                        white_label=self.player_name,
                        black_label=self.agent_name,
                    ),
                )
                context.setdefault("agent_color", "Black")
                context.setdefault("player_color", "White")
                last_move = self.chess_game.get_last_move()
                if last_move:
                    context.setdefault("last_move_san", last_move.get("move_san", ""))
                    context.setdefault("last_move_player", last_move.get("player", ""))

            # ── Subconscious memory retrieval ─────────────────────────────────
            memories = []
            if self.subconscious_agent:
                try:
                    memories = await self.subconscious_agent.process(
                        player_id=self.player_id,
                        game_context=context,
                        trigger_point=point,
                    )
                except Exception as e:
                    logger.warning(f"Subconscious error: {e}")

            # ── Main agent call ───────────────────────────────────────────────
            user_input = context.get("user_input") or self._get_default_input(point)

            response = await self.main_agent.respond(
                player_id=self.player_id,
                input_text=user_input,
                context_data=context,
                trigger_point=point,
                subconscious_memories=memories if memories else None,
                current_match_history=self.conversation_history if self.conversation_history else None,
            )

            # Annotate with memory count
            if response and memories:
                response["memories_surfaced"] = len(memories)

            # Track when Viktor last spoke (for silence gate)
            if response and response.get("action") == "send_message" and point == TriggerPoint.ON_USER_MOVE:
                self.viktor_last_spoke_at_move = self.on_user_move_count

            # Log response to conversation history
            if response:
                if response.get("action") == "send_message":
                    self.conversation_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "speaker": "chess_master",
                        "content": response.get("content", ""),
                        "tone": response.get("tone"),
                        "trigger_point": point,
                    })
                elif response.get("action") == "save_memory":
                    self.conversation_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "speaker": "chess_master_internal",
                        "content": f"[SAVED MEMORY] {response.get('content', '')}",
                        "action": "save_memory",
                        "memory_id": response.get("memory_id"),
                        "trigger_point": point,
                    })

            return response

        except Exception as e:
            logger.error(f"Error in trigger {point}: {e}", exc_info=True)
            return {"action": "stop", "error": True}

    def _get_default_input(self, point: str) -> str:
        """Generate default user input based on trigger point."""
        relationship = self._cached_relationship
        defaults = {
            TriggerPoint.BEFORE_MATCH: (
                "Ready for a real challenge?" if relationship == "rival"
                else "Let's play" if relationship == "familiar"
                else "Let's see what you've got"
            ),
            TriggerPoint.ON_USER_INPUT: "I'm here",
            TriggerPoint.ON_USER_MOVE: "Your move",
            TriggerPoint.BEFORE_AGENT_MOVE: "Your turn",
            TriggerPoint.IDLE_WAIT: (
                "Take your time, I'm patient" if relationship == "new"
                else "Still calculating?" if relationship == "familiar"
                else "Time to move, don't you think?"
            ),
            TriggerPoint.AFTER_MATCH: "Well played",
        }
        return defaults.get(point, "")

    def start_match(self) -> None:
        """Mark match as started and initialize chess game."""
        self.match_start_time = datetime.now()
        self.last_user_activity = datetime.now()
        self.chess_game = ChessGame(
            white_player=self.player_name,
            black_player=self.agent_name,
        )
        self.chess_game.started_at = self.match_start_time

        # Cache player relationship to avoid sync DB calls inside async triggers
        try:
            from db import get_player
            p = get_player(self.player_id)
            if p:
                self._cached_relationship = p.relationship_state
        except Exception:
            pass

        logger.info(f"Match {self.match_id} started: {self.player_name} (white) vs {self.agent_name} (black)")

    async def end_match(self, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fire AFTER_MATCH trigger and persist game outcome to the database."""
        response = await self.trigger(TriggerPoint.AFTER_MATCH, context)
        await self._record_game_outcome()
        return response

    async def _record_game_outcome(self) -> None:
        """Persist game result and update player relationship in the database."""
        if not self.chess_game:
            return
        result = self.chess_game.get_game_result()
        if result is None:
            return

        # Player is always White
        if result == "1-0":
            outcome = "win"
        elif result == "0-1":
            outcome = "loss"
        else:
            outcome = "draw"

        try:
            from db.database import get_db_manager
            from db.models import PlayerProfile as PP
            db = get_db_manager()
            with db.get_session() as session:
                player = session.query(PP).filter_by(player_id=self.player_id).first()
                if player:
                    player.record_game(outcome)
                    player.update_relationship()
                    self._cached_relationship = player.relationship_state
                    logger.info(f"Recorded game outcome '{outcome}' for player {self.player_id}")
        except Exception as e:
            logger.error(f"Failed to record game outcome: {e}")

    # ── Idle monitoring ───────────────────────────────────────────────────────

    async def start_idle_monitoring(
        self,
        check_interval_seconds: int = 10,
        idle_threshold_seconds: int = 30,
    ) -> None:
        """Start background asyncio task that fires IDLE_WAIT when the player stalls."""
        if self.idle_monitoring_active:
            return
        self.idle_monitoring_active = True
        self.scheduler = asyncio.create_task(
            self._idle_loop(check_interval_seconds, idle_threshold_seconds)
        )

    async def stop_idle_monitoring(self) -> None:
        """Cancel the idle monitoring task."""
        self.idle_monitoring_active = False
        if self.scheduler:
            self.scheduler.cancel()
            try:
                await self.scheduler
            except asyncio.CancelledError:
                pass
            self.scheduler = None

    async def _idle_loop(self, check_interval_seconds: int, idle_threshold_seconds: int) -> None:
        while self.idle_monitoring_active:
            await asyncio.sleep(check_interval_seconds)
            await self._check_idle(idle_threshold_seconds)

    async def _check_idle(self, idle_threshold_seconds: int = 30) -> Optional[Dict[str, Any]]:
        """Fire IDLE_WAIT if the player has been inactive for longer than the threshold."""
        if not self.last_user_activity:
            return None
        elapsed = (datetime.now() - self.last_user_activity).total_seconds()
        if elapsed < idle_threshold_seconds:
            return None
        response = await self.trigger(TriggerPoint.IDLE_WAIT, {"idle_seconds": int(elapsed)})
        self.last_user_activity = datetime.now()
        return response

    # ── History accessors ─────────────────────────────────────────────────────

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.conversation_history.copy()

    def get_trigger_history(self) -> List[Dict[str, Any]]:
        return self.trigger_history.copy()

    # ── Move helpers ──────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get match statistics."""
        duration = None
        if self.match_start_time:
            duration = (datetime.now() - self.match_start_time).total_seconds()

        chess_stats = {}
        if self.chess_game:
            chess_stats = {
                "moves_count": self.chess_game.get_move_count(),
                "game_phase": self.chess_game.get_game_phase(),
                "is_game_over": self.chess_game.is_game_over(),
                "result": self.chess_game.result,
            }

        return {
            "match_id": self.match_id,
            "player_id": self.player_id,
            "duration_seconds": duration,
            "trigger_count": len(self.trigger_history),
            "conversation_count": len(self.conversation_history),
            "viktor_comments": self.viktor_last_spoke_at_move,
            "last_activity": self.last_user_activity.isoformat() if self.last_user_activity else None,
            "idle_monitoring_active": self.idle_monitoring_active,
            **chess_stats,
        }

    def make_player_move(self, move: str) -> Dict[str, Any]:
        if not self.chess_game:
            return {"success": False, "error": "No chess game in progress"}
        success, error = self.chess_game.make_move(move)
        if not success:
            return {"success": False, "error": error, "legal_moves": self.chess_game.get_legal_moves()}
        return {
            "success": True,
            "move": move,
            "fen": self.chess_game.get_fen(),
            "board_ascii": self.chess_game.get_ascii_board(),
            "game_status": self.chess_game.get_game_status(),
            "legal_moves": self.chess_game.get_legal_moves(),
        }

    def make_agent_move(self, move: str) -> Dict[str, Any]:
        result = self.make_player_move(move)
        if result.get("success"):
            logger.info(f"Agent played: {move}")
        return result

    def resign_player(self) -> Dict[str, Any]:
        if not self.chess_game:
            return {"success": False, "error": "No chess game in progress"}
        success, result = self.chess_game.resign(self.player_name)
        if not success:
            return {"success": False, "error": result}
        return {"success": True, "result": result}

    def offer_draw(self) -> Dict[str, Any]:
        if not self.chess_game:
            return {"success": False, "error": "No chess game in progress"}
        success, result = self.chess_game.draw()
        if not success:
            return {"success": False, "error": result}
        return {"success": True, "result": result}


__all__ = ["TriggerPoint", "MatchScheduler"]
