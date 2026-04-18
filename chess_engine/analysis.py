"""
Chess position analysis and evaluation.

Provides:
- Material balance calculation
- Piece activity assessment
- Threat detection
- Position description for agent
"""

import logging
import chess as python_chess
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class PositionAnalysis:
    """Analyze chess positions and provide context for the agent."""

    # Piece values in centipawns
    PIECE_VALUES = {
        python_chess.PAWN: 100,
        python_chess.KNIGHT: 320,
        python_chess.BISHOP: 330,
        python_chess.ROOK: 500,
        python_chess.QUEEN: 900,
        python_chess.KING: 0,
    }

    @staticmethod
    def material_balance(board: python_chess.Board) -> Dict[str, Any]:
        """
        Calculate material balance.

        Returns:
            Dict with white_material, black_material, balance
        """
        white_material = 0
        black_material = 0

        for piece_type, value in PositionAnalysis.PIECE_VALUES.items():
            white_count = len(board.pieces(piece_type, python_chess.WHITE))
            black_count = len(board.pieces(piece_type, python_chess.BLACK))

            white_material += white_count * value
            black_material += black_count * value

        balance = white_material - black_material

        return {
            "white_material": white_material,
            "black_material": black_material,
            "balance": balance,
            "description": (
                "White is winning" if balance > 300
                else "White is better" if balance > 100
                else "Equal" if abs(balance) <= 100
                else "Black is better" if balance < -100
                else "Black is winning"
            ),
        }

    @staticmethod
    def piece_activity(board: python_chess.Board) -> Dict[str, Any]:
        """
        Assess piece activity (how mobile and threatening pieces are).

        Returns:
            Dict with white_activity, black_activity scores
        """
        white_moves = 0
        black_moves = 0

        white_copy = board.copy()
        white_copy.turn = python_chess.WHITE
        white_moves = len(list(white_copy.legal_moves))

        black_copy = board.copy()
        black_copy.turn = python_chess.BLACK
        black_moves = len(list(black_copy.legal_moves))

        return {
            "white_moves": white_moves,
            "black_moves": black_moves,
            "white_activity": "high" if white_moves > 30 else "normal" if white_moves > 20 else "restricted",
            "black_activity": "high" if black_moves > 30 else "normal" if black_moves > 20 else "restricted",
        }

    @staticmethod
    def king_safety(board: python_chess.Board) -> Dict[str, str]:
        """
        Assess king safety for both sides.

        Returns:
            Dict with white_safety, black_safety descriptions
        """
        def assess_king(color: python_chess.Color) -> str:
            king_square = board.king(color)
            if king_square is None:
                return "unknown"

            # Check if king is in check
            if board.is_check() and board.turn == color:
                return "in_check"

            # Count defending pieces around king
            king_file = python_chess.square_file(king_square)
            king_rank = python_chess.square_rank(king_square)

            has_castling = (
                board.has_kingside_castling_rights(color)
                or board.has_queenside_castling_rights(color)
            )

            if not has_castling and king_file > 2 and king_file < 6:
                return "exposed"

            return "safe"

        return {
            "white_safety": assess_king(python_chess.WHITE),
            "black_safety": assess_king(python_chess.BLACK),
        }

    @staticmethod
    def pawn_structure(board: python_chess.Board) -> Dict[str, Any]:
        """
        Analyze pawn structure (weak squares, passed pawns, etc.).

        Returns:
            Dict with pawn structure analysis
        """
        white_pawns = board.pieces(python_chess.PAWN, python_chess.WHITE)
        black_pawns = board.pieces(python_chess.PAWN, python_chess.BLACK)

        # Check for passed pawns (simplified)
        white_passed = []
        black_passed = []

        for pawn_square in white_pawns:
            pawn_file = python_chess.square_file(pawn_square)
            pawn_rank = python_chess.square_rank(pawn_square)
            # Simplified: pawn is passed if no enemy pawns ahead on adjacent files
            is_passed = True
            for enemy_pawn in black_pawns:
                enemy_file = python_chess.square_file(enemy_pawn)
                if abs(enemy_file - pawn_file) <= 1 and python_chess.square_rank(enemy_pawn) > pawn_rank:
                    is_passed = False
                    break
            if is_passed:
                white_passed.append(python_chess.square_name(pawn_square))

        # Same for black
        for pawn_square in black_pawns:
            pawn_file = python_chess.square_file(pawn_square)
            pawn_rank = python_chess.square_rank(pawn_square)
            is_passed = True
            for enemy_pawn in white_pawns:
                enemy_file = python_chess.square_file(enemy_pawn)
                if abs(enemy_file - pawn_file) <= 1 and python_chess.square_rank(enemy_pawn) < pawn_rank:
                    is_passed = False
                    break
            if is_passed:
                black_passed.append(python_chess.square_name(pawn_square))

        return {
            "white_pawns": len(white_pawns),
            "black_pawns": len(black_pawns),
            "white_passed_pawns": white_passed,
            "black_passed_pawns": black_passed,
            "pawn_balance": "White ahead" if len(white_pawns) > len(black_pawns) else (
                "Black ahead" if len(black_pawns) > len(white_pawns) else "Equal"
            ),
        }

    @staticmethod
    def threats(board: python_chess.Board) -> Dict[str, List[str]]:
        """
        Detect immediate threats (checks, attacks on pieces).

        Returns:
            Dict with white_threats, black_threats
        """
        threats = {
            "white_threats": [],
            "black_threats": [],
        }

        # Check for checks
        if board.is_check():
            if board.turn == python_chess.WHITE:
                threats["white_threats"].append("In check")
            else:
                threats["black_threats"].append("In check")

        # Check for hanging pieces (could be improved)
        for square in python_chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None:
                continue

            # Check if piece is attacked
            if board.is_attacked_by(not piece.color, square):
                piece_name = python_chess.piece_name(piece.piece_type)
                threat_str = f"{piece_name.capitalize()} hanging on {python_chess.square_name(square)}"
                if piece.color == python_chess.WHITE:
                    threats["black_threats"].append(threat_str)
                else:
                    threats["white_threats"].append(threat_str)

        return threats

    @staticmethod
    def get_position_summary(board: python_chess.Board, player_color: Optional[bool] = None) -> Dict[str, Any]:
        """
        Get a comprehensive position summary.

        Args:
            board: Chess board
            player_color: WHITE, BLACK, or None to describe from both perspectives

        Returns:
            Dict with complete position analysis
        """
        material = PositionAnalysis.material_balance(board)
        activity = PositionAnalysis.piece_activity(board)
        safety = PositionAnalysis.king_safety(board)
        pawns = PositionAnalysis.pawn_structure(board)
        threat_list = PositionAnalysis.threats(board)

        summary = {
            "material": material,
            "activity": activity,
            "king_safety": safety,
            "pawn_structure": pawns,
            "threats": threat_list,
            "summary_text": (
                f"Material: {material['description']}. "
                f"White has {activity['white_moves']} legal moves, "
                f"Black has {activity['black_moves']} legal moves."
            ),
        }

        return summary

    @staticmethod
    def describe_position_for_agent(board: python_chess.Board) -> str:
        """
        Create a natural language description of the position for the agent.

        Args:
            board: Chess board

        Returns:
            Human-readable position description
        """
        analysis = PositionAnalysis.get_position_summary(board)
        material = analysis["material"]
        activity = analysis["activity"]
        safety = analysis["king_safety"]
        threats = analysis["threats"]

        lines = [
            f"Position Status: {material['description']}",
            f"White King: {safety['white_safety']}, Black King: {safety['black_safety']}",
            f"White Mobility: {activity['white_activity']}, Black Mobility: {activity['black_activity']}",
        ]

        if threats["white_threats"]:
            lines.append(f"White threats: {', '.join(threats['white_threats'])}")
        if threats["black_threats"]:
            lines.append(f"Black threats: {', '.join(threats['black_threats'])}")

        return "\n".join(lines)


__all__ = ["PositionAnalysis"]
