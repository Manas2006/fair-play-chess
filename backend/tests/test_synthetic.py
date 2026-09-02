import chess

from fairplay.synthetic import generate_synthetic_moves


def test_synthetic_generation_is_deterministic_and_anonymized():
    moves_a, labels_a = generate_synthetic_moves(accounts=12, games_per_account=2, moves_per_game=8, seed=42)
    moves_b, labels_b = generate_synthetic_moves(accounts=12, games_per_account=2, moves_per_game=8, seed=42)
    assert moves_a.equals(moves_b)
    assert labels_a.equals(labels_b)
    assert labels_a["account_id"].str.startswith("acct_").all()
    assert len(moves_a) == 12 * 2 * 8


def test_every_displayed_move_has_a_legal_replayable_position():
    moves, _ = generate_synthetic_moves(accounts=2, games_per_account=1, moves_per_game=6, seed=3)
    for row in moves.itertuples():
        board = chess.Board(row.fen_before)
        move = chess.Move.from_uci(row.move_uci)
        assert move in board.legal_moves
        board.push(move)
        assert board.fen() == row.fen_after
