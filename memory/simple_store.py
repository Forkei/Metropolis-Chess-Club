"""
In-process vector store — drop-in replacement for WeaviateClient.

Requires no external service. Uses sentence-transformers for embeddings and
numpy for cosine similarity. Lore memories are loaded from the markdown file
at startup and are always included in search results regardless of player_id
filters. Player-specific memories are persisted to a JSON file.
"""

import asyncio
import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from memory.schemas import MemoryType

logger = logging.getLogger(__name__)

# Map lore-file type strings to MemoryType enum values.
# The enum values are already lowercase strings, so direct construction works
# for well-formed entries; this explicit map covers any aliases.
_LORE_TYPE_MAP: Dict[str, MemoryType] = {
    "lore": MemoryType.LORE,
    "emotional": MemoryType.EMOTIONAL,
    "streak": MemoryType.STREAK,
    "personal_note": MemoryType.PERSONAL_NOTE,
    "pattern": MemoryType.PATTERN,
    "player_behavior": MemoryType.PLAYER_BEHAVIOR,
    "player_observation": MemoryType.PLAYER_OBSERVATION,
    "game_context": MemoryType.GAME_CONTEXT,
}


class _MemoryEntry:
    """Internal record holding a single memory and its embedding."""

    __slots__ = (
        "id",
        "content",
        "memory_type",
        "related_player_id",
        "metadata",
        "timestamp",
        "created_by",
        "embedding",  # unit-normalised numpy vector (float32)
    )

    def __init__(
        self,
        *,
        id: str,
        content: str,
        memory_type: MemoryType,
        related_player_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        timestamp: datetime,
        created_by: str,
        embedding: np.ndarray,
    ) -> None:
        self.id = id
        self.content = content
        self.memory_type = memory_type
        self.related_player_id = related_player_id
        self.metadata = metadata
        self.timestamp = timestamp
        self.created_by = created_by
        self.embedding = embedding

    def to_result(self, distance: float) -> Dict[str, Any]:
        """Return caller-facing dict with the standard keys."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "distance": distance,
            "metadata": self.metadata or {},
            "related_player_id": self.related_player_id,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dict (for dynamic_memories.json)."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "related_player_id": self.related_player_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "created_by": self.created_by,
            "embedding": self.embedding.tolist(),
        }

    @classmethod
    def from_json_dict(cls, data: Dict[str, Any]) -> "_MemoryEntry":
        """Deserialise from a JSON dict (loaded from dynamic_memories.json)."""
        embedding = np.array(data["embedding"], dtype=np.float32)
        embedding = _normalise(embedding)
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            related_player_id=data.get("related_player_id"),
            metadata=data.get("metadata"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            created_by=data.get("created_by", "main_agent"),
            embedding=embedding,
        )


def _normalise(vec: np.ndarray) -> np.ndarray:
    """Return a unit-normalised copy of *vec* (float32)."""
    vec = vec.astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0.0:
        vec = vec / norm
    return vec


class SimpleVectorStore:
    """
    In-process semantic memory store — drop-in replacement for WeaviateClient.

    Public interface:
        await store(content, memory_type, related_player_id, metadata) -> str
        await retrieve(query, related_player_id, limit, memory_types) -> List[Dict]

    Lore memories (related_player_id=None) are always returned in searches,
    regardless of any player_id filter.  Player memories are only returned
    when their player_id matches the filter (or no filter is applied).

    The ``distance`` field equals ``1.0 - cosine_similarity``; lower is better.
    """

    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        lore_file: str = "./data/chess_master_lore.md",
        dynamic_file: str = "./data/dynamic_memories.json",
        embedding_model: str = EMBEDDING_MODEL,
        max_workers: int = 2,
    ) -> None:
        """
        Initialise the store.

        Args:
            lore_file:       Path to the Chess Master lore markdown file.
            dynamic_file:    Path where runtime memories are persisted as JSON.
            embedding_model: HuggingFace sentence-transformers model name.
            max_workers:     Thread-pool size used for embedding operations.
        """
        self.lore_path = Path(lore_file)
        self.dynamic_path = Path(dynamic_file)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="svs-embed")

        logger.info("Loading embedding model: %s", embedding_model)
        self._model = SentenceTransformer(embedding_model)

        # Two separate lists make player-id filtering cheap.
        self._lore_memories: List[_MemoryEntry] = []
        self._dynamic_memories: List[_MemoryEntry] = []

        self._load_lore()
        self._load_dynamic_memories()

        logger.info(
            "SimpleVectorStore ready — %d lore + %d dynamic memories",
            len(self._lore_memories),
            len(self._dynamic_memories),
        )

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def store(
        self,
        content: str,
        memory_type: MemoryType,
        related_player_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        created_by: str = "main_agent",
    ) -> str:
        """
        Embed and persist a new memory.

        Args:
            content:           The memory text.
            memory_type:       Category tag.
            related_player_id: Player this memory belongs to (or None for global).
            metadata:          Arbitrary key/value context.
            timestamp:         Creation time; defaults to now.
            created_by:        Originating agent label.

        Returns:
            UUID string of the stored memory.
        """
        if not content or not content.strip():
            raise ValueError("Memory content must not be empty.")

        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(self._executor, self._embed, content)

        entry = _MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=memory_type,
            related_player_id=related_player_id,
            metadata=metadata,
            timestamp=timestamp or datetime.now(),
            created_by=created_by,
            embedding=embedding,
        )

        self._dynamic_memories.append(entry)
        self._persist_dynamic_memories()

        logger.info("Stored memory %s (type=%s, player=%s)", entry.id, memory_type.value, related_player_id)
        return entry.id

    async def retrieve(
        self,
        query: str,
        related_player_id: Optional[str] = None,
        limit: int = 5,
        memory_types: Optional[List[MemoryType]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over stored memories.

        Lore memories (related_player_id=None) are always candidates.
        Player memories are included only when their player_id matches
        ``related_player_id``, or when ``related_player_id`` is None.

        Args:
            query:             Natural-language search string.
            related_player_id: Restrict player memories to this player.
            limit:             Maximum number of results to return.
            memory_types:      Optional allow-list of MemoryType values.

        Returns:
            List of memory dicts sorted by distance ascending (best first).
            Each dict has: id, content, memory_type, distance, metadata,
            related_player_id, timestamp.
        """
        if not query or not query.strip():
            return []

        loop = asyncio.get_running_loop()
        query_vec = await loop.run_in_executor(self._executor, self._embed, query)

        candidates = self._gather_candidates(related_player_id, memory_types)
        if not candidates:
            return []

        # Stack all embeddings for a single batched dot product.
        matrix = np.stack([e.embedding for e in candidates])  # (N, D)
        similarities = matrix @ query_vec  # cosine similarity (vectors are unit-norm)
        distances = 1.0 - similarities

        # Sort ascending by distance and take top-N.
        order = np.argsort(distances)[:limit]

        results = [candidates[i].to_result(float(distances[i])) for i in order]
        logger.debug("Retrieved %d/%d memories for query '%s…'", len(results), len(candidates), query[:40])
        return results

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_lore(self) -> None:
        """Parse the lore markdown file and embed all entries."""
        if not self.lore_path.exists():
            logger.warning("Lore file not found: %s", self.lore_path)
            return

        logger.info("Parsing lore file: %s", self.lore_path)
        raw = self.lore_path.read_text(encoding="utf-8")
        blocks = re.split(r"^## Memory \d+:", raw, flags=re.MULTILINE)

        parsed_blocks = [self._parse_lore_block(b) for b in blocks[1:]]
        valid = [p for p in parsed_blocks if p is not None]

        # Batch-embed all lore content at once — much faster than one-by-one
        if valid:
            texts = [p["content"] for p in valid]
            vectors = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            for p, vec in zip(valid, vectors):
                entry = _MemoryEntry(
                    id=str(uuid.uuid4()),
                    content=p["content"],
                    memory_type=p["memory_type"],
                    related_player_id=None,
                    metadata=p.get("metadata"),
                    timestamp=p["timestamp"],
                    created_by="lore_seed",
                    embedding=_normalise(np.array(vec, dtype=np.float32)),
                )
                self._lore_memories.append(entry)

        logger.info("Loaded %d lore memories", len(self._lore_memories))

    def _load_dynamic_memories(self) -> None:
        """Load previously persisted dynamic memories from JSON."""
        if not self.dynamic_path.exists():
            logger.info("No dynamic memories file found at %s — starting fresh.", self.dynamic_path)
            return

        try:
            data = json.loads(self.dynamic_path.read_text(encoding="utf-8"))
            for record in data:
                try:
                    self._dynamic_memories.append(_MemoryEntry.from_json_dict(record))
                except Exception as exc:
                    logger.warning("Skipping malformed dynamic memory record: %s", exc)
            logger.info("Loaded %d dynamic memories from %s", len(self._dynamic_memories), self.dynamic_path)
        except Exception as exc:
            logger.error("Failed to load dynamic memories: %s", exc)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_dynamic_memories(self) -> None:
        """Write all dynamic memories to JSON, atomically via a temp file."""
        self.dynamic_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.dynamic_path.with_suffix(".tmp")
        payload = json.dumps(
            [m.to_json_dict() for m in self._dynamic_memories],
            ensure_ascii=False,
            indent=2,
        )
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(self.dynamic_path)

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def _gather_candidates(
        self,
        related_player_id: Optional[str],
        memory_types: Optional[List[MemoryType]],
    ) -> List[_MemoryEntry]:
        """
        Collect the candidate memories for a search.

        Lore memories are always included.
        Dynamic memories are included when:
          - related_player_id is None (no filter), OR
          - the memory's player_id matches the filter.
        """
        type_set = set(memory_types) if memory_types else None

        def _type_ok(entry: _MemoryEntry) -> bool:
            return type_set is None or entry.memory_type in type_set

        # All lore that passes the type filter.
        candidates: List[_MemoryEntry] = [e for e in self._lore_memories if _type_ok(e)]

        # Dynamic memories: apply both player and type filters.
        for entry in self._dynamic_memories:
            if not _type_ok(entry):
                continue
            if related_player_id is None or entry.related_player_id == related_player_id:
                candidates.append(entry)

        return candidates

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        """Encode *text* and return a unit-normalised float32 vector."""
        vec = self._model.encode(text, convert_to_numpy=True)
        return _normalise(np.array(vec, dtype=np.float32))

    # ------------------------------------------------------------------
    # Lore parsing
    # ------------------------------------------------------------------

    def _parse_lore_block(self, block: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single ``## Memory N: ...`` block from the lore file.

        Returns a dict with keys ``content``, ``memory_type``, ``timestamp``,
        and optionally ``metadata``, or None if the block is invalid.
        """
        result: Dict[str, Any] = {}

        for line in block.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            stripped = stripped[2:]  # Drop "- "

            if stripped.startswith("Type: "):
                type_str = stripped[len("Type: "):].strip().lower()
                memory_type = _LORE_TYPE_MAP.get(type_str)
                if memory_type is None:
                    try:
                        memory_type = MemoryType(type_str)
                    except ValueError:
                        logger.warning("Unknown memory type in lore: %r", type_str)
                        return None
                result["memory_type"] = memory_type

            elif stripped.startswith("Timestamp: "):
                ts_str = stripped[len("Timestamp: "):].strip()
                try:
                    result["timestamp"] = datetime.fromisoformat(ts_str)
                except ValueError:
                    logger.warning("Invalid timestamp in lore: %r", ts_str)
                    return None

            elif stripped.startswith("Content: "):
                content = stripped[len("Content: "):].strip()
                # Strip surrounding quotes if present.
                if len(content) >= 2 and content[0] == '"' and content[-1] == '"':
                    content = content[1:-1]
                result["content"] = content

            elif stripped.startswith("Metadata: "):
                metadata_str = stripped[len("Metadata: "):].strip()
                result["metadata"] = self._parse_metadata_str(metadata_str)

        if "content" not in result or "memory_type" not in result:
            return None
        if "timestamp" not in result:
            result["timestamp"] = datetime.now()

        return result

    @staticmethod
    def _parse_metadata_str(metadata_str: str) -> Dict[str, str]:
        """
        Parse a ``key=value, key2=value2`` metadata string.

        Values may be quoted with double-quotes; quotes are stripped.
        """
        metadata: Dict[str, str] = {}
        for pair in metadata_str.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, _, value = pair.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
            if key:
                metadata[key] = value
        return metadata

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return a summary of the current store state."""
        return {
            "lore_memory_count": len(self._lore_memories),
            "dynamic_memory_count": len(self._dynamic_memories),
            "total_memory_count": len(self._lore_memories) + len(self._dynamic_memories),
            "embedding_model": self.EMBEDDING_MODEL,
            "dynamic_file": str(self.dynamic_path),
        }


__all__ = ["SimpleVectorStore"]
