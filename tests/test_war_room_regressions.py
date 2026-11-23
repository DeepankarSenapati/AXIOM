"""Regression cases for the review's evidence and failure boundaries."""

import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from backend.engine.survival import SurvivalRequest, run_survival
from backend.engine import war_room_claude
from backend.engine.war_room import build_review
from backend.engine.war_room_claude import _parse
from backend.engine.war_room_evidence import build_evidence
from backend.engine.war_room_models import EvidenceItem, WarRoomError, WarRoomRequest


def _review(scenario: SurvivalRequest):
    run = run_survival(scenario)
    return run, build_review(WarRoomRequest(scenario=scenario, expected_fingerprint=run.fingerprint, mode="scripted"))


@pytest.mark.parametrize(("strategy", "seed", "guard_candle", "blocked_candle", "fill_candle"), [
    ("rsi", 42, 91, 91, 92),
    ("momentum", 10, 86, 118, 119),
])
def test_real_scenarios_cite_the_actual_guard_and_linked_fill(
    strategy: str, seed: int, guard_candle: int, blocked_candle: int, fill_candle: int,
) -> None:
    scenario = SurvivalRequest(strategy_key=strategy, seed=seed, shock_index=90, guard_drawdown_pct=3)
    run, result = _review(scenario)
    evidence = {item.id: item for item in result.evidence}
    assert evidence["event.guard_trigger"].candle_index == guard_candle - 1
    assert evidence["event.guarded_first_blocked_buy"].candle_index == blocked_candle - 1
    outcome = evidence["event.unguarded_next_open_outcome"]
    assert (outcome.path, outcome.event_type, outcome.candle_index) == ("unguarded", "fill", fill_candle - 1)
    assert any(e.event_type == "fill" and e.candle_index == outcome.candle_index and e.signal_index == blocked_candle - 1
               for e in run.unguarded.events)
    assert all(set(message.evidence_ids) <= set(evidence) for message in result.messages)


@pytest.mark.parametrize(("scenario", "expected_type", "index"), [
    (SurvivalRequest(strategy_key="rsi", seed=15, num_candles=160, shock_index=90,
                     shock_pct=12, guard_drawdown_pct=0.0001, max_position_pct=0.01), "rejected", 96),
    (SurvivalRequest(strategy_key="rsi", seed=10, num_candles=91, shock_index=90,
                     shock_pct=12, guard_drawdown_pct=3), "expired", 90),
])
def test_real_rejections_and_final_expiry_are_never_presented_as_fills(
    scenario: SurvivalRequest, expected_type: str, index: int,
) -> None:
    _, result = _review(scenario)
    evidence = {item.id: item for item in result.evidence}
    outcome = evidence["event.unguarded_next_open_outcome"]
    assert outcome.event_type == expected_type and outcome.candle_index == index
    assert "fill occurred" in outcome.value if expected_type == "rejected" else "expired" in outcome.value


@pytest.mark.parametrize("corruption", ["wrong_action", "wrong_candle", "premature_expiry"])
def test_unrelated_or_badly_timed_outcomes_do_not_become_a_linked_fill(corruption: str) -> None:
    scenario = SurvivalRequest(strategy_key="rsi", seed=42, shock_index=90, guard_drawdown_pct=3)
    run = run_survival(scenario)
    block = next(e for e in run.guarded.events if e.event_type == "blocked" and e.action == "BUY")
    outcome = next(e for e in run.unguarded.events if e.event_type == "fill" and e.signal_index == block.candle_index)
    updates = {
        "wrong_action": {"action": "SELL"},
        "wrong_candle": {"candle_index": outcome.candle_index + 1},
        "premature_expiry": {"event_type": "expired", "candle_index": block.candle_index},
    }[corruption]
    bad_event = outcome.model_copy(update=updates)
    mutated = run.model_copy(update={"unguarded": run.unguarded.model_copy(update={
        "events": [bad_event if event is outcome else event for event in run.unguarded.events],
    })})
    evidence = {item.id: item for item in build_evidence(mutated)}
    assert "event.unguarded_next_open_outcome" not in evidence
    assert "unavailable.unguarded_outcome" in evidence


def test_small_nonzero_equity_difference_and_close_values_remain_distinguishable() -> None:
    scenario = SurvivalRequest(strategy_key="momentum", seed=10, shock_index=90,
                               guard_drawdown_pct=3, starting_cash=0.01)
    run, result = _review(scenario)
    delta = next(item for item in result.evidence if item.id == "metric.final_equity_delta")
    assert run.guarded.final_equity != run.unguarded.final_equity
    assert "-0.00 synthetic units" not in delta.value
    assert f"{run.guarded.final_equity!r}" in delta.detail
    assert f"{run.unguarded.final_equity!r}" in delta.detail


