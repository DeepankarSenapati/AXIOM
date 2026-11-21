import { useEffect, useState } from "react";

const STRATEGY_LABELS = {
  simple_ma: "Moving Average",
  rsi: "RSI",
  bollinger_bands: "Bollinger Bands",
  macd: "MACD",
  momentum: "Momentum",
};

const RANK_STYLES = [
  { medal: "🥇", cls: "text-yellow-400 font-bold" },
  { medal: "🥈", cls: "text-gray-300 font-bold" },
  { medal: "🥉", cls: "text-amber-600 font-bold" },
];

function SharpeBadge({ value }) {
  if (value >= 1) return <span className="text-emerald-400 font-mono font-semibold">{value.toFixed(3)}</span>;
  if (value < 0)  return <span className="text-red-400 font-mono font-semibold">{value.toFixed(3)}</span>;
  return <span className="text-gray-300 font-mono">{value.toFixed(3)}</span>;
}

function PnlCell({ value }) {
  const n = typeof value === "number" ? value : NaN;
  return <span className="text-gray-300 font-mono">{Number.isFinite(n) ? `${n > 0 ? "+" : ""}${n.toFixed(2)}` : "—"}</span>;
}

export function RawAggregates({ entries }) {
  return <details className="mt-6 border-t border-gray-800 pt-4">
    <summary className="text-sm text-gray-300 cursor-pointer">Show raw PnL and alpha calculations</summary>
    <p className="text-xs text-gray-400 mt-3">These numbers may combine different market quote units, starting balances, and periods. The API does not specify a shared unit, so they cannot be treated as comparable currency amounts or identify the best performer. Alpha compares with buy-and-hold without matching exposure.</p>
    <div className="overflow-x-auto mt-3">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-gray-800"><th className="th">Strategy</th><th className="th">Raw average PnL</th><th className="th">Raw average alpha</th><th className="th">Raw maximum PnL</th></tr></thead>
        <tbody>{entries.map((entry) => <tr key={entry.strategy_key} className="border-b border-gray-800">
          <td className="td">{STRATEGY_LABELS[entry.strategy_key] ?? entry.strategy_key}</td>
          <td className="td"><PnlCell value={entry.avg_pnl} /></td>
          <td className="td"><PnlCell value={entry.avg_alpha} /></td>
          <td className="td"><PnlCell value={entry.best_pnl} /></td>
        </tr>)}</tbody>
      </table>
    </div>
  </details>;
}

export default function Leaderboard() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  function fetchLeaderboard() {
    setLoading(true);
    setError(null);
    fetch("/arena/leaderboard")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setEntries)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { fetchLeaderboard(); }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="page-heading">
        <div>
          <p className="page-kicker">Performance intelligence</p>
          <h1>Strategy Leaderboard</h1>
          <p className="page-subtitle">
            Ranked by average Sharpe ratio across all backtest runs.
          </p>
          <p className="page-subtitle">
            Historical and simulated scores can use different markets, periods, and starting balances. They are not standardized or directly comparable; Sharpe uses a fixed 252-period annualization.
          </p>
        </div>
        <button
          onClick={fetchLeaderboard}
          className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
        >
          Refresh
        </button>
      </div>

      <div className="card">
        {loading && <p className="text-sm text-gray-500">Loading leaderboard…</p>}
        {error && <p className="text-sm text-red-400">Error: {error}</p>}

        {!loading && !error && entries.length === 0 && (
          <div className="py-12 text-center space-y-2">
            <p className="text-gray-400 font-medium">No backtest runs yet.</p>
            <p className="text-sm text-gray-600">
              Run backtests in Bot Arena to populate the leaderboard.
            </p>
          </div>
        )}

        {!loading && !error && entries.length > 0 && (
          <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="th">Rank</th>
                  <th className="th">Strategy</th>
                  <th className="th">Runs</th>
                  <th className="th">Avg Sharpe</th>
                  <th className="th">Avg Win Rate</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => {
                  const rankStyle = RANK_STYLES[entry.rank - 1];
                  return (
                    <tr key={entry.strategy_key} className="border-b border-gray-800 hover:bg-gray-800/50">
                      <td className="td text-center">
                        {rankStyle ? (
                          <span className={rankStyle.cls}>
                            {rankStyle.medal} #{entry.rank}
                          </span>
                        ) : (
                          <span className="text-gray-400 font-mono">#{entry.rank}</span>
                        )}
                      </td>
                      <td className="td">
                        <div className="space-y-0.5">
                          <span className="badge badge-blue">
                            {entry.strategy_key}
                          </span>
                          <p className="text-xs text-gray-500">
                            {STRATEGY_LABELS[entry.strategy_key] ?? entry.strategy_key}
                          </p>
                        </div>
                      </td>
                      <td className="td text-gray-400 font-mono">{entry.total_runs}</td>
                      <td className="td"><SharpeBadge value={entry.avg_sharpe} /></td>
                      <td className="td">
                        <span className={
                          entry.avg_win_rate >= 0.5
                            ? "text-emerald-400 font-mono"
                            : "text-red-400 font-mono"
                        }>
                          {(entry.avg_win_rate * 100).toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <RawAggregates entries={entries} />
          </>
        )}
      </div>

      {!loading && !error && entries.length > 0 && (
        <p className="text-xs text-gray-600 text-center">
          Rankings are descriptive only; these historical scores are not standardized across runs.
        </p>
      )}
    </div>
  );
}
