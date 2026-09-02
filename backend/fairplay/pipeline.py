from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fairplay.features import aggregate_account_features, evidence_for_account
from fairplay.model import train_model
from fairplay.policy import select_top_k
from fairplay.synthetic import generate_synthetic_moves


def run_demo_pipeline(
    artifacts_dir: Path,
    accounts: int = 900,
    games_per_account: int = 10,
    moves_per_game: int = 22,
    review_budget: int = 50,
    seed: int = 7,
) -> dict[str, object]:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    moves, labels = generate_synthetic_moves(
        accounts=accounts,
        games_per_account=games_per_account,
        moves_per_game=moves_per_game,
        seed=seed,
    )
    features = aggregate_account_features(moves)
    bundle, scored, metrics = train_model(features, labels, seed=seed)
    candidates = select_top_k(scored[scored["split"] == "test"], review_budget)

    cases: list[dict[str, object]] = []
    for row in candidates.itertuples():
        cases.append(
            {
                "account_id": row.account_id,
                "rank": int(row.rank),
                "risk_score": round(float(row.risk_score), 6),
                "confidence_band": row.confidence_band,
                "games_analyzed": int(row.games_analyzed),
                "moves_analyzed": int(row.moves_analyzed),
                "rating": int(round(row.rating_mean)),
                "dominant_speed": row.dominant_speed,
                "synthetic_ground_truth": bool(row.label),
                "assistance_rate": float(row.assistance_rate),
                "evidence": evidence_for_account(moves, row.account_id),
            }
        )

    moves.to_parquet(artifacts_dir / "synthetic_moves.parquet", index=False)
    labels.to_csv(artifacts_dir / "synthetic_labels.csv", index=False)
    features.to_parquet(artifacts_dir / "account_features.parquet", index=False)
    bundle.save(artifacts_dir / "risk_model.joblib")
    _write_json(artifacts_dir / "metrics.json", metrics)
    _write_json(artifacts_dir / "cases.json", cases)
    manifest = {
        "data_mode": "synthetic_counterfactual",
        "accounts": int(len(labels)),
        "games": int(moves["game_id"].nunique()),
        "moves": int(len(moves)),
        "review_budget": review_budget,
        "queued_cases": len(cases),
        "model": "HistGradientBoostingClassifier + sigmoid calibration",
        "seed": seed,
        "safety": "Scores route cases to human review and never trigger enforcement.",
    }
    _write_json(artifacts_dir / "manifest.json", manifest)
    return {"manifest": manifest, "metrics": metrics}


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
