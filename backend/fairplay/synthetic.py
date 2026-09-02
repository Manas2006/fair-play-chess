from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

import chess
import numpy as np
import pandas as pd


SPEEDS = np.array(["blitz", "rapid", "classical"])
PHASES = np.array(["opening", "middlegame", "endgame"])
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def _account_id(index: int) -> str:
    return "acct_" + hashlib.sha256(f"fairplay-demo-{index}".encode()).hexdigest()[:10]


def _move_priority(board: chess.Board, move: chess.Move) -> float:
    attacker = board.piece_at(move.from_square)
    victim = board.piece_at(move.to_square)
    capture_value = PIECE_VALUES.get(victim.piece_type, 1) if victim else (1 if board.is_en_passant(move) else 0)
    attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
    file_index = chess.square_file(move.to_square)
    rank_index = chess.square_rank(move.to_square)
    center = 3.5 - (abs(file_index - 3.5) + abs(rank_index - 3.5)) / 2
    return (
        capture_value * 12
        - attacker_value * 0.18
        + (PIECE_VALUES.get(move.promotion, 0) * 9 if move.promotion else 0)
        + (2.8 if board.gives_check(move) else 0)
        + (1.2 if board.is_castling(move) else 0)
        + center * 0.18
    )


def _ranked_moves(board: chess.Board, rng: np.random.Generator) -> list[chess.Move]:
    legal = list(board.legal_moves)
    return sorted(legal, key=lambda move: _move_priority(board, move) + float(rng.uniform(0, 0.16)), reverse=True)


def _material_eval_cp(board: chess.Board, rng: np.random.Generator) -> float:
    material = 0
    for piece_type, value in PIECE_VALUES.items():
        material += value * (len(board.pieces(piece_type, chess.WHITE)) - len(board.pieces(piece_type, chess.BLACK)))
    return float(np.clip(material * 100 + rng.normal(0, 34), -1200, 1200))


def _phase(board: chess.Board) -> str:
    if board.fullmove_number <= 10:
        return "opening"
    pieces = sum(len(board.pieces(piece_type, color)) for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT] for color in chess.COLORS)
    return "endgame" if pieces <= 8 else "middlegame"


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
            board = chess.Board()
            for move_index in range(moves_per_game):
                if board.is_game_over():
                    break
                ply = board.ply() + 1
                phase = _phase(board)
                complexity = float(np.clip(rng.beta(2.2, 2.4), 0.03, 0.99))
                injected = bool(is_assisted and rng.random() < assistance_rate and move_index >= 5)

                human_match_probability = np.clip(0.16 + 0.36 * skill - 0.17 * complexity, 0.05, 0.64)
                ranked_moves = _ranked_moves(board, rng)
                best_move = ranked_moves[0]
                engine_match = bool(injected or rng.random() < human_match_probability or len(ranked_moves) == 1)
                if engine_match:
                    move_rank = 1
                    cp_loss = float(abs(rng.normal(1.8 if injected else 5.5, 3.0)))
                    chosen_move = best_move
                else:
                    move_rank = int(min(len(ranked_moves), rng.choice([2, 3, 4, 5, 6], p=[0.28, 0.24, 0.20, 0.16, 0.12])))
                    chosen_move = ranked_moves[move_rank - 1]
                    cp_loss = float(rng.gamma(2.1, 14 * (1.15 - 0.55 * skill)) * (0.75 + complexity))

                base_time = {"blitz": 4.0, "rapid": 12.0, "classical": 34.0}[speed]
                if injected:
                    move_time = float(np.clip(rng.normal(base_time * 0.72, base_time * 0.08), 0.3, None))
                else:
                    move_time = float(np.clip(rng.lognormal(np.log(base_time * (0.55 + complexity)), 0.42), 0.3, None))
                fen_before = board.fen()
                chosen_san = board.san(chosen_move)
                best_san = board.san(best_move)
                legal_moves = len(ranked_moves)
                board.push(chosen_move)
                fen_after = board.fen()
                eval_cp = _material_eval_cp(board, rng)
                move_rows.append(
                    {
                        "account_id": account_id,
                        "game_id": game_id,
                        "played_at": played_at.isoformat(),
                        "ply": ply,
                        "rating": rating + int(rng.normal(0, 18)),
                        "speed": speed,
                        "phase": phase,
                        "move_uci": chosen_move.uci(),
                        "move_san": chosen_san,
                        "best_move_uci": best_move.uci(),
                        "best_move_san": best_san,
                        "fen_before": fen_before,
                        "fen_after": fen_after,
                        "eval_cp": eval_cp,
                        "player_color": "white",
                        "move_rank": move_rank,
                        "cp_loss": cp_loss,
                        "complexity": complexity,
                        "move_time_s": move_time,
                        "clock_s": max(0.0, base_time * 50 - move_index * move_time),
                        "legal_moves": legal_moves,
                        "engine_match": engine_match,
                        "injected": injected,
                    }
                )
                if board.is_game_over():
                    break
                opponent_moves = _ranked_moves(board, rng)
                opponent_pool = opponent_moves[: min(8, len(opponent_moves))]
                board.push(opponent_pool[int(rng.integers(0, len(opponent_pool)))])
    return pd.DataFrame(move_rows), pd.DataFrame(account_rows)
