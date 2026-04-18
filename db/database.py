"""
Database initialization and session management.

Handles:
- Database connection and creation
- Session factory
- Context managers for database access
"""

import logging
from typing import Optional, List
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session

from db.models import Base, PlayerProfile, ConversationMessage

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database lifecycle and session creation.

    Supports:
    - SQLite (local files)
    - Connection pooling
    - Schema initialization
    - Session context managers
    """

    def __init__(self, database_url: str = "sqlite:///chess_club.db"):
        """
        Initialize database manager.

        Args:
            database_url: SQLAlchemy database URL
                         Default: SQLite file at chess_club.db
                         Example: "sqlite:///chess_club.db"
                                  "postgresql://user:pass@localhost/chess_club"
        """
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize database connection and create schema."""
        if self._initialized:
            logger.debug("Database already initialized")
            return

        logger.info(f"Initializing database: {self.database_url}")

        # Create engine
        if "sqlite" in self.database_url:
            self.engine = create_engine(
                self.database_url,
                connect_args={"check_same_thread": False},
            )
        else:
            # Other databases
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,  # Test connection before using
                pool_size=20,
                max_overflow=40,
            )

        # Create session factory
        # expire_on_commit=False allows detached objects to be used outside the session context
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=False,
        )

        # Create schema
        self._create_schema()
        self._initialized = True

    def _create_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        logger.info("Creating database schema")
        Base.metadata.create_all(self.engine)
        logger.info("Schema created successfully")

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions.

        Usage:
            with db_manager.get_session() as session:
                player = session.query(PlayerProfile).first()
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close database connection."""
        if self.engine:
            logger.info("Closing database connection")
            self.engine.dispose()
            self._initialized = False


# Global instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(database_url: str = "sqlite:///chess_club.db") -> DatabaseManager:
    """
    Get or create the global database manager.

    Args:
        database_url: SQLAlchemy database URL

    Returns:
        Initialized DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(database_url)
        _db_manager.initialize()
    return _db_manager


def close_db() -> None:
    """Close the global database connection."""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None


# Convenience repository functions

def get_or_create_player(
    player_id: str,
    player_name: str = "Opponent",
) -> PlayerProfile:
    """
    Get an existing player or create a new one.

    Args:
        player_id: Unique player identifier
        player_name: Display name for the player

    Returns:
        PlayerProfile instance (persisted)
    """
    db = get_db_manager()
    with db.get_session() as session:
        player = session.query(PlayerProfile).filter_by(player_id=player_id).first()

        if player is None:
            logger.info(f"Creating new player profile: {player_id}")
            player = PlayerProfile(
                player_id=player_id,
                player_name=player_name,
            )
            session.add(player)

        return player


def get_player(player_id: str) -> Optional[PlayerProfile]:
    """Get a player by ID."""
    db = get_db_manager()
    with db.get_session() as session:
        player = session.query(PlayerProfile).filter_by(player_id=player_id).first()
        return player


def get_player_conversation_history(
    player_id: str,
    limit: int = 10,
) -> List[ConversationMessage]:
    """
    Get recent conversation history for a player.

    Args:
        player_id: Player ID
        limit: Maximum number of messages to retrieve

    Returns:
        List of ConversationMessage objects, ordered by timestamp (newest first)
    """
    db = get_db_manager()
    with db.get_session() as session:
        messages = (
            session.query(ConversationMessage)
            .filter_by(player_id=player_id)
            .order_by(ConversationMessage.timestamp.desc())
            .limit(limit)
            .all()
        )
        # Reverse to chronological order
        return list(reversed(messages))


def save_conversation_message(
    player_id: str,
    speaker: str,
    content: str,
    context_json: Optional[str] = None,
) -> ConversationMessage:
    """
    Save a message to conversation history.

    Args:
        player_id: Player ID
        speaker: "chess_master" or "player"
        content: Message text
        context_json: Optional JSON context

    Returns:
        Saved ConversationMessage
    """
    db = get_db_manager()
    with db.get_session() as session:
        message = ConversationMessage(
            player_id=player_id,
            speaker=speaker,
            content=content,
            context_json=context_json,
        )
        session.add(message)
        logger.debug(f"Saved message for {player_id}: {content[:50]}...")
        return message


def get_all_players() -> List[PlayerProfile]:
    """Get all player profiles."""
    db = get_db_manager()
    with db.get_session() as session:
        return session.query(PlayerProfile).all()


__all__ = [
    "DatabaseManager",
    "get_db_manager",
    "close_db",
    "get_or_create_player",
    "get_player",
    "get_player_conversation_history",
    "save_conversation_message",
    "get_all_players",
]
