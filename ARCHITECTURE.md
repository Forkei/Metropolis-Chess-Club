# Architecture & Design Decisions

Deep dive into Chess Master agent system design.

## Multi-Agent System

1. **Main Agent** (Chess Master)
   - Responds to game context and user input
   - Always outputs JSON with action + content
   - Personality-driven responses with optional thinking

2. **Subconscious Agent**
   - Runs every turn before main agent
   - Queries Weaviate for relevant memories
   - Decides which memories to inject to main agent
   - Filters: no recently-given, no recently-created

3. **Scheduler**
   - Coordinates trigger points
   - Manages timing and idle monitoring

4. **Memory Vector Database** (Weaviate)
   - Semantic search over all observations
   - Supports filtering by type, date, metadata

## Trigger Points

- **before_match**: Setup, greet opponent
- **on_user_input**: User sends message/action
- **on_user_move**: After opponent's chess move
- **before_agent_move**: Agent decides action
- **idle_wait**: Periodic check while user thinks
- **after_match**: Reflect, summarize

## Game Context

Passed to agents each turn:

- Match metadata (id, opponent, difficulty, start_time, current_time)
- Game state (status, odds, move count, last N moves with odds delta)
- Match history (previous results, streaks)
- User local time (for context-aware responses)

## Memory Schema

```
id: str
timestamp: datetime
content: str (what gets embedded)
memory_type: MemoryType (category for filtering)
related_match_id: Optional[str]
created_by: str ("main_agent" or "subconscious")
metadata: dict (player_name, difficulty, etc.)
```

Types: player_behavior, player_observation, game_context, personal_note, streak, pattern, emotional

## Main Agent Response (JSON)

```json
{
  "thinking": "Optional",
  "action": "send_message | stop | save_memory | set_emotion",
  "content": "Message or memory content",
  "tone": "playful | sharp | respectful | dismissive",
  "metadata": { "optional": "context" }
}
```

## Subconscious Flow

1. Analyze current context (game state, user behavior)
2. Query Weaviate semantically for relevant memories
3. Filter: remove already-given and recently-created
4. Decide: are these useful? Provide or empty list.
5. Can iterate: search -> search -> provide (any order)

## Implementation Notes

**Weaviate Embedding**: Use local sentence-transformers (all-MiniLM-L6-v2)
**Models**: Claude Opus + Gemini Flash (both support JSON output and tool use)
**Scheduler**: TODO - sync vs async decision

## Next Steps

1. Weaviate client wrapper
2. LLM API wrappers (Claude, Gemini)
3. Main agent response generation
4. Subconscious memory retrieval
5. Scheduler implementation
6. Test suite with synthetic data
7. Iterate on personality

## Questions for Collaborative Iteration

1. **Memory Decay**: Should older memories fade over time?
2. **Subconscious Judgment**: Always decide, or structured fallback rules?
3. **Emotion Display**: JSON field or separate channel?
4. **Match History**: Store full PGN or just summaries?
5. **Multi-Modality (Phase 2+)**: How should agent receive non-text input?
