"""Typed contract for the synthetic, read-only War Room review."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.engine.survival_models import EventType, SurvivalRequest


EvidencePath = Literal["guarded", "unguarded", "scenario"]
MessageRole = Literal["challenger", "defender", "auditor"]
ReviewMode = Literal["scripted", "claude"]


class WarRoomError(Exception):
    """A failure with a fixed, client-safe message and HTTP status."""

    def __init__(self, status_code: int, public_message: str) -> None:
        super().__init__(public_message)
        self.status_code = status_code
        self.public_message = public_message


class WarRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: SurvivalRequest
    expected_fingerprint: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mode: ReviewMode


class WarRoomScenario(BaseModel):
    strategy_key: str
    seed: int
    shock_pct: float
    guard_enabled: bool
    fee_bps: float
    slippage_bps: float


class EvidenceItem(BaseModel):
    id: str
    label: str
    value: str
    detail: str
    path: EvidencePath
    candle_index: int | None = None  # zero-based; display text uses one-based numbers
    event_type: EventType | None = None


class WarRoomMessage(BaseModel):
    role: MessageRole
    headline: str
    body: str
    evidence_ids: list[str]


class WarRoomResponse(BaseModel):
    mode: ReviewMode
    model: str | None
    fingerprint: str
    engine_version: str
    scenario: WarRoomScenario
    evidence: list[EvidenceItem]
    messages: list[WarRoomMessage]
    limitations: list[str]


class CapabilitiesResponse(BaseModel):
    claude_configured: bool
    model: str | None
    max_claude_reviews: int
    claude_reviews_remaining: int
