from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from io import TextIOWrapper
from pathlib import Path
from typing import Iterator, TextIO

import chess
import chess.pgn
import pandas as pd
import zstandard as zstd

from fairplay.domain import MoveSignal
from fairplay.engine import EngineConfig, StockfishAnalyzer


@contextmanager
def _open_pgn(path: Path) -> Iterator[TextIO]:
    if path.suffix == ".zst":
        with path.open("rb") as compressed:
            with zstd.ZstdDecompressor().stream_reader(compressed) as reader:
                with TextIOWrapper(reader, encoding="utf-8", errors="replace") as stream:
                    yield stream
    else:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            yield stream


def analyze_player_pgn(
    source: Path,
    destination: Path,
    username: str,
    stockfish_binary: str,
    nodes: int = 50_000,
    multipv: int = 5,
    max_games: int | None = None,
) -> int:
    analyzer = StockfishAnalyzer(EngineConfig(stockfish_binary, nodes, multipv))
    signals: list[MoveSignal] = []
    username_lower = username.lower()
    games = 0
    with _open_pgn(source) as stream:
        while max_games is None or games < max_games:
            game = chess.pgn.read_game(stream)
            if game is None:
                break
            white = game.headers.get("White", "")
            black = game.headers.get("Black", "")
            if white.lower() == username_lower:
                color = chess.WHITE
                rating = _int(game.headers.get("WhiteElo"), 1500)
            elif black.lower() == username_lower:
                color = chess.BLACK
                rating = _int(game.headers.get("BlackElo"), 1500)
            else:
                continue
            site = game.headers.get("Site", "unknown")
            game_id = site.rsplit("/", 1)[-1][:8]
            date = game.headers.get("UTCDate", "")
            time = game.headers.get("UTCTime", "")
            played_at = f"{date}T{time}Z" if date else datetime.now(timezone.utc).isoformat()
            speed = _speed(game.headers.get("TimeControl", ""))
            signals.extend(
                analyzer.analyze_game(
                    game=game,
                    account_id=username_lower,
                    game_id=game_id,
                    player_color=color,
                    rating=rating,
                    speed=speed,
                    played_at=played_at,
                )
            )
            games += 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([signal.to_dict() for signal in signals]).to_parquet(destination, index=False)
    return len(signals)


def _int(value: str | None, fallback: int) -> int:
    try:
        return int(value) if value else fallback
    except ValueError:
        return fallback


def _speed(time_control: str) -> str:
    try:
        base = int(time_control.split("+", 1)[0])
    except ValueError:
        return "unknown"
    if base < 180:
        return "bullet"
    if base < 480:
        return "blitz"
    if base < 1500:
        return "rapid"
    return "classical"
