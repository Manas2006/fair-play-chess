from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    project_root: Path
    artifacts_dir: Path
    database_path: Path
    stockfish_path: str | None
    stockfish_nodes: int
    stockfish_multipv: int

    @classmethod
    def load(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        artifacts_dir = Path(os.getenv("FAIRPLAY_ARTIFACTS_DIR", project_root / "artifacts"))
        return cls(
            project_root=project_root,
            artifacts_dir=artifacts_dir,
            database_path=Path(
                os.getenv("FAIRPLAY_DATABASE_PATH", artifacts_dir / "reviews.sqlite3")
            ),
            stockfish_path=os.getenv("STOCKFISH_PATH"),
            stockfish_nodes=int(os.getenv("STOCKFISH_NODES", "50000")),
            stockfish_multipv=int(os.getenv("STOCKFISH_MULTIPV", "5")),
        )


settings = Settings.load()
