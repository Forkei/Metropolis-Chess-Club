"""
Weaviate vector database client for Chess Master memories.

Handles:
- Embedded Weaviate initialization (Python in-process)
- Memory storage with semantic embeddings
- Semantic search with filtering
- Lore seeding from data/chess_master_lore.md
"""

import uuid
import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from sentence_transformers import SentenceTransformer

from memory.schemas import Memory, MemoryType

logger = logging.getLogger(__name__)


class WeaviateClient:
    """
    Weaviate vector database client for Chess Master memories.

    Handles:
    - Embedded Weaviate initialization
    - Memory embedding and storage
    - Semantic search with optional filtering
    - Lore seeding
    """

    MEMORY_CLASS = "ChessMasterMemory"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    def __init__(
        self,
        path: str = "./weaviate_data",
        embedding_model: str = EMBEDDING_MODEL,
    ):
        """
        Initialize Weaviate client with embedded instance.

        Args:
            path: Directory for Weaviate data persistence
            embedding_model: HuggingFace sentence-transformer model name
        """
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing embedded Weaviate at {self.path}")

        # Initialize embedded Weaviate
        self.client = weaviate.connect_to_local(
            host="localhost",
            port=6789,
            skip_init_checks=False,
        )

        logger.info("Connected to Weaviate")

        # Initialize embedding model (local)
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)

        # Create schema if needed
        self._create_schema()

        self.memory_count = 0
        self.search_count = 0

    def _create_schema(self) -> None:
        """Create Weaviate schema for memories if it doesn't exist."""
        # Check if class already exists
        if self.client.collections.exists(self.MEMORY_CLASS):
            logger.info(f"Schema {self.MEMORY_CLASS} already exists")
            return

        logger.info(f"Creating schema {self.MEMORY_CLASS}")

        # Create the collection with properties
        self.client.collections.create(
            name=self.MEMORY_CLASS,
            properties=[
                Property(
                    name="content",
                    data_type=DataType.TEXT,
                    description="The memory content (what gets embedded)",
                    skip_vectorization=False,  # Will be vectorized
                ),
                Property(
                    name="timestamp",
                    data_type=DataType.DATE,
                    description="When the memory was created",
                ),
                Property(
                    name="memory_type",
                    data_type=DataType.TEXT,
                    description="Category: lore, personal_note, emotional, pattern, streak, player_behavior, player_observation, game_context",
                ),
                Property(
                    name="related_match_id",
                    data_type=DataType.TEXT,
                    description="Associated chess match ID if any",
                ),
                Property(
                    name="related_player_id",
                    data_type=DataType.TEXT,
                    description="Associated player ID if any",
                ),
                Property(
                    name="created_by",
                    data_type=DataType.TEXT,
                    description="Agent that created this memory",
                ),
                Property(
                    name="metadata_json",
                    data_type=DataType.TEXT,
                    description="Additional metadata as JSON string",
                ),
            ],
            # We'll handle vectorization client-side
            vectorizer_config=Configure.Vectorizer.none(),
        )

        logger.info(f"Schema {self.MEMORY_CLASS} created successfully")

    async def store(
        self,
        content: str,
        memory_type: MemoryType,
        timestamp: Optional[datetime] = None,
        related_match_id: Optional[str] = None,
        related_player_id: Optional[str] = None,
        created_by: str = "main_agent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a memory in Weaviate with embedding.

        Args:
            content: The memory text (what gets embedded)
            memory_type: Category of memory
            timestamp: When the memory was created (defaults to now)
            related_match_id: Optional chess match ID
            related_player_id: Optional player ID
            created_by: Which agent created this
            metadata: Additional context

        Returns:
            UUID of the stored memory
        """
        memory_id = str(uuid.uuid4())
        timestamp = timestamp or datetime.now()

        # Embed the content
        logger.debug(f"Embedding memory: {content[:50]}...")
        embedding = self.embedding_model.encode(content).tolist()

        # Prepare object for Weaviate
        obj = {
            "content": content,
            "timestamp": timestamp.isoformat(),
            "memory_type": memory_type.value,
            "related_match_id": related_match_id,
            "related_player_id": related_player_id,
            "created_by": created_by,
            "metadata_json": self._serialize_metadata(metadata),
        }

        # Store in Weaviate with vector
        collection = self.client.collections.get(self.MEMORY_CLASS)
        collection.data.insert(
            properties=obj,
            vector=embedding,
            uuid=memory_id,
        )

        self.memory_count += 1
        logger.info(f"Stored memory {memory_id}: {content[:50]}...")

        return memory_id

    async def retrieve(
        self,
        query: str,
        limit: int = 5,
        memory_types: Optional[List[MemoryType]] = None,
        related_player_id: Optional[str] = None,
        date_after: Optional[datetime] = None,
        date_before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories via semantic search with optional filtering.

        Args:
            query: What to search for (will be embedded)
            limit: Max number of results
            memory_types: Optional filter by memory type
            related_player_id: Optional filter by player ID
            date_after: Optional filter by date range (after)
            date_before: Optional filter by date range (before)

        Returns:
            List of memory dicts with id, content, type, timestamp, etc.
        """
        self.search_count += 1

        # Embed the query
        logger.debug(f"Searching for: {query}")
        query_embedding = self.embedding_model.encode(query).tolist()

        # Build where filter if needed
        where_filter = None
        if memory_types or related_player_id or date_after or date_before:
            where_filter = self._build_where_filter(
                memory_types,
                related_player_id,
                date_after,
                date_before,
            )

        # Query Weaviate
        collection = self.client.collections.get(self.MEMORY_CLASS)
        results = collection.query.near_vector(
            near_vector=query_embedding,
            limit=limit,
            where=where_filter,
            return_properties=["content", "timestamp", "memory_type", "related_player_id", "metadata_json"],
        )

        # Format results
        memories = []
        for item in results.objects:
            memory = {
                "id": item.uuid,
                "content": item.properties["content"],
                "timestamp": item.properties["timestamp"],
                "memory_type": item.properties["memory_type"],
                "related_player_id": item.properties.get("related_player_id"),
                "distance": item.metadata.distance,  # Similarity score
            }
            memories.append(memory)

        logger.info(f"Retrieved {len(memories)} memories for query: {query}")
        return memories

    def _build_where_filter(
        self,
        memory_types: Optional[List[MemoryType]] = None,
        related_player_id: Optional[str] = None,
        date_after: Optional[datetime] = None,
        date_before: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build Weaviate where filter for optional constraints."""
        conditions = []

        if memory_types:
            type_values = [t.value for t in memory_types]
            conditions.append({
                "path": ["memory_type"],
                "operator": "ContainsAny",
                "valueText": type_values,
            })

        if related_player_id:
            conditions.append({
                "path": ["related_player_id"],
                "operator": "Equal",
                "valueText": related_player_id,
            })

        if date_after:
            conditions.append({
                "path": ["timestamp"],
                "operator": "GreaterOrEqual",
                "valueDate": date_after.isoformat(),
            })

        if date_before:
            conditions.append({
                "path": ["timestamp"],
                "operator": "LessOrEqual",
                "valueDate": date_before.isoformat(),
            })

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        # Multiple conditions: AND them together
        return {
            "operator": "And",
            "operands": conditions,
        }

    async def seed_lore(self, lore_file: str = "data/chess_master_lore.md") -> int:
        """
        Seed Chess Master's lore from markdown file.

        Args:
            lore_file: Path to the lore markdown file

        Returns:
            Number of memories seeded
        """
        lore_path = Path(lore_file)
        if not lore_path.exists():
            logger.warning(f"Lore file not found: {lore_file}")
            return 0

        logger.info(f"Seeding lore from {lore_file}")
        count = 0

        with open(lore_path, "r") as f:
            content = f.read()

        # Parse lore markdown
        # Format: ## Memory X: [Title]
        #         - Type: lore
        #         - Timestamp: YYYY-MM-DD
        #         - Content: "..."
        #         - Metadata: ...

        memory_blocks = re.split(r"^## Memory \d+:", content, flags=re.MULTILINE)

        for block in memory_blocks[1:]:  # Skip header
            try:
                memory_data = self._parse_memory_block(block)
                if memory_data:
                    await self.store(**memory_data)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to seed memory block: {e}")
                continue

        logger.info(f"Seeded {count} lore memories")
        return count

    def _parse_memory_block(self, block: str) -> Optional[Dict[str, Any]]:
        """Parse a single memory block from lore markdown."""
        lines = block.strip().split("\n")

        data = {}
        for line in lines:
            if not line.startswith("-"):
                continue

            line = line[2:].strip()  # Remove "- "

            if line.startswith("Type: "):
                memory_type_str = line.replace("Type: ", "").strip()
                try:
                    data["memory_type"] = MemoryType(memory_type_str)
                except ValueError:
                    return None

            elif line.startswith("Timestamp: "):
                timestamp_str = line.replace("Timestamp: ", "").strip()
                try:
                    data["timestamp"] = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    return None

            elif line.startswith("Content: "):
                content = line.replace("Content: ", "").strip()
                # Remove quotes if present
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                data["content"] = content

            elif line.startswith("Metadata: "):
                metadata_str = line.replace("Metadata: ", "").strip()
                # Parse simple key=value format
                data["metadata"] = self._parse_metadata_str(metadata_str)

        if "content" not in data or "memory_type" not in data:
            return None

        data["created_by"] = "lore_seed"
        return data

    def _parse_metadata_str(self, metadata_str: str) -> Dict[str, str]:
        """Parse metadata string like 'key1=value1, key2=value2'."""
        metadata = {}
        for pair in metadata_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                metadata[key.strip()] = value.strip()
        return metadata

    def _serialize_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        """Serialize metadata dict to string."""
        if not metadata:
            return "{}"
        items = [f"{k}={v}" for k, v in metadata.items()]
        return "{" + ", ".join(items) + "}"

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "memory_count": self.memory_count,
            "search_count": self.search_count,
            "embedding_model": self.EMBEDDING_MODEL,
        }

    def close(self) -> None:
        """Close Weaviate connection."""
        logger.info("Closing Weaviate connection")
        self.client.close()


__all__ = ["WeaviateClient"]