def test_tiny_drawdown_difference_is_not_contradicted_by_rounded_values() -> None:
    scenario = SurvivalRequest(strategy_key="rsi", seed=38, shock_index=90, guard_drawdown_pct=3)
    run, result = _review(scenario)
    assert run.guarded.max_drawdown_pct < run.unguarded.max_drawdown_pct
    challenger = result.messages[0].body
    assert "differ by at most" in challenger and "before rounding" in challenger
    assert "is not lower" not in challenger


def test_disabled_guard_does_not_claim_two_strategy_paths() -> None:
    _, result = _review(SurvivalRequest(strategy_key="simple_ma", guard_enabled=False))
    defender = result.messages[1].body
    assert "no guarded strategy path" in defender
    assert "Both paths" not in defender


@pytest.mark.parametrize("inner", [False, True])
def test_deep_provider_json_returns_a_sanitized_error(inner: bool) -> None:
    nested = "[" * 3000 + "]" * 3000
    raw = (json.dumps({"type": "message", "stop_reason": "end_turn", "content": [
        {"type": "text", "text": nested},
    ]}).encode() if inner else nested.encode())
    with pytest.raises(WarRoomError) as exc:
        _parse(raw, {"assumption.scenario"})
    assert exc.value.status_code == 502
    assert "invalid" in exc.value.public_message


def test_model_can_use_mathematical_comparisons_without_inserting_markup() -> None:
    statement = {"headline": "Drawdown < 8%", "body": "A 5% loss is > a 3% trigger.",
                 "evidence_ids": ["assumption.scenario"]}
    raw = json.dumps({"type": "message", "stop_reason": "end_turn", "content": [
        {"type": "text", "text": json.dumps(statement)},
    ]}).encode()
    assert _parse(raw, {"assumption.scenario"}).body == statement["body"]


@pytest.mark.parametrize(("code", "status", "text"), [
    (401, 502, "credentials"), (403, 502, "permissions"), (404, 502, "model"), (429, 429, "rate limit"),
])
def test_provider_statuses_are_useful_but_sanitized(monkeypatch: pytest.MonkeyPatch, code: int, status: int, text: str) -> None:
    def fail(request, _timeout):
        raise HTTPError(request.full_url, code, "secret-upstream-body", {}, None)

    monkeypatch.setattr(war_room_claude, "_send", fail)
    with pytest.raises(WarRoomError) as exc:
        war_room_claude._call("secret-key", "claude-test", "auditor", "evidence", {"fact"}, timeout=1)
    assert exc.value.status_code == status and text in exc.value.public_message
    assert "secret" not in exc.value.public_message


def test_wrapped_connection_timeout_is_reported_as_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_request, _timeout):
        raise URLError(TimeoutError("hidden"))

    monkeypatch.setattr(war_room_claude, "_send", fail)
    with pytest.raises(WarRoomError) as exc:
        war_room_claude._call("secret-key", "claude-test", "auditor", "evidence", {"fact"}, timeout=1)
    assert exc.value.status_code == 504 and "hidden" not in exc.value.public_message


def test_provider_response_read_is_bounded_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read1(self, length): return b"x" * length

    class Opener:
        def add_handler(self, _handler): pass
        def open(self, _request, timeout): return Response()

    monkeypatch.setattr(war_room_claude.urllib.request, "OpenerDirector", Opener)
    monkeypatch.setattr(war_room_claude, "time", SimpleNamespace(monotonic=lambda: 0.0))
    raw = war_room_claude._send(Request("https://api.anthropic.com/v1/messages"), 1)
    assert len(raw) == 65_537
    with pytest.raises(WarRoomError) as exc:
        _parse(raw, {"fact"})
    assert exc.value.status_code == 502


def test_dripping_provider_response_stops_after_elapsed_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([0.0, 0.1, 0.6, 0.7, 1.1])

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read1(self, _length): return b"x"

    class Opener:
        def add_handler(self, _handler): pass
        def open(self, _request, timeout): return Response()

    monkeypatch.setattr(war_room_claude.urllib.request, "OpenerDirector", Opener)
    monkeypatch.setattr(war_room_claude, "time", SimpleNamespace(monotonic=lambda: next(times)))
    with pytest.raises(TimeoutError):
        war_room_claude._send(Request("https://api.anthropic.com/v1/messages"), 1)


def test_review_deadline_stops_before_more_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([0.0, 1.0, 46.0])
    calls = []
    statement = {"headline": "Review", "body": "One case.", "evidence_ids": ["fact"]}
    raw = json.dumps({"type": "message", "stop_reason": "end_turn", "content": [
        {"type": "text", "text": json.dumps(statement)},
    ]}).encode()
    monkeypatch.setattr(war_room_claude, "time", SimpleNamespace(monotonic=lambda: next(times)))
    monkeypatch.setattr(war_room_claude, "_send", lambda *_args: calls.append(1) or raw)
    evidence = [EvidenceItem(id="fact", label="Case", value="One", detail="Synthetic", path="scenario")]
    with pytest.raises(WarRoomError) as exc:
        war_room_claude.run_claude_dialogue(evidence, "test-key", "claude-test")
    assert exc.value.status_code == 504
    assert len(calls) == 1
