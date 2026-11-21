"""The legacy bot profile's historical risk heuristic."""
import pytest

from backend.api.bots import _compute_risk_rating


@pytest.mark.parametrize(
    ("sharpe", "drawdown", "runs", "rating"),
    [
        (1.2, -0.80, 5, "High"),
        (1.2, 0.0, 5, "Low"),
        (1.0, -0.15, 1, "Low"),
        (1.0, -0.1501, 1, "Medium"),
        (0.3, -0.30, 1, "Medium"),
        (0.3, -0.3001, 1, "High"),
        (0.2999, -0.01, 1, "High"),
        (None, -0.1, 1, "Unrated"),
        (1.2, None, 1, "Unrated"),
        (1.2, -0.1, 0, "Unrated"),
    ],
)
def test_historical_risk_uses_drawdown_magnitude_and_requires_evidence(
    sharpe: float | None, drawdown: float | None, runs: int, rating: str
) -> None:
    assert _compute_risk_rating(sharpe, drawdown, runs) == rating
