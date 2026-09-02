import pandas as pd
import pytest

from fairplay.policy import select_top_k


def test_top_k_respects_budget_and_threshold():
    scored = pd.DataFrame(
        {"account_id": ["c", "a", "b"], "risk_score": [0.2, 0.9, 0.7]}
    )
    result = select_top_k(scored, k=2, minimum_score=0.5)
    assert result["account_id"].tolist() == ["a", "b"]
    assert result["rank"].tolist() == [1, 2]


def test_top_k_rejects_zero_budget():
    with pytest.raises(ValueError):
        select_top_k(pd.DataFrame({"account_id": [], "risk_score": []}), k=0)
