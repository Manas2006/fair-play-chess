from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "games_analyzed",
    "moves_analyzed",
    "rating_mean",
    "engine_match_rate",
    "top3_match_rate",
    "cp_loss_mean",
    "cp_loss_median",
    "cp_loss_p90",
    "low_loss_rate",
    "hard_position_match_rate",
    "match_streak_max",
    "move_time_mean",
    "move_time_cv",
    "time_complexity_corr",
    "performance_delta",
]


def _longest_true_run(values: pd.Series) -> int:
    best = current = 0
    for value in values.astype(bool):
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def _safe_corr(group: pd.DataFrame) -> float:
    if len(group) < 3 or group["move_time_s"].nunique() < 2 or group["complexity"].nunique() < 2:
        return 0.0
    value = group["move_time_s"].corr(group["complexity"])
    return 0.0 if pd.isna(value) else float(value)


def aggregate_account_features(moves: pd.DataFrame) -> pd.DataFrame:
    """Aggregate move evidence into one reviewable account snapshot."""
    required = {
        "account_id", "game_id", "rating", "speed", "engine_match", "move_rank",
        "cp_loss", "complexity", "move_time_s", "played_at",
    }
    missing = required.difference(moves.columns)
    if missing:
        raise ValueError(f"Missing move columns: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    ordered = moves.sort_values(["account_id", "played_at", "game_id", "ply"])
    for account_id, group in ordered.groupby("account_id", sort=False):
        hard = group[group["complexity"] >= 0.65]
        game_perf = group.groupby("game_id").agg(
            match_rate=("engine_match", "mean"),
            rating=("rating", "mean"),
        )
        inferred_performance = 800 + 1800 * game_perf["match_rate"].clip(0, 1)
        speed_mode = group["speed"].mode()
        move_time_mean = float(group["move_time_s"].mean())
        move_time_std = float(group["move_time_s"].std(ddof=0))
        rows.append(
            {
                "account_id": account_id,
                "games_analyzed": int(group["game_id"].nunique()),
                "moves_analyzed": int(len(group)),
                "rating_mean": float(group["rating"].mean()),
                "dominant_speed": str(speed_mode.iloc[0] if not speed_mode.empty else "unknown"),
                "engine_match_rate": float(group["engine_match"].mean()),
                "top3_match_rate": float((group["move_rank"] <= 3).mean()),
                "cp_loss_mean": float(group["cp_loss"].mean()),
                "cp_loss_median": float(group["cp_loss"].median()),
                "cp_loss_p90": float(group["cp_loss"].quantile(0.9)),
                "low_loss_rate": float((group["cp_loss"] <= 10).mean()),
                "hard_position_match_rate": float(hard["engine_match"].mean()) if len(hard) else 0.0,
                "match_streak_max": int(_longest_true_run(group["engine_match"])),
                "move_time_mean": move_time_mean,
                "move_time_cv": move_time_std / max(move_time_mean, 1e-6),
                "time_complexity_corr": _safe_corr(group),
                "performance_delta": float((inferred_performance - game_perf["rating"]).mean()),
            }
        )
    result = pd.DataFrame(rows)
    for column in FEATURE_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    return result


def evidence_for_account(moves: pd.DataFrame, account_id: str, limit: int = 24) -> dict[str, object]:
    group = moves[moves["account_id"] == account_id].copy()
    group["signal"] = (
        0.45 * group["engine_match"].astype(float)
        + 0.35 * (1 - np.minimum(group["cp_loss"], 100) / 100)
        + 0.20 * group["complexity"]
    )
    strongest = group.nlargest(limit, "signal")
    timeline = [
        {
            "game_id": str(row.game_id),
            "ply": int(row.ply),
            "move": str(row.move_uci),
            "best_move": str(row.best_move_uci),
            "cp_loss": round(float(row.cp_loss), 1),
            "complexity": round(float(row.complexity), 3),
            "move_time_s": round(float(row.move_time_s), 2),
            "engine_match": bool(row.engine_match),
            "injected": bool(getattr(row, "injected", False)),
        }
        for row in strongest.itertuples()
    ]
    return {
        "engine_match_rate": round(float(group["engine_match"].mean()), 4),
        "median_cp_loss": round(float(group["cp_loss"].median()), 2),
        "hard_position_match_rate": round(
            float(group.loc[group["complexity"] >= 0.65, "engine_match"].mean())
            if (group["complexity"] >= 0.65).any() else 0.0,
            4,
        ),
        "timeline": timeline,
    }
