import pandas as pd

from fairplay.features import FEATURE_COLUMNS, aggregate_account_features


def test_account_features_are_one_row_per_account():
    moves = pd.DataFrame(
        [
            {"account_id": "a", "game_id": "g1", "played_at": "2025-01-01", "ply": 11, "rating": 1500, "speed": "blitz", "engine_match": True, "move_rank": 1, "cp_loss": 2.0, "complexity": 0.8, "move_time_s": 4.0},
            {"account_id": "a", "game_id": "g1", "played_at": "2025-01-01", "ply": 13, "rating": 1500, "speed": "blitz", "engine_match": False, "move_rank": 4, "cp_loss": 30.0, "complexity": 0.4, "move_time_s": 2.0},
            {"account_id": "b", "game_id": "g2", "played_at": "2025-01-02", "ply": 11, "rating": 1900, "speed": "rapid", "engine_match": True, "move_rank": 1, "cp_loss": 1.0, "complexity": 0.9, "move_time_s": 8.0},
        ]
    )
    result = aggregate_account_features(moves)
    assert result["account_id"].tolist() == ["a", "b"]
    assert set(FEATURE_COLUMNS).issubset(result.columns)
    assert result.loc[result["account_id"] == "a", "engine_match_rate"].item() == 0.5
