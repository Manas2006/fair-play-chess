from fairplay.synthetic import generate_synthetic_moves


def test_synthetic_generation_is_deterministic_and_anonymized():
    moves_a, labels_a = generate_synthetic_moves(accounts=12, games_per_account=2, moves_per_game=8, seed=42)
    moves_b, labels_b = generate_synthetic_moves(accounts=12, games_per_account=2, moves_per_game=8, seed=42)
    assert moves_a.equals(moves_b)
    assert labels_a.equals(labels_b)
    assert labels_a["account_id"].str.startswith("acct_").all()
    assert len(moves_a) == 12 * 2 * 8
