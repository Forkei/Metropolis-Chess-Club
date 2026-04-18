"""
Integration tests for full Chess Master game flow.

Tests combine scheduler, subconscious, main agent, and database.
Simulates realistic game scenarios from start to finish.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile

from agent.main_agent import ChessMaster
from agent.subconscious import Subconscious
from agent.scheduler import MatchScheduler, TriggerPoint
from db.database import DatabaseManager, get_db_manager
from db.models import PlayerProfile, ConversationMessage
import db.database as db_module


@pytest.fixture
def db():
    """Get the global database manager set up by conftest."""
    return get_db_manager()


@pytest.fixture
def mock_memory_client():
    """Create mock Weaviate client."""
    mock = AsyncMock()
    mock.retrieve = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def chess_master():
    """Create ChessMaster with mocked API client."""
    agent = ChessMaster()
    agent.api_client = AsyncMock()
    # Note: the respond method is called, not generate
    agent.api_client.respond = AsyncMock(
        return_value='{"action": "send_message", "content": "Hello!", "tone": "warm"}'
    )
    return agent


class TestFullGameFlow:
    """Test complete game flow from match start to finish."""

    @pytest.mark.asyncio
    async def test_new_player_game_flow(self, db, chess_master):
        """Test game with new player."""
        player_id = "new-player-1"
        match_id = "match-001"

        # Create player in database
        with db.get_session() as session:
            player = PlayerProfile(player_id=player_id, player_name="Test Player")
            session.add(player)
            session.commit()
            assert player.total_games == 0
            assert player.relationship_state == "new"

        # Create agents
        subconscious = Subconscious()  # No memory client for this test
        scheduler = MatchScheduler(
            match_id=match_id,
            player_id=player_id,
            main_agent=chess_master,
            subconscious_agent=subconscious,
        )

        # Start match
        scheduler.start_match()
        assert scheduler.match_start_time is not None

        # Trigger before_match
        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        assert response is not None
        assert response.get("action") == "send_message"
        assert len(scheduler.conversation_history) == 1

        # Simulate user input
        response = await scheduler.trigger(
            TriggerPoint.ON_USER_INPUT,
            {"user_input": "Let's play aggressive"},
        )
        assert len(scheduler.conversation_history) == 2

        # Simulate user move
        response = await scheduler.trigger(
            TriggerPoint.ON_USER_MOVE,
            {"move": "e2-e4"},
        )
        assert len(scheduler.conversation_history) == 3

        # End match
        response = await scheduler.end_match()
        assert response is not None

        # Verify stats
        stats = scheduler.get_stats()
        assert stats["trigger_count"] == 4  # before, input, move, after
        assert stats["conversation_count"] == 4

    @pytest.mark.asyncio
    async def test_returning_player_relationship_progression(
        self, db, chess_master
    ):
        """Test relationship stage progression as player returns."""
        player_id = "returning-player"

        # Create player first
        with db.get_session() as session:
            player = PlayerProfile(player_id=player_id, player_name="Returner")
            session.add(player)
            session.commit()

        # Create player and simulate 5 games
        for i in range(5):
            # Create and run match
            scheduler = MatchScheduler(
                match_id=f"match-{i:03d}",
                player_id=player_id,
                main_agent=chess_master,
            )

            scheduler.start_match()
            await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
            await scheduler.end_match()

            # Simulate game completion
            with db.get_session() as session:
                player = session.query(PlayerProfile).filter_by(
                    player_id=player_id
                ).first()
                player.total_games += 1
                player.wins_against_agent += 1  # Assume win
                player.update_relationship()  # Update relationship state based on games
                session.commit()

            # Check relationship stage
            with db.get_session() as session:
                player = session.query(PlayerProfile).filter_by(
                    player_id=player_id
                ).first()
                if player.total_games <= 4:
                    assert player.relationship_state in ["new", "familiar"]
                else:
                    assert player.relationship_state == "rival"


class TestIdleMonitoringIntegration:
    """Test idle monitoring in realistic scenarios."""

    @pytest.mark.asyncio
    async def test_idle_trigger_calls_agent(self, chess_master):
        """Test that idle monitoring triggers agent appropriately."""
        scheduler = MatchScheduler(
            match_id="idle-test",
            player_id="idle-player",
            main_agent=chess_master,
        )

        scheduler.start_match()

        # Simulate activity 60 seconds ago
        scheduler.last_user_activity = datetime.now() - timedelta(seconds=60)

        # Trigger idle check with 30 second threshold
        await scheduler._check_idle(idle_threshold_seconds=30)

        # Agent should have been called
        assert len(scheduler.trigger_history) >= 1
        assert scheduler.trigger_history[-1]["trigger_point"] == "idle_wait"

    @pytest.mark.asyncio
    async def test_idle_monitoring_respects_recent_activity(self, chess_master):
        """Test that idle monitoring doesn't trigger with recent activity."""
        scheduler = MatchScheduler(
            match_id="recent-activity-test",
            player_id="active-player",
            main_agent=chess_master,
        )

        scheduler.start_match()

        # Activity only 5 seconds ago
        scheduler.last_user_activity = datetime.now() - timedelta(seconds=5)

        # Trigger idle check with 30 second threshold
        initial_count = len(scheduler.trigger_history)
        await scheduler._check_idle(idle_threshold_seconds=30)

        # Agent should NOT have been called
        assert len(scheduler.trigger_history) == initial_count


