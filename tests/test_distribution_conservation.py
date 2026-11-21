"""New simulated distributions conserve every cent and payout unit."""
from decimal import Decimal
import math

import pytest
from sqlalchemy import event

from backend.db.models import DBDistributionEvent, DBDistributionPayout, DBToken, DBUser
from backend.tokenomics.distributor import Distributor, InvalidRevenueError
from backend.tokenomics.ledger import TokenLedger


def dec(value: float) -> Decimal:
    return Decimal(str(value))


def assert_conserved(result) -> None:
    assert dec(result.platform_fee) + dec(result.distributable) == dec(result.total_revenue)
    assert sum(map(dec, (result.public_share, result.tech_share, result.gov_share))) == dec(result.distributable)
    assert sum(dec(p.amount) for p in result.distributions) == dec(result.distributable)
    for holder_type, share in (("public", result.public_share), ("tech", result.tech_share),
                               ("governance", result.gov_share)):
        assert sum(dec(p.amount) for p in result.distributions if p.holder_type == holder_type) == dec(share)


@pytest.mark.parametrize(
    ("revenue", "fee", "buckets"),
    [(0.04, 0.00, (0.03, 0.01, 0.00)), (0.25, 0.01, (0.17, 0.04, 0.03))],
)
def test_small_revenue_cents_are_conserved_with_deterministic_ties(
    db_session, seeded_bot: str, revenue: float, fee: float, buckets: tuple[float, float, float],
) -> None:
    ledger = TokenLedger(db_session)
    ledger.initialize_bot_tokens(seeded_bot)
    result = Distributor(db_session, ledger).distribute(seeded_bot, revenue, quarter="2026-Q2")
    assert result.platform_fee == fee
    assert (result.public_share, result.tech_share, result.gov_share) == buckets
    assert_conserved(result)
    saved = db_session.query(DBDistributionEvent).one()
    assert (saved.public_share, saved.tech_share, saved.gov_share) == buckets
    assert sum(dec(p.amount) for p in db_session.query(DBDistributionPayout).all()) == dec(saved.distributable)


def test_three_equal_holders_split_payout_units_with_lexical_ties(db_session, seeded_bot: str) -> None:
    # Reverse insertion order ensures the remainder is not awarded by DB row order.
    db_session.add_all([
        DBToken(bot_id=seeded_bot, holder_address=name, holder_type=kind, balance=1)
        for name, kind in [("charlie", "public"), ("bob", "public"), ("alice", "public"),
                           ("tech_wallet", "tech"), ("gov_wallet", "governance")]
    ])
    db_session.commit()
    result = Distributor(db_session, TokenLedger(db_session)).distribute(seeded_bot, 0.03)
    payments = {p.holder_address: p.amount for p in result.distributions}
    assert result.public_share == 0.02
    assert {name: payments[name] for name in ("alice", "bob", "charlie")} == {
        "alice": 0.0067, "bob": 0.0067, "charlie": 0.0066,
    }
    assert_conserved(result)


@pytest.mark.parametrize("revenue", [0, -1, 0.001, 1.001, math.nan, math.inf, -math.inf, True])
def test_invalid_revenue_is_rejected_before_any_event(db_session, seeded_bot: str, revenue: float) -> None:
    ledger = TokenLedger(db_session)
    ledger.initialize_bot_tokens(seeded_bot)
    with pytest.raises(InvalidRevenueError):
        Distributor(db_session, ledger).distribute(seeded_bot, revenue)
    assert db_session.query(DBDistributionEvent).count() == 0
    assert db_session.query(DBDistributionPayout).count() == 0


def test_uninitialized_tokens_cannot_generate_a_distribution(db_session, seeded_bot: str) -> None:
    with pytest.raises(InvalidRevenueError):
        Distributor(db_session, TokenLedger(db_session)).distribute(seeded_bot, 100)
    assert db_session.query(DBDistributionEvent).count() == 0


@pytest.mark.parametrize("damage", ["missing_category", "zero_category", "negative", "infinite", "duplicate", "unknown_type"])
def test_invalid_ledger_is_rejected_before_any_event(db_session, seeded_bot: str, damage: str) -> None:
    ledger = TokenLedger(db_session)
    ledger.initialize_bot_tokens(seeded_bot)
    gov = db_session.query(DBToken).filter_by(bot_id=seeded_bot, holder_address="gov_wallet").one()
    if damage == "missing_category":
        db_session.delete(gov)
    elif damage == "zero_category":
        gov.balance = 0
    elif damage == "negative":
        gov.balance = -1
    elif damage == "infinite":
        gov.balance = math.inf
    elif damage == "duplicate":
        db_session.add(DBToken(bot_id=seeded_bot, holder_address="gov_wallet", holder_type="governance", balance=1))
    else:
        gov.holder_type = "unknown"
    db_session.commit()
    with pytest.raises(InvalidRevenueError):
        Distributor(db_session, ledger).distribute(seeded_bot, 100)
    assert db_session.query(DBDistributionEvent).count() == 0
    assert db_session.query(DBDistributionPayout).count() == 0


def test_wallet_failure_rolls_back_event_and_payouts_preserving_history(db_session, seeded_bot: str) -> None:
    ledger = TokenLedger(db_session)
    ledger.initialize_bot_tokens(seeded_bot)
    db_session.add(DBUser(id="alice", email="alice@example.test", role="token_holder",
                          password_hash="unused", wallet_balance=100, is_active=True))
    db_session.commit()
    ledger.transfer(seeded_bot, "public_pool", "alice@example.test", 70_000)
    distributor = Distributor(db_session, ledger)
    distributor.distribute(seeded_bot, 1000, quarter="2026-Q1")
    before_wallet = db_session.get(DBUser, "alice").wallet_balance
    before_events = db_session.query(DBDistributionEvent).count()
    before_payouts = db_session.query(DBDistributionPayout).count()
    engine = db_session.get_bind()

    def fail_wallet_write(conn, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith("update users set") and "wallet_balance" in statement.lower():
            raise RuntimeError("injected wallet update failure")

    event.listen(engine, "before_cursor_execute", fail_wallet_write)
    try:
        with pytest.raises(RuntimeError, match="injected wallet update failure"):
            distributor.distribute(seeded_bot, 1000, quarter="2026-Q2")
    finally:
        event.remove(engine, "before_cursor_execute", fail_wallet_write)
    db_session.expire_all()
    assert db_session.query(DBDistributionEvent).count() == before_events == 1
    assert db_session.query(DBDistributionPayout).count() == before_payouts
    assert db_session.get(DBUser, "alice").wallet_balance == pytest.approx(before_wallet)
