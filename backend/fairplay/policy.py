from __future__ import annotations

import pandas as pd


def confidence_band(score: float) -> str:
    if score >= 0.9:
        return "very_high"
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def select_top_k(scored: pd.DataFrame, k: int, minimum_score: float = 0.0) -> pd.DataFrame:
    """Apply a fixed human-review budget; this function never takes enforcement action."""
    if k < 1:
        raise ValueError("k must be positive")
    selected = (
        scored[scored["risk_score"] >= minimum_score]
        .sort_values(["risk_score", "account_id"], ascending=[False, True])
        .head(k)
        .copy()
    )
    selected.insert(0, "rank", range(1, len(selected) + 1))
    selected["confidence_band"] = selected["risk_score"].map(confidence_band)
    return selected
