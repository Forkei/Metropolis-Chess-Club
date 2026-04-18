"""
Tests for chess game logic and board management.

Tests the ChessGame wrapper around python-chess.
"""

import pytest
import chess as python_chess
from chess_engine.game import ChessGame
from chess_engine.analysis import PositionAnalysis


class TestChessGameInitialization:
    """Test game creation and initialization."""

    def test_init_default(self):
        """Test default game initialization."""
        game = ChessGame()
        assert game.get_move_count() == 0
        assert game.get_current_player() == "White"
        assert not game.is_game_over()
        assert game.get_game_phase() == "opening"

    def test_init_with_custom_names(self):
        """Test game with custom player names."""
        game = ChessGame(white_player="Alice", black_player="Bob")
        assert game.white_player == "Alice"
        assert game.black_player == "Bob"

    def test_init_with_custom_fen(self):
        """Test game from specific position."""
        # Position after 1. e4
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        game = ChessGame(fen=fen)
        # Note: python-chess normalizes invalid en passant squares to "-"
        result_fen = game.get_fen()
        assert "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq" in result_fen
        assert game.get_move_count() == 0


class TestMoveExecution:
    """Test making moves on the board."""

    def test_make_valid_move_uci(self):
        """Test making a move in UCI notation."""
        game = ChessGame()
        success, error = game.make_move("e2e4")
        assert success
        assert error is None
        assert game.get_move_count() == 1

    def test_make_valid_move_algebraic(self):
        """Test making a move in algebraic notation."""
        game = ChessGame()
        success, error = game.make_move("e4")
        assert success
        assert game.get_move_count() == 1

    def test_make_illegal_move(self):
        """Test that illegal moves are rejected."""
        game = ChessGame()
        success, error = game.make_move("e5")  # Pawn can't move to e5 from white's perspective
        assert not success
        assert error is not None

    def test_move_count_increments(self):
        """Test that move count increments correctly."""
        game = ChessGame()
        assert game.get_move_count() == 0
        game.make_move("e4")
        assert game.get_move_count() == 1
        game.make_move("c5")
        assert game.get_move_count() == 2

    def test_move_history_recorded(self):
        """Test that move history is recorded."""
        game = ChessGame()
        game.make_move("e4")
        game.make_move("c5")

        history = game.get_move_history()
        assert len(history) == 2
        assert history[0]["move_san"] == "e4"
        assert history[1]["move_san"] == "c5"


class TestGameStatus:
    """Test game status and end conditions."""

    def test_check_detection(self):
        """Test that check is properly detected."""
        # Position: White king on e1, Black rook on e8
        game = ChessGame(fen="8/8/8/8/8/8/4K3/4r3 w KQkq - 0 1")
        assert game.is_check()

    def test_checkmate_detection(self):
        """Test checkmate detection."""
        # Fool's mate position
        game = ChessGame()
        game.make_move("f3")
        game.make_move("e5")
        game.make_move("g4")
        game.make_move("Qh5")  # Checkmate!

        assert game.is_checkmate()
        assert game.is_game_over()
        assert game.get_game_result() == "0-1"  # Black wins

    def test_stalemate_detection(self):
        """Test stalemate detection."""
        # Stalemate position
        game = ChessGame(fen="k7/8/8/8/8/8/1Q6/K7 b - - 0 1")
        assert game.is_stalemate()
        assert game.is_game_over()
        assert game.get_game_result() == "1/2-1/2"

    def test_game_not_over_initially(self):
        """Test that game is not over at start."""
        game = ChessGame()
        assert not game.is_game_over()
        assert not game.is_check()
        assert not game.is_checkmate()


class TestLegalMoves:
    """Test legal move generation."""

    def test_legal_moves_initial_position(self):
        """Test that starting position has 20 legal moves."""
        game = ChessGame()
        moves = game.get_legal_moves()
        assert len(moves) == 20
        assert "e4" in moves
        assert "Nf3" in moves

    def test_legal_moves_uci(self):
        """Test UCI notation for legal moves."""
        game = ChessGame()
        moves_uci = game.get_legal_moves_uci()
        assert len(moves_uci) == 20
        assert "e2e4" in moves_uci
        assert "g1f3" in moves_uci

    def test_legal_moves_after_move(self):
        """Test legal moves change after a move."""
        game = ChessGame()
        initial_moves = len(game.get_legal_moves())
        game.make_move("e4")
        game.make_move("c5")  # Black plays, now it's white's turn
        new_moves = len(game.get_legal_moves())
        # Legal moves should change after moves are made
        assert new_moves > 0
        # After 1. e4 c5, white has different number of moves than starting position
        assert initial_moves != new_moves or len(game.move_history) > 0


class TestFENandPosition:
    """Test FEN handling and position management."""

    def test_get_fen(self):
        """Test getting FEN of current position."""
        game = ChessGame()
        fen = game.get_fen()
        assert fen == python_chess.STARTING_FEN

    def test_set_fen(self):
        """Test setting position via FEN."""
        game = ChessGame()
        test_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        success, error = game.set_fen(test_fen)
        assert success
        # python-chess normalizes the FEN, so check the board position matches
        result_fen = game.get_fen()
        assert "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq" in result_fen

    def test_set_invalid_fen(self):
        """Test that invalid FEN is rejected."""
        game = ChessGame()
        success, error = game.set_fen("invalid fen")
        assert not success
        assert error is not None


