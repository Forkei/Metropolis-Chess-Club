#!/usr/bin/env python
"""
Play chess against the Chess Master agent.

A full interactive CLI game with the complete trigger system,
personality, and memory integration.
"""

import asyncio
import traceback
from datetime import datetime
from typing import Optional

from agent.main_agent import ChessMaster
from agent.subconscious import Subconscious
from agent.scheduler import MatchScheduler, TriggerPoint
from db.database import get_db_manager, get_or_create_player
from chess_engine import ChessGame, choose_move


async def display_board(scheduler: MatchScheduler) -> None:
    """Display the chess board with context."""
    game = scheduler.chess_game
    print("\n" + "=" * 70)
    print(game.get_ascii_board())
    print("=" * 70)

    status = game.get_game_status()
    if status["is_checkmate"]:
        winner = "White" if status["is_check"] else "Black"
        print(f"♞ CHECKMATE! {winner} wins!")
    elif status["is_stalemate"]:
        print("♞ STALEMATE! Draw!")
    elif status["is_check"]:
        print(f"♞ CHECK! {game.get_current_player()} is in check!")

    print(f"Move count: {status['moves_count']} | Phase: {game.get_game_phase()}")
    print()


def show_legal_moves(scheduler: MatchScheduler) -> None:
    """Show available moves."""
    moves = scheduler.chess_game.get_legal_moves()
    print(f"Legal moves ({len(moves)}): {', '.join(moves[:15])}", end="")
    if len(moves) > 15:
        print(f", ... (+{len(moves) - 15} more)", end="")
    print("\n")


def show_help() -> None:
    """Show command help."""
    print("""
Commands:
  <move>      - Make a move (e.g., e4, Nf3, O-O for castling)
  resign      - Resign the game
  draw        - Offer a draw
  board       - Show the board again
  moves       - Show all legal moves
  history     - Show move history
  help        - Show this help
  quit        - Exit
""")


async def get_player_move(scheduler: MatchScheduler, player_name: str) -> Optional[str]:
    """Get and validate a player move."""
    while True:
        try:
            move_input = input(f"\n{player_name}'s move (or 'help'): ").strip()

            if not move_input:
                print("Please enter a move or command")
                continue

            move_lower = move_input.lower()

            # Commands
            if move_lower == "help":
                show_help()
                continue
            elif move_lower == "board":
                await display_board(scheduler)
                continue
            elif move_lower == "moves":
                show_legal_moves(scheduler)
                continue
            elif move_lower == "history":
                history = scheduler.chess_game.get_move_history()
                if history:
                    moves_str = " ".join([m["move_san"] for m in history])
                    print(f"Move history: {moves_str}\n")
                else:
                    print("No moves yet.\n")
                continue
            elif move_lower in ["resign", "draw"]:
                return move_lower
            elif move_lower == "quit":
                return "quit"

            # Try to make the move
            success, error = scheduler.chess_game.make_move(move_input)
            if success:
                return move_input
            else:
                print(f"❌ {error}")
                print("Try 'moves' to see legal moves.")
                continue

        except KeyboardInterrupt:
            return "quit"
        except Exception as e:
            print(f"Error: {e}")
            continue


async def make_agent_move(scheduler: MatchScheduler) -> bool:
    """Make agent's move with trigger system."""
    game = scheduler.chess_game

    if not game.get_legal_moves_uci():
        return False

    response = await scheduler.trigger(TriggerPoint.BEFORE_AGENT_MOVE)
    if response and response.get("action") == "send_message":
        print(f"\n🎭 Chess Master: {response.get('content')}")
        if response.get("tone"):
            print(f"   (tone: {response.get('tone')})")

    mv = choose_move(game.board, depth=2)
    if mv is None:
        return False

    san = game.board.san(mv)  # compute before pushing
    result = scheduler.make_agent_move(mv.uci())

    if result["success"]:
        print(f"\n♘ Chess Master played: {san}")
        return True

    return False


