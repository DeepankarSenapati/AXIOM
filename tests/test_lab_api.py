"""HTTP-level checks without an HTTP-client dependency or real network access."""
import asyncio
import json
import math
from threading import BoundedSemaphore

import pytest

from backend.api import lab
from backend.engine.survival import SurvivalRequest, run_survival
from backend.engine.survival_landscape import ShockLandscapeRequest
from backend.engine.survival_worlds import SyntheticWorldsRequest
from backend.main import app


def post_json(path: str, payload: dict | None = None, raw: bytes | None = None) -> tuple[int, dict]:
    """Exercise the mounted ASGI app including validation and response encoding."""
    async def call() -> tuple[int, dict]:
        sent: list[dict] = []
        received = False
        body = raw if raw is not None else json.dumps(payload).encode()

        async def receive() -> dict:
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": body, "more_body": False}
            # Keep the client connected while Starlette streams the response.
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def send(event: dict) -> None:
            sent.append(event)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": path,
            "raw_path": path.encode(), "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("test", 1), "server": ("test", 80),
        }
        await app(scope, receive, send)
        status = next(event["status"] for event in sent if event["type"] == "http.response.start")
        response_body = b"".join(
            event.get("body", b"") for event in sent if event["type"] == "http.response.body"
        )
        return status, json.loads(response_body)

    return asyncio.run(call())


def test_http_run_is_synthetic_reproducible_and_guard_off_is_null() -> None:
    payload = {
        "strategy_key": "rsi", "num_candles": 40, "seed": 123,
        "guard_enabled": False, "shock_pct": 20, "shock_index": 20,
    }
    status, response = post_json("/arena/lab/run", payload)
    status_again, repeated = post_json("/arena/lab/run", payload)

    assert status == status_again == 200
    assert response == repeated
    assert response["scenario"]["source"] == "synthetic"
    assert response["scenario"]["shock_index"] == 20
    assert response["guarded"] is None
    assert len(response["candles"]) == len(response["unguarded"]["equity_curve"]) == 40
    assert len(response["fingerprint"]) == 64
    assert response["strategy_parameters"] and response["engine_version"]


@pytest.mark.parametrize(
    "payload",
    [
        {"strategy_key": "unregistered"},
        {"num_candles": 1},
        {"num_candles": 601},
        {"fee_bps": -1},
        {"fee_bps": 501},
        {"starting_cash": "Infinity"},
        {"num_candles": 10, "shock_index": 10},
        {"unexpected_field": 42},
    ],
)
def test_http_rejects_out_of_bounds_or_extra_request_fields(payload: dict) -> None:
    status, response = post_json("/arena/lab/run", payload)
    assert status == 422
    assert response["detail"]


@pytest.mark.parametrize(
    ("path", "raw"),
    [
        # Valid JSON number syntax, but Python's parser turns it into infinity.
        ("/arena/lab/run", b'{"starting_cash":1e400}'),
        ("/arena/lab/run", b'{"fee_bps":-1e400}'),
        ("/arena/lab/paired", b'{"starting_cash":1e400}'),
        ("/arena/lab/worlds", b'{"scenario":{"starting_cash":1e400},"world_count":1}'),
        ("/arena/lab/landscape", b'{"scenario":{},"shock_pcts":[0,1e400]}'),
        # Python's JSON decoder also accepts these non-standard constants.
        ("/arena/lab/run", b'{"starting_cash":NaN}'),
        ("/arena/lab/run", b'{"unexpected_field":Infinity}'),
    ],
)
def test_http_rejects_nonfinite_number_without_server_error(path: str, raw: bytes) -> None:
    status, response = post_json(path, raw=raw)
    assert status == 422
    assert response["detail"]


def test_http_accepts_the_minimum_supported_percentages() -> None:
    status, response = post_json("/arena/lab/run", {
        "num_candles": 20, "max_position_pct": 0.0001, "guard_drawdown_pct": 0.0001,
    })
    assert status == 200
    assert response["scenario"]["candle_count"] == 20


