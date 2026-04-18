"""
Tests for Subconscious memory agent.

Tests cover:
- Memory querying and retrieval
- Filtering out already-given and recently-created memories
- Memory selection based on relevance
- TTL-based memory tracking expiration
- Statistics tracking
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from agent.subconscious import Subconscious


@pytest.fixture
def mock_memory_client():
    """Create a mock Weaviate client."""
    mock = AsyncMock()
    mock.retrieve = AsyncMock()
    return mock


@pytest.fixture
def subconscious(mock_memory_client):
    """Create a Subconscious agent with mock memory client."""
    agent = Subconscious(
        memory_client=mock_memory_client,
        recently_given_memory_ttl=300,
        recently_created_memory_ttl=600,
    )
    return agent


class TestSubconsciousInitialization:
    """Test subconscious agent initialization."""

    def test_init_default(self):
        """Test default initialization."""
        agent = Subconscious()
        assert agent.memory_client is None
        assert len(agent.recently_given_memory_ids) == 0
        assert len(agent.recently_created_memory_ids) == 0
        assert agent.search_count == 0

    def test_init_with_memory_client(self, mock_memory_client):
        """Test initialization with memory client."""
        agent = Subconscious(memory_client=mock_memory_client)
        assert agent.memory_client == mock_memory_client

    def test_init_custom_ttl(self):
        """Test initialization with custom TTL."""
        agent = Subconscious(
            recently_given_memory_ttl=100,
            recently_created_memory_ttl=200,
        )
        assert agent.recently_given_memory_ttl == 100
        assert agent.recently_created_memory_ttl == 200


class TestSearchQueryBuilding:
    """Test search query construction."""

    def test_build_search_query_from_user_input(self, subconscious):
        """Test query building from user input."""
        query = subconscious._build_search_query(user_input="I want to play aggressive")
        assert "aggressive" in query
        assert "want to play" in query

    def test_build_search_query_from_game_context(self, subconscious):
        """Test query building from game context."""
        context = {
            "move": "e2-e4",
            "position": "mid-game",
            "difficulty": "hard",
        }
        query = subconscious._build_search_query(game_context=context)
        assert "e2-e4" in query
        assert "mid-game" in query
        assert "hard" in query

    def test_build_search_query_combined(self, subconscious):
        """Test query building with all sources."""
        context = {"move": "Nf3"}
        query = subconscious._build_search_query(
            user_input="that's interesting",
            game_context=context,
            trigger_point="on_move",
        )
        assert "interesting" in query
        assert "Nf3" in query
        assert "on_move" in query

    def test_build_search_query_empty(self, subconscious):
        """Test query building with no input."""
        query = subconscious._build_search_query()
        assert len(query) > 0
        assert "chess" in query.lower()


class TestMemoryFiltering:
    """Test memory filtering logic."""

    def test_filter_memories_no_filtering(self, subconscious):
        """Test filtering when nothing should be filtered."""
        memories = [
            {"id": "mem-1", "content": "Alice likes the Sicilian", "distance": 0.2},
            {"id": "mem-2", "content": "Bob plays aggressively", "distance": 0.3},
        ]

        filtered = subconscious._filter_memories(memories)

        assert len(filtered) == 2

    def test_filter_memories_recently_given(self, subconscious):
        """Test filtering out recently-given memories."""
        subconscious.recently_given_memory_ids["mem-1"] = datetime.now()

        memories = [
            {"id": "mem-1", "content": "Alice likes the Sicilian", "distance": 0.2},
            {"id": "mem-2", "content": "Bob plays aggressively", "distance": 0.3},
        ]

        filtered = subconscious._filter_memories(memories)

        assert len(filtered) == 1
        assert filtered[0]["id"] == "mem-2"

    def test_filter_memories_recently_created(self, subconscious):
        """Test filtering out recently-created memories."""
        subconscious.recently_created_memory_ids["mem-2"] = datetime.now()

        memories = [
            {"id": "mem-1", "content": "Alice likes the Sicilian", "distance": 0.2},
            {"id": "mem-2", "content": "Bob plays aggressively", "distance": 0.3},
        ]

        filtered = subconscious._filter_memories(memories)

        assert len(filtered) == 1
        assert filtered[0]["id"] == "mem-1"

    def test_filter_memories_both_types(self, subconscious):
        """Test filtering with both recently-given and recently-created."""
        subconscious.recently_given_memory_ids["mem-1"] = datetime.now()
        subconscious.recently_created_memory_ids["mem-3"] = datetime.now()

        memories = [
            {"id": "mem-1", "content": "Alice likes the Sicilian", "distance": 0.2},
            {"id": "mem-2", "content": "Bob plays aggressively", "distance": 0.3},
            {"id": "mem-3", "content": "Charlie just joined", "distance": 0.4},
        ]

        filtered = subconscious._filter_memories(memories)

        assert len(filtered) == 1
        assert filtered[0]["id"] == "mem-2"


class TestMemorySelection:
    """Test memory selection logic."""

    def test_select_memories_empty(self, subconscious):
        """Test selecting from empty list."""
        selected = subconscious._select_memories([])
        assert selected == []

    def test_select_memories_top_n(self, subconscious):
        """Test selecting top N memories by relevance."""
        memories = [
            {"id": "mem-1", "content": "Most relevant", "distance": 0.1},
            {"id": "mem-2", "content": "Middle", "distance": 0.5},
            {"id": "mem-3", "content": "Least relevant", "distance": 0.9},
            {"id": "mem-4", "content": "Also good", "distance": 0.2},
        ]

        selected = subconscious._select_memories(memories, max_count=2)

        assert len(selected) == 2
        assert selected[0]["id"] == "mem-1"  # Lowest distance
        assert selected[1]["id"] == "mem-4"  # Second lowest

    def test_select_memories_less_than_max(self, subconscious):
        """Test selecting when fewer memories than max."""
        memories = [
            {"id": "mem-1", "content": "Only one", "distance": 0.5},
        ]

        selected = subconscious._select_memories(memories, max_count=3)

        assert len(selected) == 1


class TestMemoryQuerying:
    """Test memory query execution."""

    @pytest.mark.asyncio
    async def test_query_memories_basic(self, subconscious, mock_memory_client):
        """Test basic memory querying."""
        mock_memories = [
            {"id": "mem-1", "content": "Test memory", "distance": 0.2},
        ]
        mock_memory_client.retrieve.return_value = mock_memories

        results = await subconscious.query_memories("test query")

        assert len(results) == 1
        assert results[0]["content"] == "Test memory"
        mock_memory_client.retrieve.assert_called_once()
        assert subconscious.search_count == 1

    @pytest.mark.asyncio
    async def test_query_memories_with_player_filter(self, subconscious, mock_memory_client):
        """Test querying with player ID filter."""
        mock_memory_client.retrieve.return_value = []

        await subconscious.query_memories(
            "test query", player_id="player-123", limit=5
        )

        # Verify player_id was passed
        call_kwargs = mock_memory_client.retrieve.call_args[1]
        assert call_kwargs["related_player_id"] == "player-123"
        assert call_kwargs["limit"] == 5

    @pytest.mark.asyncio
    async def test_query_memories_no_client(self):
        """Test querying when no memory client available."""
        agent = Subconscious(memory_client=None)
        results = await agent.query_memories("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_query_memories_error_handling(self, subconscious, mock_memory_client):
        """Test error handling in memory queries."""
        mock_memory_client.retrieve.side_effect = Exception("Network error")

        results = await subconscious.query_memories("test query")

        assert results == []


class TestMemoryTracking:
    """Test memory tracking and TTL."""

    @pytest.mark.asyncio
    async def test_provide_memories(self, subconscious):
        """Test marking memories as provided."""
        memory_ids = ["mem-1", "mem-2"]
        await subconscious.provide_memories(memory_ids)

        assert "mem-1" in subconscious.recently_given_memory_ids
        assert "mem-2" in subconscious.recently_given_memory_ids

    @pytest.mark.asyncio
    async def test_save_created_memory(self, subconscious):
        """Test tracking newly created memories."""
        await subconscious.save_created_memory("mem-new")

        assert "mem-new" in subconscious.recently_created_memory_ids

    def test_clean_expired_memories_given(self, subconscious):
        """Test expiration of recently-given memories."""
        # Add a memory with old timestamp
        old_time = datetime.now() - timedelta(seconds=400)
        subconscious.recently_given_memory_ids["mem-old"] = old_time
        subconscious.recently_given_memory_ids["mem-new"] = datetime.now()

        subconscious._clean_expired_memories()

        # Old one should be removed (TTL is 300 seconds)
        assert "mem-old" not in subconscious.recently_given_memory_ids
        assert "mem-new" in subconscious.recently_given_memory_ids

    def test_clean_expired_memories_created(self, subconscious):
        """Test expiration of recently-created memories."""
        # Add a memory with old timestamp
        old_time = datetime.now() - timedelta(seconds=700)
        subconscious.recently_created_memory_ids["mem-old"] = old_time
        subconscious.recently_created_memory_ids["mem-new"] = datetime.now()

        subconscious._clean_expired_memories()

        # Old one should be removed (TTL is 600 seconds)
        assert "mem-old" not in subconscious.recently_created_memory_ids
        assert "mem-new" in subconscious.recently_created_memory_ids


class TestFullMemoryProcess:
    """Test full memory retrieval and filtering process."""

    @pytest.mark.asyncio
    async def test_process_returns_relevant_memories(self, subconscious, mock_memory_client):
        """Test full process returns relevant, filtered memories."""
        mock_memories = [
            {"id": "mem-1", "content": "Most relevant", "distance": 0.1},
            {"id": "mem-2", "content": "Also relevant", "distance": 0.2},
            {"id": "mem-3", "content": "Less relevant", "distance": 0.8},
        ]
        mock_memory_client.retrieve.return_value = mock_memories

        result = await subconscious.process(
            player_id="player-1",
            user_input="How should I play?",
            game_context={"move": "e4"},
        )

        # Should return top 3 (selected by relevance), no filtering applied
        assert len(result) <= 3
        assert any(m["id"] == "mem-1" for m in result)

    @pytest.mark.asyncio
    async def test_process_filters_recently_given(self, subconscious, mock_memory_client):
        """Test process filters out recently-given memories."""
        # Mark a memory as recently given
        subconscious.recently_given_memory_ids["mem-1"] = datetime.now()

        mock_memories = [
            {"id": "mem-1", "content": "Recently given", "distance": 0.1},
            {"id": "mem-2", "content": "Fresh memory", "distance": 0.2},
        ]
        mock_memory_client.retrieve.return_value = mock_memories

        result = await subconscious.process(player_id="player-1", user_input="Hello")

        # mem-1 should be filtered out
        assert not any(m["id"] == "mem-1" for m in result)

    @pytest.mark.asyncio
    async def test_process_no_memory_client(self):
        """Test process with no memory client available."""
        agent = Subconscious(memory_client=None)
        result = await agent.process(player_id="player-1", user_input="Hello")
        assert result == []


class TestSubconsciousStatistics:
    """Test statistics tracking."""

    def test_get_stats(self, subconscious):
        """Test getting statistics."""
        subconscious.search_count = 5
        subconscious.memory_provided_count = 10
        subconscious.recently_given_memory_ids["mem-1"] = datetime.now()
        subconscious.recently_created_memory_ids["mem-2"] = datetime.now()

        stats = subconscious.get_stats()

        assert stats["search_count"] == 5
        assert stats["memory_provided_count"] == 10
        assert stats["recently_given_count"] == 1
        assert stats["recently_created_count"] == 1
