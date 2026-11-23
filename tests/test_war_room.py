"""War Room: evidence integrity, scripted mode and mocked Claude mode. No network."""
import asyncio
import json
from threading import BoundedSemaphore
from urllib.error import HTTPError

import pytest

from backend.api import war_room as war_room_api
from backend.auth.dependencies import get_current_user
from backend.engine import war_room, war_room_claude
from backend.engine.survival import SurvivalRequest, run_survival
from backend.engine.war_room_evidence import build_evidence
from backend.engine.war_room_quota import WarRoomQuota
from backend.main import app

SECRET = "synthetic-test-credential-not-a-real-key"
BLOCKED = dict(strategy_key="rsi", seed=1, num_candles=60, shock_pct=25, guard_drawdown_pct=1.0, max_position_pct=100)
FINAL_BLOCK = dict(strategy_key="rsi", seed=0, num_candles=33, shock_pct=25, guard_drawdown_pct=1.0, max_position_pct=100)
MOMENTUM_10 = dict(strategy_key="momentum", seed=10, shock_pct=0, guard_enabled=False)


def call(method: str, path: str, payload: dict | None = None, auth: bool = True) -> tuple[int, dict]:
    async def run() -> tuple[int, dict]:
        sent: list[dict] = []
        body = json.dumps(payload).encode() if payload is not None else b""
        done = False

        async def receive() -> dict:
            nonlocal done
            if not done:
                done = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def send(event: dict) -> None:
            sent.append(event)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
            "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
            "headers": [(b"content-type", b"application/json")], "client": ("t", 1), "server": ("t", 80),
        }
        await app(scope, receive, send)
        status = next(e["status"] for e in sent if e["type"] == "http.response.start")
        data = b"".join(e.get("body", b"") for e in sent if e["type"] == "http.response.body")
        return status, json.loads(data)

    if auth:
        app.dependency_overrides[get_current_user] = lambda: object()
    try:
        return asyncio.run(run())
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def review(scenario: dict, mode: str = "scripted", fingerprint: str | None = None) -> tuple[int, dict]:
    fp = fingerprint or run_survival(SurvivalRequest(**scenario)).fingerprint
    return call("POST", "/arena/war-room/review", {"scenario": scenario, "expected_fingerprint": fp, "mode": mode})


def by_id(body: dict) -> dict[str, dict]:
    return {e["id"]: e for e in body["evidence"]}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AXIOM_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AXIOM_ANTHROPIC_MODEL", raising=False)
    monkeypatch.setattr(war_room, "claude_quota", WarRoomQuota(5))


# ---------------------------------------------------------------- scripted mode

def test_default_rsi_scripted_is_offline_and_marks_missing_facts_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(war_room_claude, "_send", lambda *a, **k: pytest.fail("network used in scripted mode"))
    status, body = review({"strategy_key": "rsi"})
    assert status == 200
    assert body["mode"] == "scripted" and body["model"] is None
    assert body["fingerprint"] == run_survival(SurvivalRequest(strategy_key="rsi")).fingerprint
    assert body["scenario"] == {
        "strategy_key": "rsi", "seed": 42, "shock_pct": 12.0, "guard_enabled": True, "fee_bps": 10.0, "slippage_bps": 5.0,
    }
    ev = by_id(body)
    assert "unavailable.guard_trigger" in ev and "unavailable.blocked_buy" in ev
    assert "event.guard_trigger" not in ev and "event.guarded_first_blocked_buy" not in ev
    assert [m["role"] for m in body["messages"]] == ["challenger", "defender", "auditor"]
    for m in body["messages"]:
        assert m["evidence_ids"] and set(m["evidence_ids"]) <= set(ev)
    assert any("no AI model" in text for text in body["limitations"])
    # Metric/assumption evidence never pretends to be an event.
    assert all(e["event_type"] is None for i, e in ev.items() if i.startswith(("metric.", "assumption.", "unavailable.")))


def test_momentum_seed_10_guard_and_shock_off_has_no_guard_evidence() -> None:
    status, body = review(MOMENTUM_10)
    assert status == 200
    ev = by_id(body)
    assert "unavailable.guard_disabled" in ev and "unavailable.shock" in ev
    for absent in ("metric.guarded_max_drawdown", "metric.final_equity_delta", "event.guard_trigger",
                   "event.guarded_first_blocked_buy", "scenario.shock_timing", "assumption.guard_mechanics"):
        assert absent not in ev
    assert "unavailable.guard_disabled" in body["messages"][0]["evidence_ids"]
    assert "guard is disabled" in body["messages"][0]["body"]


