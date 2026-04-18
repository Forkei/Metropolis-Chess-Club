# Chess Master GUI

A modern web interface for playing chess against the Chess Master agent with real-time chat and natural conversation.

## Features

- **Modern Web UI** - Beautiful board display with chess position
- **Real-time Chat** - Messages appear instantly on the right sidebar
- **Natural Conversation** - Agent chooses when to speak (not forced after every move)
- **Click to Play** - Click legal moves or type algebraic notation
- **Game Stats** - Duration, move count, message count
- **Responsive Design** - Works on desktop and tablet

## Installation

### 1. Install GUI Dependencies

```bash
pip install -r requirements-gui.txt
```

### 2. Set Up Gemini API

Get a free key: https://aistudio.google.com/app/apikey

```bash
# Windows
set GEMINI_API_KEY=your_api_key_here

# Linux/Mac
export GEMINI_API_KEY=your_api_key_here
```

## Running

```bash
python app.py
```

Then open your browser to:
```
http://localhost:5000
```

## How to Play

1. **Enter your name** on the start screen
2. **View the board** on the left side
3. **Make moves** by:
   - Clicking on a legal move button
   - Typing algebraic notation (e.g., `e4`, `Nf3`)
4. **Chat** using the sidebar on the right
5. **Watch the agent respond** naturally (it won't always talk after every move)

## Natural Conversation

The Chess Master will:
- ✓ Speak when you make interesting moves
- ✓ Comment during critical moments
- ✓ Stay silent when there's nothing meaningful to add
- ✓ Respond to your messages
- ✓ Remember you across games
- ✓ Adapt tone based on your relationship (new/familiar/rival)

## Architecture

### Backend (Flask + SocketIO)
- `app.py` - Main Flask server
- Real-time WebSocket communication
- Game state management per session
- Agent trigger coordination

### Frontend (HTML/CSS/JavaScript)
- `templates/index.html` - Game UI
- `static/style.css` - Styling
- `static/game.js` - Client logic
- WebSocket client for real-time updates

### Game Logic
- `chess_engine/` - Board state and move validation
- `agent/main_agent.py` - Viktor's personality and responses
- `agent/scheduler.py` - Trigger system coordination
- `db/` - Player persistence

## Known Limitations

1. Agent uses random legal moves (not a real chess engine)
2. No move time limits
3. No draw offers (only resignation)
4. Chat messages persist only during the game

## Future Improvements

- [ ] Implement chess AI for smarter moves
- [ ] Add difficulty levels
- [ ] Draw offers and move undo
- [ ] Game history/replay
- [ ] Multiple game replay
- [ ] Performance analysis