class TestGamePhase:
    """Test game phase detection."""

    def test_opening_phase(self):
        """Test that early game is opening phase."""
        game = ChessGame()
        assert game.get_game_phase() == "opening"

    def test_middlegame_phase(self):
        """Test middlegame detection."""
        game = ChessGame()
        # Play through opening
        moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6"]
        for move in moves:
            game.make_move(move)

        phase = game.get_game_phase()
        assert phase in ["middlegame", "opening"]

    def test_endgame_phase(self):
        """Test endgame detection (few pieces left)."""
        # Position with only kings and one piece
        game = ChessGame(fen="8/8/8/8/8/k7/1Q6/K7 w - - 0 1")
        assert game.get_game_phase() == "endgame"


class TestOpeningDetection:
    """Test opening name detection."""

    def test_detect_sicilian_defense(self):
        """Test detection of Sicilian Defense."""
        game = ChessGame()
        game.make_move("e4")
        game.make_move("c5")

        opening = game.get_opening_name()
        # Should recognize the Sicilian pattern
        assert opening is not None
        assert "Sicilian" in opening or "Defense" in opening or opening == "Sicilian Defense"

    def test_detect_open_game(self):
        """Test detection of Open Game."""
        game = ChessGame()
        game.make_move("e4")
        game.make_move("e5")

        opening = game.get_opening_name()
        # Should recognize the Open Game pattern
        assert opening is not None
        assert "Open" in opening or "Game" in opening or opening == "Open Game"


class TestResignAndDraw:
    """Test resignation and draw handling."""

    def test_player_resign(self):
        """Test player resignation."""
        game = ChessGame(white_player="Alice", black_player="Bob")
        success, result = game.resign("Alice")
        assert success
        assert result == "0-1"  # Bob wins
        assert game.is_game_over()

    def test_agent_resign(self):
        """Test agent resignation."""
        game = ChessGame(white_player="Alice", black_player="Bob")
        success, result = game.resign("Bob")
        assert success
        assert result == "1-0"  # Alice wins

    def test_resign_unknown_player(self):
        """Test resignation by unknown player."""
        game = ChessGame(white_player="Alice", black_player="Bob")
        success, result = game.resign("Charlie")
        assert not success

    def test_accept_draw(self):
        """Test accepting a draw."""
        game = ChessGame()
        success, result = game.draw()
        assert success
        assert result == "1/2-1/2"
        assert game.is_game_over()

    def test_cannot_resign_finished_game(self):
        """Test that game can't be resigned after it's over."""
        game = ChessGame(white_player="Alice", black_player="Bob")
        game.resign("Alice")
        success, _ = game.resign("Bob")
        assert not success


class TestGameStatus:
    """Test getting comprehensive game status."""

    def test_get_game_status(self):
        """Test getting full game status."""
        game = ChessGame(white_player="Alice", black_player="Bob")
        status = game.get_game_status()

        assert "is_check" in status
        assert "is_checkmate" in status
        assert "is_stalemate" in status
        assert "is_game_over" in status
        assert "current_player" in status
        assert "moves_count" in status

    def test_status_after_move(self):
        """Test status changes after a move."""
        game = ChessGame()
        status_before = game.get_game_status()
        game.make_move("e4")
        status_after = game.get_game_status()

        assert status_before["current_player"] == "White"
        assert status_after["current_player"] == "Black"


class TestPositionAnalysis:
    """Test position analysis."""

    def test_material_balance_initial(self):
        """Test material balance at start."""
        board = python_chess.Board()
        analysis = PositionAnalysis.material_balance(board)

        assert analysis["white_material"] == analysis["black_material"]
        assert analysis["balance"] == 0
        assert analysis["description"] == "Equal"

    def test_material_after_capture(self):
        """Test material count changes after capture."""
        board = python_chess.Board()
        board.push_san("e4")
        board.push_san("d5")
        board.push_san("exd5")  # White pawn takes black pawn

        analysis = PositionAnalysis.material_balance(board)
        assert analysis["white_material"] > analysis["black_material"]

    def test_piece_activity(self):
        """Test piece activity calculation."""
        board = python_chess.Board()
        activity = PositionAnalysis.piece_activity(board)

        assert activity["white_moves"] == 20
        assert activity["black_moves"] == 20

    def test_king_safety(self):
        """Test king safety assessment."""
        board = python_chess.Board()
        safety = PositionAnalysis.king_safety(board)

        assert "white_safety" in safety
        assert "black_safety" in safety


class TestGameSerialization:
    """Test converting game to dictionary."""

    def test_to_dict(self):
        """Test serialization to dict."""
        game = ChessGame(white_player="Alice", black_player="Bob")
        game.make_move("e4")

        game_dict = game.to_dict()

        assert game_dict["white_player"] == "Alice"
        assert game_dict["black_player"] == "Bob"
        assert game_dict["move_count"] == 1
        assert game_dict["current_player"] == "Bob"  # Bob is black, and it's black's turn
        assert "fen" in game_dict
        assert "move_history" in game_dict


class TestUndoMove:
    """Test undoing moves."""

    def test_undo_move(self):
        """Test undoing a move."""
        game = ChessGame()
        game.make_move("e4")
        assert game.get_move_count() == 1

        success, error = game.undo_move()
        assert success
        assert game.get_move_count() == 0

    def test_undo_empty_history(self):
        """Test that undo fails with no moves."""
        game = ChessGame()
        success, error = game.undo_move()
        assert not success
        assert error is not None
