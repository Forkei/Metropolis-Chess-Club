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
    PLAYER_BEHAVIOR = "player_behavior"  # How the user plays
    PLAYER_OBSERVATION = "player_observation"  # Observations about the user
    GAME_CONTEXT = "game_context"  # Context about a match
    PERSONAL_NOTE = "personal_note"  # Thoughts about itself/the game
    STREAK = "streak"  # Win/loss streaks noticed
    PATTERN = "pattern"  # Repeated behaviors or strategies
    EMOTIONAL = "emotional"  # Emotional reactions or states


@dataclass
class Memory:
    """
    A single memory in the Chess Master's subconscious.
    
    Attributes:
        id: Unique identifier (UUID)
        timestamp: When the memory was created
        content: The actual memory text (what to embed)
        memory_type: Category/tag for retrieval
        related_match_id: Optional association with a chess match
        relevance_decay_date: Optional date after which memory becomes less relevant
        created_by: Whether created by main agent or subconscious
        metadata: Additional context (e.g., player_name, match_difficulty)
    """
    id: str
    timestamp: datetime
    content: str
    memory_type: MemoryType
    related_match_id: Optional[str] = None
    relevance_decay_date: Optional[datetime] = None
    created_by: str = "main_agent"  # "main_agent" or "subconscious"
    metadata: Optional[dict] = None
    
    # Note: `embedding` is computed by Weaviate, not stored here


# Weaviate class definition (schema)
MEMORY_CLASS_DEFINITION = {
    "class": "ChessMasterMemory",
    "description": "A memory of the Chess Master",
    "properties": [
        {
            "name": "content",
            "description": "The memory content",
            "dataType": ["text"],
        },
        {
            "name": "timestamp",
            "description": "When the memory was created",
            "dataType": ["date"],
        },
        {
            "name": "memory_type",
            "description": "Category of memory",
            "dataType": ["text"],
        },
        {
            "name": "related_match_id",
            "description": "Associated chess match ID if any",
            "dataType": ["text"],
        },
        {
            "name": "relevance_decay_date",
            "description": "When this memory should be considered stale",
            "dataType": ["date"],
        },
        {
            "name": "created_by",
            "description": "Agent that created this memory",
            "dataType": ["text"],
        },
        {
            "name": "metadata",
            "description": "Additional JSON metadata",
            "dataType": ["text"],  # Store as JSON string
        },
    ],
    "vectorizer": "text2vec-openai",  # We'll configure this based on model choice
}
