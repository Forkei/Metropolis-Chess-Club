"""
SQLAlchemy ORM models for player profiles and conversation history.

Persistent storage for:
- Player profiles (names, stats, relationship state)
- Conversation messages (for context retrieval)
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

Base = declarative_base()


class PlayerProfile(Base):
    """
    Persistent profile for a player across multiple games.

    Tracks relationship state, skill level, play patterns, and history
    so the Chess Master can remember and adapt to individual players.
    """

    __tablename__ = "player_profiles"

    player_id = Column(String(255), primary_key=True)
    player_name = Column(String(255), nullable=False)

    # Timeline
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_played = Column(DateTime, default=datetime.now, nullable=False)

    # Stats
    total_games = Column(Integer, default=0)
    wins_against_agent = Column(Integer, default=0)
    losses_against_agent = Column(Integer, default=0)
    draws = Column(Integer, default=0)

    # Preferences and skill
    preferred_difficulty = Column(String(50), default="intermediate")
    estimated_elo = Column(Integer, default=1400)

    # Relationship state: "new" -> "familiar" -> "rival"
    relationship_state = Column(String(50), default="new")

    # Notes
    notes = Column(Text, nullable=True)

    # Relationship to conversations
    conversations = relationship(
        "ConversationMessage",
        back_populates="player",
        cascade="all, delete-orphan",
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<PlayerProfile("
            f"player_id={self.player_id}, "
            f"player_name={self.player_name}, "
            f"total_games={self.total_games}, "
            f"relationship_state={self.relationship_state}"
            ")>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_played": self.last_played.isoformat() if self.last_played else None,
            "total_games": self.total_games,
            "wins": self.wins_against_agent,
            "losses": self.losses_against_agent,
            "draws": self.draws,
            "preferred_difficulty": self.preferred_difficulty,
            "estimated_elo": self.estimated_elo,
            "relationship_state": self.relationship_state,
            "notes": self.notes,
        }

    def update_last_played(self) -> None:
        """Update last_played timestamp."""
        self.last_played = datetime.now()

    def record_game(self, outcome: str) -> None:
        """
        Record a game outcome.

        Args:
            outcome: "win", "loss", or "draw"
        """
        self.total_games += 1
        if outcome == "win":
            self.wins_against_agent += 1
        elif outcome == "loss":
            self.losses_against_agent += 1
        elif outcome == "draw":
            self.draws += 1
        self.update_last_played()

    def get_win_rate(self) -> float:
        """Calculate win rate against agent."""
        if self.total_games == 0:
            return 0.0
        return self.wins_against_agent / self.total_games

    def update_relationship(self) -> None:
        """Update relationship state based on interaction history."""
        if self.total_games == 0:
            self.relationship_state = "new"
        elif self.total_games < 5:
            self.relationship_state = "familiar"
        else:
            self.relationship_state = "rival"


class ConversationMessage(Base):
    """
    A single message in a conversation between Chess Master and a player.

    Used to store conversation history per player so the agent can
    reference recent interactions and build relationships.
    """

    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True)
    player_id = Column(String(255), ForeignKey("player_profiles.player_id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    speaker = Column(String(50), nullable=False)  # "chess_master" or "player"
    content = Column(Text, nullable=False)

    # Optional context (game state, move info, etc.) as JSON string
    context_json = Column(Text, nullable=True)

    # Relationship to player
    player = relationship(
        "PlayerProfile",
        back_populates="conversations",
        foreign_keys=[player_id],
    )

    # Timestamp for ordering
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        Index("idx_player_timestamp", "player_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationMessage("
            f"player_id={self.player_id}, "
            f"speaker={self.speaker}, "
            f"timestamp={self.timestamp}"
            ")>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "player_id": self.player_id,
            "timestamp": self.timestamp.isoformat(),
            "speaker": self.speaker,
            "content": self.content,
            "context": self.context_json,
        }
