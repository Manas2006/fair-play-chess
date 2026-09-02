from __future__ import annotations

from pathlib import Path

import zstandard as zstd

from fairplay.realdata import (
    _speed_from_time_control,
    build_cohort,
    hash_account_id,
    iter_raw_games,
)


def _game(white: str, black: str, moves: str = '1. e4 { [%clk 0:03:00] } e5 { [%clk 0:03:00] } 1-0') -> str:
    return (
        f'[Event "Rated Blitz game"]\n'
        f'[Site "https://lichess.org/abcd1234"]\n'
        f'[White "{white}"]\n'
        f'[Black "{black}"]\n'
        f'[Result "1-0"]\n'
        f'[WhiteElo "1800"]\n'
        f'[BlackElo "1790"]\n'
        f'[TimeControl "180+2"]\n'
        f'\n{moves}\n\n'
    )


def _write_zst(path: Path, text: str, truncate_bytes: int = 0) -> Path:
    compressed = zstd.ZstdCompressor().compress(text.encode())
    if truncate_bytes:
        compressed = compressed[:-truncate_bytes]
    path.write_bytes(compressed)
    return path


def test_iter_raw_games_yields_complete_games(tmp_path: Path) -> None:
    text = _game("alice", "bob") + _game("carol", "dave") + _game("erin", "frank")
    games = list(iter_raw_games(_write_zst(tmp_path / "s.pgn.zst", text)))
    # The final game is always dropped as potentially truncated.
    assert len(games) == 2
    headers, body = games[0]
    assert headers["White"] == "alice"
    assert "%clk" in body


def test_iter_raw_games_survives_truncated_stream(tmp_path: Path) -> None:
    # Real slices decode block-by-block; simulate with concatenated frames, last one cut.
    compressor = zstd.ZstdCompressor()
    frames = [
        compressor.compress("".join(_game(f"alice{f}{i}", f"bob{f}{i}") for i in range(10)).encode())
        for f in range(5)
    ]
    payload = b"".join(frames[:-1]) + frames[-1][:-20]
    path = tmp_path / "t.pgn.zst"
    path.write_bytes(payload)
    games = list(iter_raw_games(path))
    assert 30 <= len(games) < 50
    assert all(h["White"].startswith("alice") for h, _ in games)


def test_speed_filter_drops_bullet() -> None:
    assert _speed_from_time_control("60+0") is None
    assert _speed_from_time_control("180+2") == "blitz"
    assert _speed_from_time_control("600+5") == "rapid"
    assert _speed_from_time_control("1800+20") == "classical"
    assert _speed_from_time_control("-") is None


def test_build_cohort_matches_controls_by_rating_and_speed() -> None:
    def entry(games: int, rating: int, speed: str) -> dict[str, object]:
        return {"games": games, "rating_sum": rating * games, "speeds": {speed: games}}

    stats = {
        "cheater": entry(6, 2000, "blitz"),
        "near": entry(6, 1990, "blitz"),
        "far": entry(6, 1200, "blitz"),
        "wrong_speed": entry(6, 2000, "rapid"),
        "too_few": entry(2, 2000, "blitz"),
        "closed": entry(6, 2005, "blitz"),
    }
    labels = {
        "cheater": {"tosViolation": True},
        "near": {"tosViolation": False},
        "far": {"tosViolation": False},
        "wrong_speed": {"tosViolation": False},
        "too_few": {"tosViolation": False},
        "closed": {"tosViolation": False, "disabled": True},
    }
    cohort = build_cohort(stats, labels, min_games=4, controls_per_positive=2)
    assert cohort["positives"] == ["cheater"]
    # Same-speed nearest rating first; disabled and low-activity accounts excluded.
    assert cohort["controls"] == ["near", "far"]


def test_hash_account_id_is_stable_and_anonymous() -> None:
    assert hash_account_id("SomePlayer") == hash_account_id("someplayer")
    assert "someplayer" not in hash_account_id("someplayer")
    assert hash_account_id("someplayer").startswith("acct_")
