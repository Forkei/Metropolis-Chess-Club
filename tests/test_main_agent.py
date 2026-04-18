"""
Tests for ChessMaster main agent.

Tests cover:
- Agent initialization
- Response generation with player context
- JSON response parsing
- Action execution (send_message, save_memory, set_emotion, stop)
- Memory retrieval and integration
- Conversation history saving
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agent.main_agent import ChessMaster
from db import DatabaseManager, PlayerProfile, save_conversation_message


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chess_club.db"
        db_url = f"sqlite:///{db_path}"

        manager = DatabaseManager(db_url)
        manager.initialize()

        yield manager

        manager.close()


@pytest.fixture
def test_player(temp_db):
    """Create a test player in the database."""
    with temp_db.get_session() as session:
        player = PlayerProfile(
            player_id="test-player-1",
            player_name="TestPlayer",
            estimated_elo=1400,
            preferred_difficulty="intermediate",
        )
        session.add(player)
        session.commit()

    # Set global database manager
    import db.database as db_module
    old_manager = db_module._db_manager
    db_module._db_manager = temp_db
    yield player
    db_module._db_manager = old_manager


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    mock = AsyncMock()
    mock.respond = AsyncMock()
    return mock


@pytest.fixture
def chess_master(mock_api_client):
    """Create a ChessMaster instance with mocked API client."""
    agent = ChessMaster(api_provider="gemini", memory_client=None)
    agent.api_client = mock_api_client
    return agent


class TestChessMasterInitialization:
    """Test ChessMaster agent initialization."""

    def test_init_default(self):
        """Test default initialization."""
        agent = ChessMaster()
        assert agent.api_client is not None
        assert agent.memory_client is None
        assert agent.emotion_state == "neutral"
        assert agent.last_response_time is None

    def test_init_with_memory_client(self):
        """Test initialization with memory client."""
        mock_memory = MagicMock()  # Don't specify spec since WeaviateClient may not be available
        agent = ChessMaster(api_provider="gemini", memory_client=mock_memory)
        assert agent.memory_client == mock_memory

    def test_init_with_custom_model(self):
        """Test initialization with custom model."""
        agent = ChessMaster(api_provider="gemini", model="gemini-1.5-flash")
        assert agent.api_client is not None


class TestSystemPromptGeneration:
    """Test system prompt generation."""

    def test_build_system_prompt_new_player(self, chess_master):
        """Test system prompt for new player."""
        player = PlayerProfile(
            player_id="new-player",
            player_name="NewPlayer",
            total_games=0,
            estimated_elo=1400,
            relationship_state="new",
        )

        prompt = chess_master._build_system_prompt(player)

        assert "Viktor Petrov" in prompt
        assert "NewPlayer" in prompt
        assert "new" in prompt
        assert "JSON" in prompt
        assert "send_message" in prompt

    def test_build_system_prompt_rival(self, chess_master):
        """Test system prompt for rival player."""
        player = PlayerProfile(
            player_id="rival-player",
            player_name="Rival",
            total_games=10,
            wins_against_agent=5,
            estimated_elo=1600,
            relationship_state="rival",
        )

        prompt = chess_master._build_system_prompt(player)

        assert "Rival" in prompt
        assert "rival" in prompt
        assert "1600" in prompt
        assert "50.0%" in prompt  # win rate


class TestResponseParsing:
    """Test JSON response parsing."""

    def test_parse_valid_json_response(self, chess_master):
        """Test parsing valid JSON response."""
        response = json.dumps({
            "thinking": "The player is asking for advice.",
            "action": "send_message",
            "content": "Your position is weak.",
            "tone": "analytical",
            "metadata": {"emotion": "focused"},
        })

        parsed = chess_master._parse_agent_response(response)

        assert parsed["action"] == "send_message"
        assert parsed["content"] == "Your position is weak."
        assert parsed["tone"] == "analytical"
        assert parsed["metadata"]["emotion"] == "focused"

    def test_parse_json_with_markdown_code_block(self, chess_master):
        """Test parsing JSON from markdown code block."""
        response = """Here's my response:
