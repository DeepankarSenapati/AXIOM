"""Generate stable, evidence-linked facts from one Survival Lab response."""

from backend.engine.survival_models import SurvivalEvent, SurvivalResponse, SurvivalRun
from backend.engine.war_room_models import EvidenceItem

_OUTCOME_TYPES = ("fill", "rejected", "expired")


def _number(value: float, places: int = 2, *, signed: bool = False) -> str:
    """Keep small nonzero values visible instead of rounding them to zero."""
    if value == 0:
        value = 0.0  # Do not display a misleading negative zero.
    sign = "+" if signed else ""
    rounded = f"{value:{sign},.{places}f}"
    if value != 0 and float(rounded.replace(",", "")) == 0:
        return f"{value:{sign}.6g}"
    return rounded


def _pct(value: float) -> str:
    return f"{_number(value)}%"


def _units(value: float) -> str:
    return f"{_number(value)} synthetic units"


def _peak_drawdown_index(run: SurvivalRun) -> int | None:
    point = max(run.equity_curve, key=lambda p: p.drawdown_pct)
    return point.index if point.drawdown_pct > 0 else None


def _drawdown_item(item_id: str, label: str, path: str, run: SurvivalRun) -> EvidenceItem:
    index = _peak_drawdown_index(run)
    where = f"at the close of candle {index + 1}" if index is not None else "never (no close below its prior peak)"
    return EvidenceItem(
        id=item_id, label=label, value=_pct(run.max_drawdown_pct),
        detail=f"Largest close-marked peak-to-trough equity drop, reached {where}. Intrabar losses are not measured.",
        path=path, candle_index=index, event_type=None,
    )


def _outcome_value(event: SurvivalEvent) -> str:
    if event.event_type == "fill":
        if event.price is None:
            return f"{event.action} filled: quantity {event.quantity:.6g} at next open; recorded price unavailable"
        return f"{event.action} filled: quantity {event.quantity:.6g} at {_number(event.price, 4)} (next open)"
    if event.event_type == "rejected":
        return f"{event.action} rejected at next open; no fill occurred"
    return f"{event.action} expired; no next candle existed"


def _blocked_chain(result: SurvivalResponse, guarded: SurvivalRun) -> list[EvidenceItem]:
    blocked = next((e for e in guarded.events if e.event_type == "blocked" and e.action == "BUY"), None)
    if blocked is None:
        return [EvidenceItem(
            id="unavailable.blocked_buy", label="Blocked BUY (not established)",
            value="No BUY was blocked in the guarded run",
            detail="No guarded decision was blocked, so no per-decision guard comparison is established.",
            path="guarded",
        )]
    items = [EvidenceItem(
        id="event.guarded_first_blocked_buy", label="First guarded blocked BUY",
        value=f"BUY blocked at candle {blocked.candle_index + 1}", detail=blocked.reason,
        path="guarded", candle_index=blocked.candle_index, event_type="blocked",
    )]
    signal = next((
        e for e in result.unguarded.events
        if blocked.signal_index == blocked.candle_index
        and e.event_type == "signal" and e.action == "BUY"
        and e.candle_index == blocked.candle_index and e.signal_index == e.candle_index
    ), None)
    if signal is None:
        items.append(EvidenceItem(
            id="unavailable.unguarded_link", label="Unguarded same-candle signal (not established)",
            value="No matching unguarded BUY signal is established",
            detail="The recorded signal link is missing or does not match this blocked decision.",
            path="unguarded",
        ))
        return items
    items.append(EvidenceItem(
        id="event.unguarded_same_candle_signal", label="Unguarded BUY signal on the same candle",
        value=f"BUY signal at candle {signal.candle_index + 1}; requested quantity {signal.quantity:.6g}",
        detail=signal.reason, path="unguarded", candle_index=signal.candle_index, event_type="signal",
    ))
    outcome = next((
        e for e in result.unguarded.events
        if e.event_type in _OUTCOME_TYPES and e.action == "BUY" and e.signal_index == signal.candle_index
        and (
            (e.event_type in ("fill", "rejected") and e.candle_index == signal.candle_index + 1
             and e.candle_index < len(result.candles))
            or (e.event_type == "expired" and e.candle_index == signal.candle_index == len(result.candles) - 1)
        )
    ), None)
    if outcome is None:
        items.append(EvidenceItem(
            id="unavailable.unguarded_outcome", label="Unguarded signal outcome (not established)",
            value="No linked fill, rejection or expiry was recorded",
            detail="The recorded unguarded events contain no outcome linked to that signal.",
            path="unguarded",
        ))
    else:
        items.append(EvidenceItem(
            id="event.unguarded_next_open_outcome", label="Unguarded outcome of that signal",
            value=_outcome_value(outcome), detail=outcome.reason, path="unguarded",
            candle_index=outcome.candle_index, event_type=outcome.event_type,
        ))
    return items


