from __future__ import annotations

import argparse
import json
from pathlib import Path

from fairplay.analyze import analyze_player_pgn
from fairplay.config import settings
from fairplay.lichess import export_metadata_jsonl
from fairplay.pipeline import run_demo_pipeline


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


if __name__ == "__main__":
    main()
