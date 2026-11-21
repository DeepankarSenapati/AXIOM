"""HTTP regressions for local-only, balance-weighted governance."""
import asyncio
from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.auth.security import create_access_token
from backend.db.models import DBBot, DBGovernanceVote, DBToken, DBUser
from backend.db.session import Base, get_db
from backend.main import app


def asgi_post(path: str, payload: dict, token: str | None, *, method: str = "POST") -> tuple[int, dict | None]:
    async def call() -> tuple[int, dict | None]:
        received = False
        sent: list[dict] = []

        async def receive() -> dict:
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": json.dumps(payload).encode(), "more_body": False}
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def send(event: dict) -> None:
            sent.append(event)

        headers = [(b"content-type", b"application/json")]
        if token is not None:
            headers.append((b"authorization", f"Bearer {token}".encode()))
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "client": ("test", 1), "server": ("test", 80),
            "headers": headers,
        }
        await app(scope, receive, send)
        status = next(event["status"] for event in sent if event["type"] == "http.response.start")
        body = b"".join(event.get("body", b"") for event in sent if event["type"] == "http.response.body")
        return status, json.loads(body) if body else None

    return asyncio.run(call())


@pytest.fixture
def local_governance(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    users = {
        "holder": ("holder@example.test", "token_holder"),
        "holder2": ("holder2@example.test", "token_holder"),
        "empty": ("empty@example.test", "token_holder"),
        "zero": ("zero@example.test", "token_holder"),
        "tech": ("tech@example.test", "tech_company"),
        "admin": ("admin@example.test", "admin"),
        "gov": ("gov@example.test", "governance_company"),
    }
    with Session(engine) as db:
        db.add(DBBot(id="bot", name="Demo", strategy_name="rsi", created_at=now, is_active=True, status="approved"))
        db.add_all([
            DBUser(id=key, email=email, role=role, password_hash="unused", wallet_balance=10_000,
                   is_active=True, created_at=now)
            for key, (email, role) in users.items()
        ])
        db.add_all([
            DBToken(bot_id="bot", holder_address=users[key][0], holder_type="public", balance=balance)
            for key, balance in (("holder", 175.5), ("holder2", 30.0), ("zero", 0.0))
        ])
        db.commit()

    def override_get_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db)

    def post(path: str, payload: dict, identity: str):
        email, role = users[identity]
        token = create_access_token({"sub": identity, "email": email, "role": role})
        return asgi_post(path, payload, token)

    yield post, engine
    engine.dispose()


def vote_payload(quarter: str = "2026-Q1", **legacy: object) -> dict:
    return {"bot_id": "bot", "quarter": quarter, "vote": "unsatisfied", **legacy}


def close_payload(quarter: str = "2026-Q1") -> dict:
    return {"bot_id": "bot", "quarter": quarter}


def test_vote_uses_authenticated_identity_and_snapshots_actual_balance(local_governance) -> None:
    post, engine = local_governance
    status, _ = post("/governance/vote", vote_payload(), "holder")
    assert status == 204
    with Session(engine) as db:
        vote = db.query(DBGovernanceVote).one()
        assert vote.voter_address == "holder@example.test"
        assert vote.token_weight == pytest.approx(175.5)
        holding = db.query(DBToken).filter_by(holder_address=vote.voter_address).one()
        holding.balance = 20.0
        db.commit()
    status, result = post("/governance/poll/close", close_payload(), "admin")
    assert status == 200
    assert result["total_weight"] == pytest.approx(175.5)
    assert result["vote_count"] == 1


def test_matching_legacy_fields_are_accepted(local_governance) -> None:
    post, _ = local_governance
    status, _ = post("/governance/vote", vote_payload(
        voter_address="holder@example.test", token_weight=175.5,
    ), "holder")
    assert status == 204


@pytest.mark.parametrize(
    "legacy", [{"voter_address": "victim@example.test"}, {"token_weight": 99_999_999}]
)
def test_spoofed_legacy_vote_fields_are_rejected(local_governance, legacy: dict) -> None:
    post, engine = local_governance
    status, _ = post("/governance/vote", vote_payload(**legacy), "holder")
    assert status == 422
    with Session(engine) as db:
        assert db.query(DBGovernanceVote).count() == 0


@pytest.mark.parametrize("identity", ["empty", "zero"])
def test_voter_requires_a_positive_holding(local_governance, identity: str) -> None:
    post, engine = local_governance
    status, _ = post("/governance/vote", vote_payload(), identity)
    assert status == 403
    with Session(engine) as db:
        assert db.query(DBGovernanceVote).count() == 0


def test_a_vote_after_close_returns_409(local_governance) -> None:
    post, _ = local_governance
    assert post("/governance/vote", vote_payload(), "holder")[0] == 204
    assert post("/governance/poll/close", close_payload(), "admin")[0] == 200
    status, _ = post("/governance/vote", vote_payload(), "holder2")
    assert status == 409


def test_empty_polls_cannot_be_closed_as_unsatisfied(local_governance) -> None:
    post, _ = local_governance
    status, _ = post("/governance/poll/close", close_payload(), "admin")
    assert status == 422


@pytest.mark.parametrize("quarter", [
    "2026-Q0", "2026-Q5", "2026-Q10", "26-Q1", "2026-q1", "2026-Q1 ",
    "٢٠٢٦-Q1", "２０２６-Q1",
])
@pytest.mark.parametrize("path", ["/governance/vote", "/governance/poll/close"])
def test_malformed_quarters_are_rejected(local_governance, quarter: str, path: str) -> None:
    post, _ = local_governance
    payload = vote_payload(quarter) if path.endswith("/vote") else close_payload(quarter)
    identity = "holder" if path.endswith("/vote") else "admin"
    status, _ = post(path, payload, identity)
    assert status == 422


@pytest.mark.parametrize("identity", ["holder", "tech"])
def test_only_oversight_roles_may_close_polls(local_governance, identity: str) -> None:
    post, _ = local_governance
    assert post("/governance/vote", vote_payload(), "holder")[0] == 204
    status, _ = post("/governance/poll/close", close_payload(), identity)
    assert status == 403


@pytest.mark.parametrize("identity", ["admin", "gov"])
def test_admin_and_governance_company_may_close_polls(local_governance, identity: str) -> None:
    post, _ = local_governance
    assert post("/governance/vote", vote_payload(), "holder")[0] == 204
    status, result = post("/governance/poll/close", close_payload(), identity)
    assert status == 200 and result["total_weight"] == pytest.approx(175.5)
