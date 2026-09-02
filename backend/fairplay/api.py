from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from fairplay.config import settings
from fairplay.storage import ReviewStore


class DecisionRequest(BaseModel):
    decision: Literal["clear", "insufficient", "escalate"]
    reason: str = Field(min_length=3, max_length=500)
    reviewer: str = Field(default="demo-reviewer", min_length=2, max_length=80)


def _read_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def create_app(artifacts_dir: Path | None = None, database_path: Path | None = None) -> FastAPI:
    artifacts = artifacts_dir or settings.artifacts_dir
    store = ReviewStore(database_path or settings.database_path)
    app = FastAPI(
        title="FairPlay Review API",
        version="0.1.0",
        description="Calibrated risk ranking for human review. This API never bans accounts.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "artifacts_ready": (artifacts / "cases.json").exists()}

    @app.get("/api/v1/summary")
    def summary() -> dict[str, object]:
        manifest = _read_json(artifacts / "manifest.json", {})
        metrics = _read_json(artifacts / "metrics.json", {})
        decisions = store.all()
        return {
            "manifest": manifest,
            "metrics": metrics,
            "reviewed": len(decisions),
            "decision_counts": {
                decision: sum(item["decision"] == decision for item in decisions.values())
                for decision in ["clear", "insufficient", "escalate"]
            },
        }

    @app.get("/api/v1/cases")
    def list_cases(
        status: Literal["all", "pending", "reviewed"] = "all",
        limit: int = Query(default=50, ge=1, le=500),
    ) -> list[dict[str, object]]:
        cases = _read_json(artifacts / "cases.json", [])
        if not isinstance(cases, list):
            raise HTTPException(500, "Invalid cases artifact")
        decisions = store.all()
        output: list[dict[str, object]] = []
        for case in cases:
            account_id = str(case["account_id"])
            decision = decisions.get(account_id)
            if status == "pending" and decision:
                continue
            if status == "reviewed" and not decision:
                continue
            output.append({**case, "review": decision})
        return output[:limit]

    @app.get("/api/v1/cases/{account_id}")
    def get_case(account_id: str) -> dict[str, object]:
        cases = _read_json(artifacts / "cases.json", [])
        case = next((item for item in cases if item.get("account_id") == account_id), None)
        if case is None:
            raise HTTPException(404, "Case not found")
        return {**case, "review": store.all().get(account_id)}

    @app.post("/api/v1/cases/{account_id}/decision")
    def decide(account_id: str, request: DecisionRequest) -> dict[str, str]:
        cases = _read_json(artifacts / "cases.json", [])
        if not any(item.get("account_id") == account_id for item in cases):
            raise HTTPException(404, "Case not found")
        return store.upsert(account_id, request.decision, request.reason, request.reviewer)

    return app


app = create_app()