@pytest.mark.parametrize("field", ["max_position_pct", "guard_drawdown_pct"])
@pytest.mark.parametrize("value", [math.nextafter(0.0001, 0.0), math.ulp(0.0)])
def test_http_rejects_subminimum_percentages(field: str, value: float) -> None:
    status, response = post_json("/arena/lab/run", {"num_candles": 20, field: value})
    assert status == 422 and response["detail"]


@pytest.mark.parametrize("field", ["max_position_pct", "guard_drawdown_pct"])
def test_http_rejects_underflowing_json_exponents(field: str) -> None:
    # The standard JSON exponent underflows to 0.0 in the Python parser.
    raw = ('{"num_candles":20,"' + field + '":1e-400}').encode()
    status, response = post_json("/arena/lab/paired", raw=raw)
    assert status == 422 and response["detail"]


def test_http_worlds_validates_bounds_and_dispatches() -> None:
    status, response = post_json("/arena/lab/worlds", {
        "scenario": {"strategy_key": "rsi", "num_candles": 30, "seed": 9, "guard_enabled": False},
        "world_count": 2,
    })
    assert status == 200
    assert response["world_count"] == 2
    assert [world["seed"] for world in response["worlds"]] == [9, 10]
    assert response["guarded"] is None and response["comparison"] is None
    status, response = post_json("/arena/lab/worlds", {
        "scenario": {"num_candles": 241}, "world_count": 1,
    })
    assert status == 422
    assert response["detail"]


