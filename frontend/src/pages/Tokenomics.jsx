import { useEffect, useState } from "react";

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
      .then((r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
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
      .then((r) => {
        if (!r.ok) return r.json().then((d) => { throw new Error(d.detail); });
        return r.json();
      })
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
      .then((r) => {
        if (!r.ok) return r.json().then((d) => { throw new Error(d.detail); });
        return r.json();
      })
      .then((data) => {
        setDistResult(data);
        fetchBalances();
      })
      .catch((e) => setError(e.message))
      .finally(() => setDistributing(false));
  }

  const totalRst = balances
    ? Object.values(balances.balances).reduce((s, v) => s + v, 0)
    : 0;

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-100">{bot.name}</h3>
          <p className="text-xs text-gray-500">{bot.strategy_name}</p>
        </div>
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

      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {balances === null && !loading && (
        <p className="text-sm text-gray-500">Tokens not initialized for this bot.</p>
      )}

      {balances && (
        <>
          <div className="space-y-2">
            {Object.entries(balances.balances).map(([holder, amount]) => {
              const colorMap = {
                public_pool: "bg-indigo-500",
                tech_wallet: "bg-emerald-500",
                gov_wallet: "bg-amber-500",
              };
              return (
                <BalanceBar
                  key={holder}
                  label={holder.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  amount={amount}
                  total={totalRst}
                  colorClass={colorMap[holder] ?? "bg-gray-500"}
                />
              );
            })}
          </div>

          <div className="border-t border-gray-800 pt-3 space-y-2">
            <h4 className="text-xs font-medium text-gray-400">Distribute Revenue</h4>
            <div className="flex gap-2">
              <div className="flex-1">
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={revenue}
                  onChange={(e) => setRevenue(e.target.value)}
                  placeholder="Revenue amount ($)"
                />
              </div>
              <button onClick={handleDistribute} disabled={distributing} className="btn-primary">
                {distributing ? "Distributing…" : "Distribute"}
              </button>
            </div>
          </div>

          {distResult && (
            <div className="bg-gray-800 rounded p-3 text-xs space-y-1">
              <p className="text-gray-300 font-medium">Distribution Result</p>
              <div className="grid grid-cols-3 gap-2 text-gray-400">
                <span>Public: <span className="text-green-400">${distResult.public_share?.toFixed(2)}</span></span>
                <span>Tech: <span className="text-blue-400">${distResult.tech_share?.toFixed(2)}</span></span>
                <span>Gov: <span className="text-amber-400">${distResult.gov_share?.toFixed(2)}</span></span>
              </div>
              <p className="text-gray-500">{distResult.distributions?.length} holder payouts processed</p>
            </div>
          )}
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
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setBots)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-100">Tokenomics</h1>
      <p className="text-sm text-gray-400">
        Each bot has 1,000,000 RST — 70% public / 15% tech / 15% governance.
      </p>

      {loading && <p className="text-sm text-gray-500">Loading bots…</p>}
      {error && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && bots.length === 0 && (
        <p className="text-sm text-gray-500">No bots found.</p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {bots.map((bot) => (
          <BotTokenomics key={bot.id} bot={bot} />
        ))}
      </div>
    </div>
  );
}
