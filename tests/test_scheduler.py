"""
Tests for MatchScheduler event-driven trigger system.

Tests cover:
- Trigger dispatching and main agent integration
- Idle monitoring with APScheduler
- Conversation history tracking
- Subconscious memory integration
- Match lifecycle (start, idle checks, end)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from agent.scheduler import MatchScheduler, TriggerPoint


@pytest.fixture
def mock_main_agent():
    """Create a mock main agent."""
    mock = AsyncMock()
    mock.respond = AsyncMock()
    return mock


@pytest.fixture
def mock_subconscious():
    """Create a mock subconscious agent."""
    mock = AsyncMock()
    mock.process = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def scheduler(mock_main_agent, mock_subconscious):
    """Create a scheduler with mock agents."""
    return MatchScheduler(
        match_id="match-1",
        player_id="player-1",
        main_agent=mock_main_agent,
        subconscious_agent=mock_subconscious,
    )


class TestSchedulerInitialization:
    """Test scheduler initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        scheduler = MatchScheduler(match_id="m1", player_id="p1")
        assert scheduler.match_id == "m1"
        assert scheduler.player_id == "p1"
        assert scheduler.main_agent is None
        assert len(scheduler.conversation_history) == 0

    def test_init_with_agents(self, mock_main_agent, mock_subconscious):
        """Test initialization with agents."""
        scheduler = MatchScheduler(
            match_id="m1",
            player_id="p1",
            main_agent=mock_main_agent,
            subconscious_agent=mock_subconscious,
        )
        assert scheduler.main_agent == mock_main_agent
        assert scheduler.subconscious_agent == mock_subconscious


