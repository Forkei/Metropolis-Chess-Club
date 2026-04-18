"""
Chess game manager using python-chess library.

Handles:
- Board state and move validation
- Game status (check, checkmate, stalemate, etc.)
- Move history and notation
- Position analysis and FEN
- ASCII board representation
"""

import logging
import chess as python_chess
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ChessGame:
    """
    Chess game state manager.

    Wraps python-chess board with additional tracking for player names,
    move history, and metadata.
    """

    def __init__(
        self,
        white_player: str = "White",
        black_player: str = "Black",
        fen: Optional[str] = None,
    ):
        """
        Initialize a chess game.

        Args:
            white_player: Name of white player (e.g., "Player")
            black_player: Name of black player (e.g., "Chess Master")
            fen: Optional starting position (default: standard starting position)
        """
        self.white_player = white_player
        self.black_player = black_player
        self.board = python_chess.Board(fen if fen else python_chess.STARTING_FEN)
        self.move_history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.started_at = None
        self.ended_at = None
        self.result = None  # "1-0", "0-1", "1/2-1/2", or None

    def get_move_count(self) -> int:
        """Get total number of moves made."""
        return len(self.move_history)

    def get_current_player(self) -> str:
        """Get name of player whose turn it is."""
        return (
            self.white_player
            if self.board.turn == python_chess.WHITE
            else self.black_player
        )

    def get_opponent_player(self) -> str:
        """Get name of player waiting to move."""
        return (
            self.black_player
            if self.board.turn == python_chess.WHITE
            else self.white_player
        )

    def make_move(self, move_uci: str) -> Tuple[bool, Optional[str]]:
        """
        Make a move on the board.

        Args:
            move_uci: Move in UCI format (e.g., "e2e4") or algebraic (e.g., "e4")

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Try SAN first (handles e4, Nf3, O-O, and promotion e7e8=Q)
            try:
                move = self.board.parse_san(move_uci)
            except Exception:
                # Fallback to UCI (e2e4, e7e8q, etc.)
                try:
                    move = python_chess.Move.from_uci(move_uci)
                except Exception:
                    return False, f"Invalid move format: {move_uci}"

            if move not in self.board.legal_moves:
                return False, f"Illegal move: {move_uci}"

            player_who_moved = self.get_current_player()
            fen_before = self.board.fen()
            san = self.board.san(move)  # compute before pushing

            self.board.push(move)

            self.move_history.append({
                "move_number": len(self.move_history) + 1,
                "player": player_who_moved,
                "move_uci": move.uci(),
                "move_san": san,
                "timestamp": datetime.now().isoformat(),
                "fen_before": fen_before,
                "fen_after": self.board.fen(),
            })

            logger.info(f"{player_who_moved} played {san}")
            return True, None

        except ValueError:
            return False, f"Invalid move format: {move_uci}"
        except Exception as e:
            return False, f"Error making move: {str(e)}"

    def get_legal_moves(self) -> List[str]:
        """Get all legal moves in algebraic notation."""
        return [self.board.san(move) for move in self.board.legal_moves]

    def get_legal_moves_uci(self) -> List[str]:
        """Get all legal moves in UCI notation."""
        return [move.uci() for move in self.board.legal_moves]

    def is_check(self) -> bool:
        """Is the current player in check?"""
        return self.board.is_check()

    def is_checkmate(self) -> bool:
        """Is the game in checkmate?"""
        return self.board.is_checkmate()

    def is_stalemate(self) -> bool:
        """Is the game in stalemate?"""
        return self.board.is_stalemate()

    def is_game_over(self) -> bool:
        """Is the game over?"""
        return self.board.is_game_over() or self.result is not None

    def get_game_result(self) -> Optional[str]:
        """
        Get game result.

        Returns:
            "1-0" (white wins), "0-1" (black wins), "1/2-1/2" (draw), or None (ongoing)
        """
        if not self.is_game_over():
            return None

        # Resignation and agreed draws set self.result directly
        if self.result is not None:
            return self.result

        if self.board.is_checkmate():
            return "1-0" if self.board.turn == python_chess.BLACK else "0-1"

        return "1/2-1/2"

    def get_game_status(self) -> Dict[str, Any]:
        """Get detailed game status."""
        return {
            "is_check": self.is_check(),
            "is_checkmate": self.is_checkmate(),
            "is_stalemate": self.is_stalemate(),
            "is_game_over": self.is_game_over(),
            "result": self.get_game_result(),
            "current_player": self.get_current_player(),
            "moves_count": self.get_move_count(),
            "legal_moves_count": self.board.legal_moves.count(),
        }

    def get_ascii_board(self) -> str:
        """Get ASCII representation of the board."""
        return str(self.board)

    def get_piece_positions(self, white_label: str = "White", black_label: str = "Black") -> str:
        """
        Get structured piece positions for LLM context.
        Much clearer than ASCII art — explicit piece, color, and square.
        """
        _names = {
            python_chess.KING: "King",
            python_chess.QUEEN: "Queen",
            python_chess.ROOK: "Rook",
            python_chess.BISHOP: "Bishop",
            python_chess.KNIGHT: "Knight",
            python_chess.PAWN: "Pawn",
        }
        _order = ["King", "Queen", "Rook", "Bishop", "Knight", "Pawn"]

        white, black = [], []
        for square, piece in self.board.piece_map().items():
            entry = f"{_names[piece.piece_type]}-{python_chess.square_name(square)}"
            (white if piece.color == python_chess.WHITE else black).append(entry)

        white.sort(key=lambda p: _order.index(p.split("-")[0]))
        black.sort(key=lambda p: _order.index(p.split("-")[0]))

        return (
            f"{white_label} (White): {', '.join(white)}\n"
            f"{black_label} (Black): {', '.join(black)}"
        )

    def get_fen(self) -> str:
        """Get FEN string of current position."""
        return self.board.fen()

    def set_fen(self, fen: str) -> Tuple[bool, Optional[str]]:
        """
        Set board to a specific FEN position.

        Args:
            fen: FEN string

        Returns:
            Tuple of (success, error_message)
        """
        try:
            self.board.set_fen(fen)
            logger.info(f"Position set to: {fen}")
            return True, None
        except ValueError as e:
            return False, f"Invalid FEN: {str(e)}"

    def get_move_history(self) -> List[Dict[str, Any]]:
        """Get full move history."""
        return self.move_history.copy()

    def get_last_move(self) -> Optional[Dict[str, Any]]:
        """Get the last move made."""
        return self.move_history[-1] if self.move_history else None

    def get_opening_name(self) -> Optional[str]:
        """
        Guess the opening name from move history using SAN prefix matching.
        Patterns are ordered longest-first so the most specific name wins.
        """
        if len(self.move_history) < 2:
            return None

        moves = [m["move_san"] for m in self.move_history[:6]]
        s = " ".join(moves)

        # Ordered longest-to-shortest so specific lines beat generic ones
        patterns = [
            # Sicilian variations
            ("e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6",  "Sicilian Najdorf"),
            ("e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 g6",          "Sicilian Dragon"),
            ("e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6",          "Sicilian Scheveningen"),
            ("e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 Nc6",  "Sicilian Classical"),
            ("e4 c5 Nc3 Nc6 g3",                        "Sicilian Closed"),
            ("e4 c5",                                   "Sicilian Defense"),
            # Open game (e4 e5) lines
            ("e4 e5 Nf3 Nc6 Bb5 a6",                   "Ruy Lopez — Morphy Defence"),
            ("e4 e5 Nf3 Nc6 Bb5",                      "Ruy Lopez"),
            ("e4 e5 Nf3 Nc6 Bc4 Bc5",                  "Giuoco Piano"),
            ("e4 e5 Nf3 Nc6 Bc4 Nf6",                  "Two Knights Defense"),
            ("e4 e5 Nf3 Nc6 Bc4",                      "Italian Game"),
            ("e4 e5 Nf3 Nc6 d4 exd4 Bc4",              "Scotch Gambit"),
            ("e4 e5 Nf3 Nc6 d4",                       "Scotch Game"),
            ("e4 e5 Nf3 f5",                            "Latvian Gambit"),
            ("e4 e5 f4",                                "King's Gambit"),
            ("e4 e5 Nc3 Nc6 f4",                        "Vienna Gambit"),
            ("e4 e5 Nc3",                               "Vienna Game"),
            ("e4 e5",                                   "Open Game"),
            # French and Caro
            ("e4 e6 d4 d5 Nc3 Bb4",                    "French Winawer"),
            ("e4 e6 d4 d5 Nc3 Nf6",                    "French Classical"),
            ("e4 e6 d4 d5 e5",                         "French Advance"),
            ("e4 e6 d4 d5 Nd2",                        "French Tarrasch"),
            ("e4 e6",                                   "French Defense"),
            ("e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5",         "Caro-Kann Classical"),
            ("e4 c6 d4 d5 e5 Bf5",                     "Caro-Kann Advance"),
            ("e4 c6",                                   "Caro-Kann Defense"),
            # Pirc / Modern
            ("e4 d6 d4 Nf6 Nc3 g6",                   "Pirc Defense"),
            ("e4 g6 d4 Bg7",                           "Modern Defense"),
            # e4 other
            ("e4 d5 exd5",                             "Scandinavian Defense"),
            ("e4 Nf6",                                  "Alekhine's Defense"),
            # Queen's pawn
            ("d4 d5 c4 e6 Nc3 Nf6 Bg5",               "Queen's Gambit Declined — Orthodox"),
            ("d4 d5 c4 e6 Nc3 Nf6",                    "Queen's Gambit Declined"),
            ("d4 d5 c4 dxc4",                          "Queen's Gambit Accepted"),
            ("d4 d5 c4 c6 Nf3 Nf6",                   "Slav Defense"),
            ("d4 d5 c4 c6",                            "Slav Defense"),
            ("d4 d5 c4",                               "Queen's Gambit"),
            ("d4 Nf6 c4 e6 Nc3 Bb4",                  "Nimzo-Indian Defense"),
            ("d4 Nf6 c4 e6 Nf3 b6",                   "Queen's Indian Defense"),
            ("d4 Nf6 c4 g6 Nc3 d5",                   "Grünfeld Defense"),
            ("d4 Nf6 c4 g6 Nc3 Bg7 e4",               "King's Indian Defense"),
            ("d4 Nf6 c4 g6",                           "King's Indian"),
            ("d4 Nf6 c4 c5",                           "Benoni Defense"),
            ("d4 f5",                                   "Dutch Defense"),
            ("d4 d5",                                   "Closed Game"),
            ("d4",                                      "Queen's Pawn Game"),
            # Flank
            ("c4 e5",                                   "English Opening — Reversed Sicilian"),
            ("c4 Nf6 Nc3 d5",                          "English — Anglo-Indian"),
            ("c4",                                      "English Opening"),
            ("Nf3 d5 c4",                               "Reti Opening"),
            ("Nf3 Nf6 c4",                              "Reti Opening"),
            ("Nf3",                                     "King's Indian Attack"),
            ("g3",                                      "King's Fianchetto Opening"),
            ("b3",                                      "Nimzowitsch-Larsen Attack"),
            ("f4",                                      "Bird's Opening"),
        ]

        for pattern, name in patterns:
            if s.startswith(pattern):
                return name

        return None

    def get_game_phase(self) -> str:
        """Estimate the game phase (opening, middlegame, endgame)."""
        move_count = self.get_move_count()

        # Count pieces on board (excluding kings)
        piece_count = len(self.board.piece_map())

        # Endgame: very few pieces left (5 or fewer)
        if piece_count <= 5:
            return "endgame"
        # Opening: early in the game
        elif move_count < 10:
            return "opening"
        # Middlegame: beyond opening with reasonable piece count
        else:
            return "middlegame"

    def undo_move(self) -> Tuple[bool, Optional[str]]:
        """
        Undo the last move.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not self.move_history:
                return False, "No moves to undo"

            self.board.pop()
            self.move_history.pop()
            logger.info("Last move undone")
            return True, None
        except Exception as e:
            return False, f"Error undoing move: {str(e)}"

    def resign(self, player: str) -> Tuple[bool, str]:
        """
        Resign the game for a player.

        Args:
            player: Player name who is resigning

        Returns:
            Tuple of (success, result)
        """
        if self.is_game_over():
            return False, "Game is already over"

        if player == self.white_player:
            result = "0-1"  # Black wins
        elif player == self.black_player:
            result = "1-0"  # White wins
        else:
            return False, f"Unknown player: {player}"

        self.result = result
        self.ended_at = datetime.now()
        logger.info(f"{player} resigned. Result: {result}")
        return True, result

    def draw(self) -> Tuple[bool, str]:
        """
        Accept a draw.

        Returns:
            Tuple of (success, result)
        """
        if self.is_game_over():
            return False, "Game is already over"

        self.result = "1/2-1/2"
        self.ended_at = datetime.now()
        logger.info("Game drawn by agreement")
        return True, self.result

    def to_dict(self) -> Dict[str, Any]:
        """Convert game to dictionary for serialization."""
        return {
            "white_player": self.white_player,
            "black_player": self.black_player,
            "fen": self.get_fen(),
            "move_history": self.get_move_history(),
            "move_count": self.get_move_count(),
            "current_player": self.get_current_player(),
            "game_status": self.get_game_status(),
            "opening": self.get_opening_name(),
            "phase": self.get_game_phase(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "result": self.result,
        }


__all__ = ["ChessGame"]
