"""Real-data pipeline: Lichess dump slice -> proxy labels -> Stockfish evidence -> ranked queue.

Every stage caches its output under ``data/processed/real`` so the expensive steps
(label fetching, engine analysis) never re-run unnecessarily. Account IDs are hashed in
every published artifact; the username map stays in a private, git-ignored file.

Labels are the public ``tosViolation`` flag: a noisy terms-of-service proxy, not a
verified engine-cheating label. Accounts that are closed without a mark are excluded
as ambiguous rather than treated as clean.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import time
from typing import Iterator
from urllib.request import Request, urlopen

import chess
import chess.pgn
import pandas as pd
import zstandard as zstd

from fairplay.engine import EngineConfig, StockfishAnalyzer
from fairplay.features import aggregate_account_features, evidence_for_account
from fairplay.lichess import LichessPublicClient, open_pgn_zst, ssl_context
from fairplay.model import train_model
from fairplay.policy import select_top_k

DUMP_URL = "https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"
_HEADER_RE = re.compile(r'^\[(\w+) "(.*)"\]')
_RESULTS = {"1-0", "0-1", "1/2-1/2"}


def hash_account_id(username: str) -> str:
    return "acct_" + hashlib.sha256(f"fairplay-real-{username.lower()}".encode()).hexdigest()[:10]


def download_slice(month: str, slice_mb: int, destination: Path, max_attempts: int = 30) -> Path:
    """Fetch only the first ``slice_mb`` MB of a monthly dump via HTTP range requests.

    Resumes from the partial file after connection stalls instead of restarting.
    """
    target_bytes = slice_mb * 1024 * 1024
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = DUMP_URL.format(month=month)
    written = destination.stat().st_size if destination.exists() else 0
    for attempt in range(max_attempts):
        if written >= target_bytes:
            return destination
        request = Request(
            url,
            headers={
                "Range": f"bytes={written}-{target_bytes - 1}",
                "User-Agent": "fairplay-portfolio-research/0.1",
            },
        )
        try:
            with urlopen(request, timeout=60, context=ssl_context()) as response, destination.open("ab") as output:
                while written < target_bytes and (chunk := response.read(1 << 20)):
                    output.write(chunk)
                    written += len(chunk)
                    if written % (10 << 20) < (1 << 20):
                        print(f"download: {written >> 20}/{slice_mb} MB")
        except (TimeoutError, OSError) as exc:
            print(f"download: retrying after {type(exc).__name__} at {written >> 20} MB")
            time.sleep(min(30, 2 ** min(attempt, 5)))
    raise RuntimeError(f"Slice download failed after {max_attempts} attempts: {written} bytes from {url}")


def iter_raw_games(path: Path) -> Iterator[tuple[dict[str, str], str]]:
    """Yield (headers, full PGN text) per game from a possibly-truncated .zst slice.

    The final game is dropped: the range request usually cuts mid-game.
    """
    pending: tuple[dict[str, str], str] | None = None
    headers: dict[str, str] = {}
    lines: list[str] = []
    try:
        with open_pgn_zst(path) as stream:
            for line in stream:
                if line.startswith("[Event ") and lines and any(not l.startswith("[") and l.strip() for l in lines):
                    if pending is not None:
                        yield pending
                    pending = (headers, "".join(lines))
                    headers = {}
                    lines = []
                match = _HEADER_RE.match(line)
                if match:
                    headers[match.group(1)] = match.group(2)
                lines.append(line)
    except (zstd.ZstdError, EOFError, OSError):
        pass  # truncated slice: keep whatever full games we saw
    if pending is not None:
        yield pending


def _speed_from_time_control(time_control: str) -> str | None:
    try:
        base = int(time_control.split("+", 1)[0])
    except ValueError:
        return None
    if base < 180:
        return None  # bullet: too noisy for engine-assistance evidence
    if base < 480:
        return "blitz"
    if base < 1500:
        return "rapid"
    return "classical"


def scan_players(slice_path: Path, cache_path: Path) -> dict[str, dict[str, object]]:
    """First pass: per-player game counts, ratings, and speeds from raw headers only."""
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    stats: dict[str, dict[str, object]] = {}
    games_seen = 0
    for headers, text in iter_raw_games(slice_path):
        if headers.get("Result") not in _RESULTS:
            continue
        speed = _speed_from_time_control(headers.get("TimeControl", ""))
        if speed is None or "%clk" not in text:
            continue
        games_seen += 1
        for side, elo_key, title_key in (("White", "WhiteElo", "WhiteTitle"), ("Black", "BlackElo", "BlackTitle")):
            username = headers.get(side, "")
            if not username or username == "?" or headers.get(title_key) == "BOT":
                continue
            try:
                rating = int(headers.get(elo_key, ""))
            except ValueError:
                continue
            entry = stats.setdefault(username.lower(), {"games": 0, "rating_sum": 0, "speeds": {}})
            entry["games"] = int(entry["games"]) + 1
            entry["rating_sum"] = int(entry["rating_sum"]) + rating
            speeds = entry["speeds"]
            speeds[speed] = int(speeds.get(speed, 0)) + 1
    if not stats:
        raise RuntimeError(f"No usable games found in {slice_path}")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(stats), encoding="utf-8")
    print(f"scan: {games_seen} usable games, {len(stats)} players")
    return stats


def fetch_labels(
    usernames: list[str],
    cache_path: Path,
    target_positives: int,
    max_players: int,
    token: str | None = None,
) -> dict[str, dict[str, object]]:
    """Batch usernames through the public bulk-user API until enough proxy positives are found."""
    labels: dict[str, dict[str, object]] = {}
    if cache_path.exists():
        labels = json.loads(cache_path.read_text(encoding="utf-8"))
    client = LichessPublicClient(token=token)
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    remaining = [name for name in usernames[:max_players] if name not in labels]
    positives = sum(1 for item in labels.values() if item.get("tosViolation"))
    for start in range(0, len(remaining), 300):
        if positives >= target_positives:
            break
        batch = remaining[start : start + 300]
        for attempt in range(3):
            try:
                users = client.users_by_id(batch)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(30)
        returned = {str(user.get("id", "")).lower() for user in users}
        for user in users:
            user_id = str(user.get("id", "")).lower()
            labels[user_id] = {
                "tosViolation": bool(user.get("tosViolation", False)),
                "disabled": bool(user.get("disabled", False)),
                "fetched_at": fetched_at,
            }
        for name in batch:
            if name not in returned:
                labels[name] = {"missing": True, "fetched_at": fetched_at}
        positives = sum(1 for item in labels.values() if item.get("tosViolation"))
        cache_path.write_text(json.dumps(labels), encoding="utf-8")
        print(f"labels: {len(labels)} fetched, {positives} proxy positives")
    return labels


def _dominant_speed(entry: dict[str, object]) -> str:
    speeds: dict[str, int] = entry["speeds"]  # type: ignore[assignment]
    return max(speeds, key=lambda key: speeds[key])


def build_cohort(
    stats: dict[str, dict[str, object]],
    labels: dict[str, dict[str, object]],
    min_games: int,
    controls_per_positive: int,
) -> dict[str, list[str]]:
    """All eligible proxy positives plus rating/speed/activity-matched unlabeled controls."""
    positives: list[str] = []
    control_pool: list[str] = []
    for username, label in labels.items():
        entry = stats.get(username)
        if entry is None or int(entry["games"]) < min_games:
            continue
        if label.get("tosViolation"):
            positives.append(username)
        elif not label.get("disabled") and not label.get("missing"):
            control_pool.append(username)

    def rating_of(name: str) -> float:
        entry = stats[name]
        return int(entry["rating_sum"]) / max(int(entry["games"]), 1)

    controls: list[str] = []
    used: set[str] = set()
    for positive in positives:
        candidates = sorted(
            (name for name in control_pool if name not in used),
            key=lambda name: (
                _dominant_speed(stats[name]) != _dominant_speed(stats[positive]),
                abs(rating_of(name) - rating_of(positive)),
                abs(int(stats[name]["games"]) - int(stats[positive]["games"])),
            ),
        )
        for name in candidates[:controls_per_positive]:
            used.add(name)
            controls.append(name)
    return {"positives": positives, "controls": controls}


def extract_cohort_games(
    slice_path: Path,
    cohort_usernames: set[str],
    max_games_per_account: int,
    cache_path: Path,
) -> dict[str, list[str]]:
    """Second pass: collect full PGN text for cohort accounts only."""
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    games: dict[str, list[str]] = {name: [] for name in cohort_usernames}
    for headers, text in iter_raw_games(slice_path):
        if headers.get("Result") not in _RESULTS:
            continue
        if _speed_from_time_control(headers.get("TimeControl", "")) is None or "%clk" not in text:
            continue
        for side in ("White", "Black"):
            username = headers.get(side, "").lower()
            bucket = games.get(username)
            if bucket is not None and len(bucket) < max_games_per_account:
                bucket.append(text)
    games = {name: texts for name, texts in games.items() if texts}
    cache_path.write_text(json.dumps(games), encoding="utf-8")
    return games


def _analyze_account(args: tuple[str, list[str], str, int, int]) -> list[dict[str, object]]:
    username, pgn_texts, stockfish_binary, nodes, multipv = args
    analyzer = StockfishAnalyzer(EngineConfig(stockfish_binary, nodes, multipv))
    account_id = hash_account_id(username)
    rows: list[dict[str, object]] = []
    for text in pgn_texts:
        game = chess.pgn.read_game(StringIO(text))
        if game is None:
            continue
        white = game.headers.get("White", "").lower()
        color = chess.WHITE if white == username else chess.BLACK
        elo_key = "WhiteElo" if color == chess.WHITE else "BlackElo"
        try:
            rating = int(game.headers.get(elo_key, ""))
        except ValueError:
            rating = 1500
        speed = _speed_from_time_control(game.headers.get("TimeControl", "")) or "unknown"
        site = game.headers.get("Site", "unknown")
        played_at = f"{game.headers.get('UTCDate', '')}T{game.headers.get('UTCTime', '')}Z"
        try:
            signals = analyzer.analyze_game(
                game=game,
                account_id=account_id,
                game_id=site.rsplit("/", 1)[-1][:8],
                player_color=color,
                rating=rating,
                speed=speed,
                played_at=played_at,
            )
            rows.extend(signal.to_dict() for signal in signals)
        except chess.engine.EngineError:
            continue
    return rows


def analyze_cohort(
    games: dict[str, list[str]],
    stockfish_binary: str,
    nodes: int,
    multipv: int,
    workers: int,
    cache_path: Path,
) -> pd.DataFrame:
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    tasks = [(username, texts, stockfish_binary, nodes, multipv) for username, texts in sorted(games.items())]
    rows: list[dict[str, object]] = []
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_analyze_account, task) for task in tasks]
        for future in as_completed(futures):
            rows.extend(future.result())
            done += 1
            if done % 10 == 0 or done == len(tasks):
                print(f"engine: {done}/{len(tasks)} accounts analyzed")
    moves = pd.DataFrame(rows)
    if moves.empty:
        raise RuntimeError("Stockfish analysis produced no move signals")
    moves.to_parquet(cache_path, index=False)
    return moves


@dataclass(frozen=True)
class RealRunConfig:
    month: str = "2025-06"
    slice_mb: int = 150
    min_games: int = 4
    target_positives: int = 40
    controls_per_positive: int = 3
    max_label_players: int = 30_000
    max_games_per_account: int = 6
    review_budget: int = 25
    nodes: int = 30_000
    multipv: int = 5
    workers: int = 6
    seed: int = 7
    token: str | None = None


def run_real_pipeline(
    artifacts_dir: Path,
    work_dir: Path,
    raw_dir: Path,
    stockfish_binary: str,
    config: RealRunConfig,
) -> dict[str, object]:
    work_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    slice_path = download_slice(
        config.month, config.slice_mb, raw_dir / f"lichess_{config.month}_{config.slice_mb}mb.pgn.zst"
    )
    stats = scan_players(slice_path, work_dir / "players.json")
    ranked = sorted(
        (name for name, entry in stats.items() if int(entry["games"]) >= config.min_games),
        key=lambda name: -int(stats[name]["games"]),
    )
    labels_raw = fetch_labels(
        ranked,
        work_dir / "labels.json",
        target_positives=config.target_positives,
        max_players=config.max_label_players,
        token=config.token,
    )
    cohort = build_cohort(stats, labels_raw, config.min_games, config.controls_per_positive)
    positives, controls = cohort["positives"], cohort["controls"]
    if len(positives) < 10 or len(controls) < 10:
        raise RuntimeError(
            f"Cohort too small to train: {len(positives)} positives, {len(controls)} controls. "
            "Increase --slice-mb, --max-label-players, or lower --min-games."
        )
    (work_dir / "cohort.json").write_text(json.dumps(cohort, indent=2), encoding="utf-8")
    print(f"cohort: {len(positives)} proxy positives, {len(controls)} matched controls")

    games = extract_cohort_games(
        slice_path, set(positives) | set(controls), config.max_games_per_account, work_dir / "cohort_games.json"
    )
    moves = analyze_cohort(
        games, stockfish_binary, config.nodes, config.multipv, config.workers, work_dir / "real_moves.parquet"
    )

    id_map = {hash_account_id(name): name for name in games}
    (work_dir / "id_map_private.json").write_text(json.dumps(id_map, indent=2), encoding="utf-8")

    labels = pd.DataFrame(
        [
            {
                "account_id": hash_account_id(name),
                "label": int(name in set(positives)),
                "assistance_rate": 0.0,  # unknown for real accounts; kept for schema compatibility
            }
            for name in games
        ]
    )
    features = aggregate_account_features(moves)
    labels = labels[labels["account_id"].isin(features["account_id"])].reset_index(drop=True)
    bundle, scored, metrics = train_model(features, labels, seed=config.seed)
    metrics["warning"] = (
        "Labels are the public tosViolation flag: a noisy terms-of-service proxy, not verified "
        "engine cheating. Controls are unlabeled, not verified clean."
    )
    candidates = select_top_k(scored[scored["split"] == "test"], config.review_budget)

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
                "proxy_label": bool(row.label),
                "label_source": "lichess_tosViolation_proxy",
                "evidence": evidence_for_account(moves, row.account_id),
            }
        )

    moves.to_parquet(artifacts_dir / "real_moves.parquet", index=False)
    features.to_parquet(artifacts_dir / "account_features.parquet", index=False)
    labels.to_csv(artifacts_dir / "real_labels.csv", index=False)
    bundle.save(artifacts_dir / "risk_model.joblib")
    manifest = {
        "data_mode": "real_lichess_tos_proxy",
        "source": DUMP_URL.format(month=config.month),
        "slice_mb": config.slice_mb,
        "accounts": int(len(labels)),
        "proxy_positives": int(labels["label"].sum()),
        "games": int(moves["game_id"].nunique()),
        "moves": int(len(moves)),
        "review_budget": config.review_budget,
        "queued_cases": len(cases),
        "model": "HistGradientBoostingClassifier + sigmoid calibration",
        "engine": {"binary": stockfish_binary, "nodes": config.nodes, "multipv": config.multipv},
        "seed": config.seed,
        "privacy": "Account IDs are hashed; the username map stays in a private git-ignored file.",
        "safety": "Scores route cases to human review and never trigger enforcement.",
    }
    (artifacts_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (artifacts_dir / "cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    (artifacts_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"manifest": manifest, "metrics": metrics}
