from __future__ import annotations

from contextlib import contextmanager
from io import TextIOWrapper
import json
from pathlib import Path
import ssl
import time
from typing import Iterator, TextIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import chess.pgn
import zstandard as zstd


def ssl_context() -> ssl.SSLContext:
    """Default context, but fall back to certifi roots for Pythons without system CAs."""
    try:
        context = ssl.create_default_context()
        if not context.get_ca_certs():
            raise ssl.SSLError("no system CA certificates")
        return context
    except (ssl.SSLError, OSError):
        import certifi

        return ssl.create_default_context(cafile=certifi.where())


@contextmanager
def open_pgn_zst(path: Path) -> Iterator[TextIO]:
    """Stream a Lichess dump without expanding the archive on disk."""
    with path.open("rb") as compressed:
        # Official dumps are compressed with a long window (--long=31).
        decompressor = zstd.ZstdDecompressor(max_window_size=2**31)
        with decompressor.stream_reader(compressed) as reader:
            with TextIOWrapper(reader, encoding="utf-8", errors="replace") as text_stream:
                yield text_stream


def iter_games(path: Path, max_games: int | None = None) -> Iterator[chess.pgn.Game]:
    with open_pgn_zst(path) as stream:
        emitted = 0
        while max_games is None or emitted < max_games:
            game = chess.pgn.read_game(stream)
            if game is None:
                return
            if game.headers.get("Variant", "Standard") != "Standard":
                continue
            emitted += 1
            yield game


def export_metadata_jsonl(source: Path, destination: Path, max_games: int | None = None) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with destination.open("w", encoding="utf-8") as output:
        for game in iter_games(source, max_games=max_games):
            site = game.headers.get("Site", "")
            row = {
                "game_id": site.rsplit("/", 1)[-1][:8],
                "played_at": f"{game.headers.get('UTCDate', '')}T{game.headers.get('UTCTime', '')}Z",
                "white": game.headers.get("White"),
                "black": game.headers.get("Black"),
                "white_rating": _integer(game.headers.get("WhiteElo")),
                "black_rating": _integer(game.headers.get("BlackElo")),
                "time_control": game.headers.get("TimeControl"),
                "opening": game.headers.get("Opening"),
                "result": game.headers.get("Result"),
                "plies": game.end().ply(),
            }
            output.write(json.dumps(row) + "\n")
            count += 1
    return count


class LichessPublicClient:
    """Small, bounded client for public profile labels; never attempts a full-site export."""

    def __init__(self, token: str | None = None, pause_seconds: float = 1.0):
        self.token = token
        self.pause_seconds = pause_seconds

    def users_by_id(self, user_ids: list[str]) -> list[dict[str, object]]:
        if len(user_ids) > 300:
            raise ValueError("Lichess /api/users accepts at most 300 IDs per request")
        body = ",".join(user_ids).encode()
        headers = {"Content-Type": "text/plain", "User-Agent": "fairplay-portfolio-research/0.1"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request("https://lichess.org/api/users", data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=30, context=ssl_context()) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 429:
                time.sleep(60)
            raise
        time.sleep(self.pause_seconds)
        return payload


def _integer(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
