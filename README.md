# Metropolis Chess Club

An agentic chess character system for the virtual city Metropolis.

The Chess Master is a sophisticated yet sharp-tongued player who runs the Chess Club, engaging visitors with personality, pattern recognition, and genuine competition. This is Phase 1: building the agent and memory system (no chess engine yet).

## Project Vision

**Phase 1 (Current)**: Agent system with memory, relationships, and personality
- Build the Chess Master character agent (Gemini 3.1 Flash Lite)
- Implement memory vector database (Weaviate) with semantic search
- Create async scheduler for triggering agent at various game moments
- Persist player profiles and conversation history (players are remembered)
- Bootstrap Chess Master's lore (backstory, history, mentors)
- Iterate on personality through test games and feedback

Key Phase 1 features:
- **Player relationships**: Agents remembers returning players, builds familiarity
- **Conversation memory**: Stores recent messages so agent can reference them
- **Lore system**: Chess Master has a personal history that players discover
- **Async architecture**: Non-blocking triggers, background idle monitoring

**Phase 2**: Chess engine integration
- Integrate python-chess + Stockfish (multiple difficulty levels)
- Connect agent to game state (odds, moves, time, board hints)
- Persist match history to Postgres database
- Agent can comment on move quality, suggest improvements, tease blunders

**Future**: Visual representation, emotion display, multi-modal interaction, connection to other Metropolis properties

## Architecture

```
metropolis-chess-club/
├── agent/
│   ├── main_agent.py          # Chess Master conversational agent
│   ├── subconscious.py        # Memory manager
│   ├── scheduler.py           # Trigger points and timing
│   ├── personality.md         # Character definition
│   └── tools.py               # [TODO] Tool definitions
│
├── memory/
│   ├── weaviate_client.py     # [TODO] Vector DB client
│   ├── schemas.py             # Memory schema definitions
│   └── retrieval.py           # [TODO] Query logic
│
├── models/
│   ├── claude_api.py          # [TODO] Claude API wrapper
│   ├── gemini_api.py          # [TODO] Gemini API wrapper
│   └── base.py                # [TODO] Abstract interface
│
├── config/
│   └── settings.py            # Environment configuration
│
├── tests/                     # [TODO] Test suite
│
├── requirements.txt           # Python dependencies
├── .gitignore
└── README.md
```

## Quick Start

### 1. Setup

```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### 2. Environment

Create a `.env` file:

```
# Gemini (primary)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-3.1-flash-lite-preview

# Or Claude (fallback):
# CLAUDE_API_KEY=your_claude_key_here
# CLAUDE_MODEL=claude-opus-4-20250514

# Weaviate
WEAVIATE_EMBEDDED=true
WEAVIATE_URL=http://localhost:8080

# Database (for Phase 2, player profiles for Phase 1)
# DATABASE_URL=sqlite:///chess_club.db

