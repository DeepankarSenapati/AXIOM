// Values are local simulated amounts; there is no currency conversion.
export function isIndian(symbol) {
  return typeof symbol === "string" && (symbol.endsWith(".NS") || symbol.startsWith("^"));
}

export function marketUnit(symbol) {
  if (typeof symbol !== "string" || !symbol) return "simulated units";
  if (symbol.startsWith("^")) return "synthetic index-point units";
  if (symbol.endsWith(".NS")) return "INR";
  const parts = symbol.split("/");
  return parts.length === 2 && parts[1] ? parts[1] : "simulated units";
}

export function resultMarket(result, submittedMarket) {
  const record = Array.isArray(result?.equity_records)
    ? result.equity_records.find((item) => typeof item?.symbol === "string" && item.symbol) : null;
  return record?.symbol ?? submittedMarket ?? "Unknown";
}

export function compareMarkets(markets) {
  const units = new Set(markets.map(marketUnit));
  const mixedMarkets = new Set(markets).size > 1;
  // Index points do not have a common monetary unit across different indices.
  const comparable = markets.length > 0 && units.size === 1 && !units.has("simulated units") &&
    !(mixedMarkets && units.has("synthetic index-point units"));
  return {
    comparable,
    sharedUnit: comparable ? [...units][0] : null,
    mixedMarkets,
  };
}

export function sharedStartingCash(results) {
  const values = Object.values(results).map((result) => result?.start_cash);
  if (!values.length || values.some((value) => typeof value !== "number" || !Number.isFinite(value))) return null;
  return values.every((value) => value === values[0]) ? values[0] : null;
}

export function nseFourHourUnsupported(dataSource, timeframe, symbols) {
  return dataSource === "live" && timeframe === "4h" && symbols.some(isIndian);
}

function csvText(value) {
  const text = String(value ?? "");
  // Text supplied as a bot name or reason must not become a spreadsheet formula.
  const safe = /^[\t\r\n ]*[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

export function buildArenaCsv(summary, comparable) {
  const header = ["Rank", "Bot", "Strategy", "Market", "Simulated Unit", "Final PnL", "Buy & Hold", "Alpha", "End Cash", "Trades", "Win Rate", "Sharpe", "Max DD"];
  return [header.join(","), ...summary.map((r, index) => [
    comparable ? index + 1 : "", csvText(r.name), csvText(r.strategy), csvText(r.symbol), csvText(r.unit),
    r.finalPnl.toFixed(2), r.benchmarkPnl.toFixed(2), r.alpha.toFixed(2), r.endCash.toFixed(2),
    r.trades, r.winRate !== null ? `${r.winRate}%` : "—", r.sharpe.toFixed(2),
    `${(r.maxDrawdown * 100).toFixed(2)}%`,
  ].join(","))].join("\n");
}

export function buildBacktestCsv(records) {
  const header = ["Date", "Market", "Simulated Unit", "Action", "Price", "Qty", "PnL", "Cash After", "Reason"];
  return [header.join(","), ...records.map((r) => [
    csvText(new Date(r.timestamp).toLocaleString()), csvText(r.symbol), csvText(marketUnit(r.symbol)),
    csvText(r.action_type), Number(r.price ?? 0).toFixed(2), Number(r.quantity ?? 0).toFixed(4),
    Number(r.pnl ?? 0).toFixed(2), Number(r.cash_after ?? 0).toFixed(2), csvText(r.reason),
  ].join(","))].join("\n");
}
