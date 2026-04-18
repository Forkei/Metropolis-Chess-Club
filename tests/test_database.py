"""
Tests for SQLite database models and session management.

Tests cover:
- Player profile CRUD operations
- Conversation message storage and retrieval
- Game statistics tracking
- Relationship state transitions
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

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
from db.models import PlayerProfile, ConversationMessage


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chess_club.db"
        db_url = f"sqlite:///{db_path}"

        # Create and initialize manager
        manager = DatabaseManager(db_url)
        manager.initialize()

        yield manager

        # Cleanup
        manager.close()


@pytest.fixture
def db_with_cleanup():
    """Use the global database manager but clean up afterward."""
    # Use in-memory SQLite for tests
    db = DatabaseManager("sqlite:///:memory:")
    db.initialize()
    yield db
    db.close()


class TestDatabaseManager:
    """Test DatabaseManager initialization and lifecycle."""

    def test_initialize(self, temp_db):
        """Test database initialization."""
        assert temp_db._initialized
        assert temp_db.engine is not None
        assert temp_db.SessionLocal is not None

    def test_initialize_idempotent(self, temp_db):
        """Test that calling initialize twice doesn't cause issues."""
        # First initialization already happened in fixture
        temp_db.initialize()
        # Should still work
        assert temp_db._initialized

    def test_get_session(self, temp_db):
        """Test context manager for sessions."""
        with temp_db.get_session() as session:
            assert session is not None
            # Session should be usable
            result = session.query(PlayerProfile).all()
            assert result == []

    def test_uninitialized_raises_error(self):
        """Test that get_session raises error if not initialized."""
        manager = DatabaseManager()
        with pytest.raises(RuntimeError, match="Database not initialized"):
            with manager.get_session() as session:
                pass

    def test_close(self, temp_db):
        """Test closing database connection."""
        temp_db.close()
        assert not temp_db._initialized
        # Should raise error on next session attempt
        with pytest.raises(RuntimeError):
            with temp_db.get_session() as session:
                pass


