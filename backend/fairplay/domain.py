from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MoveSignal:
    account_id: str
    game_id: str
    played_at: str
    ply: int
    rating: int
    speed: str
    phase: str
    move_uci: str
    best_move_uci: str
    move_rank: int
    cp_loss: float
    complexity: float
    move_time_s: float
    clock_s: float
    legal_moves: int
    engine_match: bool
    injected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewCase:
    account_id: str
    rank: int
    risk_score: float
    confidence_band: str
    games_analyzed: int
    moves_analyzed: int
    rating: int
    dominant_speed: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
