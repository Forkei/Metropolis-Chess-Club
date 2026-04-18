"""
Lightweight chess AI for Viktor.

Negamax with alpha-beta pruning, quiescence search for tactics, material +
piece-square-table evaluation, and small randomization in the root to avoid
repetition across games. Plays at roughly club level at depth 3.
"""

import random
import chess

# ── Evaluation ──────────────────────────────────────────────────────────────

PIECE_VALUE = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:   20000,
}

# Piece-square tables from White's perspective (a1 = index 0, h8 = 63)
PST_PAWN = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-20,-20, 10, 10,  5,
     5, -5,-10,  0,  0,-10, -5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
     0,  0,  0,  0,  0,  0,  0,  0,
]
PST_KNIGHT = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]
PST_BISHOP = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]
PST_ROOK = [
     0,  0,  5, 10, 10,  5,  0,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     5, 10, 10, 10, 10, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]
PST_QUEEN = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -10,  5,  5,  5,  5,  5,  0,-10,
      0,  0,  5,  5,  5,  5,  0, -5,
     -5,  0,  5,  5,  5,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
]
PST_KING_MID = [
     20, 30, 10,  0,  0, 10, 30, 20,
     20, 20,  0,  0,  0,  0, 20, 20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
]

PST = {
    chess.PAWN:   PST_PAWN,
    chess.KNIGHT: PST_KNIGHT,
    chess.BISHOP: PST_BISHOP,
    chess.ROOK:   PST_ROOK,
    chess.QUEEN:  PST_QUEEN,
    chess.KING:   PST_KING_MID,
}


def evaluate(board: chess.Board) -> int:
    """Static evaluation in centipawns, from the side-to-move's perspective."""
    if board.is_checkmate():
        return -99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for piece_type in PIECE_VALUE:
        pst = PST[piece_type]
        val = PIECE_VALUE[piece_type]
        for sq in board.pieces(piece_type, chess.WHITE):
            score += val + pst[sq]
        for sq in board.pieces(piece_type, chess.BLACK):
            # Mirror the square vertically for Black
            score -= val + pst[chess.square_mirror(sq)]

    return score if board.turn == chess.WHITE else -score


# ── Search ──────────────────────────────────────────────────────────────────

def _mvv_lva(board: chess.Board, move: chess.Move) -> int:
    """Most Valuable Victim / Least Valuable Attacker — for move ordering."""
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        v = PIECE_VALUE.get(victim.piece_type, 0) if victim else 100  # en passant
        a = PIECE_VALUE.get(attacker.piece_type, 0) if attacker else 0
        return 10 * v - a + 10000
    if move.promotion:
        return PIECE_VALUE.get(move.promotion, 0) + 5000
    if board.gives_check(move):
        return 100
    return 0


def _ordered_moves(board: chess.Board):
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: _mvv_lva(board, m), reverse=True)
    return moves


def _quiesce(board: chess.Board, alpha: int, beta: int) -> int:
    """Quiescence search — extend through captures to avoid horizon effects."""
    stand_pat = evaluate(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    for move in _ordered_moves(board):
        if not board.is_capture(move):
            continue
        board.push(move)
        score = -_quiesce(board, -beta, -alpha)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int) -> int:
    if depth == 0:
        return _quiesce(board, alpha, beta)
    if board.is_game_over():
        return evaluate(board)

    best = -1_000_000
    for move in _ordered_moves(board):
        board.push(move)
        score = -_negamax(board, depth - 1, -beta, -alpha)
        board.pop()
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def choose_move(board: chess.Board, depth: int = 3, randomness: float = 30.0) -> chess.Move:
    """
    Pick a move using negamax + alpha-beta.

    Args:
        board: current position
        depth: search depth in plies (3 is club-level, 4 is slow)
        randomness: centipawn window — moves within this of the best are
            candidates. Keeps Viktor from always playing the same lines.

    Returns:
        A legal move. Never None (caller must ensure legal moves exist).
    """
    scored = []
    for move in _ordered_moves(board):
        board.push(move)
        score = -_negamax(board, depth - 1, -1_000_000, 1_000_000)
        board.pop()
        scored.append((score, move))

    if not scored:
        return None

    scored.sort(key=lambda s: s[0], reverse=True)
    best_score = scored[0][0]
    # Any move within `randomness` cp of the best becomes a candidate
    candidates = [m for s, m in scored if best_score - s <= randomness]
    return random.choice(candidates)


__all__ = ["choose_move", "evaluate"]