def test_blocked_buy_links_only_the_same_candle_unguarded_signal_and_next_open_outcome() -> None:
    status, body = review(BLOCKED)
    ev = by_id(body)
    result = run_survival(SurvivalRequest(**BLOCKED))
    trigger = result.guarded.guard_trigger_index
    assert ev["event.guard_trigger"]["candle_index"] == trigger
    assert ev["event.guard_trigger"]["event_type"] == "guard" and ev["event.guard_trigger"]["path"] == "guarded"
    assert ev["event.guard_trigger"]["value"] == f"Triggered at candle {trigger + 1}"  # one-based display
    blocked = ev["event.guarded_first_blocked_buy"]
    assert (blocked["path"], blocked["event_type"]) == ("guarded", "blocked")
    signal = ev["event.unguarded_same_candle_signal"]
    assert (signal["path"], signal["event_type"], signal["candle_index"]) == ("unguarded", "signal", blocked["candle_index"])
    outcome = ev["event.unguarded_next_open_outcome"]
    assert (outcome["path"], outcome["event_type"], outcome["candle_index"]) == ("unguarded", "fill", blocked["candle_index"] + 1)
    fill = next(e for e in result.unguarded.events if e.event_type == "fill" and e.signal_index == blocked["candle_index"])
    assert f"{fill.price:.4f}" in outcome["value"]
    delta = ev["metric.final_equity_delta"]
    assert delta["event_type"] is None and "not attributed to any single decision" in delta["detail"]
    defender = body["messages"][1]
    assert "event.unguarded_next_open_outcome" in defender["evidence_ids"]
    assert "effect on the whole run is not isolated" in defender["body"]


def test_final_candle_buy_is_blocked_in_guarded_run_but_expires_unguarded() -> None:
    _, body = review(FINAL_BLOCK)
    ev = by_id(body)
    last = FINAL_BLOCK["num_candles"] - 1
    assert (ev["event.guarded_first_blocked_buy"]["candle_index"], ev["event.guarded_first_blocked_buy"]["event_type"]) == (last, "blocked")
    outcome = ev["event.unguarded_next_open_outcome"]
    assert (outcome["event_type"], outcome["candle_index"]) == ("expired", last)
    assert "filled" not in outcome["value"] and "expired" in outcome["value"]
    guarded = run_survival(SurvivalRequest(**FINAL_BLOCK)).guarded
    assert not any(e.event_type == "expired" and e.candle_index == last for e in guarded.events)


def test_rejected_unguarded_signal_does_not_invent_a_fill() -> None:
    result = run_survival(SurvivalRequest(**BLOCKED))
    events = result.unguarded.events
    fill = next(e for e in events if e.event_type == "fill" and e.signal_index == next(
        b.signal_index for b in result.guarded.events if b.event_type == "blocked"))
    rejected = fill.model_copy(update={"event_type": "rejected", "quantity": 0.0, "price": None, "reason": "No fill: test"})
    mutated = result.model_copy(update={"unguarded": result.unguarded.model_copy(
        update={"events": [rejected if e is fill else e for e in events]})})
    outcome = {e.id: e for e in build_evidence(mutated)}["event.unguarded_next_open_outcome"]
    assert outcome.event_type == "rejected" and "rejected" in outcome.value
    assert "filled" not in outcome.value and "quantity" not in outcome.value and "no fill occurred" in outcome.value


def test_missing_unguarded_signal_or_outcome_is_reported_as_not_established() -> None:
    result = run_survival(SurvivalRequest(**BLOCKED))
    sig_idx = next(b.signal_index for b in result.guarded.events if b.event_type == "blocked")
    no_signal = result.model_copy(update={"unguarded": result.unguarded.model_copy(update={"events": [
        e for e in result.unguarded.events if not (e.event_type == "signal" and e.candle_index == sig_idx)]})})
    ids = {e.id for e in build_evidence(no_signal)}
    assert "unavailable.unguarded_link" in ids and "event.unguarded_next_open_outcome" not in ids
    no_outcome = result.model_copy(update={"unguarded": result.unguarded.model_copy(update={"events": [
        e for e in result.unguarded.events if not (e.signal_index == sig_idx and e.event_type != "signal")]})})
    ids = {e.id for e in build_evidence(no_outcome)}
    assert "unavailable.unguarded_outcome" in ids and "event.unguarded_next_open_outcome" not in ids