# Game defaults
DEFAULT_USERNAME=Opponent
DEFAULT_DIFFICULTY=intermediate
```

### 3. Run

```bash
# [TODO] Once main loop is implemented
python -m agent.main
```

## Key Design Decisions

### Memory System

Memories are stored in Weaviate with semantic search. Each memory includes:
- **content**: The actual memory text (what gets embedded)
- **timestamp**: When created (preserved for recency awareness)
- **memory_type**: Category (player_behavior, player_observation, game_context, personal_note, pattern, streak, emotional, lore)
- **related_match_id**: Optional connection to a specific chess match
- **related_player_id**: Optional connection to a specific player
- **created_by**: Which agent created it (main_agent or subconscious)
- **metadata**: Additional context (player_name, difficulty, opening_name, etc.)

**Why this schema?**
- Type tags enable targeted retrieval ("find player behavior patterns", "find my lore")
- Timestamps are preserved, not decayed—the agent knows memory recency
- `related_player_id` enables player-specific memory queries
- Metadata allows extensibility without schema migration
- `created_by` prevents memory loops (subconscious won't re-provide its own recent memories)

### Player Persistence

For each player, the system maintains:
- **Player Profile**: First seen, last played, total games, win/loss record, relationship state
- **Conversation History**: Recent messages so the agent can reference them
- **Memory Search**: Filtered by `related_player_id` for player-specific insights

This enables:
- Agent remembers returning players across sessions
- Agent can reference past games: "You're playing the Sicilian again"
- Agent builds familiarity and warmth over time
- Newcomers get tested; familiar players get greeted warmly

### Lore & Backstory

Chess Master has a persistent personal history:
- Tournament experiences, victories, losses, mentors, rivals
- Personal quirks, philosophies, superstitions
- Stored as `memory_type=lore` in Weaviate
- Players gradually discover his backstory through natural conversation
- Makes the character feel real and lived-in, not generic

### Scheduler & Trigger Points (Async)

The agent doesn't run continuously. Instead, specific events trigger it asynchronously:

1. **before_match**: Setup, greet opponent
2. **on_user_input**: User sends a message or performs an action
3. **on_user_move**: After opponent makes a chess move
4. **before_agent_move**: Agent decides what to do/say before its turn
5. **idle_wait**: Periodic background check if user is taking a long time (APScheduler)
6. **after_match**: Game concludes, agent reflects and saves

**Async Architecture**:
- All triggers are non-blocking
- Idle monitoring runs in background via APScheduler
- Player profiles and conversation history loaded lazily
- Multiple matches can run concurrently without blocking

This keeps the agent reactive and efficient while allowing multiple personality moments.

### Subconscious Agent

Runs every turn, separate from main agent. Responsibilities:
- Query vector DB for relevant memories
- Filter: don't re-provide already-given memories, don't re-provide recently-created ones
- Decide: are any memories useful right now? If yes, provide; if no, provide nothing
- Can iterate: search → search → search → provide, or search → provide → search

This layer prevents:
- Wasted context on irrelevant memories
- Memory loops (agent creates memory → immediately sees it)
- Stale information being re-emphasized

### JSON-Only Responses

All agent responses are JSON, always. Structure:

```json
{
  "thinking": "Optional pre-response reasoning",
  "action": "send_message | stop | save_memory | set_emotion",
  "content": "...",
  "tone": "playful | sharp | respectful | dismissive",
  "metadata": { "optional": "context" }
}
```

This enables structured parsing, tool calling, and consistent formatting.

## Personality & Character Design

See `agent/personality.md` for full character brief. Key points:

- **Elegant but street-wise**: Sophisticated vocabulary + sharp trash-talking
- **Pattern reader**: Notices habits, strategies, emotional tells
- **Competitive**: Plays to win, doesn't go easy
- **Observant & human**: Has opinions, vulnerabilities, playfulness
- **Context-aware**: Changes tone based on time of day, game state, player behavior

## Development Notes

### TODOs

- [ ] Weaviate Python client integration
- [ ] Gemini API wrapper with tool calling (primary)
- [ ] Claude API wrapper (fallback)
- [ ] Main agent response generation & tool dispatching
- [ ] Subconscious memory retrieval & filtering logic
- [ ] Scheduler with APScheduler
- [ ] Test suite
- [ ] Example usage / demo script

### Model Support

**Primary**: Gemini 3.1 Flash Lite Preview
- Lightweight and fast (ideal for subconscious agent)
- Supports JSON structured output
- Supports tool use / function calling

**Fallback**: Claude Opus 4 (if Gemini unavailable)
- Supports JSON structured output
- Excellent tool use capabilities

### Memory Database

For Phase 1, Weaviate runs embedded in Python. Later, consider:
- Separate Docker container
- Cloud deployment (Weaviate Cloud)
- Alternative vector DB (Pinecone, Qdrant, etc.)

---

## Contributing

This is an active design project. Feedback, ideas, and collaborative iteration are welcome!

See `ARCHITECTURE.md` for deeper technical discussion and design decisions.
