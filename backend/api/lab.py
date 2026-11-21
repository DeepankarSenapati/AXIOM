"""Offline, synthetic strategy experiments for the Survival Lab."""

from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.engine.survival import SurvivalRequest, SurvivalResponse, run_survival
from backend.engine.survival_landscape import (
    ShockLandscapeRequest,
    ShockLandscapeResponse,
    run_shock_landscape,
)
from backend.engine.survival_worlds import (
    SyntheticWorldsRequest,
    SyntheticWorldsResponse,
    run_synthetic_worlds,
)

router = APIRouter(prefix="/arena/lab", tags=["survival lab"])

# These CPU-bound endpoints are designed for a local demo. This per-process
# limit also keeps an accidental burst from monopolizing the server.
_experiment_slots = BoundedSemaphore(2)


class PairedExperimentResponse(BaseModel):
    baseline: SurvivalResponse
    shock: SurvivalResponse


@router.post("/run", response_model=SurvivalResponse)
def run_lab_experiment(request: SurvivalRequest) -> SurvivalResponse:
    """Run a deterministic simulation without placing orders or fetching data."""
    if not _experiment_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="The lab is busy. Please try again shortly.")
    try:
        return run_survival(request)
    finally:
        _experiment_slots.release()


@router.post("/paired", response_model=PairedExperimentResponse)
def run_paired_experiment(request: SurvivalRequest) -> PairedExperimentResponse:
    """Compare a scenario to its no-shock baseline within one lab slot."""
    if not _experiment_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="The lab is busy. Please try again shortly.")
    try:
        baseline = run_survival(request.model_copy(update={"shock_pct": 0.0}))
        shock = run_survival(request)
        if (
            baseline.engine_version != shock.engine_version
            or baseline.strategy_parameters != shock.strategy_parameters
            or baseline.signal_cash_fraction != shock.signal_cash_fraction
        ):
            raise RuntimeError("simulation implementation or signal sizing changed during the paired run")
        return PairedExperimentResponse(baseline=baseline, shock=shock)
    finally:
        _experiment_slots.release()


@router.post("/worlds", response_model=SyntheticWorldsResponse)
def run_lab_worlds(request: SyntheticWorldsRequest) -> SyntheticWorldsResponse:
    """Compare bounded seeded synthetic replays of the requested scenario."""
    if not _experiment_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="The lab is busy. Please try again shortly.")
    try:
        return run_synthetic_worlds(request)
    finally:
        _experiment_slots.release()


@router.post("/landscape", response_model=ShockLandscapeResponse)
def run_lab_landscape(request: ShockLandscapeRequest) -> ShockLandscapeResponse:
    """Explore a bounded grid of shocks and fees on one synthetic market."""
    if not _experiment_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="The lab is busy. Please try again shortly.")
    try:
        return run_shock_landscape(request)
    finally:
        _experiment_slots.release()
