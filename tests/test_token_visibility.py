"""Visibility and trading behavior for local simulated token holdings."""

from sqlalchemy.orm import Session

from backend.auth.security import create_access_token
from backend.db.models import DBBot, DBToken
from tests.test_governance_api import asgi_post, local_governance  # shared isolated HTTP fixture


def request(method: str, path: str, identity: str, role: str, payload: dict | None = None):
    token = create_access_token({
        "sub": identity, "email": f"{identity}@example.test", "role": role,
    })
    return asgi_post(path, payload or {}, token, method=method)


def prepare_market(engine) -> None:
    with Session(engine) as db:
        db.get(DBBot, "bot").tech_company_id = "tech"
        db.add(DBToken(bot_id="bot", holder_address="public_pool", holder_type="public", balance=700_000))
        db.commit()


def test_selling_all_excludes_zero_balances_from_holder_views_without_deleting_rows(local_governance) -> None:
    post, engine = local_governance
    prepare_market(engine)

    def counts():
        status, profile = request("GET", "/bots/bot/profile", "tech", "tech_company")
        assert status == 200
        status, dashboard = request("GET", "/tech/my-dashboard", "tech", "tech_company")
        assert status == 200
        return (
            profile["token_distribution"]["investor_count"],
            dashboard["bots"][0]["token_holder_count"],
            dashboard["summary"]["total_token_holders"],
        )

    # An existing zero-balance row is not a holder; the other two are.
    assert counts() == (2, 2, 2)
    assert post("/tokenomics/sell", {"bot_id": "bot", "amount": 175.5}, "holder")[0] == 200
    assert counts() == (1, 1, 1)
    status, holdings = request("GET", "/tokenomics/my-holdings", "holder", "token_holder")
    assert status == 200 and holdings["holdings"] == []
    with Session(engine) as db:
        row = db.query(DBToken).filter_by(bot_id="bot", holder_address="holder@example.test").one()
        assert row.balance == 0

    assert post("/tokenomics/sell", {"bot_id": "bot", "amount": 30}, "holder2")[0] == 200
    assert counts() == (0, 0, 0)


def test_deactivated_bot_remains_in_history_blocks_purchase_and_allows_existing_sales(local_governance) -> None:
    post, engine = local_governance
    prepare_market(engine)
    assert post("/tokenomics/purchase", {"bot_id": "bot", "amount": 25}, "empty")[0] == 201
    assert request("DELETE", "/bots/bot", "tech", "tech_company")[0] == 204

    status, bots = request("GET", "/bots/", "tech", "tech_company")
    assert status == 200 and bots[0]["is_active"] is False and bots[0]["status"] == "approved"
    status, profile = request("GET", "/bots/bot/profile", "tech", "tech_company")
    assert status == 200 and profile["is_active"] is False and profile["status"] == "approved"
    status, dashboard = request("GET", "/tech/my-dashboard", "tech", "tech_company")
    assert status == 200 and dashboard["summary"]["approved_bots"] == 0

    with Session(engine) as db:
        before = db.query(DBToken).filter_by(bot_id="bot", holder_address="empty@example.test").one().balance
    status, error = post("/tokenomics/purchase", {"bot_id": "bot", "amount": 10}, "empty")
    assert status == 422 and "deactivated" in error["detail"]
    with Session(engine) as db:
        assert db.query(DBToken).filter_by(bot_id="bot", holder_address="empty@example.test").one().balance == before

    # Deactivation does not strand an existing holder or erase token history.
    assert post("/tokenomics/sell", {"bot_id": "bot", "amount": 25}, "empty")[0] == 200
    assert post("/admin/bots/bot/approve", {}, "admin")[0] == 200
    assert post("/tokenomics/purchase", {"bot_id": "bot", "amount": 10}, "empty")[0] == 201
    status, profile = request("GET", "/bots/bot/profile", "tech", "tech_company")
    assert status == 200 and profile["is_active"] is True
    status, dashboard = request("GET", "/tech/my-dashboard", "tech", "tech_company")
    assert status == 200 and dashboard["summary"]["approved_bots"] == 1