class TestTriggerDispatch:
    """Test trigger dispatching."""

    @pytest.mark.asyncio
    async def test_trigger_before_match(self, scheduler, mock_main_agent):
        """Test before_match trigger."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Welcome!",
            "tone": "warm",
        }

        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)

        assert response["action"] == "send_message"
        assert response["content"] == "Welcome!"
        mock_main_agent.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_on_user_input(self, scheduler, mock_main_agent):
        """Test on_user_input trigger."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Noted.",
            "tone": "sharp",
        }

        context = {"user_input": "I want to play aggressive"}
        response = await scheduler.trigger(TriggerPoint.ON_USER_INPUT, context)

        assert response["action"] == "send_message"
        assert response["content"] == "Noted."

    @pytest.mark.asyncio
    async def test_trigger_on_user_move(self, scheduler, mock_main_agent):
        """Test on_user_move trigger."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Interesting move.",
        }

        context = {"move": "e2-e4"}
        response = await scheduler.trigger(TriggerPoint.ON_USER_MOVE, context)

        assert response["action"] == "send_message"

    @pytest.mark.asyncio
    async def test_trigger_no_main_agent(self):
        """Test trigger fails gracefully without main agent."""
        scheduler = MatchScheduler(match_id="m1", player_id="p1")
        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        assert response is None

    @pytest.mark.asyncio
    async def test_trigger_records_history(self, scheduler, mock_main_agent):
        """Test that triggers are recorded in history."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Test",
        }

        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        await scheduler.trigger(TriggerPoint.ON_USER_INPUT, {"user_input": "Hi"})

        assert len(scheduler.trigger_history) == 2
        assert scheduler.trigger_history[0]["trigger_point"] == "before_match"
        assert scheduler.trigger_history[1]["trigger_point"] == "on_user_input"

    @pytest.mark.asyncio
    async def test_trigger_records_conversation(self, scheduler, mock_main_agent):
        """Test that messages are recorded in conversation history."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Hello there!",
            "tone": "warm",
        }

        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)

        assert len(scheduler.conversation_history) == 1
        assert scheduler.conversation_history[0]["content"] == "Hello there!"
        assert scheduler.conversation_history[0]["speaker"] == "chess_master"


class TestSubconsciousIntegration:
    """Test integration with subconscious agent."""

    @pytest.mark.asyncio
    async def test_subconscious_retrieves_memories(
        self, scheduler, mock_main_agent, mock_subconscious
    ):
        """Test that subconscious is called to retrieve memories."""
        mock_memories = [
            {"id": "mem-1", "content": "Player likes the Sicilian"}
        ]
        mock_subconscious.process.return_value = mock_memories

        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "I remember you like the Sicilian.",
        }

        await scheduler.trigger(
            TriggerPoint.ON_USER_INPUT,
            {"user_input": "Let's play again"},
        )

        # Verify subconscious was called
        mock_subconscious.process.assert_called_once()
        call_kwargs = mock_subconscious.process.call_args[1]
        assert call_kwargs["player_id"] == "player-1"

    @pytest.mark.asyncio
    async def test_subconscious_error_handled(
        self, scheduler, mock_main_agent, mock_subconscious
    ):
        """Test that subconscious errors are handled gracefully."""
        mock_subconscious.process.side_effect = Exception("DB error")
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Let's play.",
        }

        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)

        # Should still work
        assert response["action"] == "send_message"


class TestIdleMonitoring:
    """Test idle monitoring functionality."""

    @pytest.mark.asyncio
    async def test_start_idle_monitoring(self, scheduler):
        """Test starting idle monitoring."""
        await scheduler.start_idle_monitoring(check_interval_seconds=600)

        assert scheduler.idle_monitoring_active
        assert scheduler.scheduler is not None

        await scheduler.stop_idle_monitoring()

    @pytest.mark.asyncio
    async def test_idle_check_not_idle(self, scheduler, mock_main_agent):
        """Test idle check when user is not idle."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Still here?",
        }

        scheduler.last_user_activity = datetime.now()

        await scheduler._check_idle(idle_threshold_seconds=60)

        mock_main_agent.respond.assert_not_called()

    @pytest.mark.asyncio
    async def test_idle_check_is_idle(self, scheduler, mock_main_agent):
        """Test idle check when user is idle."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Still here?",
        }

        scheduler.last_user_activity = datetime.now() - timedelta(seconds=40)

        await scheduler._check_idle(idle_threshold_seconds=30)

        mock_main_agent.respond.assert_called_once()
        call_args = mock_main_agent.respond.call_args
        assert "idle_seconds" in call_args[1]["context_data"]

    @pytest.mark.asyncio
    async def test_stop_idle_monitoring(self, scheduler):
        """Test stopping idle monitoring."""
        await scheduler.start_idle_monitoring(check_interval_seconds=600)
        assert scheduler.idle_monitoring_active

        await scheduler.stop_idle_monitoring()
        assert not scheduler.idle_monitoring_active


class TestMatchLifecycle:
    """Test match lifecycle (start, during, end)."""

    def test_start_match(self, scheduler):
        """Test starting a match."""
        scheduler.start_match()

        assert scheduler.match_start_time is not None
        assert scheduler.last_user_activity is not None

    @pytest.mark.asyncio
    async def test_end_match(self, scheduler, mock_main_agent):
        """Test ending a match fires AFTER_MATCH trigger."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Good game!",
        }

        scheduler.start_match()
        response = await scheduler.end_match()

        assert response is not None
        assert len(scheduler.trigger_history) >= 1

    @pytest.mark.asyncio
    async def test_end_match_without_start(self, scheduler, mock_main_agent):
        """Test ending match that wasn't started still fires trigger."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Game ended.",
        }

        response = await scheduler.end_match()

        assert response is not None


class TestHistoryTracking:
    """Test conversation and trigger history tracking."""

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, scheduler, mock_main_agent):
        """Test retrieving conversation history."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Message 1",
        }

        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)

        history = scheduler.get_conversation_history()

        assert len(history) == 1
        assert history[0]["content"] == "Message 1"
        assert history[0]["speaker"] == "chess_master"

    @pytest.mark.asyncio
    async def test_get_trigger_history(self, scheduler, mock_main_agent):
        """Test retrieving trigger history."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Message",
        }

        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        await scheduler.trigger(TriggerPoint.ON_USER_INPUT)

        history = scheduler.get_trigger_history()

        assert len(history) == 2
        assert history[0]["trigger_point"] == TriggerPoint.BEFORE_MATCH
        assert history[1]["trigger_point"] == TriggerPoint.ON_USER_INPUT

    @pytest.mark.asyncio
    async def test_only_send_message_actions_recorded(self, scheduler, mock_main_agent):
        """Test that only send_message actions are recorded in conversation."""
        # Return a non-message action
        mock_main_agent.respond.return_value = {
            "action": "set_emotion",
            "metadata": {"emotion": "excited"},
        }

        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)

        # Should not add to conversation history
        assert len(scheduler.conversation_history) == 0


class TestSchedulerStatistics:
    """Test statistics and reporting."""

    def test_get_stats(self, scheduler):
        """Test getting scheduler statistics."""
        scheduler.start_match()

        stats = scheduler.get_stats()

        assert stats["match_id"] == "match-1"
        assert stats["player_id"] == "player-1"
        assert stats["duration_seconds"] is not None
        assert stats["idle_monitoring_active"] == False

    @pytest.mark.asyncio
    async def test_get_stats_with_activity(self, scheduler, mock_main_agent):
        """Test statistics with activity."""
        mock_main_agent.respond.return_value = {
            "action": "send_message",
            "content": "Hello",
        }

        scheduler.start_match()
        await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
        await scheduler.trigger(TriggerPoint.ON_USER_INPUT)

        stats = scheduler.get_stats()

        assert stats["trigger_count"] == 2
        assert stats["conversation_count"] == 2


class TestDefaultInputGeneration:
    """Test default input generation for trigger points."""

    def test_default_input_before_match(self, scheduler):
        """Test default input for before_match is contextual."""
        input_text = scheduler._get_default_input(TriggerPoint.BEFORE_MATCH)
        # Should be non-empty and contextual (play/challenge/see/ready)
        assert len(input_text) > 0
        assert any(word in input_text.lower() for word in ["play", "challenge", "see", "ready"])

    def test_default_input_on_user_move(self, scheduler):
        """Test default input for on_user_move."""
        input_text = scheduler._get_default_input(TriggerPoint.ON_USER_MOVE)
        assert "move" in input_text.lower()

    def test_default_input_idle_wait(self, scheduler):
        """Test default input for idle_wait is contextual."""
        input_text = scheduler._get_default_input(TriggerPoint.IDLE_WAIT)
        # Should be non-empty and show patience or engagement
        assert len(input_text) > 0
        assert any(word in input_text.lower() for word in ["time", "patient", "ready", "move"])

    def test_default_input_after_match(self, scheduler):
        """Test default input for after_match."""
        input_text = scheduler._get_default_input(TriggerPoint.AFTER_MATCH)
        assert "play" in input_text.lower() or "played" in input_text.lower()
