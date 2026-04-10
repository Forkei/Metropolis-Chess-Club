# Metropolis Chess Club

An agentic chess character system for the virtual city Metropolis.

The Chess Master is a sophisticated yet sharp-tongued player who runs the Chess Club, engaging visitors with personality, pattern recognition, and genuine competition. This is Phase 1: building the agent and memory system (no chess engine yet).

## Project Vision

**Phase 1 (Current)**: Agent system with subconscious memory management
- Build the Chess Master character agent
- Implement memory vector database (Weaviate)
- Create scheduler for triggering agent at various game moments
- Craft authentic personality through iteration

**Phase 2**: Chess engine integration
- Integrate python-chess + Stockfish
- Connect agent to game state (odds, moves, time)
- Persist match history to database

**Future**: Visual representation, multi-modal interaction, connection to other Metropolis properties

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
LLM_PROVIDER=claude
CLAUDE_API_KEY=your_key_here
CLAUDE_MODEL=claude-opus-4-20250514

# Or for Gemini:
# GEMINI_API_KEY=your_key_here

WEAVIATE_EMBEDDED=true
WEAVIATE_URL=http://localhost:8080

DEFAULT_USERNAME=Opponent
```

### 3. Run

```bash
# [TODO] Once main loop is implemented
python -m agent.main
```

## Key Design Decisions

### Memory System

Memories are stored in Weaviate with semantic search. Each memory includes:
- **content**: The actual memory (what gets embedded)
- **timestamp**: When created
- **memory_type**: Category (player_behavior, game_context, personal_note, pattern, emotional, etc.)
- **related_match_id**: Optional connection to a chess match
- **created_by**: Which agent created it (main_agent or subconscious)
- **metadata**: Additional context

**Why this schema?**
- Type tags enable targeted retrieval (e.g., "find player behavior patterns")
- Metadata allows extensibility without schema migration
- `created_by` prevents memory loops (subconscious won't re-provide its own recent memories)

### Scheduler & Trigger Points

The agent doesn't run continuously. Instead, specific events trigger it:

1. **before_match**: Setup, greet opponent
2. **on_user_input**: User sends a message or performs an action
3. **on_user_move**: After opponent makes a chess move
4. **before_agent_move**: Agent decides what to do/say before its turn
5. **idle_wait**: Periodic check if user is taking a long time
6. **after_match**: Game concludes, agent reflects

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
