"""
Scheduler for triggering the Chess Master agent at different points in a game.

Possible trigger points:
- Before match starts
- After opponent sends a message/modality input
- After opponent makes a move
- Before Chess Master makes a move
- While waiting for opponent (periodic checks)
- After match ends

The scheduler coordinates timing and calls the agent with appropriate context.
"""

from enum import Enum
from datetime import datetime
from typing import Callable, Optional, Dict, Any


class TriggerPoint(str, Enum):
    """When the agent should be triggered."""
    BEFORE_MATCH = "before_match"  # Match setup
    ON_USER_INPUT = "on_user_input"  # Message/emotion/action from user
    ON_USER_MOVE = "on_user_move"  # After user makes a chess move
    BEFORE_AGENT_MOVE = "before_agent_move"  # Agent deciding what to do
    IDLE_WAIT = "idle_wait"  # Periodic check while waiting for user
    AFTER_MATCH = "after_match"  # Match ends


class MatchScheduler:
    """
    Manages timing and dispatch of agent triggers during a chess match.
    
    TODO:
    - Implement APScheduler integration
    - Store trigger history for analysis
    - Support custom trigger logic (e.g., "only every 5 moves")
    """
    
    def __init__(self, match_id: str):
        self.match_id = match_id
        self.triggers = []
        
    async def trigger(self, point: TriggerPoint, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Trigger the agent for a given event.
        
        Args:
            point: When this trigger is happening
            context: Game state, messages, move history, etc.
            
        Returns:
            Agent response (message, action, etc.) or None if agent chooses to do nothing
        """
        # TODO: Dispatch to agent with context
        pass
    
    async def start_idle_monitoring(self, check_interval_seconds: int = 10):
        """
        Periodically check if user is taking too long. Agent can comment or pass.
        """
        # TODO: Implement with APScheduler
        pass
    
    async def end_match(self):
        """
        Called when match concludes. Agent can reflect.
        """
        # TODO: Save match history, trigger final agent response
        pass
