"""Minimal role boundaries for the local demo, not a security certification."""
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from backend.auth.security import create_access_token
from backend.db.models import DBBot, DBSatisfactionPoll, DBToken, DBUser
from tests.test_governance_api import asgi_post, local_governance


@pytest.fixture
def role_market(local_governance):
    post, engine = local_governance
    with Session(engine) as db:
        bot = db.get(DBBot, "bot")
        bot.tech_company_id = "tech"
        db.add(DBUser(id="other-tech", email="other-tech@example.test", role="tech_company",
                      password_hash="unused", wallet_balance=10_000, is_active=True,
                      created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        db.commit()

    def call(path: str, payload: dict, identity: str, *, method: str = "POST"):
        if identity == "other-tech":
            token = create_access_token({"sub": "other-tech", "role": "tech_company", "email": "other-tech@example.test"})
            return asgi_post(path, payload, token, method=method)
        if method == "POST":
            return post(path, payload, identity)
        roles = {"tech": "tech_company", "admin": "admin", "holder": "token_holder", "gov": "governance_company"}
        token = create_access_token({"sub": identity, "role": roles[identity], "email": f"{identity}@example.test"})
        return asgi_post(path, payload, token, method=method)

    return call, engine


@pytest.mark.parametrize("role", ["admin", "tech_company", "governance_company"])
def test_public_registration_cannot_create_privileged_accounts(role_market, role: str) -> None:
    _, engine = role_market
    status, _ = asgi_post("/auth/register", {
        "email": f"new-{role}@example.test", "password": "example-password", "role": role,
    }, None)
    assert status == 403
    with Session(engine) as db:
        assert db.query(DBUser).filter_by(email=f"new-{role}@example.test").count() == 0


def test_public_registration_can_create_token_holder(role_market) -> None:
    _, engine = role_market
    status, user = asgi_post("/auth/register", {
        "email": "new-holder@example.test", "password": "example-password", "role": "token_holder",
    }, None)
    assert status == 201 and user["role"] == "token_holder"
    with Session(engine) as db:
        assert db.query(DBUser).filter_by(email="new-holder@example.test").count() == 1


@pytest.mark.parametrize(("identity", "allowed"), [
    ("admin", True), ("tech", True), ("other-tech", False), ("holder", False), ("gov", False),
])
def test_deactivation_requires_admin_or_owning_tech(role_market, identity: str, allowed: bool) -> None:
    call, engine = role_market
    status, _ = call("/bots/bot", {}, identity, method="DELETE")
    assert status == (204 if allowed else 403)
    with Session(engine) as db:
        assert db.get(DBBot, "bot").is_active is not allowed


@pytest.mark.parametrize(("identity", "allowed"), [
    ("admin", True), ("tech", True), ("other-tech", False), ("holder", False), ("gov", False),
])
def test_token_initialization_requires_admin_or_owning_tech(role_market, identity: str, allowed: bool) -> None:
    call, engine = role_market
    # Remove fixture's holder rows so this represents a genuinely uninitialized bot.
    with Session(engine) as db:
        db.query(DBToken).filter_by(bot_id="bot").delete()
        db.commit()
    status, _ = call("/tokenomics/init", {"bot_id": "bot"}, identity)
    assert status == (201 if allowed else 403)
    with Session(engine) as db:
        assert db.query(DBToken).filter_by(bot_id="bot").count() == (3 if allowed else 0)


@pytest.mark.parametrize(("identity", "allowed"), [
    ("admin", True), ("gov", True), ("tech", False), ("holder", False), ("other-tech", False),
])
def test_manual_distribution_requires_admin_or_governance(role_market, identity: str, allowed: bool) -> None:
    call, engine = role_market
    with Session(engine) as db:
        db.add_all([
            DBToken(bot_id="bot", holder_address=address, holder_type=kind, balance=100)
            for address, kind in [("public_pool", "public"), ("tech_wallet", "tech"), ("gov_wallet", "governance")]
        ])
        db.commit()
    status, _ = call("/tokenomics/distribute", {"bot_id": "bot", "total_revenue": 100, "quarter": "2026-Q1"}, identity)
    assert status == (200 if allowed else 403)


@pytest.mark.parametrize(("identity", "allowed"), [
    ("admin", True), ("gov", True), ("tech", False), ("holder", False), ("other-tech", False),
])
def test_audit_submission_requires_admin_or_governance(role_market, identity: str, allowed: bool) -> None:
    call, engine = role_market
    with Session(engine) as db:
        for quarter in ("2026-Q1", "2026-Q2"):
            db.add(DBSatisfactionPoll(bot_id="bot", quarter=quarter, satisfied_weight=0, total_weight=100,
                                      satisfaction_rate=0, stage_at_close=1,
                                      closed_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        db.commit()
    status, _ = call("/governance/bot/audit", {
        "quarter": "2026-Q2", "finding": "Example finding",
        "recommendation": "Example recommendation", "severity": "medium",
    }, identity)
    assert status == (201 if allowed else 403)
