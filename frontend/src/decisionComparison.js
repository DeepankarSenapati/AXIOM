// Compare only recorded events on the same completed synthetic tape. A blocked
// signal is not evidence that an order would otherwise have filled.
export function compareGuardDecisions(run) {
  if (run?.guarded === null) return { status: "guard_disabled" };
  if (!run?.guarded || !run?.unguarded || !Array.isArray(run.candles) ||
      !Array.isArray(run.guarded.events) || !Array.isArray(run.unguarded.events)) {
    return { status: "unavailable" };
  }

  const count = run.candles.length;
  const validIndex = (index) => Number.isInteger(index) && index >= 0 && index < count;
  const difference = Number.isFinite(run.guarded.final_equity) && Number.isFinite(run.unguarded.final_equity)
    ? run.guarded.final_equity - run.unguarded.final_equity : null;
  // Engine events are chronological; taking the smallest candle index also
  // remains correct if a consumer supplies them in a different order.
  const blocked = run.guarded.events.reduce((first, event) => {
    if (event?.event_type !== "blocked" || event.action !== "BUY" || !validIndex(event.candle_index)) return first;
    return first === null || event.candle_index < first.candle_index ? event : first;
  }, null);
  if (!blocked) return { status: "no_blocked_buy", difference };

  const signal = run.unguarded.events.find((event) =>
    event?.event_type === "signal" && event.candle_index === blocked.candle_index,
  ) ?? null;
  if (!signal) return { status: "compared", blocked, signal: null, outcome: null, outcomeStatus: "no_signal", difference };
  if (signal.action !== "BUY") {
    return { status: "compared", blocked, signal, outcome: null, outcomeStatus: "different_signal", difference };
  }

  // Match on the originating signal index, not the next fill on the tape.
  // A fill/rejection belongs to the next open; expiry is recorded at the final
  // close. Invalid or incomplete records are reported as unavailable.
  let outcome = null;
  if (validIndex(signal.signal_index) && signal.signal_index === signal.candle_index) {
    outcome = run.unguarded.events.find((event) => {
      if (event?.action !== "BUY" || event.signal_index !== signal.signal_index || !validIndex(event.candle_index)) return false;
      if (event.event_type === "fill" || event.event_type === "rejected") {
        return event.candle_index === signal.candle_index + 1;
      }
      return event.event_type === "expired" && event.candle_index === signal.candle_index && event.candle_index === count - 1;
    }) ?? null;
  }
  return { status: "compared", blocked, signal, outcome, outcomeStatus: outcome?.event_type ?? "no_outcome", difference };
}