class TestPlayerProfile:
    """Test PlayerProfile model."""

    def test_create_player(self, temp_db):
        """Test creating a new player profile."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="alice-123",
                player_name="Alice",
            )
            session.add(player)
            session.commit()

            # Verify it was saved
            retrieved = session.query(PlayerProfile).filter_by(
                player_id="alice-123"
            ).first()
            assert retrieved is not None
            assert retrieved.player_name == "Alice"
            assert retrieved.total_games == 0
            assert retrieved.wins_against_agent == 0
            assert retrieved.relationship_state == "new"

    def test_player_record_game_win(self, temp_db):
        """Test recording a game win."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="bob-456",
                player_name="Bob",
            )
            session.add(player)
            session.commit()

        # Record a win
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="bob-456"
            ).first()
            player.record_game("win")
            session.commit()

        # Verify
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="bob-456"
            ).first()
            assert player.total_games == 1
            assert player.wins_against_agent == 1
            assert player.losses_against_agent == 0
            assert player.draws == 0

    def test_player_record_multiple_games(self, temp_db):
        """Test recording multiple game outcomes."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="charlie-789",
                player_name="Charlie",
            )
            session.add(player)
            session.commit()

        # Record multiple games
        outcomes = ["win", "loss", "draw", "win", "win"]
        for outcome in outcomes:
            with temp_db.get_session() as session:
                player = session.query(PlayerProfile).filter_by(
                    player_id="charlie-789"
                ).first()
                player.record_game(outcome)
                session.commit()

        # Verify
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="charlie-789"
            ).first()
            assert player.total_games == 5
            assert player.wins_against_agent == 3
            assert player.losses_against_agent == 1
            assert player.draws == 1

    def test_player_get_win_rate(self, temp_db):
        """Test win rate calculation."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="diana-100",
                player_name="Diana",
            )
            session.add(player)
            session.commit()

        # Record games
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="diana-100"
            ).first()
            for _ in range(3):
                player.record_game("win")
            for _ in range(2):
                player.record_game("loss")
            session.commit()

        # Check win rate
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="diana-100"
            ).first()
            win_rate = player.get_win_rate()
            assert win_rate == 0.6  # 3 wins out of 5 games

    def test_player_win_rate_no_games(self, temp_db):
        """Test win rate when no games played."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="eve-200",
                player_name="Eve",
            )
            session.add(player)
            session.commit()

        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="eve-200"
            ).first()
            assert player.get_win_rate() == 0.0

    def test_player_update_relationship(self, temp_db):
        """Test relationship state transitions."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="frank-300",
                player_name="Frank",
            )
            session.add(player)
            session.commit()

        # State: new (0 games)
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="frank-300"
            ).first()
            player.update_relationship()
            assert player.relationship_state == "new"

        # State: familiar (1-4 games)
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="frank-300"
            ).first()
            player.record_game("win")
            player.update_relationship()
            assert player.relationship_state == "familiar"

        # State: rival (5+ games)
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="frank-300"
            ).first()
            for _ in range(4):
                player.record_game("loss")
            player.update_relationship()
            assert player.relationship_state == "rival"

    def test_player_to_dict(self, temp_db):
        """Test converting player to dictionary."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="grace-400",
                player_name="Grace",
                preferred_difficulty="hard",
                estimated_elo=1600,
            )
            session.add(player)
            session.commit()

        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="grace-400"
            ).first()
            data = player.to_dict()

            assert data["player_id"] == "grace-400"
            assert data["player_name"] == "Grace"
            assert data["preferred_difficulty"] == "hard"
            assert data["estimated_elo"] == 1600
            assert data["total_games"] == 0
            assert "first_seen" in data


class TestConversationMessage:
    """Test ConversationMessage model."""

    def test_create_message(self, temp_db):
        """Test creating a conversation message."""
        # First create a player
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="henry-500",
                player_name="Henry",
            )
            session.add(player)
            session.commit()

        # Create a message
        with temp_db.get_session() as session:
            message = ConversationMessage(
                player_id="henry-500",
                speaker="chess_master",
                content="Your opening is weak.",
            )
            session.add(message)
            session.commit()

        # Verify
        with temp_db.get_session() as session:
            retrieved = session.query(ConversationMessage).filter_by(
                player_id="henry-500"
            ).first()
            assert retrieved is not None
            assert retrieved.speaker == "chess_master"
            assert retrieved.content == "Your opening is weak."

    def test_message_with_context(self, temp_db):
        """Test message with context JSON."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="iris-600",
                player_name="Iris",
            )
            session.add(player)
            session.commit()

        with temp_db.get_session() as session:
            message = ConversationMessage(
                player_id="iris-600",
                speaker="player",
                content="I want to play again",
                context_json='{"elo": 1400, "difficulty": "intermediate"}',
            )
            session.add(message)
            session.commit()

        with temp_db.get_session() as session:
            retrieved = session.query(ConversationMessage).filter_by(
                player_id="iris-600"
            ).first()
            assert retrieved.context_json == '{"elo": 1400, "difficulty": "intermediate"}'

    def test_conversation_history(self, temp_db):
        """Test retrieving conversation history."""
        # Create player
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="jack-700",
                player_name="Jack",
            )
            session.add(player)
            session.commit()

        # Create multiple messages
        messages = [
            ("chess_master", "Welcome back."),
            ("player", "I want to play"),
            ("chess_master", "Let's begin."),
        ]

        for speaker, content in messages:
            with temp_db.get_session() as session:
                msg = ConversationMessage(
                    player_id="jack-700",
                    speaker=speaker,
                    content=content,
                )
                session.add(msg)
                session.commit()

        # Retrieve history
        with temp_db.get_session() as session:
            history = session.query(ConversationMessage).filter_by(
                player_id="jack-700"
            ).order_by(ConversationMessage.timestamp).all()

            assert len(history) == 3
            assert history[0].content == "Welcome back."
            assert history[1].content == "I want to play"
            assert history[2].content == "Let's begin."

    def test_message_timestamp_ordering(self, temp_db):
        """Test that messages are ordered by timestamp."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="kate-800",
                player_name="Kate",
            )
            session.add(player)
            session.commit()

        # Create messages with specific timestamps
        base_time = datetime.now()
        for i in range(3):
            with temp_db.get_session() as session:
                msg = ConversationMessage(
                    player_id="kate-800",
                    speaker="chess_master",
                    content=f"Message {i}",
                    timestamp=base_time + timedelta(seconds=i),
                )
                session.add(msg)
                session.commit()

        # Retrieve in order
        with temp_db.get_session() as session:
            messages = session.query(ConversationMessage).filter_by(
                player_id="kate-800"
            ).order_by(ConversationMessage.timestamp).all()

            assert [m.content for m in messages] == ["Message 0", "Message 1", "Message 2"]

    def test_message_to_dict(self, temp_db):
        """Test converting message to dictionary."""
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="lisa-900",
                player_name="Lisa",
            )
            session.add(player)
            session.commit()

        with temp_db.get_session() as session:
            message = ConversationMessage(
                player_id="lisa-900",
                speaker="player",
                content="Great game!",
                context_json='{"result": "draw"}',
            )
            session.add(message)
            session.commit()

        with temp_db.get_session() as session:
            msg = session.query(ConversationMessage).filter_by(
                player_id="lisa-900"
            ).first()
            data = msg.to_dict()

            assert data["player_id"] == "lisa-900"
            assert data["speaker"] == "player"
            assert data["content"] == "Great game!"
            assert "timestamp" in data
            assert "id" in data


class TestConvenienceFunctions:
    """Test convenience repository functions."""

    def test_get_or_create_player_new(self, temp_db):
        """Test creating a new player via convenience function."""
        # Clear global state
        global _db_manager
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            player = get_or_create_player("mike-1000", "Mike")
            assert player.player_id == "mike-1000"
            assert player.player_name == "Mike"
            assert player.total_games == 0
        finally:
            db_module._db_manager = old_manager

    def test_get_or_create_player_existing(self, temp_db):
        """Test retrieving existing player."""
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            # Create player
            player1 = get_or_create_player("nancy-1100", "Nancy")

            # Record a game
            with temp_db.get_session() as session:
                p = session.query(PlayerProfile).filter_by(
                    player_id="nancy-1100"
                ).first()
                p.record_game("win")
                session.commit()

            # Get the same player again
            player2 = get_or_create_player("nancy-1100", "Nancy")
            assert player2.total_games == 1
        finally:
            db_module._db_manager = old_manager

    def test_get_player(self, temp_db):
        """Test retrieving a player by ID."""
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            # Create player
            with temp_db.get_session() as session:
                player = PlayerProfile(
                    player_id="oscar-1200",
                    player_name="Oscar",
                )
                session.add(player)
                session.commit()

            # Retrieve via function
            result = get_player("oscar-1200")
            assert result is not None
            assert result.player_name == "Oscar"
        finally:
            db_module._db_manager = old_manager

    def test_get_player_not_found(self, temp_db):
        """Test getting a player that doesn't exist."""
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            result = get_player("nonexistent-id")
            assert result is None
        finally:
            db_module._db_manager = old_manager

    def test_save_conversation_message(self, temp_db):
        """Test saving a conversation message via convenience function."""
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            # Create a player first
            with temp_db.get_session() as session:
                player = PlayerProfile(
                    player_id="paul-1300",
                    player_name="Paul",
                )
                session.add(player)
                session.commit()

            # Save message
            message = save_conversation_message(
                player_id="paul-1300",
                speaker="chess_master",
                content="That was a blunder.",
                context_json='{"move": "e4"}',
            )

            assert message.player_id == "paul-1300"
            assert message.content == "That was a blunder."
        finally:
            db_module._db_manager = old_manager

    def test_get_player_conversation_history(self, temp_db):
        """Test retrieving conversation history."""
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            # Create player
            with temp_db.get_session() as session:
                player = PlayerProfile(
                    player_id="quinn-1400",
                    player_name="Quinn",
                )
                session.add(player)
                session.commit()

            # Save some messages
            for i in range(3):
                save_conversation_message(
                    player_id="quinn-1400",
                    speaker="chess_master" if i % 2 == 0 else "player",
                    content=f"Message {i}",
                )

            # Retrieve history
            history = get_player_conversation_history("quinn-1400", limit=10)
            assert len(history) == 3
            assert [m.content for m in history] == ["Message 0", "Message 1", "Message 2"]
        finally:
            db_module._db_manager = old_manager

    def test_get_player_conversation_history_limit(self, temp_db):
        """Test conversation history limit."""
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            # Create player
            with temp_db.get_session() as session:
                player = PlayerProfile(
                    player_id="ruby-1500",
                    player_name="Ruby",
                )
                session.add(player)
                session.commit()

            # Save 15 messages
            for i in range(15):
                save_conversation_message(
                    player_id="ruby-1500",
                    speaker="chess_master",
                    content=f"Message {i}",
                )

            # Retrieve with limit of 5
            history = get_player_conversation_history("ruby-1500", limit=5)
            assert len(history) == 5
            # Should get the 5 most recent (10-14)
            assert "Message 10" in history[0].content
        finally:
            db_module._db_manager = old_manager

    def test_get_all_players(self, temp_db):
        """Test retrieving all players."""
        import db.database as db_module
        old_manager = db_module._db_manager
        db_module._db_manager = temp_db

        try:
            # Create multiple players
            player_ids = ["sam-1600", "tina-1700", "uma-1800"]
            for pid in player_ids:
                with temp_db.get_session() as session:
                    player = PlayerProfile(
                        player_id=pid,
                        player_name=pid.split("-")[0].title(),
                    )
                    session.add(player)
                    session.commit()

            # Get all
            all_players = get_all_players()
            assert len(all_players) == 3
            retrieved_ids = {p.player_id for p in all_players}
            assert retrieved_ids == set(player_ids)
        finally:
            db_module._db_manager = old_manager


