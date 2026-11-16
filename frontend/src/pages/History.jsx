import { useEffect, useState, useCallback } from "react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function PnlCell({ value }) {
  const n = Number(value ?? 0);
  if (n > 0) return <span className="text-emerald-400 font-mono font-semibold">+{n.toFixed(2)}</span>;
  if (n < 0) return <span className="text-red-400 font-mono font-semibold">{n.toFixed(2)}</span>;
  return <span className="text-gray-400 font-mono">0.00</span>;
}

function SortIcon({ dir }) {
  if (!dir) return <span className="ml-1 text-gray-600 text-xs">⇅</span>;
  return <span className="ml-1 text-indigo-400 text-xs">{dir === "asc" ? "↑" : "↓"}</span>;
}

const ALL_STRATEGIES = [
  { value: "", label: "All Strategies" },
  { value: "simple_ma", label: "Moving Average" },
  { value: "rsi", label: "RSI" },
  { value: "macd", label: "MACD" },
  { value: "bollinger_bands", label: "Bollinger Bands" },
  { value: "momentum", label: "Momentum" },
];

const DATA_SOURCES = [
  { value: "", label: "All Sources" },
  { value: "mock", label: "Mock (simulated)" },
  { value: "live", label: "Live" },
];

const COLUMNS = [
  { key: "created_at", label: "Date" },
  { key: "bot_name", label: "Bot" },
  { key: "strategy_key", label: "Strategy" },
  { key: "symbol", label: "Symbol" },
  { key: "data_source", label: "Data Source" },
  { key: "num_candles", label: "Candles" },
  { key: "final_pnl", label: "Final PnL" },
  { key: "end_cash", label: "End Cash" },
  { key: "total_trades", label: "Trades" },
  { key: "win_rate", label: "Win Rate" },
  { key: "sharpe_ratio", label: "Sharpe" },
  { key: "max_drawdown", label: "Max DD" },
];

