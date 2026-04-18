#!/usr/bin/env python
"""
Integration demo - simulates a game without API calls to verify everything works.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

from agent.main_agent import ChessMaster
from agent.subconscious import Subconscious
from agent.scheduler import MatchScheduler, TriggerPoint
from db.database import get_db_manager, get_or_create_player


async def run_demo():
    """Run a demo game with mocked API responses."""

    print("\n" + "=" * 70)
    print("CHESS MASTER - INTEGRATION DEMO")
    print("=" * 70)

    # Initialize database
    print("\n1. Initializing database...")
    db = get_db_manager()
    db.initialize()
    player = get_or_create_player("DemoPlayer", "DemoPlayer")
    print(f"   Player: {player.player_name}")

    # Initialize agents
    print("\n2. Initializing agents...")
    chess_master = ChessMaster()
    subconscious = Subconscious()

    # Mock the API client to avoid needing credentials
    chess_master.api_client = AsyncMock()
    print("   Chess Master ready")
    print("   Subconscious ready")

    # Create match
    print("\n3. Creating match...")
    match_id = f"demo-{datetime.now().timestamp()}"
    scheduler = MatchScheduler(
        match_id=match_id,
        player_id=player.player_id,
        main_agent=chess_master,
        subconscious_agent=subconscious,
        player_name="DemoPlayer",
        agent_name="Chess Master",
    )
    print(f"   Match ID: {match_id}")

    # Start match
    print("\n4. Starting match...")
    scheduler.start_match()
    print(f"   Chess game initialized")
    print(f"   Board:\n{scheduler.chess_game.get_ascii_board()}")

    # Before match trigger
    print("\n5. Testing BEFORE_MATCH trigger...")
    chess_master.api_client.respond = AsyncMock(
        return_value='{"action": "send_message", "content": "Ready for our game!", "tone": "warm"}'
    )
    response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
    print(f"   Response: {response}")
    assert response["action"] == "send_message"
    assert "Ready" in response["content"]
    print("   [OK] Trigger system works")

    # Test moves
    print("\n6. Testing chess moves...")
    success, error = scheduler.chess_game.make_move("e4")
    assert success, f"Move failed: {error}"
    print(f"   White played: e4")
    print(f"   Legal moves for black: {scheduler.chess_game.get_legal_moves()[:5]}...")

    success, error = scheduler.chess_game.make_move("c5")
    assert success, f"Move failed: {error}"
    print(f"   Black played: c5")

    # On user move trigger
    print("\n7. Testing ON_USER_MOVE trigger...")
    chess_master.api_client.respond = AsyncMock(
        return_value='{"action": "send_message", "content": "Sicilian! A good choice.", "tone": "analytical"}'
    )
    response = await scheduler.trigger(TriggerPoint.ON_USER_MOVE, {"move": "c5"})
    print(f"   Response: {response}")
    assert response["action"] == "send_message"
    print("   [OK] Move trigger works")

    # Test board context
    print("\n8. Testing chess context integration...")
    context = {
        "board_fen": scheduler.chess_game.get_fen(),
        "game_phase": scheduler.chess_game.get_game_phase(),
        "legal_moves": scheduler.chess_game.get_legal_moves(),
    }
    print(f"   Game phase: {context['game_phase']}")
    print(f"   Legal moves available: {len(context['legal_moves'])}")
    assert context["game_phase"] == "opening"
    assert len(context["legal_moves"]) > 0
    print("   [OK] Chess context works")

    # Before agent move trigger
    print("\n9. Testing BEFORE_AGENT_MOVE trigger...")
    chess_master.api_client.respond = AsyncMock(
        return_value='{"action": "send_message", "content": "Let me think...", "tone": "focused"}'
    )
    response = await scheduler.trigger(TriggerPoint.BEFORE_AGENT_MOVE)
    print(f"   Response: {response}")
    print("   [OK] Agent move trigger works")

    # Make agent move
    import random

    agent_move = random.choice(scheduler.chess_game.get_legal_moves_uci())
    result = scheduler.make_agent_move(agent_move)
    assert result["success"]
    print(f"   Agent move: {agent_move}")

    # Get stats
    print("\n10. Testing statistics...")
    stats = scheduler.get_stats()
    print(f"    Duration: {stats['duration_seconds']:.1f}s")
    print(f"    Moves: {stats['moves_count']}")
    print(f"    Triggers: {stats['trigger_count']}")
    print(f"    Conversation: {stats['conversation_count']} messages")

    # After match trigger
    print("\n11. Testing AFTER_MATCH trigger...")
    chess_master.api_client.respond = AsyncMock(
        return_value='{"action": "send_message", "content": "Good start!", "tone": "sharp"}'
    )
    response = await scheduler.end_match()
    print(f"   Response: {response}")
    print("   [OK] After match trigger works")

    print("\n" + "=" * 70)
    print("ALL INTEGRATION TESTS PASSED!")
    print("=" * 70)
    print("\nThe system is ready to play. Run: python play.py")
    print("\nNote: Set GEMINI_API_KEY environment variable for full personality.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
