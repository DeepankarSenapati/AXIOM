import { useEffect, useState } from "react";

const STRATEGIES = ["simple_ma", "rsi", "bollinger_bands", "macd"];

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
  };
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {STRATEGIES.map((s) => (
        <span key={s} className="badge badge-blue text-xs">{labels[s]}</span>
      ))}
    </div>
  );
}

function TopPerformerCard({ bots }) {
  if (bots.length === 0) {
    return (
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Top Performer</h2>
        <p className="text-sm text-gray-500">
          Run the arena on the <span className="text-indigo-400">Bot Arena</span> page to see performance rankings here.
        </p>
      </div>
    );
  }
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Top Performer</h2>
      <p className="text-sm text-gray-500">
        No backtest results stored yet —{" "}
        <span className="text-indigo-400">Bot Arena</span> to run a simulation.
      </p>
      <p className="text-xs text-gray-600 mt-2">
        {bots.length} bot{bots.length !== 1 ? "s" : ""} available to compete.
      </p>
    </div>
  );
}

export default function Dashboard() {
  const { bots, loading, error, refetch } = useBots();
  const [form, setForm] = useState({ name: "", strategy_key: "simple_ma" });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [deactivating, setDeactivating] = useState(null);

  const totalBots = bots.length;
  const totalActive = bots.filter((b) => b.is_active).length;

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const res = await fetch("/bots/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: form.name, strategy_key: form.strategy_key }),
      });
      const data = await res.json();
      if (!res.ok) {
        setCreateError(JSON.stringify(data.detail || data));
        return;
      }
      setForm({ name: "", strategy_key: "simple_ma" });
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
          value={4}
          sub="MA · RSI · BB · MACD"
        />
      </div>

      {/* Top Performer */}
      <TopPerformerCard bots={bots} />

      {/* Create bot */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Register New Bot</h2>
        <form onSubmit={handleCreate} className="flex gap-3 items-end">
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
              onChange={(e) => setForm({ ...form, strategy_key: e.target.value })}
            >
              {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <button type="submit" className="btn-primary" disabled={creating}>
            {creating ? "Creating…" : "Create Bot"}
          </button>
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