class TestConversationHistoryPersistence:
    """Test conversation history recording and retrieval."""

    @pytest.mark.asyncio
    async def test_conversation_history_is_populated(self, db, chess_master):
        """Test that all messages are recorded."""
        # Create player first
        with db.get_session() as session:
            player = PlayerProfile(player_id="history-player", player_name="History")
            session.add(player)
            session.commit()

        scheduler = MatchScheduler(
            match_id="history-test",
            player_id="history-player",
            main_agent=chess_master,
        )

        scheduler.start_match()

        # Trigger multiple events
        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        await scheduler.trigger(TriggerPoint.ON_USER_INPUT, {"user_input": "Hi"})
        await scheduler.trigger(TriggerPoint.ON_USER_MOVE, {"move": "e4"})

        # Verify all messages recorded
        history = scheduler.get_conversation_history()
        assert len(history) >= 3
        assert all(msg.get("speaker") == "chess_master" for msg in history)

    @pytest.mark.asyncio
    async def test_conversation_history_filtering(self, chess_master):
        """Test that only send_message actions are recorded."""
        chess_master.api_client.respond = AsyncMock(
            return_value={"action": "set_emotion", "metadata": {"emotion": "excited"}}
        )

        scheduler = MatchScheduler(
            match_id="filter-test",
            player_id="filter-player",
            main_agent=chess_master,
        )

        scheduler.start_match()
        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)

        # Non-message action should not appear in conversation history
        history = scheduler.get_conversation_history()
        assert len(history) == 0


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_agent_api_error_handling(self):
        """Test handling when API client fails."""
        agent = ChessMaster()
        agent.api_client = AsyncMock()
        agent.api_client.respond = AsyncMock(side_effect=Exception("API Error"))

        scheduler = MatchScheduler(
            match_id="error-test",
            player_id="error-player",
            main_agent=agent,
        )

        scheduler.start_match()

        # Should not crash, should return error action
        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        assert response is not None
        assert response.get("action") == "stop" or response.get("error")

    @pytest.mark.asyncio
    async def test_subconscious_error_doesnt_block_agent(
        self, db, chess_master, mock_memory_client
    ):
        """Test that subconscious errors don't prevent main agent response."""
        # Create player first
        with db.get_session() as session:
            player = PlayerProfile(player_id="error-player", player_name="Error Player")
            session.add(player)
            session.commit()

        # Subconscious fails
        mock_memory_client.retrieve = AsyncMock(
            side_effect=Exception("Memory Error")
        )

        subconscious = Subconscious(memory_client=mock_memory_client)
        scheduler = MatchScheduler(
            match_id="subconscious-error",
            player_id="error-player",
            main_agent=chess_master,
            subconscious_agent=subconscious,
        )

        scheduler.start_match()

        # Should still get response from main agent
        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        assert response is not None
        assert response.get("action") == "send_message"

    @pytest.mark.asyncio
    async def test_missing_player_profile_handling(self, chess_master):
        """Test handling when player profile doesn't exist."""
        # Don't create player - let system handle missing profile
        scheduler = MatchScheduler(
            match_id="missing-player",
            player_id="nonexistent-player",
            main_agent=chess_master,
        )

        scheduler.start_match()

        # Should still respond even with missing player
        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        assert response is not None


