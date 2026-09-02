from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import chess
import chess.engine
import chess.pgn

from fairplay.domain import MoveSignal


@dataclass(frozen=True)
class EngineConfig:
    binary: str
    nodes: int = 50_000
    multipv: int = 5


def _phase(board: chess.Board) -> str:
    non_pawn_material = sum(
        len(board.pieces(piece, color)) * value
        for piece, value in [(chess.KNIGHT, 3), (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9)]
        for color in chess.COLORS
    )
    if board.fullmove_number <= 10:
        return "opening"
    return "endgame" if non_pawn_material <= 18 else "middlegame"


class StockfishAnalyzer:
    """Node-limited, multi-PV analyzer with explicit engine provenance."""

    def __init__(self, config: EngineConfig):
        if not Path(config.binary).exists():
            raise FileNotFoundError(f"Stockfish not found: {config.binary}")
        self.config = config

    def analyze_game(
        self,
        game: chess.pgn.Game,
        account_id: str,
        game_id: str,
        player_color: chess.Color,
        rating: int,
        speed: str,
        played_at: str,
    ) -> Iterable[MoveSignal]:
        board = game.board()
        previous_clock: float | None = None
        increment = _increment_seconds(game.headers.get("TimeControl", ""))
        with chess.engine.SimpleEngine.popen_uci(self.config.binary) as engine:
            for ply, node in enumerate(game.mainline(), start=1):
                move = node.move
                if board.turn != player_color:
                    board.push(move)
                    continue
                legal_moves = board.legal_moves.count()
                if ply <= 10 or legal_moves <= 1:
                    board.push(move)
                    previous_clock = node.clock()
                    continue
                infos = engine.analyse(
                    board,
                    chess.engine.Limit(nodes=self.config.nodes),
                    multipv=self.config.multipv,
                )
                best_score = infos[0]["score"].pov(board.turn).score(mate_score=100_000)
                best_move = infos[0]["pv"][0]
                ranks = {info["pv"][0]: index + 1 for index, info in enumerate(infos) if info.get("pv")}
                chosen_rank = ranks.get(move, self.config.multipv + 1)
                chosen_info = next((info for info in infos if info.get("pv") and info["pv"][0] == move), None)
                if chosen_info is None:
                    chosen_info = engine.analyse(
                        board,
                        chess.engine.Limit(nodes=max(10_000, self.config.nodes // 2)),
                        root_moves=[move],
                    )
                chosen_score = chosen_info["score"].pov(board.turn).score(mate_score=100_000)
                cp_loss = max(0.0, float((best_score or 0) - (chosen_score or 0)))
                score_gap = 0.0
                if len(infos) > 1:
                    second = infos[1]["score"].pov(board.turn).score(mate_score=100_000)
                    score_gap = abs(float((best_score or 0) - (second or 0)))
                complexity = min(1.0, 0.55 * legal_moves / 45 + 0.45 * max(0.0, 1 - score_gap / 120))
                clock = node.clock()
                move_time = 0.0 if previous_clock is None or clock is None else max(0.0, previous_clock + increment - clock)
                yield MoveSignal(
                    account_id=account_id,
                    game_id=game_id,
                    played_at=played_at,
                    ply=ply,
                    rating=rating,
                    speed=speed,
                    phase=_phase(board),
                    move_uci=move.uci(),
                    best_move_uci=best_move.uci(),
                    move_rank=chosen_rank,
                    cp_loss=cp_loss,
                    complexity=complexity,
                    move_time_s=move_time,
                    clock_s=float(clock or 0.0),
                    legal_moves=legal_moves,
                    engine_match=move == best_move,
                )
                board.push(move)
                previous_clock = clock


def _increment_seconds(time_control: str) -> float:
    if "+" not in time_control:
        return 0.0
    try:
        return float(time_control.split("+", 1)[1])
    except ValueError:
        return 0.0
