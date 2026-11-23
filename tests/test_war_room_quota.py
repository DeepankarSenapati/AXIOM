"""The local paid-review guardrail reserves atomically and never calls the network."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.engine import war_room
from backend.engine.survival import SurvivalRequest, run_survival
from backend.engine.war_room_models import WarRoomError, WarRoomRequest
from backend.engine.war_room_quota import WarRoomQuota


def test_review_reservations_are_atomic_under_concurrency() -> None:
    quota = WarRoomQuota(5)

    def attempt() -> bool:
        try:
            quota.reserve()
            return True
        except WarRoomError as exc:
            assert exc.status_code == 429
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: attempt(), range(30)))
    assert sum(results) == 5
    assert quota.remaining() == 0


def test_missing_key_and_stale_fingerprint_do_not_consume_a_review(monkeypatch: pytest.MonkeyPatch) -> None:
    quota = WarRoomQuota(2)
    monkeypatch.setattr(war_room, "claude_quota", quota)
    monkeypatch.delenv("AXIOM_ANTHROPIC_API_KEY", raising=False)
    scenario = SurvivalRequest(strategy_key="rsi")
    request = WarRoomRequest(scenario=scenario, expected_fingerprint="0" * 64, mode="claude")
    with pytest.raises(WarRoomError) as missing:
        war_room.build_review(request)
    assert missing.value.status_code == 503 and quota.remaining() == 2
    monkeypatch.setenv("AXIOM_ANTHROPIC_API_KEY", "local-test-key")
    with pytest.raises(WarRoomError) as stale:
        war_room.build_review(request)
    assert stale.value.status_code == 409 and quota.remaining() == 2


def test_failed_provider_review_still_consumes_quota_and_exhaustion_prevents_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quota = WarRoomQuota(1)
    monkeypatch.setattr(war_room, "claude_quota", quota)
    monkeypatch.setenv("AXIOM_ANTHROPIC_API_KEY", "local-test-key")
    scenario = SurvivalRequest(strategy_key="rsi")
    request = WarRoomRequest(scenario=scenario, expected_fingerprint=run_survival(scenario).fingerprint, mode="claude")
    calls = []

    def fail(*_args):
        calls.append(1)
        raise WarRoomError(502, "Provider failed.")

    monkeypatch.setattr(war_room.claude, "run_claude_dialogue", fail)
    with pytest.raises(WarRoomError) as failed:
        war_room.build_review(request)
    assert failed.value.status_code == 502 and quota.remaining() == 0
    with pytest.raises(WarRoomError) as limited:
        war_room.build_review(request)
    assert limited.value.status_code == 429 and len(calls) == 1

    # The no-cost scripted walkthrough remains available after the paid cap.
    scripted = request.model_copy(update={"mode": "scripted"})
    assert war_room.build_review(scripted).mode == "scripted"
