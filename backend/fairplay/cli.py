from __future__ import annotations

import argparse
import json
from pathlib import Path

import os

from fairplay.analyze import analyze_player_pgn
from fairplay.config import settings
from fairplay.lichess import export_metadata_jsonl
from fairplay.pipeline import run_demo_pipeline
from fairplay.realdata import RealRunConfig, run_real_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="fairplay")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Generate data, train, calibrate, and rank a demo queue")
    demo.add_argument("--accounts", type=int, default=900)
    demo.add_argument("--games-per-account", type=int, default=10)
    demo.add_argument("--moves-per-game", type=int, default=22)
    demo.add_argument("--review-budget", type=int, default=50)
    demo.add_argument("--seed", type=int, default=7)

    ingest = subparsers.add_parser("ingest", help="Stream a Lichess .pgn.zst dump into metadata JSONL")
    ingest.add_argument("source", type=Path)
    ingest.add_argument("destination", type=Path)
    ingest.add_argument("--max-games", type=int)

    analyze = subparsers.add_parser("analyze", help="Extract real Stockfish move features from a player's PGN")
    analyze.add_argument("source", type=Path)
    analyze.add_argument("destination", type=Path)
    analyze.add_argument("--username", required=True)
    analyze.add_argument("--stockfish", default=settings.stockfish_path)
    analyze.add_argument("--nodes", type=int, default=settings.stockfish_nodes)
    analyze.add_argument("--multipv", type=int, default=settings.stockfish_multipv)
    analyze.add_argument("--max-games", type=int)

    real = subparsers.add_parser(
        "real",
        help="End-to-end real pipeline: dump slice -> tosViolation proxy labels -> Stockfish -> ranked queue",
    )
    real.add_argument("--month", default="2025-06", help="Lichess dump month, YYYY-MM")
    real.add_argument("--slice-mb", type=int, default=150, help="How many MB of the dump to stream")
    real.add_argument("--min-games", type=int, default=4)
    real.add_argument("--target-positives", type=int, default=40)
    real.add_argument("--controls-per-positive", type=int, default=3)
    real.add_argument("--max-label-players", type=int, default=30_000)
    real.add_argument("--max-games-per-account", type=int, default=6)
    real.add_argument("--review-budget", type=int, default=25)
    real.add_argument("--nodes", type=int, default=30_000)
    real.add_argument("--multipv", type=int, default=5)
    real.add_argument("--workers", type=int, default=6)
    real.add_argument("--seed", type=int, default=7)
    real.add_argument("--stockfish", default=settings.stockfish_path)

    args = parser.parse_args()
    if args.command == "demo":
        result = run_demo_pipeline(
            artifacts_dir=settings.artifacts_dir,
            accounts=args.accounts,
            games_per_account=args.games_per_account,
            moves_per_game=args.moves_per_game,
            review_budget=args.review_budget,
            seed=args.seed,
        )
        print(json.dumps(result, indent=2))
    elif args.command == "ingest":
        count = export_metadata_jsonl(args.source, args.destination, max_games=args.max_games)
        print(json.dumps({"games_exported": count, "destination": str(args.destination)}))
    elif args.command == "analyze":
        if not args.stockfish:
            parser.error("--stockfish or STOCKFISH_PATH is required for real analysis")
        count = analyze_player_pgn(
            source=args.source,
            destination=args.destination,
            username=args.username,
            stockfish_binary=args.stockfish,
            nodes=args.nodes,
            multipv=args.multipv,
            max_games=args.max_games,
        )
        print(json.dumps({"move_signals": count, "destination": str(args.destination)}))
    elif args.command == "real":
        if not args.stockfish:
            parser.error("--stockfish or STOCKFISH_PATH is required for real analysis")
        result = run_real_pipeline(
            artifacts_dir=settings.artifacts_dir,
            work_dir=settings.project_root / "data" / "processed" / "real",
            raw_dir=settings.project_root / "data" / "raw",
            stockfish_binary=args.stockfish,
            config=RealRunConfig(
                month=args.month,
                slice_mb=args.slice_mb,
                min_games=args.min_games,
                target_positives=args.target_positives,
                controls_per_positive=args.controls_per_positive,
                max_label_players=args.max_label_players,
                max_games_per_account=args.max_games_per_account,
                review_budget=args.review_budget,
                nodes=args.nodes,
                multipv=args.multipv,
                workers=args.workers,
                seed=args.seed,
                token=os.getenv("LICHESS_TOKEN"),
            ),
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
