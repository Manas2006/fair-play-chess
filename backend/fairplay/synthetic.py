from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

import numpy as np
import pandas as pd


SPEEDS = np.array(["blitz", "rapid", "classical"])
PHASES = np.array(["opening", "middlegame", "endgame"])
MOVE_POOL = np.array(["e2e4", "d2d4", "g1f3", "c2c4", "b1c3", "f1b5", "c1g5", "e1g1"])


def _account_id(index: int) -> str:
    return "acct_" + hashlib.sha256(f"fairplay-demo-{index}".encode()).hexdigest()[:10]


def generate_synthetic_moves(
    accounts: int = 900,
    games_per_account: int = 10,
    moves_per_game: int = 22,
    positive_rate: float = 0.08,
    seed: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate coherent evidence traces without creating or accusing real accounts.

    Synthetic assistance is represented as counterfactual decisions at positions. It is
    suitable for pipeline and sensitivity testing, not a substitute for real labels.
    """
    rng = np.random.default_rng(seed)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    move_rows: list[dict[str, object]] = []
    account_rows: list[dict[str, object]] = []

    for account_index in range(accounts):
        account_id = _account_id(account_index)
        is_assisted = bool(rng.random() < positive_rate)
        assistance_rate = float(rng.choice([0.2, 0.5, 1.0], p=[0.5, 0.35, 0.15])) if is_assisted else 0.0
        rating = int(np.clip(rng.normal(1650, 360), 700, 2700))
        skill = np.clip((rating - 700) / 2000, 0, 1)
        speed = str(rng.choice(SPEEDS, p=[0.55, 0.35, 0.10]))
        flagged = bool(is_assisted and rng.random() < (0.55 + 0.4 * assistance_rate))
        account_rows.append(
            {
                "account_id": account_id,
                "label": int(is_assisted),
                "observed_tos_proxy": int(flagged),
                "assistance_rate": assistance_rate,
                "rating": rating,
                "label_source": "synthetic_counterfactual",
            }
        )

        for game_index in range(games_per_account):
            game_id = f"g_{account_index:04d}_{game_index:02d}"
            played_at = start + timedelta(days=game_index * 4 + account_index % 31)
            for move_index in range(moves_per_game):
                ply = 2 * move_index + 1
                phase = str(PHASES[min(2, move_index // max(1, moves_per_game // 3))])
                complexity = float(np.clip(rng.beta(2.2, 2.4), 0.03, 0.99))
                injected = bool(is_assisted and rng.random() < assistance_rate and move_index >= 5)

                human_match_probability = np.clip(0.16 + 0.36 * skill - 0.17 * complexity, 0.05, 0.64)
                engine_match = bool(injected or rng.random() < human_match_probability)
                if engine_match:
                    move_rank = 1
                    cp_loss = float(abs(rng.normal(1.8 if injected else 5.5, 3.0)))
                else:
                    move_rank = int(rng.choice([2, 3, 4, 5, 6], p=[0.28, 0.24, 0.20, 0.16, 0.12]))
                    cp_loss = float(rng.gamma(2.1, 14 * (1.15 - 0.55 * skill)) * (0.75 + complexity))

                base_time = {"blitz": 4.0, "rapid": 12.0, "classical": 34.0}[speed]
                if injected:
                    move_time = float(np.clip(rng.normal(base_time * 0.72, base_time * 0.08), 0.3, None))
                else:
                    move_time = float(np.clip(rng.lognormal(np.log(base_time * (0.55 + complexity)), 0.42), 0.3, None))
                best_move = str(rng.choice(MOVE_POOL))
                chosen_move = best_move if engine_match else str(rng.choice(MOVE_POOL[MOVE_POOL != best_move]))
                move_rows.append(
                    {
                        "account_id": account_id,
                        "game_id": game_id,
                        "played_at": played_at.isoformat(),
                        "ply": ply,
                        "rating": rating + int(rng.normal(0, 18)),
                        "speed": speed,
                        "phase": phase,
                        "move_uci": chosen_move,
                        "best_move_uci": best_move,
                        "move_rank": move_rank,
                        "cp_loss": cp_loss,
                        "complexity": complexity,
                        "move_time_s": move_time,
                        "clock_s": max(0.0, base_time * 50 - move_index * move_time),
                        "legal_moves": int(rng.integers(12, 42)),
                        "engine_match": engine_match,
                        "injected": injected,
                    }
                )
    return pd.DataFrame(move_rows), pd.DataFrame(account_rows)
