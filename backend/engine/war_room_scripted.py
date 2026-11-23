"""Offline, deterministic template dialogue. Not an AI model; no network."""

from backend.engine.survival_models import SurvivalResponse
from backend.engine.war_room_models import EvidenceItem, MessageRole, WarRoomMessage

# Drawdown differences below this many percentage points are treated as equal.
_DRAWDOWN_TIE_PP = 0.005


class _Draft:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.ids: list[str] = []

    def add(self, text: str, *evidence_ids: str) -> None:
        self.parts.append(text)
        for item in evidence_ids:
            if item not in self.ids:
                self.ids.append(item)

    def message(self, role: MessageRole, headline: str) -> WarRoomMessage:
        return WarRoomMessage(role=role, headline=headline, body=" ".join(self.parts), evidence_ids=self.ids)


def _challenger(result: SurvivalResponse, ev: dict[str, EvidenceItem]) -> WarRoomMessage:
    d = _Draft()
    unguarded = result.unguarded.max_drawdown_pct
    unguarded_text = ev["metric.unguarded_max_drawdown"].value
    if result.guarded is None:
        d.add(
            f"The guard is disabled, so this run cannot show the guard helped. Unguarded max close drawdown was {unguarded_text}.",
            "unavailable.guard_disabled", "metric.unguarded_max_drawdown",
        )
    else:
        guarded_text = ev["metric.guarded_max_drawdown"].value
        difference = result.guarded.max_drawdown_pct - unguarded
        if abs(difference) <= _DRAWDOWN_TIE_PP:
            d.add(
                f"Guarded max close drawdown ({guarded_text}) and unguarded ({unguarded_text}) differ by at most {_DRAWDOWN_TIE_PP:g} percentage points before rounding on this synthetic tape.",
                "metric.guarded_max_drawdown", "metric.unguarded_max_drawdown",
            )
        elif guarded_text == unguarded_text:
            d.add(
                f"Both max close drawdowns round to {guarded_text}; before rounding, guarded minus unguarded is {difference:+.6g} percentage points on this synthetic tape.",
                "metric.guarded_max_drawdown", "metric.unguarded_max_drawdown",
            )
        elif difference > 0:
            d.add(
                f"Guarded max close drawdown ({guarded_text}) is higher than unguarded ({unguarded_text}) on this synthetic tape.",
                "metric.guarded_max_drawdown", "metric.unguarded_max_drawdown",
            )
        else:
            d.add(
                f"Guarded drawdown ({guarded_text}) is lower than unguarded ({unguarded_text}), but it is measured at closes only and covers one synthetic tape.",
                "metric.guarded_max_drawdown", "metric.unguarded_max_drawdown",
            )
        d.add(
            f"The final-equity difference ({ev['metric.final_equity_delta'].value}) is a whole-run figure and cannot be pinned on any one decision.",
            "metric.final_equity_delta",
        )
        d.add(
            "The guard only pauses new buys; it does not sell existing positions or cap losses through gaps.",
            "assumption.guard_mechanics",
        )
    shock = ev.get("scenario.shock_timing")
    if shock is not None and shock.candle_index is not None:
        d.add(
            f"The scenario's hypothetical shock lands at candle {shock.candle_index + 1}, which is an assumption rather than market data.",
            "scenario.shock_timing",
        )
    d.add(f"Results depend on modeled costs ({ev['assumption.costs'].value}).", "assumption.costs")
    return d.message("challenger", "Challenge: what do the numbers actually show?")


def _defender(result: SurvivalResponse, ev: dict[str, EvidenceItem]) -> WarRoomMessage:
    d = _Draft()
    if result.guarded is None:
        d.add(
            "With the guard disabled, no guarded strategy path was recorded, so its effects cannot be compared.",
            "unavailable.guard_disabled",
        )
    elif "event.guard_trigger" in ev:
        d.add(
            f"The guard did trigger ({ev['event.guard_trigger'].value}), as recorded in the guarded run.",
            "event.guard_trigger",
        )
    else:
        d.add(
            "The guard never triggered, so the evidence neither supports nor refutes its protective effect.",
            "unavailable.guard_trigger",
        )
    blocked = ev.get("event.guarded_first_blocked_buy")
    if blocked is not None and blocked.candle_index is not None:
        d.add(f"Its first blocked BUY was at candle {blocked.candle_index + 1}.", "event.guarded_first_blocked_buy")
        outcome = ev.get("event.unguarded_next_open_outcome")
        if outcome is not None:
            d.add(
                f"On that same candle the unguarded run signalled BUY and the recorded outcome was: {outcome.value}. This is one decision, and its effect on the whole run is not isolated.",
                "event.unguarded_same_candle_signal", "event.unguarded_next_open_outcome",
            )
        else:
            missing = "unavailable.unguarded_outcome" if "unavailable.unguarded_outcome" in ev else "unavailable.unguarded_link"
            d.add("No matching unguarded signal outcome is established, so no per-decision comparison is claimed.", missing)
    elif result.guarded is not None:
        d.add("No BUY was blocked, so no individual avoided decision is shown.", "unavailable.blocked_buy")
    if result.guarded is not None:
        d.add(
            "The guarded and unguarded paths use the same synthetic tape and cost settings; their exposures and later decisions may differ.",
            "assumption.scenario", "assumption.costs",
        )
    else:
        d.add(
            "The unguarded path uses the recorded synthetic tape and modeled costs.",
            "assumption.scenario", "assumption.costs",
        )
    return d.message("defender", "Defence: what the record supports")


def _auditor(ev: dict[str, EvidenceItem]) -> WarRoomMessage:
    d = _Draft()
    d.add(
        "Both sides use one seeded synthetic run (fingerprint in the scenario evidence). Nothing here generalises to real markets, other seeds, or live trading.",
        "assumption.scenario",
    )
    gaps = [item for item in ev if item.startswith("unavailable.")]
    if gaps:
        d.add("Not established by this run: " + ", ".join(gaps) + ".", *gaps)
    if "metric.final_equity_delta" in ev:
        d.add("The final-equity difference is not attributed to any single decision.", "metric.final_equity_delta")
    d.add(
        "These statements are templates filled from the cited values; they are not an independent audit, and drawdown is close-marked so intrabar losses are unmeasured.",
        "metric.unguarded_max_drawdown",
    )
    return d.message("auditor", "Audit: uncertainty and limits")


def scripted_messages(result: SurvivalResponse, evidence: list[EvidenceItem]) -> list[WarRoomMessage]:
    ev = {item.id: item for item in evidence}
    return [_challenger(result, ev), _defender(result, ev), _auditor(ev)]