@pytest.mark.parametrize(("shock_pct", "guard_enabled"), [(20, True), (0, False)])
def test_paired_http_matches_standalone_runs_with_one_other_slot_occupied(
    shock_pct: int, guard_enabled: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    semaphore = BoundedSemaphore(2)
    assert semaphore.acquire(blocking=False)
    monkeypatch.setattr(lab, "_experiment_slots", semaphore)
    payload = {
        "strategy_key": "rsi", "num_candles": 50, "seed": 17,
        "shock_pct": shock_pct, "shock_index": 30, "guard_enabled": guard_enabled,
        "fee_bps": 20, "slippage_bps": 8,
    }
    status, paired = post_json("/arena/lab/paired", payload)
    base_status, baseline = post_json("/arena/lab/run", {**payload, "shock_pct": 0})
    shock_status, shock = post_json("/arena/lab/run", payload)

    assert status == base_status == shock_status == 200
    assert paired == {"baseline": baseline, "shock": shock}
    assert baseline["scenario"]["shock_pct"] == 0
    assert shock["scenario"]["shock_pct"] == shock_pct
    assert baseline["candles"][:30] == shock["candles"][:30]
    if shock_pct == 0:
        assert baseline == shock
    assert semaphore.acquire(blocking=False)  # The paired request returned its one slot.
    assert not semaphore.acquire(blocking=False)
    semaphore.release()
    semaphore.release()


def test_paired_http_validates_the_scenario() -> None:
    status, response = post_json("/arena/lab/paired", {
        "num_candles": 20, "shock_index": 20,
    })
    assert status == 422 and response["detail"]


def test_http_landscape_validates_bounds_and_dispatches() -> None:
    status, response = post_json("/arena/lab/landscape", {
        "scenario": {"strategy_key": "rsi", "num_candles": 30, "seed": 9, "guard_enabled": False},
        "shock_pcts": [0, 20], "fee_bps_values": [0, 10],
    })
    assert status == 200
    assert [(cell["shock_pct"], cell["fee_bps"]) for cell in response["cells"]] == [
        (0, 0), (0, 10), (20, 0), (20, 10)
    ]
    assert all(cell["guarded"] is None and len(cell["fingerprint"]) == 64 for cell in response["cells"])
    status, response = post_json("/arena/lab/landscape", {
        "scenario": {"num_candles": 30}, "shock_pcts": [0, 20, 10], "fee_bps_values": [0, 10],
    })
    assert status == 422
    assert response["detail"]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/arena/lab/run", {"num_candles": 20}),
        ("/arena/lab/paired", {"num_candles": 20}),
        ("/arena/lab/worlds", {"scenario": {"num_candles": 20}, "world_count": 1}),
        ("/arena/lab/landscape", {"scenario": {"num_candles": 20}}),
    ],
)
def test_busy_guard_rejects_both_routes(path: str, payload: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    semaphore = BoundedSemaphore(2)
    assert semaphore.acquire(blocking=False)
    assert semaphore.acquire(blocking=False)
    monkeypatch.setattr(lab, "_experiment_slots", semaphore)

    status, response = post_json(path, payload)

    assert status == 429
    assert "busy" in response["detail"].lower()
    semaphore.release()
    semaphore.release()


@pytest.mark.parametrize("endpoint", ["run", "paired", "worlds", "landscape"])
def test_slot_is_released_when_calculation_raises(
    endpoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    semaphore = BoundedSemaphore(2)
    monkeypatch.setattr(lab, "_experiment_slots", semaphore)

    def fail(*args: object) -> None:
        raise RuntimeError("simulated engine failure")

    if endpoint == "run":
        monkeypatch.setattr(lab, "run_survival", fail)
        call = lambda: lab.run_lab_experiment(SurvivalRequest(num_candles=20))
    elif endpoint == "paired":
        monkeypatch.setattr(lab, "run_survival", fail)
        call = lambda: lab.run_paired_experiment(SurvivalRequest(num_candles=20))
    elif endpoint == "worlds":
        monkeypatch.setattr(lab, "run_synthetic_worlds", fail)
        call = lambda: lab.run_lab_worlds(SyntheticWorldsRequest(
            scenario=SurvivalRequest(num_candles=20), world_count=1
        ))
    else:
        monkeypatch.setattr(lab, "run_shock_landscape", fail)
        call = lambda: lab.run_lab_landscape(ShockLandscapeRequest(
            scenario=SurvivalRequest(num_candles=20)
        ))
    with pytest.raises(RuntimeError, match="simulated engine failure"):
        call()

    assert semaphore.acquire(blocking=False)
    assert semaphore.acquire(blocking=False)
    assert not semaphore.acquire(blocking=False)
    semaphore.release()
    semaphore.release()


@pytest.mark.parametrize("failed_call", [1, 2])
def test_paired_releases_slot_on_either_replay_failure(
    failed_call: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    semaphore = BoundedSemaphore(2)
    monkeypatch.setattr(lab, "_experiment_slots", semaphore)
    calls = 0

    def fail_on_selected_call(request: SurvivalRequest):
        nonlocal calls
        calls += 1
        if calls == failed_call:
            raise RuntimeError("replay failed")
        return run_survival(request)

    monkeypatch.setattr(lab, "run_survival", fail_on_selected_call)
    with pytest.raises(RuntimeError, match="replay failed"):
        lab.run_paired_experiment(SurvivalRequest(num_candles=20))
    assert calls == failed_call
    assert semaphore.acquire(blocking=False)
    assert semaphore.acquire(blocking=False)
    semaphore.release()
    semaphore.release()


@pytest.mark.parametrize(
    ("field", "changed"),
    [("engine_version", "changed-version"),
     ("strategy_parameters", {"changed": 42}),
     ("signal_cash_fraction", 0.987)],
)
def test_paired_rejects_inconsistent_implementation_metadata_and_releases_slot(
    field: str, changed: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    semaphore = BoundedSemaphore(2)
    monkeypatch.setattr(lab, "_experiment_slots", semaphore)
    reference = run_survival(SurvivalRequest(num_candles=20))
    calls = 0

    def inconsistent(request: SurvivalRequest):
        nonlocal calls
        calls += 1
        return reference if calls == 1 else reference.model_copy(update={field: changed})

    monkeypatch.setattr(lab, "run_survival", inconsistent)
    with pytest.raises(RuntimeError, match="implementation or signal sizing changed"):
        lab.run_paired_experiment(SurvivalRequest(num_candles=20))
    assert calls == 2
    assert semaphore.acquire(blocking=False)
    assert semaphore.acquire(blocking=False)
    semaphore.release()
    semaphore.release()
