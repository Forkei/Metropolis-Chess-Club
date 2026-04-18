# Play Against Chess Master

You can now play a full game of chess against the Chess Master agent with the complete personality, memory, and trigger system in action.

## Quick Start

```bash
python play.py
```

## What You'll Experience

- **Personality**: Chess Master responds based on who you are (new/familiar/rival player)
- **Memory**: The agent remembers players across games
- **Emotional Responses**: Emotional state changes based on the game flow
- **Conversation**: Full personality with adaptive dialogue
- **Board State**: Real chess engine with legal move validation
- **Game Phases**: Different behavior in opening/middlegame/endgame

## Game Controls

While playing:
- **`e4`** or **`Nf3`** - Make a move (algebraic notation)
- **`moves`** - Show all legal moves
- **`board`** - Display the board
- **`history`** - Show move history
- **`resign`** - Resign the game
- **`draw`** - Offer a draw
- **`help`** - Show all commands

## API Key Setup

The Chess Master uses the Gemini API for responses. To enable full personality:

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set the environment variable:

```bash
# Windows
set GEMINI_API_KEY=your_api_key_here

# Linux/Mac
export GEMINI_API_KEY=your_api_key_here
```

Without an API key, the agent will still make moves but won't generate responses.

## What's Happening Behind the Scenes

1. **Before Match** - Agent greets you based on your relationship
2. **Your Move** - Validated against chess rules
3. **On User Move** - Agent responds emotionally to your move
4. **Before Agent Move** - Agent decides what to do
5. **Agent Moves** - Uses random legal moves (future: chess AI)
6. **After Match** - Agent reflects on the game

## Architecture

- **Chess Engine**: `chess_engine/` - Full board logic via python-chess
- **Agent**: `agent/main_agent.py` - Personality and responses
- **Scheduler**: `agent/scheduler.py` - Trigger system coordination
- **Memory**: `agent/subconscious.py` - Context retrieval
- **Database**: `db/` - Player persistence across games

## Known Limitations

1. Agent uses random legal moves (not a real chess AI)
2. Opening detection is basic
3. Weaviate memory is optional (mocked if unavailable)

## Future Improvements

- [ ] Implement chess engine for better moves
- [ ] More sophisticated opening detection
- [ ] Real-time emotion updates based on game state
- [ ] Chess analysis provided by the agent
- [ ] Difficulty levels
