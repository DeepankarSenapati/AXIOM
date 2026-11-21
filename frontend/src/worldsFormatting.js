// Preserve the sign of small differences even when the displayed percentage
// returns round to the same two decimal places.
export function formatEquityDelta(delta) {
  if (!Number.isFinite(delta)) return "—";
  if (delta === 0) return "$0.00";
  const magnitude = Math.abs(delta);
  const value = magnitude < 0.01
    ? magnitude.toPrecision(3)
    : magnitude.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${delta < 0 ? "−" : "+"}$${value}`;
}

export function describeEquityDelta(delta, tolerance) {
  if (!Number.isFinite(delta) || !Number.isFinite(tolerance) || tolerance < 0) return "Unavailable";
  if (Math.abs(delta) <= tolerance) return "Equal within tolerance";
  return delta > 0 ? "Higher" : "Lower";
}