# ---------------------------------------------------------------- API guards

def test_fingerprint_mismatch_is_409_and_bad_fingerprint_is_422() -> None:
    assert review({"strategy_key": "rsi"}, fingerprint="0" * 64)[0] == 409
    assert review({"strategy_key": "rsi"}, fingerprint="abc")[0] == 422
    upper = run_survival(SurvivalRequest(strategy_key="rsi")).fingerprint.upper()
    assert review({"strategy_key": "rsi"}, fingerprint=upper)[0] == 200


def test_review_and_capabilities_require_authentication() -> None:
    assert call("GET", "/arena/war-room/capabilities", auth=False)[0] in (401, 403)
    fp = "0" * 64
    payload = {"scenario": {}, "expected_fingerprint": fp, "mode": "scripted"}
    assert call("POST", "/arena/war-room/review", payload, auth=False)[0] in (401, 403)


def test_busy_review_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    full = BoundedSemaphore(1)
    full.acquire()
    monkeypatch.setattr(war_room_api, "_review_slots", full)
    assert review({"strategy_key": "rsi"})[0] == 429


def test_rejects_unknown_fields_and_modes() -> None:
    fp = "a" * 64
    assert call("POST", "/arena/war-room/review", {"scenario": {}, "expected_fingerprint": fp, "mode": "x"})[0] == 422
    assert call("POST", "/arena/war-room/review", {
        "scenario": {}, "expected_fingerprint": fp, "mode": "scripted", "notes": "free text"})[0] == 422


def test_capabilities_never_expose_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert call("GET", "/arena/war-room/capabilities")[1] == {
        "claude_configured": False, "model": None, "max_claude_reviews": 5, "claude_reviews_remaining": 5,
    }
    monkeypatch.setenv("AXIOM_ANTHROPIC_API_KEY", SECRET)
    status, body = call("GET", "/arena/war-room/capabilities")
    assert status == 200 and body == {
        "claude_configured": True, "model": "claude-sonnet-4-6", "max_claude_reviews": 5, "claude_reviews_remaining": 5,
    }
    monkeypatch.setenv("AXIOM_ANTHROPIC_MODEL", "claude-test-model")
    assert call("GET", "/arena/war-room/capabilities")[1]["model"] == "claude-test-model"
    assert SECRET not in json.dumps(body)


# ---------------------------------------------------------------- Claude mode (mocked provider)

def reply(statement: dict | str, stop_reason: str = "end_turn") -> bytes:
    text = statement if isinstance(statement, str) else json.dumps(statement)
    return json.dumps({"type": "message", "stop_reason": stop_reason, "content": [{"type": "text", "text": text}]}).encode()


def good(role: str) -> dict:
    return {"headline": f"{role} view", "body": f"Plain text from {role}.", "evidence_ids": ["assumption.scenario"]}


@pytest.fixture()
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXIOM_ANTHROPIC_API_KEY", SECRET)


def test_claude_mode_requires_server_key() -> None:
    status, body = review({"strategy_key": "rsi"}, mode="claude")
    assert status == 503 and "not configured" in body["detail"]


