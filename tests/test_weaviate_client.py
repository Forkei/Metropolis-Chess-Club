"""
Tests for Weaviate vector database client.

Note: Integration tests require Weaviate running. Unit tests below don't require it.
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile

# Import only when needed for integration tests
try:
    from memory.weaviate_client import WeaviateClient
    from memory.schemas import MemoryType
    HAS_WEAVIATE = True
except ImportError:
    HAS_WEAVIATE = False


@pytest.fixture
def temp_weaviate_path():
    """Create temporary directory for Weaviate data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def client(temp_weaviate_path):
    """Create a Weaviate client with temporary storage."""
    if not HAS_WEAVIATE:
        pytest.skip("Weaviate dependencies not available")
    try:
        c = WeaviateClient(path=temp_weaviate_path)
        yield c
        c.close()
    except Exception as e:
        pytest.skip(f"Weaviate not available: {e}")


@pytest.mark.skipif(not HAS_WEAVIATE, reason="Weaviate dependencies not available")
class TestWeaviateClient:
    """Test Weaviate client operations."""

    @pytest.mark.asyncio
    async def test_store_memory(self, client):
        """Test storing a memory."""
        memory_id = await client.store(
            content="Alice plays aggressively",
            memory_type=MemoryType.PLAYER_BEHAVIOR,
            related_player_id="alice-123",
        )

        assert memory_id is not None
        assert len(memory_id) > 0
        assert client.memory_count == 1

    @pytest.mark.asyncio
    async def test_retrieve_memories(self, client):
        """Test retrieving memories via semantic search."""
        # Store some memories
        await client.store(
            content="Alice always plays the Sicilian Defense",
            memory_type=MemoryType.PLAYER_BEHAVIOR,
            related_player_id="alice-123",
        )

        await client.store(
            content="Bob prefers aggressive openings",
            memory_type=MemoryType.PLAYER_BEHAVIOR,
            related_player_id="bob-456",
        )

        # Search
        results = await client.retrieve(
            query="Sicilian openings",
            limit=5,
        )

        assert len(results) > 0
        assert any("Sicilian" in r["content"] for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_with_player_filter(self, client):
        """Test retrieving memories filtered by player."""
        # Store memories for different players
        await client.store(
            content="Alice won 3 games in a row",
            memory_type=MemoryType.STREAK,
            related_player_id="alice-123",
        )

        await client.store(
            content="Bob lost his last game",
            memory_type=MemoryType.STREAK,
            related_player_id="bob-456",
        )

        # Search for Alice's memories
        results = await client.retrieve(
            query="games won",
            related_player_id="alice-123",
            limit=5,
        )

        # Should only get Alice's memory
        assert len(results) > 0
        assert all(r["related_player_id"] == "alice-123" for r in results if r["related_player_id"])

    @pytest.mark.asyncio
    async def test_retrieve_with_type_filter(self, client):
        """Test retrieving memories filtered by type."""
        # Store memories of different types
        await client.store(
            content="Alice plays the Italian Game",
            memory_type=MemoryType.PLAYER_BEHAVIOR,
        )

        await client.store(
            content="I respect players who play creatively",
            memory_type=MemoryType.PERSONAL_NOTE,
        )

        # Search for only player behavior memories
        results = await client.retrieve(
            query="Italian Game",
            memory_types=[MemoryType.PLAYER_BEHAVIOR],
            limit=5,
        )

        assert len(results) > 0
        assert all(r["memory_type"] == "player_behavior" for r in results)

    @pytest.mark.asyncio
    async def test_seed_lore(self, client):
        """Test seeding lore from file."""
        # This test requires the lore file to exist
        lore_file = "data/chess_master_lore.md"
        if not Path(lore_file).exists():
            pytest.skip(f"Lore file not found: {lore_file}")

        count = await client.seed_lore(lore_file)
        assert count > 0
        assert client.memory_count == count

    def test_get_stats(self, client):
        """Test statistics."""
        stats = client.get_stats()
        assert "memory_count" in stats
        assert "search_count" in stats
        assert "embedding_model" in stats

    def test_parse_metadata_str(self, client):
        """Test metadata string parsing."""
        metadata_str = "mentor_name=Viktor, location=Budapest, age=24"
        parsed = client._parse_metadata_str(metadata_str)

        assert parsed["mentor_name"] == "Viktor"
        assert parsed["location"] == "Budapest"
        assert parsed["age"] == "24"

    def test_serialize_metadata(self, client):
        """Test metadata serialization."""
        metadata = {
            "mentor_name": "Mikhail",
            "location": "Minsk",
        }
        serialized = client._serialize_metadata(metadata)
        assert "mentor_name" in serialized
        assert "Mikhail" in serialized


@pytest.mark.skipif(not HAS_WEAVIATE, reason="Weaviate dependencies not available")
class TestWeaviateParsingUnit:
    """Unit tests for parsing functions (no Weaviate required)."""

    def test_parse_metadata_str(self):
        """Test metadata string parsing."""
        client = WeaviateClient.__new__(WeaviateClient)
        metadata_str = "key1=value1, key2=value2"
        parsed = client._parse_metadata_str(metadata_str)

        assert parsed["key1"] == "value1"
        assert parsed["key2"] == "value2"

    def test_serialize_metadata(self):
        """Test metadata serialization."""
        client = WeaviateClient.__new__(WeaviateClient)
        metadata = {"key": "value"}
        serialized = client._serialize_metadata(metadata)

        assert "key" in serialized
        assert "value" in serialized

    def test_serialize_empty_metadata(self):
        """Test serializing empty metadata."""
        client = WeaviateClient.__new__(WeaviateClient)
        serialized = client._serialize_metadata(None)
        assert serialized == "{}"