```json
{
    "thinking": "Analyzing the position",
    "action": "send_message",
    "content": "That was a brilliant move.",
    "tone": "warm"
}
```
"""

        parsed = chess_master._parse_agent_response(response)

        assert parsed["action"] == "send_message"
        assert parsed["content"] == "That was a brilliant move."
        assert parsed["tone"] == "warm"

    def test_parse_json_defaults(self, chess_master):
        """Test that parsing adds default values."""
        response = '{"content": "Hello"}'

        parsed = chess_master._parse_agent_response(response)

        assert parsed["action"] == "send_message"
        assert parsed["tone"] == "neutral"
        assert "metadata" in parsed

    def test_parse_invalid_json(self, chess_master):
        """Test parsing invalid JSON returns safe defaults."""
        response = "This is not JSON at all"

        parsed = chess_master._parse_agent_response(response)

        assert parsed["action"] == "stop"
        assert "Error" in parsed["content"]


class TestUserPromptBuilding:
    """Test user prompt construction."""

    def test_build_user_prompt_basic(self, chess_master, test_player):
        """Test basic user prompt building."""
        prompt = chess_master._build_user_prompt(
            input_text="I want to play again",
            player=test_player,
            memory_context={"memories": [], "conversation_history": []},
        )

        assert "I want to play again" in prompt
        assert "TestPlayer" in prompt

    def test_build_user_prompt_with_history(self, chess_master, test_player):
        """Test user prompt with conversation history."""
        memory_context = {
            "memories": [],
            "conversation_history": [
                {"speaker": "chess_master", "content": "Welcome back.", "timestamp": None},
                {"speaker": "player", "content": "Let's play", "timestamp": None},
            ],
        }

        prompt = chess_master._build_user_prompt(
            input_text="I'm ready",
            player=test_player,
            memory_context=memory_context,
        )

        assert "# Conversation History" in prompt
        assert "Welcome back" in prompt

    def test_build_user_prompt_with_context_data(self, chess_master, test_player):
        """Test user prompt with game context."""
        context_data = {
            "game_state": "mid-game",
            "move": "e2-e4",
            "event": "game_started",
        }

        prompt = chess_master._build_user_prompt(
            input_text="Your move",
            player=test_player,
            memory_context={"memories": [], "conversation_history": []},
            context_data=context_data,
        )

        assert "Context" in prompt
        assert "e2-e4" in prompt


class TestActionExecution:
    """Test action execution."""

    @pytest.mark.asyncio
    async def test_execute_send_message_action(self, chess_master):
        """Test executing send_message action."""
        parsed_response = {
            "action": "send_message",
            "content": "Your move.",
            "tone": "sharp",
            "metadata": {},
        }

        result = await chess_master._execute_action(
            player_id="test-player-1",
            parsed_response=parsed_response,
        )

        assert result["action"] == "send_message"
        assert result["content"] == "Your move."
        assert result["tone"] == "sharp"

    @pytest.mark.asyncio
    async def test_execute_set_emotion_action(self, chess_master):
        """Test executing set_emotion action."""
        parsed_response = {
            "action": "set_emotion",
            "metadata": {"emotion": "excited"},
        }

        result = await chess_master._execute_action(
            player_id="test-player-1",
            parsed_response=parsed_response,
        )

        assert result["action"] == "emotion_changed"
        assert result["emotion"] == "excited"
        assert chess_master.emotion_state == "excited"

    @pytest.mark.asyncio
    async def test_execute_stop_action(self, chess_master):
        """Test executing stop action."""
        parsed_response = {
            "action": "stop",
            "metadata": {"reason": "player_disconnected"},
        }

        result = await chess_master._execute_action(
            player_id="test-player-1",
            parsed_response=parsed_response,
        )

        assert result["action"] == "stop"
        assert result["reason"] == "player_disconnected"

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, chess_master):
        """Test executing unknown action defaults to send_message."""
        parsed_response = {
            "action": "unknown_action",
            "content": "Fallback response",
        }

        result = await chess_master._execute_action(
            player_id="test-player-1",
            parsed_response=parsed_response,
        )

        assert result["action"] == "send_message"
        assert result["content"] == "Fallback response"


class TestMemoryRetrieval:
    """Test memory context retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_context_without_history(self, chess_master, test_player):
        """Test retrieving context when there's no history."""
        context = await chess_master._retrieve_context("test-player-1")

        assert "memories" in context
        assert "conversation_history" in context
        assert isinstance(context["memories"], list)
        assert isinstance(context["conversation_history"], list)

    @pytest.mark.asyncio
    async def test_retrieve_context_with_history(self, chess_master, test_player):
        """Test retrieving context with conversation history."""
        # Save some messages
        save_conversation_message(
            player_id="test-player-1",
            speaker="chess_master",
            content="Hello, welcome back.",
        )
        save_conversation_message(
            player_id="test-player-1",
            speaker="player",
            content="Thanks! I'm ready to play.",
        )

        context = await chess_master._retrieve_context("test-player-1")

        assert len(context["conversation_history"]) == 2
        assert context["conversation_history"][0]["content"] == "Hello, welcome back."


class TestFullResponseGeneration:
    """Test full response generation flow."""

    @pytest.mark.asyncio
    async def test_respond_success(self, chess_master, test_player, mock_api_client):
        """Test successful response generation."""
        # Mock API response
        api_response = json.dumps({
            "thinking": "Player is new, so I'll be respectful",
            "action": "send_message",
            "content": "Welcome to the board.",
            "tone": "warm",
            "metadata": {},
        })
        mock_api_client.respond.return_value = api_response

        result = await chess_master.respond(
            player_id="test-player-1",
            input_text="I want to play",
        )

        assert result["action"] == "send_message"
        assert result["content"] == "Welcome to the board."
        assert result["tone"] == "warm"
        assert chess_master.last_response_time is not None

    @pytest.mark.asyncio
    async def test_respond_missing_player(self, chess_master):
        """Test response when player doesn't exist."""
        result = await chess_master.respond(
            player_id="nonexistent-player",
            input_text="Hello",
        )

        assert result["action"] == "stop"
        assert result["error"] is True

    @pytest.mark.asyncio
    async def test_respond_api_error(self, chess_master, test_player, mock_api_client):
        """Test response when API call fails."""
        mock_api_client.respond.side_effect = Exception("API Error")

        result = await chess_master.respond(
            player_id="test-player-1",
            input_text="Hello",
        )

        assert result["action"] == "stop"
        assert result["error"] is True


class TestAgentStatus:
    """Test agent status reporting."""

    def test_get_status(self, chess_master):
        """Test getting agent status."""
        status = chess_master.get_status()

        assert "emotion" in status
        assert "last_response" in status
        assert "api_provider" in status
        assert status["emotion"] == "neutral"
        assert status["last_response"] is None

    def test_get_status_after_response(self, chess_master):
        """Test status after changing emotion."""
        chess_master.emotion_state = "excited"
        chess_master.last_response_time = datetime.now()

        status = chess_master.get_status()

        assert status["emotion"] == "excited"
        assert status["last_response"] is not None
