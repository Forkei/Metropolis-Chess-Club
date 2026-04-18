"""
Database module for Chess Master agent.

Handles:
- SQLAlchemy ORM models (PlayerProfile, ConversationMessage)
- Database initialization and session management
- Convenience repository functions for CRUD operations
"""

from db.models import Base, PlayerProfile, ConversationMessage
from db.database import (
    DatabaseManager,
    get_db_manager,
    close_db,
    get_or_create_player,
    get_player,
    get_player_conversation_history,
    save_conversation_message,
    get_all_players,
)

__all__ = [
    "Base",
    "PlayerProfile",
    "ConversationMessage",
    "DatabaseManager",
    "get_db_manager",
    "close_db",
    "get_or_create_player",
    "get_player",
    "get_player_conversation_history",
    "save_conversation_message",
    "get_all_players",
]