def build_evidence(result: SurvivalResponse) -> list[EvidenceItem]:
    """Derive evidence only from the supplied run; absent facts become 'unavailable.*' items."""
    request = result.request
    items = [
        EvidenceItem(
            id="assumption.scenario", label="Scenario",
            value=f"{result.strategy_key}, seed {request.seed}, {request.num_candles} synthetic daily candles",
            detail=(
                f"Seeded synthetic data, long-only, no leverage, starting cash {_units(request.starting_cash)}. "
                f"Signals decide at the close and may fill at the next open. Fingerprint {result.fingerprint}."
            ),
            path="scenario",
        ),
        EvidenceItem(
            id="assumption.costs", label="Costs and sizing",
            value=f"{request.fee_bps:g} bps fee, {request.slippage_bps:g} bps slippage",
            detail=(
                f"Each fill pays both; buys are capped at {request.max_position_pct:g}% of post-cost equity. "
                "Taxes, market impact and intrabar moves are excluded."
            ),
            path="scenario",
        ),
    ]
    if result.scenario.shock_index is not None:
        items.append(EvidenceItem(
            id="scenario.shock_timing", label="Shock timing",
            value=f"Candle {result.scenario.shock_index + 1}",
            detail=f"A single hypothetical {result.scenario.shock_pct:g}% downward gap is applied at this candle.",
            path="scenario", candle_index=result.scenario.shock_index,
        ))
    else:
        items.append(EvidenceItem(
            id="unavailable.shock", label="Shock (none applied)", value="No shock applied",
            detail="Shock size is 0, so there is no shock timing.", path="scenario",
        ))
    items.append(_drawdown_item("metric.unguarded_max_drawdown", "Unguarded max close drawdown", "unguarded", result.unguarded))
    guarded = result.guarded
    if guarded is None:
        items.append(EvidenceItem(
            id="unavailable.guard_disabled", label="Guard (disabled)", value="Guard disabled",
            detail="No guarded path was run, so guard comparisons are not established.", path="scenario",
        ))
        return items
    items.append(EvidenceItem(
        id="assumption.guard_mechanics", label="Guard mechanics",
        value=f"Pauses new BUYs at {request.guard_drawdown_pct:g}% close drawdown",
        detail=(
            "Once triggered at a close, new buys stay paused for the run; sells remain allowed; "
            "existing positions are not liquidated and a gap can exceed the threshold."
        ),
        path="scenario",
    ))
    items.append(_drawdown_item("metric.guarded_max_drawdown", "Guarded max close drawdown", "guarded", guarded))
    if guarded.guard_trigger_index is not None:
        items.append(EvidenceItem(
            id="event.guard_trigger", label="Guard trigger",
            value=f"Triggered at candle {guarded.guard_trigger_index + 1}",
            detail="Close-marked drawdown reached the threshold; new buys paused from this close.",
            path="guarded", candle_index=guarded.guard_trigger_index, event_type="guard",
        ))
    else:
        items.append(EvidenceItem(
            id="unavailable.guard_trigger", label="Guard trigger (not established)",
            value="Guard never triggered", detail="Drawdown stayed below the threshold at every close.",
            path="guarded",
        ))
    delta = guarded.final_equity - result.unguarded.final_equity
    guarded_value = _units(guarded.final_equity)
    unguarded_value = _units(result.unguarded.final_equity)
    if delta != 0 and guarded_value == unguarded_value:
        # Reveal the distinction when two different values round to the same
        # two-decimal display. repr() preserves the recorded float values.
        guarded_value = f"{guarded.final_equity!r} synthetic units"
        unguarded_value = f"{result.unguarded.final_equity!r} synthetic units"
    items.append(EvidenceItem(
        id="metric.final_equity_delta", label="Final equity, guarded minus unguarded",
        value=f"{_number(delta, signed=True)} synthetic units",
        detail=(
            f"Guarded {guarded_value} versus unguarded {unguarded_value}. "
            "This is a whole-run difference and is not attributed to any single decision."
        ),
        path="scenario",
    ))
    items.extend(_blocked_chain(result, guarded))
    return items
