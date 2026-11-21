import { useEffect, useState } from "react";
import { apiFetch } from "../auth.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STRATEGIES = ["simple_ma", "rsi", "bollinger_bands", "macd", "momentum"];

const STRATEGY_PARAMS = {
  simple_ma: { short_window: 5, long_window: 20 },
  rsi: { period: 14, oversold: 30, overbought: 70 },
  bollinger_bands: { window: 20, num_std: 2.0 },
  macd: { fast: 12, slow: 26, signal: 9 },
  momentum: { window: 10, threshold: 0.02, stop_loss: 0.03 },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

function fmtMoney(n) {
  return Number(n ?? 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function StatusBadge({ status }) {
  const map = {
    pending_approval: "badge-yellow",
    approved: "badge-blue",
    live: "badge-green",
    rejected: "badge-red",
  };
  return (
    <span className={`badge ${map[status] ?? "bg-gray-700 text-gray-400"}`}>
      {status ?? "unknown"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Section A — Summary Stat Cards
// ---------------------------------------------------------------------------

function SummaryCards({ summary, loading }) {
  const cards = [
    {
      label: "Tech Pool Allocations (15%)",
      value: loading ? "—" : `$${fmtMoney(summary?.total_your_earnings ?? 0)}`,
      sub: "simulated allocations, not wallet credits",
      accent: "text-emerald-400",
    },
    {
      label: "Active Bots",
      value: loading ? "—" : (summary?.approved_bots ?? 0),
      sub: `of ${summary?.total_bots ?? 0} submitted`,
      accent: "text-gray-100",
    },
    {
      label: "Token Investors",
      value: loading ? "—" : (summary?.total_token_holders ?? 0),
      sub: "unique RST holders across your bots",
      accent: "text-indigo-400",
    },
    {
      label: "Distribution Events",
      value: loading ? "—" : (summary?.total_distributions ?? 0),
      sub: "revenue events processed",
      accent: "text-gray-100",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map(({ label, value, sub, accent }) => (
        <div key={label} className="card stat-card flex flex-col gap-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
          <p className={`text-3xl font-bold font-mono ${accent}`}>{value}</p>
          <p className="text-xs text-gray-600">{sub}</p>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section B — My Bots + Earnings (merged)
// ---------------------------------------------------------------------------

function MyBotsEarnings({ bots, loading, error }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-300">My Bots</h2>
        <p className="text-xs text-gray-600">Tech pool allocations are not credits to your wallet.</p>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && bots.length === 0 && (
        <p className="text-sm text-gray-500">You haven't submitted any bots yet.</p>
      )}

      {bots.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th">Bot Name</th>
                <th className="th">Strategy</th>
                <th className="th">Status</th>
                <th className="th">Revenue Distributed</th>
                <th className="th">Tech Pool 15%</th>
                <th className="th">Investors</th>
                <th className="th">RST Circulating</th>
                <th className="th">Distributions</th>
                <th className="th">Submitted</th>
              </tr>
            </thead>
            <tbody>
              {bots.map(bot => (
                <tr key={bot.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="td">
                    <div>
                      <p className="font-medium text-gray-100">{bot.name}</p>
                      {bot.description && (
                        <p className="text-xs text-gray-500 truncate max-w-[180px]">{bot.description}</p>
                      )}
                    </div>
                  </td>
                  <td className="td">
                    <span className="badge badge-blue">{bot.strategy_key}</span>
                  </td>
                  <td className="td">
                    <StatusBadge status={bot.status} />
                  </td>
                  <td className="td font-mono text-gray-300">
                    {bot.total_revenue_distributed > 0
                      ? `$${fmtMoney(bot.total_revenue_distributed)}`
                      : <span className="text-gray-600">—</span>}
                  </td>
                  <td className="td font-mono font-semibold">
                    {bot.your_earnings > 0
                      ? <span className="text-emerald-400">${fmtMoney(bot.your_earnings)}</span>
                      : <span className="text-gray-600">—</span>}
                  </td>
                  <td className="td text-center font-mono text-gray-300">
                    {bot.token_holder_count > 0
                      ? bot.token_holder_count
                      : <span className="text-gray-600">0</span>}
                  </td>
                  <td className="td font-mono text-gray-400">
                    {bot.tokens_in_circulation > 0
                      ? bot.tokens_in_circulation.toLocaleString()
                      : <span className="text-gray-600">0</span>}
                  </td>
                  <td className="td text-center font-mono text-gray-400">
                    {bot.distribution_count > 0
                      ? bot.distribution_count
                      : <span className="text-gray-600">0</span>}
                  </td>
                  <td className="td text-gray-500">{fmt(bot.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section C — Submit New Bot (unchanged)
// ---------------------------------------------------------------------------

function SubmitBot({ onBotCreated }) {
  const [form, setForm] = useState({ name: "", strategy_key: "simple_ma", description: "" });
  const [botParams, setBotParams] = useState({ ...STRATEGY_PARAMS["simple_ma"] });
  const [paramErrors, setParamErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  function handleStrategyChange(newStrategy) {
    setForm(f => ({ ...f, strategy_key: newStrategy }));
    setBotParams({ ...STRATEGY_PARAMS[newStrategy] });
    setParamErrors({});
  }

  function handleParamChange(key, value) {
    const n = parseFloat(value);
    const invalid = isNaN(n) || n <= 0;
    setParamErrors(prev => ({ ...prev, [key]: invalid }));
    setBotParams(prev => ({ ...prev, [key]: invalid ? value : n }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    setSuccessMsg(null);

    try {
      const res = await apiFetch("/bots/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(),
          strategy_key: form.strategy_key,
          description: form.description.trim(),
          params: botParams,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSubmitError(JSON.stringify(data.detail ?? data));
        return;
      }
      setSuccessMsg("Submitted! Awaiting admin approval.");
      setForm({ name: "", strategy_key: "simple_ma", description: "" });
      setBotParams({ ...STRATEGY_PARAMS["simple_ma"] });
      setParamErrors({});
      onBotCreated();
    } catch (e) {
      setSubmitError(e.message ?? "Network error");
    } finally {
      setSubmitting(false);
    }
  }

  const currentParams = STRATEGY_PARAMS[form.strategy_key] ?? {};

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Submit New Bot</h2>

      {successMsg && (
        <div className="mb-3 px-3 py-2 rounded bg-green-900/50 border border-green-700 text-green-300 text-sm">
          {successMsg}
        </div>
      )}
      {submitError && (
        <p className="mb-2 text-xs text-red-400">{submitError}</p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[160px]">
            <label className="label">Bot Name</label>
            <input
              className="input"
              placeholder="e.g. Alpha-RSI"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              required
            />
          </div>
          <div className="w-44">
            <label className="label">Strategy</label>
            <select
              className="input"
              value={form.strategy_key}
              onChange={e => handleStrategyChange(e.target.value)}
            >
              {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            className="input min-h-[72px] resize-y"
            placeholder="What does this bot do?"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          />
        </div>

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
                    onChange={e => handleParamChange(key, e.target.value)}
                  />
                  {paramErrors[key] && (
                    <p className="text-xs text-red-400">Must be &gt; 0</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit Bot"}
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function TechDashboard() {
  const [bots, setBots] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function fetchDashboard() {
    setLoading(true);
    try {
      const res = await apiFetch("/tech/my-dashboard");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setBots(data.bots ?? []);
      setSummary(data.summary ?? null);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchDashboard(); }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="page-heading">
        <div>
          <p className="page-kicker">Builder workspace</p>
          <h1>Tech Dashboard</h1>
          <p className="page-subtitle">
            Simulated distributions allocate 15% of distributable revenue to the tech pool; this is not a credit to your wallet.
          </p>
        </div>
        <button
          onClick={fetchDashboard}
          className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
        >
          Refresh
        </button>
      </div>

      {/* A — Summary Cards */}
      <SummaryCards summary={summary} loading={loading} />

      {/* B — My Bots + Earnings */}
      <MyBotsEarnings bots={bots} loading={loading} error={error} />

      {/* C — Submit New Bot */}
      <SubmitBot onBotCreated={fetchDashboard} />
    </div>
  );
}