async def play_game() -> None:
    """Main game loop."""

    print("\n" + "=" * 70)
    print("♟️  METROPOLIS CHESS CLUB ♟️")
    print("   Play Against the Chess Master")
    print("=" * 70)

    # Get player info
    player_name = input("\nWhat's your name? ").strip()
    if not player_name:
        player_name = "Player"

    print(f"\nWelcome, {player_name}!")

    # Initialize database
    db = get_db_manager()
    db.initialize()
    player = get_or_create_player(player_name, player_name)

    print(f"Games played: {player.total_games} | Wins: {player.wins_against_agent}")

    # Initialize agents
    print("\n🔄 Initializing Chess Master...", end="", flush=True)
    chess_master = ChessMaster()
    subconscious = Subconscious()
    print(" Ready!")

    # Create match
    match_id = f"match-{datetime.now().timestamp()}"
    scheduler = MatchScheduler(
        match_id=match_id,
        player_id=player.player_id,
        main_agent=chess_master,
        subconscious_agent=subconscious,
        player_name=player_name,
        agent_name="Chess Master",
    )

    # Start match
    scheduler.start_match()

    # Before match trigger
    print("\n🎭 Triggering before_match...\n")
    response = await scheduler.trigger(TriggerPoint.BEFORE_MATCH)
    if response and response.get("action") == "send_message":
        print(f"Chess Master: {response.get('content')}")
        if response.get("tone"):
            print(f"(tone: {response.get('tone')})")

    show_help()

    # Game loop
    while not scheduler.chess_game.is_game_over():
        await display_board(scheduler)
        show_legal_moves(scheduler)

        # Get player move
        player_move = await get_player_move(scheduler, player_name)

        if player_move == "quit":
            print("\nGame abandoned.")
            return
        elif player_move == "resign":
            result = scheduler.resign_player()
            print(f"\n{player_name} resigned.")
            print(f"Result: {result.get('result')}")
            break
        elif player_move == "draw":
            result = scheduler.offer_draw()
            print(f"\nDraw accepted.")
            print(f"Result: {result.get('result')}")
            break

        # Trigger on_user_move
        response = await scheduler.trigger(
            TriggerPoint.ON_USER_MOVE,
            {"move": player_move}
        )
        if response and response.get("action") == "send_message":
            print(f"\n🎭 Chess Master: {response.get('content')}")
            if response.get("tone"):
                print(f"   (tone: {response.get('tone')})")

        if scheduler.chess_game.is_game_over():
            break

        # Agent move
        await make_agent_move(scheduler)

        if scheduler.chess_game.is_game_over():
            break

    # Game over
    await display_board(scheduler)

    game_result = scheduler.chess_game.get_game_result()
    if game_result:
        if game_result == "1-0":
            print("🎉 White wins!")
        elif game_result == "0-1":
            print("🎉 Black wins!")
        else:
            print("🤝 Draw!")

    # After match — fires AFTER_MATCH trigger and records outcome to DB
    print("\n🎭 Triggering after_match...\n")
    response = await scheduler.end_match()
    if response and response.get("action") == "send_message":
        print(f"Chess Master: {response.get('content')}")
        if response.get("tone"):
            print(f"(tone: {response.get('tone')})")

    # Show stats
    stats = scheduler.get_stats()
    print("\n" + "=" * 70)
    print("MATCH STATS")
    print("=" * 70)
    print(f"Match ID: {stats['match_id']}")
    print(f"Duration: {stats['duration_seconds']:.1f}s")
    print(f"Moves: {stats['moves_count']}")
    print(f"Messages: {stats['conversation_count']}")
    print(f"Triggers: {stats['trigger_count']}")
    print("=" * 70 + "\n")


async def main():
    """Entry point."""
    try:
        await play_game()
    except KeyboardInterrupt:
        print("\n\nGame interrupted.")
    except Exception as e:
        print(f"\nError: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
