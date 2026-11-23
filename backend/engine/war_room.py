"""Assemble an evidence-linked War Room review from a fresh Survival Lab run."""

import backend.config as settings
import backend.engine.war_room_claude as claude
from backend.engine.survival import run_survival
from backend.engine.war_room_evidence import build_evidence
from backend.engine.war_room_models import WarRoomError, WarRoomRequest, WarRoomResponse, WarRoomScenario
from backend.engine.war_room_quota import WarRoomQuota
from backend.engine.war_room_scripted import scripted_messages

claude_quota = WarRoomQuota(settings.WAR_ROOM_MAX_CLAUDE_REVIEWS)

_COMMON_LIMITATIONS = [
    "Synthetic, seeded data on a local simulation; not market data, a forecast, advice, or live trading.",
    "The fingerprint identifies the synthetic run (request, candles, strategy defaults, engine version); it is not an audit or proof of execution.",
    "The final-equity difference is a whole-run figure and is not attributed to any single decision.",
    "Drawdown is measured at candle closes; intrabar losses are not captured.",
]
_SCRIPTED_LIMITATIONS = [
    "Scripted mode is deterministic template text filled from the evidence values; no AI model was used.",
]
_CLAUDE_LIMITATIONS = [
    "AI perspectives may be wrong. Citing a valid evidence ID does not verify a statement; IDs are only checked to exist.",
    "Model text is not deterministic and is not covered by the fingerprint.",
    "Only generated synthetic evidence was sent to the Anthropic API; no user text or documents were sent.",
]


def build_review(request: WarRoomRequest) -> WarRoomResponse:
    """409 if the rerun fingerprint differs; fail closed on any Claude problem."""
    key = model = None
    if request.mode == "claude":
        key, model = claude.api_key(), claude.model_name()
        if key is None or model is None:
            raise WarRoomError(503, "Claude mode is not configured on this server.")
    result = run_survival(request.scenario)
    if result.fingerprint != request.expected_fingerprint.lower():
        raise WarRoomError(409, "The scenario no longer matches the expected fingerprint. Rerun the Survival Lab.")
    evidence = build_evidence(result)
    if key is not None and model is not None:
        # Reserve once, before any paid call. Failed reviews still count:
        # the provider may have billed one or more calls before failing.
        claude_quota.reserve()
        messages = claude.run_claude_dialogue(evidence, key, model)
        limitations = _COMMON_LIMITATIONS + _CLAUDE_LIMITATIONS
    else:
        messages = scripted_messages(result, evidence)
        limitations = _COMMON_LIMITATIONS + _SCRIPTED_LIMITATIONS
    scenario = result.request
    return WarRoomResponse(
        mode=request.mode, model=model, fingerprint=result.fingerprint, engine_version=result.engine_version,
        scenario=WarRoomScenario(
            strategy_key=scenario.strategy_key, seed=scenario.seed, shock_pct=scenario.shock_pct,
            guard_enabled=scenario.guard_enabled, fee_bps=scenario.fee_bps, slippage_bps=scenario.slippage_bps,
        ),
        evidence=evidence, messages=messages, limitations=limitations,
    )
