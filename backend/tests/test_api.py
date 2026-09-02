import json

from fastapi.testclient import TestClient

from fairplay.api import create_app


def test_reviewer_can_record_a_decision(tmp_path):
    case = {
        "account_id": "acct_demo",
        "rank": 1,
        "risk_score": 0.91,
        "confidence_band": "very_high",
        "games_analyzed": 5,
        "moves_analyzed": 50,
        "rating": 1700,
        "dominant_speed": "rapid",
        "evidence": {"timeline": []},
    }
    (tmp_path / "cases.json").write_text(json.dumps([case]))
    (tmp_path / "manifest.json").write_text(json.dumps({"review_budget": 1}))
    app = create_app(tmp_path, tmp_path / "reviews.sqlite3")
    client = TestClient(app)
    response = client.post(
        "/api/v1/cases/acct_demo/decision",
        json={"decision": "escalate", "reason": "Independent review required", "reviewer": "test"},
    )
    assert response.status_code == 200
    reviewed = client.get("/api/v1/cases?status=reviewed").json()
    assert reviewed[0]["review"]["decision"] == "escalate"