function sortRows(rows, key, dir) {
  if (!key) return rows;
  return [...rows].sort((a, b) => {
    let av = a[key];
    let bv = b[key];
    // Numeric fields
    if (["final_pnl", "end_cash", "total_trades", "win_rate", "sharpe_ratio", "max_drawdown", "num_candles"].includes(key)) {
      av = Number(av ?? 0);
      bv = Number(bv ?? 0);
    } else {
      av = String(av ?? "").toLowerCase();
      bv = String(bv ?? "").toLowerCase();
    }
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

// ---------------------------------------------------------------------------
// Detail panel for an expanded row
// ---------------------------------------------------------------------------

function DetailPanel({ row }) {
  const fields = [
    ["Bot ID", row.bot_id],
    ["Bot Name", row.bot_name ?? "—"],
    ["Strategy", row.strategy_key ?? "—"],
    ["Symbol", row.symbol ?? "—"],
    ["Data Source", row.data_source ?? "—"],
    ["Timeframe", row.timeframe ?? "—"],
    ["Candles", row.num_candles ?? "—"],
    ["Start Cash", row.start_cash != null ? `$${Number(row.start_cash).toFixed(2)}` : "—"],
    ["End Cash", row.end_cash != null ? `$${Number(row.end_cash).toFixed(2)}` : "—"],
    ["Final PnL", row.final_pnl != null ? Number(row.final_pnl).toFixed(2) : "—"],
    ["Total Trades", row.total_trades ?? "—"],
    ["Win Rate", row.win_rate != null ? `${Number(row.win_rate).toFixed(1)}%` : "—"],
    ["Sharpe Ratio", row.sharpe_ratio != null ? Number(row.sharpe_ratio).toFixed(3) : "—"],
    ["Max Drawdown", row.max_drawdown != null ? `${(Number(row.max_drawdown) * 100).toFixed(2)}%` : "—"],
    ["Run Date", row.created_at ? new Date(row.created_at).toLocaleString() : "—"],
  ];

  return (
    <tr>
      <td colSpan={COLUMNS.length + 1} className="px-4 py-3 bg-gray-800/80 border-b border-gray-700">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-x-6 gap-y-2">
          {fields.map(([label, val]) => (
            <div key={label}>
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-sm text-gray-200 font-mono">{val}</p>
            </div>
          ))}
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// History page
// ---------------------------------------------------------------------------

export default function History() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filterStrategy, setFilterStrategy] = useState("");
  const [filterDataSource, setFilterDataSource] = useState("");
  const [filterSymbol, setFilterSymbol] = useState("");

  const [sortKey, setSortKey] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");

  const [expandedId, setExpandedId] = useState(null);

  const fetchHistory = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filterStrategy) params.set("strategy_key", filterStrategy);
    if (filterSymbol.trim()) params.set("symbol", filterSymbol.trim());
    const qs = params.toString();
    fetch(`/arena/history${qs ? `?${qs}` : ""}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => setRows(Array.isArray(data) ? data : []))
      .catch((e) => setError(e.message || "Failed to load history"))
      .finally(() => setLoading(false));
  }, [filterStrategy, filterSymbol]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  function handleSortClick(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function toggleExpand(id) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  // Client-side filter for data source (not sent as query param since backend may not support it)
  const filteredRows = filterDataSource
    ? rows.filter((r) => r.data_source === filterDataSource)
    : rows;

  const sorted = sortRows(filteredRows, sortKey, sortDir);

  return (
    <div className="p-6 space-y-6">
      <div className="page-heading"><div>
        <p className="page-kicker">Research archive</p>
        <h1>Backtest History</h1>
        <p className="page-subtitle">Review and explore your previous simulation runs.</p>
      </div></div>

      {/* Filter bar */}
      <div className="card space-y-3">
        <h2 className="text-sm font-semibold text-gray-300">Filters</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="label">Strategy</label>
            <select
              className="input"
              value={filterStrategy}
              onChange={(e) => setFilterStrategy(e.target.value)}
            >
              {ALL_STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Data Source</label>
            <select
              className="input"
              value={filterDataSource}
              onChange={(e) => setFilterDataSource(e.target.value)}
            >
              {DATA_SOURCES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Symbol</label>
            <input
              className="input"
              type="text"
              placeholder="e.g. BTC/USDT"
              value={filterSymbol}
              onChange={(e) => setFilterSymbol(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn-primary"
            onClick={fetchHistory}
          >
            Apply
          </button>
          {(filterStrategy || filterDataSource || filterSymbol) && (
            <button
              type="button"
              className="px-3 py-1.5 rounded text-sm bg-gray-700 hover:bg-gray-600 text-gray-300 border border-gray-600 transition-colors"
              onClick={() => {
                setFilterStrategy("");
                setFilterDataSource("");
                setFilterSymbol("");
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-300">
            Runs
            {!loading && (
              <span className="ml-2 text-xs font-normal text-gray-500">
                ({sorted.length} result{sorted.length !== 1 ? "s" : ""})
              </span>
            )}
          </h2>
        </div>

        {loading && (
          <div className="py-10 flex items-center justify-center gap-3">
            <div style={{
              width: 28, height: 28, border: "3px solid #334155",
              borderTopColor: "#6366f1", borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }} />
            <span className="text-sm text-gray-400">Loading history…</span>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {!loading && error && (
          <p className="text-sm text-red-400 py-4">{error}</p>
        )}

        {!loading && !error && sorted.length === 0 && (
          <div className="py-16 text-center space-y-2">
            <p className="text-gray-400 font-medium">No backtest runs yet.</p>
            <p className="text-sm text-gray-600">Go to Bot Arena to run your first simulation.</p>
          </div>
        )}

        {!loading && !error && sorted.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  {COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      className="th cursor-pointer select-none hover:text-gray-100 transition-colors"
                      onClick={() => handleSortClick(col.key)}
                    >
                      {col.label}
                      <SortIcon dir={sortKey === col.key ? sortDir : null} />
                    </th>
                  ))}
                  <th className="th">Detail</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((row) => {
                  const rowId = row.id ?? row.run_id ?? JSON.stringify(row);
                  const isExpanded = expandedId === rowId;
                  const pnl = Number(row.final_pnl ?? 0);
                  const wr = row.win_rate != null ? Number(row.win_rate) : null;
                  const sharpe = Number(row.sharpe_ratio ?? 0);
                  const dd = Number(row.max_drawdown ?? 0);

                  return (
                    <>
                      <tr
                        key={rowId}
                        className={`border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer transition-colors ${isExpanded ? "bg-gray-800/70" : ""}`}
                        onClick={() => toggleExpand(rowId)}
                      >
                        {/* Date */}
                        <td className="td text-gray-400 text-xs whitespace-nowrap">
                          {row.created_at ? new Date(row.created_at).toLocaleDateString() : "—"}
                          <span className="block text-gray-600 text-xs">
                            {row.created_at ? new Date(row.created_at).toLocaleTimeString() : ""}
                          </span>
                        </td>
                        {/* Bot */}
                        <td className="td font-medium text-gray-100">{row.bot_name ?? row.bot_id?.slice(0, 8) ?? "—"}</td>
                        {/* Strategy */}
                        <td className="td">
                          {row.strategy_key
                            ? <span className="badge badge-blue">{row.strategy_key}</span>
                            : <span className="text-gray-600">—</span>}
                        </td>
                        {/* Symbol */}
                        <td className="td font-mono text-gray-300">{row.symbol ?? "—"}</td>
                        {/* Data Source */}
                        <td className="td">
                          {row.data_source === "live"
                            ? <span className="badge badge-green">live</span>
                            : <span className="badge badge-yellow">mock</span>}
                        </td>
                        {/* Candles */}
                        <td className="td text-gray-400">{row.num_candles ?? "—"}</td>
                        {/* Final PnL */}
                        <td className="td"><PnlCell value={row.final_pnl} /></td>
                        {/* End Cash */}
                        <td className="td font-mono text-gray-300">
                          {row.end_cash != null ? `$${Number(row.end_cash).toFixed(2)}` : "—"}
                        </td>
                        {/* Trades */}
                        <td className="td text-gray-400">{row.total_trades ?? "—"}</td>
                        {/* Win Rate */}
                        <td className="td">
                          {wr !== null
                            ? <span className={wr >= 50 ? "text-emerald-400" : "text-red-400"}>{wr.toFixed(1)}%</span>
                            : <span className="text-gray-600">—</span>}
                        </td>
                        {/* Sharpe */}
                        <td className="td font-mono">
                          <span className={sharpe >= 1 ? "text-emerald-400" : sharpe < 0 ? "text-red-400" : "text-gray-300"}>
                            {sharpe.toFixed(2)}
                          </span>
                        </td>
                        {/* Max DD */}
                        <td className="td font-mono">
                          <span className={dd < -0.1 ? "text-red-400" : "text-gray-300"}>
                            {(dd * 100).toFixed(1)}%
                          </span>
                        </td>
                        {/* Expand toggle */}
                        <td className="td text-center">
                          <span className="text-indigo-400 text-xs select-none">
                            {isExpanded ? "▲" : "▼"}
                          </span>
                        </td>
                      </tr>
                      {isExpanded && <DetailPanel key={`${rowId}-detail`} row={row} />}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
