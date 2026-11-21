"""Simulated token trades must not give free tokens or split wallet updates."""
import math

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.db.models import DBToken, DBUser
from tests.test_governance_api import local_governance  # shared in-memory authenticated HTTP fixture


@pytest.fixture
def token_market(local_governance):
    post, engine = local_governance
    with Session(engine) as db:
        db.add(DBToken(bot_id="bot", holder_address="public_pool", holder_type="public", balance=700_000))
        db.commit()
    return post, engine


def balances(engine, identity: str) -> tuple[float, float, float | None]:
    with Session(engine) as db:
        user = db.get(DBUser, identity)
        pool = db.query(DBToken).filter_by(bot_id="bot", holder_address="public_pool").one()
        holding = db.query(DBToken).filter_by(bot_id="bot", holder_address=user.email).first()
        return user.wallet_balance, pool.balance, holding.balance if holding else None


@pytest.mark.parametrize("amount", [0, -1, 0.1, 0.5, True, False, math.nan, math.inf, -math.inf])
def test_purchase_requires_a_positive_whole_finite_token_count(token_market, amount: float) -> None:
    post, engine = token_market
    before = balances(engine, "empty")
    status, _ = post("/tokenomics/purchase", {"bot_id": "bot", "amount": amount}, "empty")
    assert status == 422
    assert balances(engine, "empty") == before


def test_whole_token_purchase_debits_wallet_and_pool_together(token_market) -> None:
    post, engine = token_market
    status, result = post("/tokenomics/purchase", {"bot_id": "bot", "amount": 25}, "empty")
    assert status == 201
    assert result["cost"] == pytest.approx(0.25)
    assert balances(engine, "empty") == pytest.approx((9999.75, 699_975, 25))


def test_existing_fractional_tokens_can_be_sold_for_positive_proceeds(token_market) -> None:
    post, engine = token_market
    status, result = post("/tokenomics/sell", {"bot_id": "bot", "amount": 0.3}, "holder")
    assert status == 200
    assert result["proceeds"] == pytest.approx(0.0029)
    assert balances(engine, "holder") == pytest.approx((10_000.0029, 700_000.3, 175.2))


@pytest.mark.parametrize("amount", [0, -1, 0.0001, True, False, math.nan, math.inf, -math.inf])
def test_sell_rejects_nonpositive_nonfinite_or_zero_proceeds(token_market, amount: float) -> None:
    post, engine = token_market
    before = balances(engine, "holder")
    status, _ = post("/tokenomics/sell", {"bot_id": "bot", "amount": amount}, "holder")
    assert status == 422
    assert balances(engine, "holder") == before


@pytest.mark.parametrize(("endpoint", "identity", "amount"), [
    ("purchase", "empty", 25), ("sell", "holder", 0.3),
])
def test_wallet_write_failure_rolls_back_both_token_and_wallet_changes(
    token_market, endpoint: str, identity: str, amount: float,
) -> None:
    post, engine = token_market
    before = balances(engine, identity)

    def fail_wallet_write(conn, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith("update users set") and "wallet_balance" in statement.lower():
            raise RuntimeError("injected wallet update failure")

    event.listen(engine, "before_cursor_execute", fail_wallet_write)
    try:
        with pytest.raises(RuntimeError, match="injected wallet update failure"):
            post(f"/tokenomics/{endpoint}", {"bot_id": "bot", "amount": amount}, identity)
    finally:
        event.remove(engine, "before_cursor_execute", fail_wallet_write)
    assert balances(engine, identity) == before
