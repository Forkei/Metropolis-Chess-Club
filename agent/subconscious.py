"""
Subconscious Agent - Memory manager.

Runs every turn, fast. Decides which memories from the vector DB are relevant
and provides them to the main Chess Master before it responds.

Flow:
1. Analyze current context (game state, user input, etc)
2. Query vector DB for relevant memories
3. Filter out: already-given memories, recently-created memories
4. Decide: which memories would help the Chess Master right now?
5. If useful memories found, provide them. Otherwise, provide none.

The subconscious can iterate: search → search → search → provide or search → provide → search.
It's not linear; it follows its own judgment.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class Subconscious:
    """
    Memory manager for the Chess Master.

    Responsibilities:
    - Retrieve relevant memories from vector database
    - Filter memories to avoid repetition and staleness
    - Decide which memories would be useful for the main agent
    - Track recently-given and recently-created memories
    """

    def __init__(
        self,
        memory_client=None,
        recently_given_memory_ttl: int = 300,  # 5 minutes
        recently_created_memory_ttl: int = 600,  # 10 minutes
    ):
        """
        Initialize subconscious agent.

        Args:
            memory_client: Weaviate client for memory retrieval
            recently_given_memory_ttl: TTL for recently-given memories (seconds)
            recently_created_memory_ttl: TTL for recently-created memories (seconds)
        """
        self.memory_client = memory_client
        self.recently_given_memory_ids: Dict[str, datetime] = {}
        self.recently_created_memory_ids: Dict[str, datetime] = {}
        self.recently_given_memory_ttl = recently_given_memory_ttl
        self.recently_created_memory_ttl = recently_created_memory_ttl
        self.search_count = 0
        self.memory_provided_count = 0

    def _clean_expired_memories(self) -> None:
        """Remove expired entries from recently-given and recently-created."""
        now = datetime.now()

        # Clean recently_given
        expired = [
            mid
            for mid, timestamp in self.recently_given_memory_ids.items()
            if (now - timestamp).total_seconds() > self.recently_given_memory_ttl
        ]
        for mid in expired:
            del self.recently_given_memory_ids[mid]

        # Clean recently_created
        expired = [
            mid
            for mid, timestamp in self.recently_created_memory_ids.items()
            if (now - timestamp).total_seconds() > self.recently_created_memory_ttl
        ]
        for mid in expired:
            del self.recently_created_memory_ids[mid]

    async def process(
        self,
        player_id: str,
        game_context: Optional[Dict[str, Any]] = None,
        user_input: Optional[str] = None,
        trigger_point: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze context and decide which memories to provide to the main agent.

        Args:
            player_id: ID of the player
            game_context: Optional game state information
            user_input: Optional user message/action
            trigger_point: When this is being called (before_match, on_move, etc.)

        Returns:
            List of relevant memory dicts, or empty list if none are useful
        """
        if not self.memory_client:
            logger.debug("Memory client not available")
            return []

        # Clean expired memory tracking
        self._clean_expired_memories()

        # Build search query from context
        search_query = self._build_search_query(
            user_input=user_input,
            game_context=game_context,
            trigger_point=trigger_point,
        )

        logger.debug(f"[SUBCONSCIOUS] query={search_query!r}")

        try:
            # Query memories
            memories = await self.query_memories(
                query=search_query,
                player_id=player_id,
                limit=10,
            )

            # Filter out already-given and recently-created memories
            filtered_memories = self._filter_memories(memories)

            # Select the most relevant ones
            selected = self._select_memories(filtered_memories)

            # Track which memories we're providing.
            # Only suppress player-specific memories (related_player_id set) —
            # lore memories (related_player_id=None) rotate naturally via semantic
            # distance and shouldn't be exhausted by the suppression window.
            for memory in selected:
                if memory.get("related_player_id"):
                    self.recently_given_memory_ids[memory["id"]] = datetime.now()

            self.memory_provided_count += len(selected)
            logger.debug(f"[SUBCONSCIOUS] surfacing {len(selected)} memories:")
            for m in selected:
                logger.debug(f"  dist={m['distance']:.3f} type={m['memory_type']} player={m.get('related_player_id')} | {m['content'][:90]}")

            return selected

        except Exception as e:
            logger.error(f"Error retrieving memories: {e}", exc_info=True)
            return []

    def _build_search_query(
        self,
        user_input: Optional[str] = None,
        game_context: Optional[Dict[str, Any]] = None,
        trigger_point: Optional[str] = None,
    ) -> str:
        """
        Build a semantic search query from context.

        Args:
            user_input: User's message or action
            game_context: Game state info
            trigger_point: When this was called

        Returns:
            Search query string
        """
        parts = []

        if user_input:
            parts.append(user_input)

        if game_context:
            if "move" in game_context:
                parts.append(f"move {game_context['move']}")
            if "game_phase" in game_context:
                parts.append(game_context['game_phase'])
            if "opening" in game_context and game_context['opening']:
                parts.append(game_context['opening'])
            # Include a short slice of position analysis for semantic richness
            if "position_analysis" in game_context and game_context['position_analysis']:
                parts.append(game_context['position_analysis'][:120])
            if "position" in game_context:
                parts.append(f"position {game_context['position']}")
            if "difficulty" in game_context:
                parts.append(f"difficulty {game_context['difficulty']}")

        if trigger_point:
            parts.append(f"at {trigger_point}")

        query = " ".join(parts) if parts else "chess game context"
        return query

    async def query_memories(
        self,
        query: str,
        player_id: Optional[str] = None,
        limit: int = 10,
        memory_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the vector DB for semantically similar memories.

        Args:
            query: What to search for
            player_id: Optional filter by player ID
            limit: Max number of results
            memory_types: Optional filter by memory type

        Returns:
            List of matching memories
        """
        if not self.memory_client:
            return []

        try:
            self.search_count += 1

            # Build memory type filter if provided
            memory_type_enum_list = None
            if memory_types:
                try:
                    from memory.schemas import MemoryType

                    memory_type_enum_list = [
                        MemoryType(mt) if isinstance(mt, str) else mt
                        for mt in memory_types
                    ]
                except Exception as e:
                    logger.warning(f"Failed to parse memory types: {e}")

            # Query Weaviate
            memories = await self.memory_client.retrieve(
                query=query,
                related_player_id=player_id,
                limit=limit,
                memory_types=memory_type_enum_list,
            )

            logger.debug(f"Found {len(memories)} matching memories")
            return memories

        except Exception as e:
            logger.error(f"Error querying memories: {e}")
            return []

    def _filter_memories(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out already-given and recently-created memories.

        Args:
            memories: Raw memories from database

        Returns:
            Filtered list
        """
        filtered = []
        for memory in memories:
            memory_id = memory.get("id")

            # Skip if recently given
            if memory_id in self.recently_given_memory_ids:
                logger.debug(f"Skipping recently-given memory: {memory_id}")
                continue

            # Skip if recently created
            if memory_id in self.recently_created_memory_ids:
                logger.debug(f"Skipping recently-created memory: {memory_id}")
                continue

            filtered.append(memory)

        return filtered

    def _select_memories(
        self, memories: List[Dict[str, Any]], max_count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Select the most relevant memories to provide.

        Simple strategy: take the top N by similarity score, prefer recent ones.

        Args:
            memories: Filtered memories
            max_count: Maximum number to select

        Returns:
            Selected memories
        """
        if not memories:
            return []

        # Sort by similarity (distance) - lower is better
        sorted_memories = sorted(
            memories, key=lambda m: m.get("distance", float("inf"))
        )

        # Return top N
        return sorted_memories[:max_count]

    async def provide_memories(
        self,
        memory_ids: List[str],
    ) -> None:
        """
        Mark these memories as "given to main agent" so we don't repeat them.

        Called after main agent has consumed the memories.

        Args:
            memory_ids: IDs of memories being provided
        """
        for memory_id in memory_ids:
            self.recently_given_memory_ids[memory_id] = datetime.now()

        logger.debug(f"Marked {len(memory_ids)} memories as recently given")

    async def save_created_memory(self, memory_id: str) -> None:
        """
        Track that a memory was just created, so we don't immediately re-provide it.

        Args:
            memory_id: ID of the newly created memory
        """
        self.recently_created_memory_ids[memory_id] = datetime.now()
        logger.debug(f"Tracked newly created memory: {memory_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get subconscious statistics."""
        return {
            "search_count": self.search_count,
            "memory_provided_count": self.memory_provided_count,
            "recently_given_count": len(self.recently_given_memory_ids),
            "recently_created_count": len(self.recently_created_memory_ids),
        }


__all__ = ["Subconscious"]
