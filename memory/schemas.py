"""
Memory schema definitions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class MemoryType(str, Enum):
    """Categories of memories for semantic tagging."""
    PLAYER_BEHAVIOR = "player_behavior"
    PLAYER_OBSERVATION = "player_observation"
    GAME_CONTEXT = "game_context"
    PERSONAL_NOTE = "personal_note"
    STREAK = "streak"
    PATTERN = "pattern"
    EMOTIONAL = "emotional"
    LORE = "lore"


@dataclass
class Memory:
    """A single memory in the Chess Master's subconscious."""
    id: str
    timestamp: datetime
    content: str
    memory_type: MemoryType
    related_match_id: Optional[str] = None
    related_player_id: Optional[str] = None
    created_by: str = "main_agent"
    metadata: Optional[dict] = None
