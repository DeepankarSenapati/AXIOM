// Preserve the sign of small nonzero values instead of rounding them to zero.
// Two significant digits keep these exceptional values compact in cards and print.
export function formatPercent(value, signed = false) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const magnitude = Math.abs(value);
  const ordinary = magnitude.toFixed(2);
  const formatted = magnitude !== 0 && ordinary === "0.00" ? magnitude.toPrecision(2) : ordinary;
  const prefix = value < 0 ? "−" : signed && value > 0 ? "+" : "";
  return `${prefix}${formatted}%`;
}
