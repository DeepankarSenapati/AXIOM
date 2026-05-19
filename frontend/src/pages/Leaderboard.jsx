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
  const n = Number(value ?? 0);
  if (n > 0) return <span className="text-emerald-400 font-mono font-semibold">+{n.toFixed(2)}</span>;
  if (n < 0) return <span className="text-red-400 font-mono font-semibold">{n.toFixed(2)}</span>;
  return <span className="text-gray-400 font-mono">0.00</span>;
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Strategy Leaderboard</h1>
          <p className="text-sm text-gray-400 mt-1">
            Ranked by average Sharpe ratio across all backtest runs.
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="th">Rank</th>
                  <th className="th">Strategy</th>
                  <th className="th">Runs</th>
                  <th className="th">Avg Sharpe</th>
                  <th className="th">Avg PnL</th>
                  <th className="th" title="Average alpha vs buy-and-hold">Avg Alpha</th>
                  <th className="th">Best PnL</th>
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
                      <td className="td"><PnlCell value={entry.avg_pnl} /></td>
                      <td className="td"><PnlCell value={entry.avg_alpha ?? 0} /></td>
                      <td className="td"><PnlCell value={entry.best_pnl} /></td>
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
        )}
      </div>

      {!loading && !error && entries.length > 0 && (
        <p className="text-xs text-gray-600 text-center">
          Sharpe ratio is the primary ranking signal — higher is better. Negative Sharpe means returns don't justify volatility.
        </p>
      )}
    </div>
  );
}