class TestDatabaseIntegration:
    """Integration tests for full database workflows."""

    def test_player_game_cycle(self, temp_db):
        """Test a full player game cycle: create, play, retrieve."""
        with temp_db.get_session() as session:
            # Create player
            player = PlayerProfile(
                player_id="victor-1900",
                player_name="Victor",
                preferred_difficulty="hard",
                estimated_elo=1550,
            )
            session.add(player)
            session.commit()

        # Record games
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="victor-1900"
            ).first()
            player.record_game("win")
            player.record_game("loss")
            player.record_game("win")
            player.update_relationship()
            session.commit()

        # Add conversation
        with temp_db.get_session() as session:
            message = ConversationMessage(
                player_id="victor-1900",
                speaker="chess_master",
                content="You're improving.",
            )
            session.add(message)
            session.commit()

        # Verify full state
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="victor-1900"
            ).first()
            assert player.total_games == 3
            assert player.wins_against_agent == 2
            assert player.get_win_rate() == pytest.approx(2/3)
            assert player.relationship_state == "familiar"

            history = session.query(ConversationMessage).filter_by(
                player_id="victor-1900"
            ).all()
            assert len(history) == 1

    def test_cascade_delete(self, temp_db):
        """Test that deleting a player deletes associated messages."""
        # Create player with messages
        with temp_db.get_session() as session:
            player = PlayerProfile(
                player_id="wendy-2000",
                player_name="Wendy",
            )
            session.add(player)
            session.commit()

        with temp_db.get_session() as session:
            for i in range(3):
                message = ConversationMessage(
                    player_id="wendy-2000",
                    speaker="chess_master",
                    content=f"Message {i}",
                )
                session.add(message)
            session.commit()

        # Verify messages exist
        with temp_db.get_session() as session:
            count = session.query(ConversationMessage).filter_by(
                player_id="wendy-2000"
            ).count()
            assert count == 3

        # Delete player
        with temp_db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id="wendy-2000"
            ).first()
            session.delete(player)
            session.commit()

        # Verify messages are gone
        with temp_db.get_session() as session:
            count = session.query(ConversationMessage).filter_by(
                player_id="wendy-2000"
            ).count()
            assert count == 0