def test_claude_mode_makes_three_ordered_bounded_calls(configured: None, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple] = []
    queue = [reply(good("challenger")), reply(good("defender")), reply(good("auditor"))]

    def fake_send(request, timeout):
        seen.append((request.full_url, dict(request.header_items()), json.loads(request.data), timeout))
        return queue.pop(0)

    monkeypatch.setattr(war_room_claude, "_send", fake_send)
    status, body = review(BLOCKED, mode="claude")
    assert status == 200 and body["mode"] == "claude" and body["model"] == "claude-sonnet-4-6"
    assert [m["role"] for m in body["messages"]] == ["challenger", "defender", "auditor"]
    assert any("AI perspectives may be wrong" in t and "does not verify" in t for t in body["limitations"])
    assert body["fingerprint"] == run_survival(SurvivalRequest(**BLOCKED)).fingerprint
    assert len(seen) == 3
    for url, headers, payload, timeout in seen:
        assert url == "https://api.anthropic.com/v1/messages" and timeout == 20.0
        assert headers["X-api-key"] == SECRET
        assert payload["model"] == "claude-sonnet-4-6" and payload["max_tokens"] == 700 and "tools" not in payload
        schema = payload["output_config"]["format"]["schema"]
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert schema["additionalProperties"] is False
        assert "assumption.scenario" in schema["properties"]["evidence_ids"]["items"]["enum"]
    challenger, defender, auditor = (s[2]["messages"][0]["content"] for s in seen)
    assert "challenger view" not in defender and "defender view" not in challenger  # independent analyses
    assert "challenger view" in auditor and "defender view" in auditor and "event.guard_trigger" in auditor
    assert "Role: auditor" in seen[2][2]["system"] and "uncertainty" in seen[2][2]["system"]
    assert SECRET not in json.dumps(body)


@pytest.mark.parametrize("bad", [
    reply({**good("x"), "evidence_ids": ["not.a.real.id"]}),                      # unknown citation
    reply({**good("x"), "evidence_ids": []}),                                      # empty citations
    reply({**good("x"), "evidence_ids": ["assumption.scenario", "assumption.scenario"]}),
    reply({**good("x"), "extra": 1}),                                              # schema is strict
    reply({**good("x"), "body": "x" * 1201}),                                      # bounded
    reply({**good("x"), "body": "<script>alert(1)</script>"}),                     # markup
    reply({**good("x"), "body": "see [link](http://evil)"}),
    reply(good("x"), stop_reason="max_tokens"),                                    # truncated
    reply("this is not json"),
    b"<html>gateway</html>",
    json.dumps({"type": "error", "error": {"message": SECRET}}).encode(),
])
def test_invalid_provider_output_fails_closed_without_partial_dialogue(
    configured: None, monkeypatch: pytest.MonkeyPatch, bad: bytes,
) -> None:
    calls = []
    monkeypatch.setattr(war_room_claude, "_send", lambda r, t: calls.append(1) or bad)
    status, body = review({"strategy_key": "rsi"}, mode="claude")
    assert status == 502 and "invalid or unverifiable" in body["detail"] and "No dialogue" in body["detail"]
    assert set(body) == {"detail"} and SECRET not in json.dumps(body) and "gateway" not in json.dumps(body)
    assert len(calls) == 1  # stops at the first bad call; no fabricated remainder, no silent scripted fallback


def test_second_call_failure_returns_no_partial_dialogue(configured: None, monkeypatch: pytest.MonkeyPatch) -> None:
    queue = [reply(good("challenger")), reply({**good("defender"), "evidence_ids": ["bogus"]})]
    monkeypatch.setattr(war_room_claude, "_send", lambda r, t: queue.pop(0))
    status, body = review({"strategy_key": "rsi"}, mode="claude")
    assert status == 502 and "messages" not in body


def test_provider_timeout_and_http_errors_are_sanitized(configured: None, monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(request, seconds):
        raise TimeoutError(f"timed out talking with key {SECRET}")

    monkeypatch.setattr(war_room_claude, "_send", timeout)
    status, body = review({"strategy_key": "rsi"}, mode="claude")
    assert status == 504 and "timed out" in body["detail"] and SECRET not in json.dumps(body)

    def http_error(request, seconds):
        raise HTTPError(request.full_url, 401, f"invalid x-api-key {SECRET}", {}, None)

    monkeypatch.setattr(war_room_claude, "_send", http_error)
    status, body = review({"strategy_key": "rsi"}, mode="claude")
    assert status == 502 and body["detail"] == "The AI provider rejected the server credentials. Check the API key. No dialogue was produced."
    assert SECRET not in json.dumps(body) and "401" not in json.dumps(body)


def test_claude_mode_still_checks_fingerprint_before_calling_provider(configured: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(war_room_claude, "_send", lambda *a: pytest.fail("provider called for stale evidence"))
    assert review({"strategy_key": "rsi"}, mode="claude", fingerprint="f" * 64)[0] == 409
