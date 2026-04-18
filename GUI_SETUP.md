# Chess Master GUI - Setup & Launch

## Quick Start

### 1. Set Gemini API Key

```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY = "your_api_key_here"

# Windows (Command Prompt)
set GEMINI_API_KEY=your_api_key_here

# Linux/Mac
export GEMINI_API_KEY=your_api_key_here
```

Get a free key: https://aistudio.google.com/app/apikey

### 2. Run the GUI

**Windows:**
```bash
run_gui.bat
```

**Linux/Mac:**
```bash
bash run_gui.sh
```

**Or manually:**
```bash
python app.py
```

### 3. Open in Browser

```
http://localhost:5000
```

## What's Included

### Files
- `app.py` - Flask server with WebSocket support
- `templates/index.html` - Game UI
- `static/style.css` - Styling
- `static/game.js` - Client-side logic
- `requirements-gui.txt` - Python dependencies
- `run_gui.bat` / `run_gui.sh` - Quick start scripts

### Features
✓ Modern, responsive web interface  
✓ Chess board with legal move highlighting  
✓ Real-time chat sidebar  
✓ Agent responds naturally (chooses when to speak)  
✓ Game statistics (moves, duration, messages)  
✓ Player persistence (remembers you)  
✓ Full trigger system (BEFORE_MATCH, ON_USER_MOVE, etc.)  

## How It Works

### Game Flow

1. **Start** → Enter name → Click "Start Game"
2. **BEFORE_MATCH trigger** → Agent greets you (if it chooses to speak)
3. **Make moves** → Type or click legal moves
4. **ON_USER_MOVE trigger** → Agent responds (if interesting)
5. **Agent moves** → Random legal move (automated)
6. **Repeat** → Until game ends
7. **AFTER_MATCH trigger** → Agent reflects on game

### Natural Conversation

The agent will:
- **Speak when:**
  - You make an interesting move
  - There's a critical moment (check, threat)
  - You ask a question in chat
  - Something unusual happens
  
- **Stay silent when:**
  - Routine opening moves
  - Nothing interesting to add
  - You're just thinking

This is controlled by the system prompt which encourages the agent to use `"action": "stop"` for silence.

## Architecture

### Backend
- **Flask** - Web server
- **Flask-SocketIO** - Real-time WebSocket communication
- **GameSession** - Per-client game state management
- **Agent System** - Full Chess Master with triggers

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Modern styling with flexbox
- **JavaScript** - WebSocket client, game logic
- **Socket.IO** - Real-time communication

### Async Flow

```
Client                    Server                      Agent
  |                         |                           |
  |--send move----------->  |                           |
  |                         |--trigger(ON_USER_MOVE)->  |
  |                         |                      [respond]
  |                         |<--response------------|
  |<--move_made------------|
  |                    [agent moves]
  |<--board update--------|
  |
  |--send message------->  |
  |                         |--trigger(ON_USER_INPUT)->|
  |                         |                     [respond]
  |                         |<--response------------|
  |<--message sent---------|
```

## Troubleshooting

### Port Already in Use
```bash
# Change port in app.py
socketio.run(app, debug=True, host="0.0.0.0", port=5001)  # Use 5001 instead
```

### API Key Issues
- Verify key is set: `echo %GEMINI_API_KEY%` (Windows) or `echo $GEMINI_API_KEY%` (Unix)
- Get new key: https://aistudio.google.com/app/apikey
- Key should start with `AIzaSy...`

### WebSocket Connection Failed
- Check browser console (F12 → Console)
- Ensure server is running: `http://localhost:5000`
- Check firewall settings

## Customization

### Change Port
Edit `app.py`:
```python
socketio.run(app, debug=True, host="0.0.0.0", port=YOUR_PORT)
```

### Change UI Colors
Edit `static/style.css`:
```css
/* Primary color */
#1e3c72  /* Dark blue */
#2a5298  /* Light blue */
#6a1b9a  /* Agent purple */
```

### Agent Personality
Edit `agent/main_agent.py` system prompt:
```python
system_prompt = f"""You are Viktor Petrov...
```

## Performance Notes

- **Single player per session** - Game state is per WebSocket connection
- **No database persistence** - Chat/moves only persist during game
- **Random moves** - Agent doesn't evaluate position (not a real chess engine)
- **Threading async** - WebSocket runs on thread pool

For production, consider:
- Redis for session management
- Database for move history
- Real chess engine for moves
- Authentication system

## Next Steps

1. Play a full game and check agent responses
2. Test natural conversation (agent staying silent)
3. Play multiple games - agent should remember you
4. (Optional) Implement real chess AI for better moves

---

**Ready to play?**

```bash
python app.py
```

Then open: http://localhost:5000
