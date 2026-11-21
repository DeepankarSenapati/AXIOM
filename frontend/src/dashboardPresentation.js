import { compareMarkets } from "./arenaPresentation.js";

// The history request is bounded; this summary only describes the runs supplied.
export function observedPnlMaximum(runs) {
  if (!Array.isArray(runs) || runs.length === 0) return { kind: "empty" };
  const markets = compareMarkets(runs.map((run) => run.symbol));
  if (!markets.comparable) return { kind: "mixed" };
  if (runs.some((run) => typeof run.final_pnl !== "number" || !Number.isFinite(run.final_pnl))) {
    return { kind: "unavailable" };
  }
  return { kind: "value", value: Math.max(...runs.map((run) => run.final_pnl)), unit: markets.sharedUnit };
}

export function simulatedAmount(value, unit) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)} ${unit}`;
}
