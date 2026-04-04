import { useEffect, useState } from "react";
import { authHeaders } from "../auth.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
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
// Section A — Platform Bots Overview
// ---------------------------------------------------------------------------

function PlatformBotsOverview({ bots, loading, error }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-1">Platform Bots Overview</h2>
      <p className="text-xs text-gray-500 mb-3">Bots under governance oversight</p>
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
              <th className="th">Candles Run</th>
            </tr>
          </thead>
          <tbody>
            {bots.map(bot => (
              <tr key={bot.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td font-medium text-gray-100">{bot.name}</td>
                <td className="td">
                  <span className="badge badge-blue">{bot.strategy_key ?? bot.strategy_name}</span>
                </td>
                <td className="td">
                  <StatusBadge status={bot.status} />
                </td>
                <td className="td text-gray-400">
                  {bot.candles_run ?? bot.total_candles ?? <span className="text-gray-600">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section B — Satisfaction Polls
// ---------------------------------------------------------------------------

function SatisfactionPolls({ bots }) {
  const [pollsByBot, setPollsByBot] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!bots || bots.length === 0) return;
    setLoading(true);
    Promise.all(
      bots.map(bot =>
        fetch(`/governance/${bot.id}/polls`, { headers: authHeaders() })
          .then(r => (r.ok ? r.json() : []))
          .then(polls => ({ botId: bot.id, botName: bot.name, polls }))
          .catch(() => ({ botId: bot.id, botName: bot.name, polls: [] }))
      )
    ).then(results => {
      const grouped = {};
      for (const { botId, botName, polls } of results) {
        if (polls.length > 0) grouped[botId] = { botName, polls };
      }
      setPollsByBot(grouped);
      setLoading(false);
    });
  }, [bots]);

  const allPolls = Object.entries(pollsByBot).flatMap(([, { botName, polls }]) =>
    polls.map(p => ({ ...p, bot_name: botName }))
  );

  function satisfactionColor(rate) {
    const pct = Number(rate ?? 0);
    return pct >= 0.5 ? "text-emerald-400" : "text-red-400";
  }

  function stageLabel(stage) {
    return { 1: "Normal", 2: "Review", 3: "Community" }[stage] ?? `Stage ${stage}`;
  }

  function stageBadgeClass(stage) {
    return { 1: "badge-green", 2: "badge-yellow", 3: "badge-red" }[stage] ?? "bg-gray-700 text-gray-400";
  }

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Satisfaction Polls</h2>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {!loading && allPolls.length === 0 && (
        <div className="py-6 text-center space-y-1">
          <p className="text-sm text-gray-500">No polls closed yet.</p>
          <p className="text-xs text-gray-600">
            Polls are submitted via the{" "}
            <span className="text-indigo-400">Governance</span> voting page and closed per bot per quarter.
          </p>
        </div>
      )}
      {allPolls.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="th">Bot</th>
              <th className="th">Quarter</th>
              <th className="th">Satisfaction</th>
              <th className="th">Stage</th>
              <th className="th">Closed At</th>
            </tr>
          </thead>
          <tbody>
            {allPolls.map((poll, i) => (
              <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td font-medium text-gray-100">{poll.bot_name ?? "—"}</td>
                <td className="td text-gray-400">{poll.quarter ?? "—"}</td>
                <td className={`td font-mono font-semibold ${satisfactionColor(poll.satisfaction_rate)}`}>
                  {poll.satisfaction_rate != null
                    ? `${(Number(poll.satisfaction_rate) * 100).toFixed(1)}%`
                    : "—"}
                </td>
                <td className="td">
                  <span className={`badge ${stageBadgeClass(poll.stage_at_close)}`}>
                    {stageLabel(poll.stage_at_close)}
                  </span>
                </td>
                <td className="td text-gray-500">{fmt(poll.closed_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section C — Revenue Summary (placeholder)
// ---------------------------------------------------------------------------

function GovRevenue() {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-2">Revenue Summary</h2>
      <p className="text-sm text-gray-500">Governance revenue tracking coming soon.</p>
      <p className="text-xs text-gray-600 mt-1">Governance company receives 15% of each bot&#39;s revenue.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function GovernanceDashboard() {
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function fetchBots() {
    setLoading(true);
    try {
      const res = await fetch("/bots/", { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBots(await res.json());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchBots(); }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Governance Dashboard</h1>
        <button
          onClick={fetchBots}
          className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
        >
          Refresh
        </button>
      </div>

      {/* A — Platform Bots Overview */}
      <PlatformBotsOverview bots={bots} loading={loading} error={error} />

      {/* B — Satisfaction Polls */}
      <SatisfactionPolls bots={bots} />

      {/* C — Revenue Summary */}
      <GovRevenue />
    </div>
  );
}
