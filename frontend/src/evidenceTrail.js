// Curated navigation to recorded moments in one completed synthetic run.
// The shock is a scenario marker, not a strategy event. Everything else is
// selected directly from the engine's event list and keeps its original order.
export function buildEvidenceTrail(run) {
  const path = run?.guarded ?? run?.unguarded;
  const events = Array.isArray(path?.events) ? path.events : [];
  const count = run?.candles?.length ?? 0;
  const valid = (event) => Number.isInteger(event?.candle_index) && event.candle_index >= 0 && event.candle_index < count;
  const selected = new Map();

  function selectFirst(predicate) {
    const index = events.findIndex((event) => valid(event) && predicate(event));
    if (index >= 0 && !selected.has(index)) selected.set(index, events[index]);
  }

  selectFirst((event) => event.event_type === "fill" && event.action === "BUY");
  selectFirst((event) => event.event_type === "fill" && event.action === "SELL");
  selectFirst((event) => event.event_type === "guard");
  selectFirst((event) => event.event_type === "blocked");
  selectFirst((event) => event.event_type === "rejected");
  selectFirst((event) => event.event_type === "expired");

  const shock = run?.scenario?.shock_index;
  const hasShock = run?.scenario?.shock_pct > 0 && Number.isInteger(shock) && shock >= 0 && shock < count;
  if (hasShock) selectFirst((event) => event.event_type === "fill" && event.candle_index >= shock);
  // A pending order may fill at the open before a guard triggers at that
  // candle's close. Include those same-candle fills so the selected trail
  // cannot hide that ordering; the shock marker likewise precedes open fills.
  const guardIndex = Array.from(selected.values()).find((event) => event.event_type === "guard")?.candle_index;
  events.forEach((event, index) => {
    if (valid(event) && event.event_type === "fill" && (event.candle_index === guardIndex || (hasShock && event.candle_index === shock))) {
      selected.set(index, event);
    }
  });

  const label = (event) => {
    if (event.event_type === "guard") return "Buy guard triggered";
    if (event.event_type === "blocked") return `${event.action} signal blocked`;
    if (event.event_type === "rejected") return `${event.action} order rejected`;
    if (event.event_type === "expired") return `${event.action} signal expired`;
    return `${event.action} filled`;
  };

  const moments = Array.from(selected, ([index, event]) => ({
    id: `event-${index}`,
    candleIndex: event.candle_index,
    order: index,
    label: label(event),
    reason: event.reason,
    event,
  }));
  if (hasShock) moments.push({
    id: "shock",
    candleIndex: shock,
    order: -1,
    label: "Hypothetical shock",
    reason: `${run.scenario.shock_pct}% downward gap at the open; this is a scenario marker, not a bot event.`,
    event: null,
  });
  return moments.sort((a, b) => a.candleIndex - b.candleIndex || a.order - b.order);
}
