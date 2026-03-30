import { useEffect, useState } from "react";

const STRATEGIES = ["simple_ma", "rsi", "bollinger_bands", "macd", "momentum"];

const STRATEGY_PARAMS = {
  simple_ma: { short_window: 5, long_window: 20 },
  rsi: { period: 14, oversold: 30, overbought: 70 },
  bollinger_bands: { window: 20, num_std: 2.0 },
  macd: { fast: 12, slow: 26, signal: 9 },
  momentum: { window: 10, threshold: 0.02, stop_loss: 0.03 },
};

function useBotHistory() {
  const [historyByBot, setHistoryByBot] = useState({});
  useEffect(() => {
    fetch("/arena/history?limit=500")
      .then(r => r.ok ? r.json() : [])
      .then(runs => {
        const grouped = {};
        for (const run of runs) {
          if (!grouped[run.bot_id]) grouped[run.bot_id] = [];
          grouped[run.bot_id].push(run);
        }
        setHistoryByBot(grouped);
      })
      .catch(() => {});
  }, []);
  return historyByBot;
}

function useBots() {
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchBots = () => {
    setLoading(true);
    fetch("/bots/")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => { setBots(data); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchBots(); }, []);
  return { bots, loading, error, refetch: fetchBots };
}

function StatCard({ label, value, sub, children }) {
  return (
    <div className="card flex flex-col gap-1">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-3xl font-bold text-gray-100">{value}</p>
      {sub && <p className="text-xs text-gray-600">{sub}</p>}
      {children}
    </div>
  );
}

function StrategyBadges() {
  const labels = {
    simple_ma: "MA",
    rsi: "RSI",
    bollinger_bands: "BB",
    macd: "MACD",
    momentum: "MOM",
  };
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {STRATEGIES.map((s) => (
        <span key={s} className="badge badge-blue text-xs">{labels[s]}</span>
      ))}
    </div>
  );
}

