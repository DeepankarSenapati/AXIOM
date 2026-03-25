import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";

const PIE_DATA = [
  { name: "Public (70%)", value: 70, color: "#6366f1" },
  { name: "Tech (15%)",   value: 15, color: "#10b981" },
  { name: "Gov (15%)",    value: 15, color: "#f59e0b" },
];

function BalanceBar({ label, amount, total, colorClass }) {
  const pct = total > 0 ? (amount / total) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-200 font-mono">{amount.toLocaleString()} RST ({pct.toFixed(1)}%)</span>
      </div>
      <div className="h-2 bg-gray-800 rounded overflow-hidden">
        <div className={`h-full ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function DistributionResult({ result }) {
  const shares = [
    { label: "Public Pool", amount: result.public_share, color: "text-indigo-400", bg: "bg-indigo-900/30 border-indigo-800" },
    { label: "Tech Company", amount: result.tech_share,   color: "text-emerald-400", bg: "bg-emerald-900/30 border-emerald-800" },
    { label: "Governance",   amount: result.gov_share,    color: "text-amber-400",   bg: "bg-amber-900/30 border-amber-800" },
  ];

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-xs">
        <p style={{ color: payload[0].payload.color }}>{payload[0].name}</p>
        <p className="text-gray-100">{payload[0].value}%</p>
      </div>
    );
  };

  return (
    <div className="border-t border-gray-800 pt-3 space-y-4">
      <h4 className="text-xs font-medium text-gray-400">Distribution Result</h4>

      {/* 3 share cards */}
      <div className="grid grid-cols-3 gap-3">
        {shares.map(({ label, amount, color, bg }) => (
          <div key={label} className={`rounded-lg border p-3 ${bg}`}>
            <p className="text-xs text-gray-400 mb-1">{label}</p>
            <p className={`text-xl font-bold font-mono ${color}`}>${amount?.toFixed(2)}</p>
            <p className="text-xs text-gray-600 mt-0.5">
              {((amount / result.total_revenue) * 100).toFixed(0)}% of revenue
            </p>
          </div>
        ))}
      </div>

      {/* Pie chart */}
      <div className="flex items-center gap-4">
        <div className="h-36 w-36 flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={PIE_DATA} cx="50%" cy="50%" innerRadius={28} outerRadius={52} paddingAngle={3} dataKey="value">
                {PIE_DATA.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2">
          {PIE_DATA.map((d) => (
            <div key={d.name} className="flex items-center gap-2 text-xs">
              <span className="inline-block w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: d.color }} />
              <span className="text-gray-400">{d.name}</span>
            </div>
          ))}
          <p className="text-xs text-gray-600 pt-1">
            {result.distributions?.length ?? 0} holder payouts processed
          </p>
        </div>
      </div>
    </div>
  );
}

function BotTokenomics({ bot }) {
  const [balances, setBalances] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [initializing, setInitializing] = useState(false);
  const [distributing, setDistributing] = useState(false);
  const [revenue, setRevenue] = useState(1000);
  const [distResult, setDistResult] = useState(null);

  function fetchBalances() {
    setLoading(true);
    fetch(`/tokenomics/${bot.id}/balances`)
      .then((r) => { if (r.status === 404) return null; if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setBalances)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { fetchBalances(); }, [bot.id]);

  function handleInit() {
    setInitializing(true);
    fetch("/tokenomics/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_id: bot.id }),
    })
      .then((r) => { if (!r.ok) return r.json().then((d) => { throw new Error(d.detail); }); return r.json(); })
      .then(setBalances)
      .catch((e) => setError(e.message))
      .finally(() => setInitializing(false));
  }

  function handleDistribute() {
    setDistributing(true);
    setDistResult(null);
    fetch("/tokenomics/distribute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_id: bot.id, total_revenue: Number(revenue) }),
    })
      .then((r) => { if (!r.ok) return r.json().then((d) => { throw new Error(d.detail); }); return r.json(); })
      .then((data) => { setDistResult(data); fetchBalances(); })
      .catch((e) => setError(e.message))
      .finally(() => setDistributing(false));
  }

  const totalRst = balances ? Object.values(balances.balances).reduce((s, v) => s + v, 0) : 0;
  const COLOR_MAP = { public_pool: "bg-indigo-500", tech_wallet: "bg-emerald-500", gov_wallet: "bg-amber-500" };

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-100">{bot.name}</h3>
          <p className="text-xs text-gray-500">{bot.strategy_name}</p>
        </div>
        <div className="flex gap-2">
          {balances === null && !loading && (
            <button onClick={handleInit} disabled={initializing} className="btn-primary text-xs">
              {initializing ? "Initializing…" : "Initialize Tokens"}
            </button>
          )}
          {balances && (
            <button onClick={fetchBalances} className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs">
              Refresh
            </button>
          )}
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {balances === null && !loading && <p className="text-sm text-gray-500">Tokens not initialized for this bot.</p>}

      {balances && (
        <>
          <div className="space-y-2">
            {Object.entries(balances.balances).map(([holder, amount]) => (
              <BalanceBar
                key={holder}
                label={holder.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                amount={amount}
                total={totalRst}
                colorClass={COLOR_MAP[holder] ?? "bg-gray-500"}
              />
            ))}
          </div>

          <div className="border-t border-gray-800 pt-3 space-y-2">
            <h4 className="text-xs font-medium text-gray-400">Distribute Revenue</h4>
            <div className="flex gap-2">
              <input
                className="input flex-1"
                type="number" min="0" step="0.01"
                value={revenue}
                onChange={(e) => setRevenue(e.target.value)}
                placeholder="Revenue amount ($)"
              />
              <button onClick={handleDistribute} disabled={distributing} className="btn-primary">
                {distributing ? "Distributing…" : "Distribute"}
              </button>
            </div>
          </div>

          {distResult && <DistributionResult result={distResult} />}
        </>
      )}
    </div>
  );
}

export default function Tokenomics() {
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/bots/")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setBots)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Tokenomics</h1>
        <p className="text-sm text-gray-400 mt-1">
          Each bot has 1,000,000 RST — 70% public / 15% tech / 15% governance.
        </p>
      </div>
      {loading && <p className="text-sm text-gray-500">Loading bots…</p>}
      {error && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && bots.length === 0 && <p className="text-sm text-gray-500">No bots found.</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {bots.map((bot) => <BotTokenomics key={bot.id} bot={bot} />)}
      </div>
    </div>
  );
}
