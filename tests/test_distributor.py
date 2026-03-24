"""Tests for backend/tokenomics/distributor.py"""
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from backend.config import (
    TOKEN_GOV_SHARE,
    TOKEN_PUBLIC_SHARE,
    TOKEN_TECH_SHARE,
    TOTAL_RST_PER_BOT,
)
from backend.db.models import DBBot, DBToken
from backend.tokenomics.distributor import Distributor
from backend.tokenomics.ledger import TokenLedger
from backend.tokenomics.models import HolderPayout, RevenueDistribution


# ---------------------------------------------------------------------------
# Fixtures (db_session, bot_id, seeded_bot come from conftest.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def initialized_ledger(db_session: Session, seeded_bot: str) -> TokenLedger:
    ledger = TokenLedger(db_session)
    ledger.initialize_bot_tokens(seeded_bot)
    return ledger


@pytest.fixture()
def distributor(db_session: Session, initialized_ledger: TokenLedger) -> Distributor:
    return Distributor(db=db_session, ledger=initialized_ledger)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

def test_distribute_returns_revenue_distribution(
    distributor: Distributor, bot_id: str
) -> None:
    result = distributor.distribute(bot_id, total_revenue=1000.0)
    assert isinstance(result, RevenueDistribution)


# ---------------------------------------------------------------------------
# Share math must match config constants exactly
# ---------------------------------------------------------------------------

def test_distribute_public_share_matches_config(
    distributor: Distributor, bot_id: str
) -> None:
    total = 2000.0
    result = distributor.distribute(bot_id, total_revenue=total)
    assert result.public_share == pytest.approx(total * TOKEN_PUBLIC_SHARE)


def test_distribute_tech_share_matches_config(
    distributor: Distributor, bot_id: str
) -> None:
    total = 2000.0
    result = distributor.distribute(bot_id, total_revenue=total)
    assert result.tech_share == pytest.approx(total * TOKEN_TECH_SHARE)


def test_distribute_gov_share_matches_config(
    distributor: Distributor, bot_id: str
) -> None:
    total = 2000.0
    result = distributor.distribute(bot_id, total_revenue=total)
    assert result.gov_share == pytest.approx(total * TOKEN_GOV_SHARE)


def test_distribute_shares_sum_to_total_revenue(
    distributor: Distributor, bot_id: str
) -> None:
    total = 3000.0
    result = distributor.distribute(bot_id, total_revenue=total)
    assert result.public_share + result.tech_share + result.gov_share == pytest.approx(total)


# ---------------------------------------------------------------------------
# bot_id and total_revenue propagation
# ---------------------------------------------------------------------------

def test_distribute_result_bot_id_matches(
    distributor: Distributor, bot_id: str
) -> None:
    result = distributor.distribute(bot_id, total_revenue=500.0)
    assert result.bot_id == bot_id


def test_distribute_result_total_revenue_matches(
    distributor: Distributor, bot_id: str
) -> None:
    result = distributor.distribute(bot_id, total_revenue=1234.56)
    assert result.total_revenue == pytest.approx(1234.56)


# ---------------------------------------------------------------------------
# Payouts list structure
# ---------------------------------------------------------------------------

def test_distribute_produces_three_payouts_for_initialized_bot(
    distributor: Distributor, bot_id: str
) -> None:
    """initialize_bot_tokens creates exactly 3 holders: public_pool, tech_wallet, gov_wallet."""
    result = distributor.distribute(bot_id, total_revenue=1000.0)
    assert len(result.distributions) == 3


def test_distribute_payout_types_cover_all_three_pools(
    distributor: Distributor, bot_id: str
) -> None:
    result = distributor.distribute(bot_id, total_revenue=1000.0)
    types = {p.holder_type for p in result.distributions}
    assert types == {"public", "tech", "governance"}


def test_distribute_payouts_are_holder_payout_instances(
    distributor: Distributor, bot_id: str
) -> None:
    result = distributor.distribute(bot_id, total_revenue=1000.0)
    assert all(isinstance(p, HolderPayout) for p in result.distributions)


# ---------------------------------------------------------------------------
# Per-holder payout amounts
# ---------------------------------------------------------------------------

def test_distribute_public_pool_payout_equals_public_share(
    distributor: Distributor, bot_id: str
) -> None:
    total = 1000.0
    result = distributor.distribute(bot_id, total_revenue=total)
    public_payout = next(p for p in result.distributions if p.holder_type == "public")
    # Single holder owns 100% of the public pool
    assert public_payout.amount == pytest.approx(total * TOKEN_PUBLIC_SHARE)


def test_distribute_tech_pool_payout_equals_tech_share(
    distributor: Distributor, bot_id: str
) -> None:
    total = 1000.0
    result = distributor.distribute(bot_id, total_revenue=total)
    tech_payout = next(p for p in result.distributions if p.holder_type == "tech")
    assert tech_payout.amount == pytest.approx(total * TOKEN_TECH_SHARE)


def test_distribute_gov_pool_payout_equals_gov_share(
    distributor: Distributor, bot_id: str
) -> None:
    total = 1000.0
    result = distributor.distribute(bot_id, total_revenue=total)
    gov_payout = next(p for p in result.distributions if p.holder_type == "governance")
    assert gov_payout.amount == pytest.approx(total * TOKEN_GOV_SHARE)


# ---------------------------------------------------------------------------
# RST balances in payouts match ledger state
# ---------------------------------------------------------------------------

def test_distribute_payout_rst_balance_matches_ledger(
    distributor: Distributor, bot_id: str
) -> None:
    result = distributor.distribute(bot_id, total_revenue=1000.0)
    public_payout = next(p for p in result.distributions if p.holder_type == "public")
    expected = float(TOTAL_RST_PER_BOT) * TOKEN_PUBLIC_SHARE
    assert public_payout.rst_balance == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Zero revenue edge case
# ---------------------------------------------------------------------------

def test_distribute_zero_revenue_produces_zero_payouts(
    distributor: Distributor, bot_id: str
) -> None:
    result = distributor.distribute(bot_id, total_revenue=0.0)
    assert all(p.amount == pytest.approx(0.0) for p in result.distributions)


# ---------------------------------------------------------------------------
# Proportional split when public pool has two holders
# ---------------------------------------------------------------------------

def test_distribute_proportional_split_for_two_public_holders(
    db_session: Session, seeded_bot: str, bot_id: str
) -> None:
    """Two public holders at 60/40 should receive 60%/40% of the public share."""
    db_session.add(DBToken(bot_id=bot_id, holder_address="alice", balance=600_000.0, holder_type="public"))
    db_session.add(DBToken(bot_id=bot_id, holder_address="bob",   balance=400_000.0, holder_type="public"))
    db_session.add(DBToken(bot_id=bot_id, holder_address="tech_wallet", balance=150_000.0, holder_type="tech"))
    db_session.add(DBToken(bot_id=bot_id, holder_address="gov_wallet",  balance=150_000.0, holder_type="governance"))
    db_session.commit()

    ledger = TokenLedger(db_session)
    dist = Distributor(db=db_session, ledger=ledger)
    result = dist.distribute(bot_id, total_revenue=1000.0)

    public_pool_revenue = 1000.0 * TOKEN_PUBLIC_SHARE  # 700.0
    alice_payout = next(p for p in result.distributions if p.holder_address == "alice")
    bob_payout   = next(p for p in result.distributions if p.holder_address == "bob")

    assert alice_payout.amount == pytest.approx(public_pool_revenue * 0.6)
    assert bob_payout.amount   == pytest.approx(public_pool_revenue * 0.4)
