#!/usr/bin/env python
"""
Chess Master GUI - FastAPI + python-socketio (async).

One event loop, native async/await throughout — no asyncio.run() hacks,
standard logging works everywhere.
"""

import asyncio
import logging
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.main_agent import ChessMaster
from agent.subconscious import Subconscious
from agent.scheduler import MatchScheduler, TriggerPoint
from config.settings import IDLE_CHECK_INTERVAL, MAX_IDLE_TIME
from db.database import get_db_manager, get_or_create_player
from chess_engine import ChessGame, choose_move

_BASE = Path(__file__).parent

# ── Logging ───────────────────────────────────────────────────────────────────

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_root.handlers.clear()

_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
_root.addHandler(_sh)

_fh = RotatingFileHandler(
    str(_BASE / "chess_debug.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_fh.setFormatter(_fmt)
_root.addHandler(_fh)

for _noisy in ("engineio", "socketio", "urllib3", "httpx", "httpcore",
               "sentence_transformers", "transformers", "torch", "numexpr",
               "datasets", "jax", "absl", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_log = logging.getLogger(__name__)

# ── Memory ────────────────────────────────────────────────────────────────────

def _init_memory_client():
    try:
        from memory.simple_store import SimpleVectorStore
        client = SimpleVectorStore()
        _log.info(f"Memory ready — {client.get_stats()['total_memory_count']} memories loaded")
        return client
    except Exception as e:
        _log.warning(f"Memory unavailable: {e}")
        return None

_memory_client = _init_memory_client()

# ── App setup ─────────────────────────────────────────────────────────────────

IDLE_THRESHOLD = MAX_IDLE_TIME

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# The ASGI app uvicorn actually serves — socket.io wraps FastAPI
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

games: dict = {}       # sid → GameSession
_idle_tasks: dict = {} # sid → asyncio.Task

_MAX_NAME_LEN = 64


# ── GameSession ───────────────────────────────────────────────────────────────

class GameSession:
    """Manages a single game session (vs Viktor or local 2-player)."""

    def __init__(self, player_name: str, mode: str = "vs_viktor",
                 depth: int = 3, player2_name: str = "Black"):
        self.player_name = player_name
        self.player2_name = player2_name
        self.mode = mode
        self.depth = depth
        self.scheduler: Optional[MatchScheduler] = None
        self._chess_game: Optional[ChessGame] = None
        self.initialized = False

    @property
    def chess_game(self) -> Optional[ChessGame]:
        if self.mode == "vs_human":
            return self._chess_game
        return self.scheduler.chess_game if self.scheduler else None

    async def initialize(self):
        if self.initialized:
            return
        if self.mode == "vs_human":
            self._chess_game = ChessGame(
                white_player=self.player_name,
                black_player=self.player2_name,
            )
        else:
            db = get_db_manager()
            db.initialize()
            player = get_or_create_player(self.player_name, self.player_name)
            chess_master = ChessMaster(memory_client=_memory_client)
            subconscious = Subconscious(memory_client=_memory_client)
            self.scheduler = MatchScheduler(
                match_id=f"web-{datetime.now().timestamp()}",
                player_id=player.player_id,
                main_agent=chess_master,
                subconscious_agent=subconscious,
                player_name=self.player_name,
                agent_name="Viktor",
            )
            self.scheduler.start_match()
        self.initialized = True

    async def trigger_agent(self, trigger_point: TriggerPoint, context=None):
        if self.mode != "vs_viktor" or not self.scheduler:
            return None
        response = await self.scheduler.trigger(trigger_point, context or {})
        if response and response.get("action") == "send_message":
            return {
                "speaker": "agent",
                "content": response.get("content"),
                "tone": response.get("tone"),
                "thinking": response.get("thinking", ""),
                "memories_surfaced": response.get("memories_surfaced", 0),
                "memory_saved": response.get("memory_saved", False),
                "timestamp": datetime.now().isoformat(),
            }
        return None

    async def end_match(self, context=None):
        """Fire AFTER_MATCH trigger and record game outcome."""
        if self.mode != "vs_viktor" or not self.scheduler:
            return None
        response = await self.scheduler.end_match(context)
        if response and response.get("action") == "send_message":
            return {
                "speaker": "agent",
                "content": response.get("content"),
                "tone": response.get("tone"),
                "thinking": response.get("thinking", ""),
                "memories_surfaced": response.get("memories_surfaced", 0),
                "memory_saved": response.get("memory_saved", False),
                "timestamp": datetime.now().isoformat(),
            }
        return None

    def add_player_message(self, text: str):
        if self.mode == "vs_viktor" and self.scheduler:
            self.scheduler.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "speaker": "player",
                "content": text,
            })

    def mark_activity(self):
        if self.mode == "vs_viktor" and self.scheduler:
            self.scheduler.last_user_activity = datetime.now()

    def make_move(self, move: str):
        game = self.chess_game
        if not game:
            return {"success": False, "error": "No game in progress"}
        if self.mode == "vs_viktor":
            return self.scheduler.make_player_move(move)
        success, error = game.make_move(move)
        if not success:
            return {"success": False, "error": error}
        return {"success": True, "move": move}

    def make_agent_move(self):
        game = self.chess_game
        if not game or not game.get_legal_moves_uci():
            return None
        import chess as _chess
        if game.board.turn != _chess.BLACK:
            _log.warning("make_agent_move called but it is not Black's turn")
            return None
        mv = choose_move(game.board, depth=self.depth)
        if mv is None:
            return None
        result = self.scheduler.make_agent_move(mv.uci())
        return result if result and result["success"] else None

    def resign(self):
        if self.mode == "vs_viktor" and self.scheduler:
            self.scheduler.resign_player()
        return self.get_board_state()

    def get_board_state(self):
        game = self.chess_game
        if not game:
            return {}
        status = game.get_game_status()
        last_move = game.get_last_move()
        return {
            "fen": game.get_fen(),
            "legal_moves_uci": game.get_legal_moves_uci(),
            "move_count": status["moves_count"],
            "current_player": game.get_current_player(),
            "white_player": game.white_player if hasattr(game, "white_player") else self.player_name,
            "black_player": game.black_player if hasattr(game, "black_player") else self.player2_name,
            "is_check": status["is_check"],
            "is_checkmate": status["is_checkmate"],
            "is_stalemate": status["is_stalemate"],
            "is_game_over": status["is_game_over"],
            "result": game.get_game_result(),
            "phase": game.get_game_phase(),
            "opening": game.get_opening_name(),
            "last_move": last_move.get("move_uci") if last_move else None,
            "move_history_san": [m["move_san"] for m in game.get_move_history()[-30:]],
        }

    def get_debug_state(self):
        if not self.scheduler:
            return {"mode": self.mode, "board": self.get_board_state()}
        return {
            "mode": self.mode,
            "player_name": self.player_name,
            "stats": self.scheduler.get_stats(),
            "conversation_history": self.scheduler.conversation_history[-20:],
            "trigger_history": self.scheduler.trigger_history[-10:],
        }


# ── HTTP routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/debug")
async def debug_view():
    return JSONResponse({sid[:8]: game.get_debug_state() for sid, game in games.items()})


# ── Background idle monitor ───────────────────────────────────────────────────

async def _idle_monitor(sid: str):
    """Nudges Viktor when the player stalls. Runs as a native asyncio task."""
    while True:
        await asyncio.sleep(IDLE_CHECK_INTERVAL)
        game = games.get(sid)
        if game is None or game.mode != "vs_viktor" or not game.scheduler:
            return
        sched = game.scheduler
        if sched.chess_game is None or sched.chess_game.is_game_over():
            return
        if sched.chess_game.get_current_player() != game.player_name:
            continue
        if not sched.last_user_activity:
            continue
        elapsed = (datetime.now() - sched.last_user_activity).total_seconds()
        if elapsed < IDLE_THRESHOLD:
            continue
        msg = await game.trigger_agent(TriggerPoint.IDLE_WAIT, {"idle_seconds": int(elapsed)})
        if msg and msg.get("content"):
            await sio.emit("idle_message", {"agent_message": msg}, to=sid)
        sched.last_user_activity = datetime.now()


# ── Socket events ─────────────────────────────────────────────────────────────

@sio.on("connect")
async def on_connect(sid, environ):
    await sio.emit("connected", {"data": "Connected"}, to=sid)


@sio.on("start_game")
async def on_start_game(sid, data):
    try:
        player_name  = (data.get("player_name", "White") or "White")[:_MAX_NAME_LEN].strip() or "White"
        player2_name = (data.get("player2_name", "Black") or "Black")[:_MAX_NAME_LEN].strip() or "Black"
        mode         = data.get("mode", "vs_viktor")
        depth        = int(data.get("depth", 3))

        game = GameSession(player_name=player_name, mode=mode, depth=depth, player2_name=player2_name)
        await game.initialize()
        games[sid] = game

        message = await game.trigger_agent(TriggerPoint.BEFORE_MATCH)

        await sio.emit("game_started", {
            "player_name":  player_name,
            "player2_name": player2_name,
            "mode":         mode,
            "board":        game.get_board_state(),
            "message":      message,
        }, to=sid)

        if mode == "vs_viktor":
            _idle_tasks[sid] = asyncio.create_task(_idle_monitor(sid))

    except Exception as e:
        _log.error("on_start_game error", exc_info=True)
        await sio.emit("error", {"message": str(e)}, to=sid)


@sio.on("make_move")
async def on_make_move(sid, data):
    try:
        game = games.get(sid)
        if not game:
            await sio.emit("error", {"message": "No active game"}, to=sid); return

        game.mark_activity()
        move   = data.get("move")
        result = game.make_move(move)

        if not result.get("success"):
            await sio.emit("move_error", {"error": result.get("error")}, to=sid); return

        board_state = game.get_board_state()

        # ── 2-player mode: just return updated board ─────────────────────────
        if game.mode == "vs_human":
            if board_state["is_game_over"]:
                await sio.emit("game_over", {
                    "board": board_state, "player_message": None,
                    "agent_message": None, "result": board_state["result"],
                }, to=sid)
            else:
                await sio.emit("move_made", {
                    "board": board_state, "player_message": None,
                    "agent_message": None, "game_over": False, "result": None,
                }, to=sid)
            return

        # ── vs Viktor ─────────────────────────────────────────────────────────
        message = await game.trigger_agent(TriggerPoint.ON_USER_MOVE, {"move": move})

        if board_state["is_game_over"]:
            end_msg = await game.end_match()
            await sio.emit("game_over", {
                "board": board_state, "player_message": message,
                "agent_message": end_msg, "result": board_state["result"],
            }, to=sid)
            return

        await asyncio.sleep(0.4)
        agent_result = game.make_agent_move()
        if agent_result is None:
            _log.warning("Agent move failed or no legal moves available")
        board_state = game.get_board_state()

        if board_state["is_game_over"]:
            end_msg = await game.end_match()
            await sio.emit("move_made", {
                "board": board_state, "player_message": message,
                "agent_message": end_msg, "game_over": True, "result": board_state["result"],
            }, to=sid)
        else:
            await sio.emit("move_made", {
                "board": board_state, "player_message": message,
                "agent_message": None, "game_over": False, "result": None,
            }, to=sid)

    except Exception as e:
        _log.error("on_make_move error", exc_info=True)
        await sio.emit("error", {"message": str(e)}, to=sid)


@sio.on("send_message")
async def on_send_message(sid, data):
    try:
        game = games.get(sid)
        if not game or game.mode != "vs_viktor":
            return
        game.mark_activity()
        text = (data.get("message", "") or "")[:1024]
        game.add_player_message(text)
        agent_msg = await game.trigger_agent(TriggerPoint.ON_USER_INPUT, {"user_input": text})
        await sio.emit("message_sent", {
            "player_message": {"speaker": "player", "content": text},
            "agent_message": agent_msg,
        }, to=sid)
    except Exception as e:
        _log.error("on_send_message error", exc_info=True)
        await sio.emit("error", {"message": str(e)}, to=sid)


@sio.on("resign")
async def on_resign(sid):
    try:
        game = games.get(sid)
        if not game:
            await sio.emit("game_over", {
                "board": None, "player_message": None, "agent_message": None, "result": "0-1",
            }, to=sid)
            return
        game.mark_activity()
        board_state = game.resign()
        end_msg = await game.end_match({"event": "player_resigned"})
        await sio.emit("game_over", {
            "board": board_state, "player_message": None,
            "agent_message": end_msg, "result": board_state["result"] or "0-1",
        }, to=sid)
    except Exception as e:
        _log.error("on_resign error", exc_info=True)
        await sio.emit("error", {"message": str(e)}, to=sid)


@sio.on("disconnect")
async def on_disconnect(sid):
    task = _idle_tasks.pop(sid, None)
    if task:
        task.cancel()
    games.pop(sid, None)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:socket_app", host="0.0.0.0", port=8080, reload=False)
