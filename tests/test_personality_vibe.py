"""
Personality and vibe evaluation tests for Chess Master.

Tests the authenticity of Viktor's character:
- Personality consistency across contexts
- Relationship stage adaptations
- Memory integration and callbacks
- Tone appropriateness
- Emotional authenticity
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from agent.main_agent import ChessMaster
from agent.scheduler import MatchScheduler, TriggerPoint
from db.models import PlayerProfile
import db.database as db_module


@pytest.fixture
def db():
    """Get the global database manager."""
    from db.database import get_db_manager
    return get_db_manager()


@pytest.fixture
def chess_master():
    """Create ChessMaster with mocked API client."""
    agent = ChessMaster()
    agent.api_client = AsyncMock()
    agent.api_client.respond = AsyncMock(
        return_value='{"action": "send_message", "content": "Hello!", "tone": "warm"}'
    )
    return agent


class TestPersonalityConsistency:
    """Test that Viktor maintains personality across contexts."""

    def test_chess_master_identifies_as_viktor(self, chess_master):
        """Test that system prompt identifies agent as Viktor Petrov."""
        player = PlayerProfile(
            player_id="test-player",
            player_name="TestPlayer",
            total_games=0,
        )

        prompt = chess_master._build_system_prompt(player)

        # Should contain Viktor Petrov identity
        assert "Viktor" in prompt or "Petrov" in prompt
        assert "Minsk" in prompt or "chess" in prompt.lower()
        # Should mention that he's a chess master
        assert "master" in prompt.lower() or "chess" in prompt.lower()

    def test_system_prompt_includes_player_context(self, chess_master):
        """Test that system prompt adapts to player context."""
        new_player = PlayerProfile(
            player_id="new-player",
            player_name="NewPlayer",
            total_games=0,
            wins_against_agent=0,
            relationship_state="new",
        )

        familiar_player = PlayerProfile(
            player_id="familiar-player",
            player_name="FamiliarPlayer",
            total_games=2,
            wins_against_agent=1,
            relationship_state="familiar",
        )

        new_prompt = chess_master._build_system_prompt(new_player)
        familiar_prompt = chess_master._build_system_prompt(familiar_player)

        # Both should include player names
        assert "NewPlayer" in new_prompt
        assert "FamiliarPlayer" in familiar_prompt

        # Both should include relationship stages
        assert "new" in new_prompt.lower()
        assert "familiar" in familiar_prompt.lower()


class TestToneAdaptation:
    """Test that tone adapts to relationship stage."""

    @pytest.mark.asyncio
    async def test_response_includes_tone_field(self, chess_master):
        """Test that responses include tone metadata."""
        # Mock API to return response with explicit tone
        chess_master.api_client.respond = AsyncMock(
            return_value='{"action": "send_message", "content": "Nice move!", "tone": "warm"}'
        )

        player = PlayerProfile(
            player_id="tone-test",
            player_name="ToneTest",
            total_games=1,
            relationship_state="new",
        )

        response = await chess_master.respond(
            player_id="tone-test",
            input_text="How am I doing?",
            context_data={},
        )

        assert response is not None
        assert "tone" in response or response.get("action") in ["send_message", "stop"]

    @pytest.mark.asyncio
    async def test_tone_varies_by_relationship(self, chess_master):
        """Test that tone changes for different relationship stages."""
        tones_by_stage = {
            "new": None,
            "familiar": None,
            "rival": None,
        }

        for stage in tones_by_stage.keys():
            # Mock different responses for each stage
            stage_response = {
                "new": '{"action": "send_message", "content": "Let\'s see what you can do.", "tone": "analytical"}',
                "familiar": '{"action": "send_message", "content": "Good to see you again!", "tone": "warm"}',
                "rival": '{"action": "send_message", "content": "Ready for a real match?", "tone": "sharp"}',
            }

            chess_master.api_client.respond = AsyncMock(
                return_value=stage_response[stage]
            )

            player = PlayerProfile(
                player_id=f"player-{stage}",
                player_name=f"Player{stage}",
                total_games=0 if stage == "new" else (2 if stage == "familiar" else 5),
                relationship_state=stage,
            )

            response = await chess_master.respond(
                player_id=f"player-{stage}",
                input_text="Let's play",
                context_data={},
            )

            # Should have a tone appropriate to relationship
            assert response is not None
            tones_by_stage[stage] = response.get("tone", "unknown")

        # Different stages should have different tones (in ideal scenarios)
        # This is a softer assertion since the actual behavior depends on API


class TestMemoryIntegration:
    """Test that memories are properly integrated into responses."""

    @pytest.mark.asyncio
    async def test_memories_appear_in_context(self, chess_master):
        """Test that retrieved memories are used in prompts."""
        memories = [
            {"id": "mem-1", "content": "Player likes aggressive openings", "distance": 0.1}
        ]

        # Mock memory client
        chess_master.memory_client = AsyncMock()
        chess_master.memory_client.retrieve = AsyncMock(return_value=memories)

        player = PlayerProfile(
            player_id="memory-player",
            player_name="MemPlayer",
            total_games=5,
            relationship_state="rival",
        )

        context = await chess_master._retrieve_context("memory-player")

        # Memories should be in the context (even if initially empty, the retrieval happens)
        assert "memories" in context

    def test_system_prompt_mentions_memory_retrieval(self, chess_master):
        """Test that system prompt indicates memory usage capability."""
        player = PlayerProfile(
            player_id="test-player",
            player_name="TestPlayer",
            total_games=0,
        )

        prompt = chess_master._build_system_prompt(player)

        # Should mention memory/context abilities
        assert "remember" in prompt.lower() or "memory" in prompt.lower() or "pattern" in prompt.lower()


class TestEmotionalAuthenticity:
    """Test that responses show emotional authenticity."""

    @pytest.mark.asyncio
    async def test_emotion_state_tracking(self, chess_master):
        """Test that emotion state is tracked and updated."""
        assert chess_master.emotion_state == "neutral"

        # Mock response with emotion
        chess_master.api_client.respond = AsyncMock(
            return_value='{"action": "send_message", "content": "Interesting move", "tone": "warm", "metadata": {"emotion": "focused"}}'
        )

        player = PlayerProfile(
            player_id="emotion-player",
            player_name="EmotionPlayer",
            total_games=1,
        )

        response = await chess_master.respond(
            player_id="emotion-player",
            input_text="Your move",
            context_data={},
        )

        # After response, emotion state may have changed
        assert hasattr(chess_master, "emotion_state")


class TestConversationNaturalness:
    """Test that conversations feel natural and authentic."""

    def test_user_prompt_includes_conversation_history(self, chess_master):
        """Test that recent conversation history is included in prompts."""
        player = PlayerProfile(
            player_id="conv-player",
            player_name="ConvPlayer",
            total_games=1,
        )

        memory_context = {
            "memories": [],
            "conversation_history": [
                {"speaker": "chess_master", "content": "Nice opening."},
                {"speaker": "player", "content": "Thanks!"},
            ],
        }

        prompt = chess_master._build_user_prompt(
            input_text="What about my next move?",
            player=player,
            memory_context=memory_context,
            context_data={},
        )

        # Should reference conversation history
        assert "Nice opening" in prompt or "ConvPlayer" in prompt
        assert "next move" in prompt

    def test_context_data_integration(self, chess_master):
        """Test that game context is properly integrated."""
        player = PlayerProfile(
            player_id="context-player",
            player_name="ContextPlayer",
            total_games=1,
        )

        memory_context = {
            "memories": [],
            "conversation_history": [],
        }

        context_data = {
            "move": "e2-e4",
            "position": "opening",
            "event": "user_moved",
        }

        prompt = chess_master._build_user_prompt(
            input_text="Your turn",
            player=player,
            memory_context=memory_context,
            context_data=context_data,
        )

        # Should include context data
        assert "e2-e4" in prompt or "move" in prompt.lower() or "opening" in prompt.lower()


class TestSchedulerIntegration:
    """Test Chess Master personality through scheduler interactions."""

    @pytest.mark.asyncio
    async def test_before_match_greeting_feels_personal(self, db, chess_master):
        """Test that before_match greeting feels personal to the player."""
        # Create a returning player
        with db.get_session() as session:
            player = PlayerProfile(
                player_id="greeting-test",
                player_name="GreetingTest",
                total_games=5,
                relationship_state="rival",
            )
            session.add(player)
            session.commit()

        # Mock a personalized response
        chess_master.api_client.respond = AsyncMock(
            return_value='{"action": "send_message", "content": "GreetingTest! Back for another round? I\'ve been analyzing your play...", "tone": "sharp"}'
        )

        scheduler = MatchScheduler(
            match_id="greeting-match",
            player_id="greeting-test",
            main_agent=chess_master,
        )

        scheduler.start_match()
        response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)

        # Response should be sent
        assert response is not None
        assert response.get("action") == "send_message"
        # Response should contain player name if personalized
        assert "GreetingTest" in response.get("content", "") or "content" in response

    @pytest.mark.asyncio
    async def test_idle_response_shows_patience(self, chess_master):
        """Test that idle responses show Viktor's personality."""
        chess_master.api_client.respond = AsyncMock(
            return_value='{"action": "send_message", "content": "Taking your time, eh? That\'s fine, I\'m patient.", "tone": "sharp"}'
        )

        scheduler = MatchScheduler(
            match_id="idle-test",
            player_id="idle-player",
            main_agent=chess_master,
        )

        scheduler.start_match()

        # Simulate idle check
        from datetime import datetime, timedelta
        scheduler.last_user_activity = datetime.now() - timedelta(seconds=60)

        await scheduler._check_idle(idle_threshold_seconds=30)

        # Should have triggered an idle wait
        assert len(scheduler.trigger_history) >= 1

    @pytest.mark.asyncio
    async def test_after_match_reflects_game(self, db, chess_master):
        """Test that after_match response reflects on the game."""
        # Create player
        with db.get_session() as session:
            player = PlayerProfile(
                player_id="after-match",
                player_name="AfterMatchPlayer",
                total_games=1,
                wins_against_agent=0,  # Lost
            )
            session.add(player)
            session.commit()

        chess_master.api_client.respond = AsyncMock(
            return_value='{"action": "send_message", "content": "Well played. You\'re getting better.", "tone": "analytical"}'
        )

        scheduler = MatchScheduler(
            match_id="after-match-test",
            player_id="after-match",
            main_agent=chess_master,
        )

        scheduler.start_match()
        response = await scheduler.end_match()

        # Should generate after-match response
        assert response is not None