function TopPerformerCard() {
  const [best, setBest] = useState(null);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    setFetching(true);
    fetch("/arena/history/best")
      .then((r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        console.log("[TopPerformerCard] fetch result:", data);
        setBest(data);
      })
      .catch((e) => {
        console.error("[TopPerformerCard] fetch error:", e);
        setBest(null);
      })
      .finally(() => setFetching(false));
  }, []);

  const strategyLabel = {
    simple_ma: "MA",
    rsi: "RSI",
    bollinger_bands: "BB",
    macd: "MACD",
    momentum: "MOM",
  };

  function formatDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric", month: "short", day: "numeric",
    });
  }

  function formatCurrency(val) {
    const n = Number(val ?? 0);
    const abs = Math.abs(n).toFixed(2);
    return n >= 0 ? `+$${abs}` : `-$${abs}`;
  }

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Top Performer</h2>
      {fetching && (
        <p className="text-sm text-gray-500">Loading…</p>
      )}
      {!fetching && !best && (
        <p className="text-sm text-gray-500">
          No runs yet — go to <span className="text-indigo-400">Bot Arena</span>
        </p>
      )}
      {!fetching && best && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-base font-bold text-gray-100">{best.bot_name}</span>
            <span className="badge badge-blue">
              {strategyLabel[best.strategy_key] ?? best.strategy_key}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-gray-500">Best PnL</p>
              <p className={`text-lg font-semibold font-mono ${Number(best.final_pnl) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatCurrency(best.final_pnl)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Symbol</p>
              <p className="text-sm font-mono text-gray-200">{best.symbol}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Sharpe Ratio</p>
              <p className={`text-sm font-mono ${Number(best.sharpe_ratio) >= 1 ? "text-emerald-400" : Number(best.sharpe_ratio) < 0 ? "text-red-400" : "text-gray-300"}`}>
                {Number(best.sharpe_ratio ?? 0).toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Run Date</p>
              <p className="text-sm text-gray-400">{formatDate(best.created_at)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const { bots, loading, error, refetch } = useBots();
  const historyByBot = useBotHistory();
  const [form, setForm] = useState({ name: "", strategy_key: "simple_ma" });
  const [botParams, setBotParams] = useState({ ...STRATEGY_PARAMS["simple_ma"] });
  const [paramErrors, setParamErrors] = useState({});
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [deactivating, setDeactivating] = useState(null);

  const totalBots = bots.length;
  const totalActive = bots.filter((b) => b.is_active).length;

  function handleStrategyChange(newStrategy) {
    setForm({ ...form, strategy_key: newStrategy });
    setBotParams({ ...STRATEGY_PARAMS[newStrategy] });
    setParamErrors({});
  }

  function handleParamChange(key, value) {
    const n = parseFloat(value);
    const invalid = isNaN(n) || n <= 0;
    setParamErrors((prev) => ({ ...prev, [key]: invalid }));
    setBotParams({ ...botParams, [key]: invalid ? value : n });
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const res = await fetch("/bots/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          strategy_key: form.strategy_key,
          params: botParams,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setCreateError(JSON.stringify(data.detail || data));
        return;
      }
      setForm({ name: "", strategy_key: "simple_ma" });
      setBotParams({ ...STRATEGY_PARAMS["simple_ma"] });
      setParamErrors({});
      refetch();
    } catch (e) {
      setCreateError(e.message || "Network error");
    } finally {
      setCreating(false);
    }
  }

  function handleDeactivate(botId) {
    setDeactivating(botId);
    fetch(`/bots/${botId}`, { method: "DELETE" })
      .then((r) => { if (!r.ok && r.status !== 204) throw new Error(`HTTP ${r.status}`); refetch(); })
      .catch(console.error)
      .finally(() => setDeactivating(null));
  }

  const currentParams = STRATEGY_PARAMS[form.strategy_key] || {};

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
        <button onClick={refetch} className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm">
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Bots"
          value={loading ? "—" : totalBots}
          sub="registered in system"
        />
        <StatCard
          label="Active Bots"
          value={loading ? "—" : totalActive}
          sub={totalBots > 0 ? `${totalBots - totalActive} deactivated` : "none registered"}
        />
        <StatCard label="Strategies Available" value={STRATEGIES.length}>
          <StrategyBadges />
        </StatCard>
        <StatCard
          label="Total Strategies"
          value={5}
          sub="MA · RSI · BB · MACD · MOM"
        />
      </div>

      {/* Top Performer */}
      <TopPerformerCard />

      {/* Create bot */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Register New Bot</h2>
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="label">Bot Name</label>
              <input
                className="input"
                placeholder="e.g. Alpha-MA"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="w-40">
              <label className="label">Strategy</label>
              <select
                className="input"
                value={form.strategy_key}
                onChange={(e) => handleStrategyChange(e.target.value)}
              >
                {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <button type="submit" className="btn-primary" disabled={creating}>
              {creating ? "Creating…" : "Create Bot"}
            </button>
          </div>

          {/* Strategy parameter inputs */}
          {Object.keys(currentParams).length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Strategy Parameters
              </p>
              <div className="flex flex-wrap gap-3">
                {Object.entries(currentParams).map(([key]) => (
                  <div key={key} className="flex flex-col gap-1">
                    <label className="label text-xs">{key}</label>
                    <input
                      type="number"
                      className={`input w-28 ${paramErrors[key] ? "border-red-500 focus:border-red-500" : ""}`}
                      step="any"
                      min="0"
                      value={botParams[key] ?? currentParams[key]}
                      onChange={(e) => handleParamChange(key, e.target.value)}
                    />
                    {paramErrors[key] && (
                      <p className="text-xs text-red-400 mt-0.5">Must be &gt; 0</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </form>
        {createError && <p className="mt-2 text-xs text-red-400">{createError}</p>}
      </div>

      {/* Bot list */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Registered Bots</h2>
        {loading && <p className="text-sm text-gray-500">Loading…</p>}
        {error && <p className="text-sm text-red-400">Error: {error}</p>}
        {!loading && !error && bots.length === 0 && (
          <p className="text-sm text-gray-500">No bots registered yet.</p>
        )}
        {bots.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th">Name</th>
                <th className="th">Strategy</th>
                <th className="th">Status</th>
                <th className="th">Runs</th>
                <th className="th">Best PnL</th>
                <th className="th">Created</th>
                <th className="th">ID</th>
                <th className="th"></th>
              </tr>
            </thead>
            <tbody>
              {bots.map((bot) => (
                <tr key={bot.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="td font-medium text-gray-100">{bot.name}</td>
                  <td className="td"><span className="badge badge-blue">{bot.strategy_name}</span></td>
                  <td className="td">
                    {bot.is_active
                      ? <span className="badge badge-green">Active</span>
                      : <span className="badge badge-red">Inactive</span>}
                  </td>
                  <td className="td">
                    <span className="badge bg-gray-700 text-gray-400">
                      {historyByBot[bot.id]?.length ?? 0}
                    </span>
                  </td>
                  <td className="td">
                    {(() => {
                      const runs = historyByBot[bot.id];
                      if (!runs || runs.length === 0) {
                        return <span className="text-gray-600">—</span>;
                      }
                      const bestPnl = Math.max(...runs.map(r => Number(r.final_pnl ?? 0)));
                      const abs = Math.abs(bestPnl).toFixed(2);
                      return bestPnl >= 0
                        ? <span className="badge badge-green font-mono">+${abs}</span>
                        : <span className="badge badge-red font-mono">-${abs}</span>;
                    })()}
                  </td>
                  <td className="td text-gray-500">{new Date(bot.created_at).toLocaleDateString()}</td>
                  <td className="td font-mono text-xs text-gray-600">{bot.id.slice(0, 8)}…</td>
                  <td className="td">
                    <button
                      onClick={() => handleDeactivate(bot.id)}
                      disabled={deactivating === bot.id || !bot.is_active}
                      className="btn-danger text-xs px-2 py-1"
                    >
                      {deactivating === bot.id ? "…" : "Deactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
