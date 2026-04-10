"""
Memory schema definitions for Weaviate vector database.
Stores all of the Chess Master's experiences and observations.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum


class MemoryType(str, Enum):
    """Categories of memories for semantic tagging."""
    PLAYER_BEHAVIOR = "player_behavior"  # How a player plays, their style
    PLAYER_OBSERVATION = "player_observation"  # Observations about a player as a person
    GAME_CONTEXT = "game_context"  # Context about a specific match
    PERSONAL_NOTE = "personal_note"  # Chess Master's thoughts, reflections, opinions
    STREAK = "streak"  # Win/loss streaks or patterns noticed
    PATTERN = "pattern"  # Repeated behaviors, strategies, or tendencies
    EMOTIONAL = "emotional"  # Emotional reactions or states
    LORE = "lore"  # Chess Master's own backstory, history, mentors, past matches


@dataclass
class Memory:
    """
    A single memory in the Chess Master's subconscious.

    Attributes:
        id: Unique identifier (UUID)
        timestamp: When the memory was created (preserved for recency context)
        content: The actual memory text (what gets embedded for semantic search)
        memory_type: Category/tag for retrieval
        related_match_id: Optional association with a chess match
        related_player_id: Optional association with a specific player
        created_by: Whether created by main_agent or subconscious
        metadata: Additional context (e.g., player_name, match_difficulty, opening_name)
    """
    id: str
    timestamp: datetime
    content: str
    memory_type: MemoryType
    related_match_id: Optional[str] = None
    related_player_id: Optional[str] = None
    created_by: str = "main_agent"  # "main_agent" or "subconscious"
    metadata: Optional[dict] = None

    # Note: `embedding` is computed by Weaviate during storage, not stored in this object


# Weaviate class definition (schema)
MEMORY_CLASS_DEFINITION = {
    "class": "ChessMasterMemory",
    "description": "A memory in the Chess Master's subconscious",
    "properties": [
        {
            "name": "content",
            "description": "The memory content (what gets embedded)",
            "dataType": ["text"],
        },
        {
            "name": "timestamp",
            "description": "When the memory was created (preserved for recency awareness)",
            "dataType": ["date"],
        },
        {
            "name": "memory_type",
            "description": "Category of memory (player_behavior, lore, pattern, etc.)",
            "dataType": ["text"],
        },
        {
            "name": "related_match_id",
            "description": "Associated chess match ID if any",
            "dataType": ["text"],
        },
        {
            "name": "related_player_id",
            "description": "Associated player ID if this memory is about a specific player",
            "dataType": ["text"],
        },
        {
            "name": "created_by",
            "description": "Agent that created this memory (main_agent or subconscious)",
            "dataType": ["text"],
        },
        {
            "name": "metadata",
            "description": "Additional JSON metadata (player_name, difficulty, opening, etc.)",
            "dataType": ["text"],
        },
    ],
    "vectorizer": "none",  # We embed client-side using sentence-transformers
    # Embeddings are sent to Weaviate via vector property
}


@dataclass
class ConversationMessage:
    """
    A single message in a conversation between Chess Master and a player.

    Used to store conversation history per player so the agent can
    reference recent interactions and build relationships.
    """
    player_id: str
    timestamp: datetime
    speaker: str  # "chess_master" or "player"
    content: str
    context: Optional[dict] = None  # Game state, move info, etc. at time of message


@dataclass
class PlayerProfile:
    """
    Persistent profile for a player across multiple games.

    Tracks relationship state, skill level, play patterns, and history
    so the Chess Master can remember and adapt to individual players.
    """
    player_id: str
    player_name: str
    first_seen: datetime
    last_played: datetime
    total_games: int = 0
    wins_against_agent: int = 0
    losses_against_agent: int = 0
    draws: int = 0
    preferred_difficulty: str = "intermediate"
    estimated_elo: int = 1400  # Rough estimate based on play
    relationship_state: str = "new"  # "new" -> "familiar" -> "rival"
    notes: Optional[str] = None  # Free-form notes about the player