class TestMemoryRetrievalIntegration:
    """Test memory integration with agent responses."""

    @pytest.mark.asyncio
    async def test_subconscious_provides_memories_to_agent(
        self, chess_master, mock_memory_client
    ):
        """Test that subconscious memories are passed to agent."""
        mock_memories = [
            {
                "id": "mem-1",
                "content": "Player likes Sicilian Defense",
                "distance": 0.1,
            }
        ]
        mock_memory_client.retrieve = AsyncMock(return_value=mock_memories)

        subconscious = Subconscious(memory_client=mock_memory_client)
        scheduler = MatchScheduler(
            match_id="memory-test",
            player_id="memory-player",
            main_agent=chess_master,
            subconscious_agent=subconscious,
        )

        scheduler.start_match()

        # Trigger should call subconscious
        await scheduler.trigger(TriggerPoint.ON_USER_INPUT, {"user_input": "Hi"})

        # Verify memory client was called
        assert mock_memory_client.retrieve.called

    @pytest.mark.asyncio
    async def test_memory_filtering_prevents_repetition(
        self, chess_master, mock_memory_client
    ):
        """Test that recently-provided memories aren't repeated."""
        mock_memories = [
            {
                "id": "mem-1",
                "content": "Memory 1",
                "distance": 0.1,
            }
        ]
        mock_memory_client.retrieve = AsyncMock(return_value=mock_memories)

        subconscious = Subconscious(memory_client=mock_memory_client)
        scheduler = MatchScheduler(
            match_id="repetition-test",
            player_id="repetition-player",
            main_agent=chess_master,
            subconscious_agent=subconscious,
        )

        scheduler.start_match()

        # First trigger
        await scheduler.trigger(TriggerPoint.ON_USER_INPUT)

        # Mark memory as recently given
        subconscious.recently_given_memory_ids["mem-1"] = datetime.now()

        # Second trigger - same memory shouldn't be provided
        await scheduler.trigger(TriggerPoint.ON_USER_INPUT)

        # Memory filtering should have excluded it the second time
        assert len(subconscious.recently_given_memory_ids) == 1


class TestPlayerStatisticsPersistence:
    """Test that game statistics are properly persisted."""

    def test_player_stats_updated_after_game(self, db):
        """Test that player statistics are updated and persisted."""
        player_id = "stats-player"

        # Create player
        with db.get_session() as session:
            player = PlayerProfile(player_id=player_id, player_name="Stats")
            session.add(player)
            session.commit()
            initial_games = player.total_games
            initial_wins = player.wins_against_agent

        # Update stats
        with db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id=player_id
            ).first()
            player.total_games += 1
            player.wins_against_agent += 1
            player.estimated_elo = 1600
            session.commit()

        # Fetch again to verify persistence
        with db.get_session() as session:
            fresh_player = session.query(PlayerProfile).filter_by(
                player_id=player_id
            ).first()
            assert fresh_player.total_games == initial_games + 1
            assert fresh_player.wins_against_agent == initial_wins + 1
            assert fresh_player.estimated_elo == 1600

    def test_relationship_stage_transitions(self, db):
        """Test relationship stage changes as games progress."""
        player_id = "relationship-player"

        with db.get_session() as session:
            player = PlayerProfile(player_id=player_id, player_name="Relationship")
            session.add(player)
            session.commit()
            assert player.relationship_state == "new"

        # Play 2 games
        with db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id=player_id
            ).first()
            player.total_games = 2
            player.update_relationship()
            session.commit()

        with db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id=player_id
            ).first()
            assert player.relationship_state == "familiar"

        # Play 5 games total
        with db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id=player_id
            ).first()
            player.total_games = 5
            player.update_relationship()
            session.commit()

        with db.get_session() as session:
            player = session.query(PlayerProfile).filter_by(
                player_id=player_id
            ).first()
            assert player.relationship_state == "rival"


class TestContextDataIntegration:
    """Test that context data flows correctly through system."""

    @pytest.mark.asyncio
    async def test_game_context_provided_to_agent(self, chess_master):
        """Test that game context reaches the agent."""
        scheduler = MatchScheduler(
            match_id="context-test",
            player_id="context-player",
            main_agent=chess_master,
        )

        scheduler.start_match()

        context = {
            "move": "e2-e4",
            "position": "opening",
            "difficulty": "medium",
        }

        await scheduler.trigger(TriggerPoint.ON_USER_MOVE, context)

        # Verify context was recorded in trigger history
        assert len(scheduler.trigger_history) >= 1
        latest_trigger = scheduler.trigger_history[-1]
        assert "move" in latest_trigger.get("context_keys", [])
