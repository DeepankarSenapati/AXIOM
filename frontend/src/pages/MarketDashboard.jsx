import { useEffect, useState } from "react";
import { apiFetch } from "../auth.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RST_PRICE = 0.01;
const EXIT_FEE  = 0.02;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STRATEGY_LABELS = {
  simple_ma:       "MA",
  rsi:             "RSI",
  bollinger_bands: "BB",
  macd:            "MACD",
  momentum:        "MOM",
};

const STRATEGY_DESCRIPTIONS = {
  simple_ma:       "Buys when a short moving average crosses above a long moving average. Sells on the reverse cross. Works best in trending markets.",
  rsi:             "Buys when RSI drops below the oversold threshold (undervalued signal). Sells when RSI rises above the overbought threshold.",
  bollinger_bands: "Buys when price touches the lower Bollinger Band (mean-reversion signal). Sells when price touches the upper band.",
  macd:            "Buys when the MACD line crosses above the signal line. Sells on the reverse. A momentum and trend-following strategy.",
  momentum:        "Buys when recent price momentum exceeds a threshold. Sells when momentum reverses or a stop-loss is hit.",
};

function fmtMoney(n) {
  return Number(n ?? 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

function StatusBadge({ status }) {
  const map = {
    pending_approval: "badge-yellow",
    approved:         "badge-blue",
    live:             "badge-green",
    rejected:         "badge-red",
  };
  return (
    <span className={`badge ${map[status] ?? "bg-gray-700 text-gray-400"}`}>
      {status ?? "unknown"}
    </span>
  );
}

function RiskBadge({ rating }) {
  const map = {
    Low:     "badge-green",
    Medium:  "badge-yellow",
    High:    "badge-red",
    Unrated: "bg-gray-700 text-gray-400",
  };
  return (
    <span className={`badge ${map[rating] ?? "bg-gray-700 text-gray-400"}`}>
      {rating ?? "Unrated"} Risk
    </span>
  );
}

function PnlText({ value }) {
  const n = Number(value ?? 0);
  if (n > 0) return <span className="text-emerald-400 font-mono font-semibold">+${fmtMoney(n)}</span>;
  if (n < 0) return <span className="text-red-400 font-mono font-semibold">-${fmtMoney(Math.abs(n))}</span>;
  return <span className="text-gray-400 font-mono">$0.00</span>;
}

// ---------------------------------------------------------------------------
// Bot Profile Modal
// ---------------------------------------------------------------------------

function BotProfileModal({ botId, onClose, onBuy }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    setLoading(true);
    apiFetch(`/bots/${botId}/profile`)
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(data => { setProfile(data); setLoading(false); })
      .catch(e  => { setError(String(e)); setLoading(false); });
  }, [botId]);

  const dist = profile?.token_distribution;
  const investorPct = dist && dist.total > 0
    ? ((dist.investor_holdings / dist.total) * 100).toFixed(1)
    : 0;
  const publicPct = dist && dist.total > 0
    ? ((dist.public_pool_remaining / dist.total) * 100).toFixed(1)
    : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl">

        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-800">
          <div className="space-y-2">
            {loading
              ? <p className="text-gray-400 text-sm">Loading profile…</p>
              : error
                ? <p className="text-red-400 text-sm">Failed to load: {error}</p>
                : (
                  <>
                    <h2 className="text-xl font-bold text-gray-100">{profile.name}</h2>
                    <div className="flex flex-wrap gap-2">
                      <span className="badge badge-blue">
                        {STRATEGY_LABELS[profile.strategy_key] ?? profile.strategy_key}
                      </span>
                      <StatusBadge status={profile.status} />
                      <RiskBadge rating={profile.risk_rating} />
                    </div>
                    <p className="text-xs text-gray-400">Risk label is a heuristic based on past simulated runs when available; it is not a prediction.</p>
                  </>
                )
            }
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-200 text-xl leading-none ml-4 flex-shrink-0"
          >
            ✕
          </button>
        </div>

        {!loading && !error && profile && (
          <div className="p-5 space-y-6">

            {/* Built by + Strategy description */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-lg bg-gray-800 border border-gray-700 p-3 space-y-1">
                <p className="text-xs text-gray-500 uppercase tracking-wider">Built by</p>
                <p className="text-sm font-medium text-gray-100">
                  {profile.tech_company_name ?? "Unknown"}
                </p>
                <p className="text-xs text-gray-500">Listed {fmtDate(profile.created_at)}</p>
              </div>
              <div className="rounded-lg bg-gray-800 border border-gray-700 p-3 space-y-1">
                <p className="text-xs text-gray-500 uppercase tracking-wider">RST Price</p>
                <p className="text-sm font-mono font-bold text-gray-100">$0.01 / token</p>
                <p className="text-xs text-gray-500">Simulated — Phase 1 MVP</p>
              </div>
            </div>

            {/* Strategy plain-English description */}
            <div className="rounded-lg bg-gray-800/50 border border-gray-700 p-3">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">How this strategy works</p>
              <p className="text-sm text-gray-300">
                {profile.description?.trim()
                  ? profile.description
                  : STRATEGY_DESCRIPTIONS[profile.strategy_key] ?? "No description provided."}
              </p>
            </div>

            {/* Token Distribution */}
            {dist ? (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                  Token Distribution
                </p>
                <div className="rounded-lg bg-gray-800 border border-gray-700 p-4 space-y-3">
                  {/* Progress bar */}
                  <div className="h-3 rounded-full bg-gray-700 overflow-hidden flex">
                    <div
                      className="h-full bg-indigo-500"
                      style={{ width: `${investorPct}%` }}
                      title={`Investors: ${investorPct}%`}
                    />
                    <div
                      className="h-full bg-gray-600"
                      style={{ width: `${publicPct}%` }}
                      title={`Public pool: ${publicPct}%`}
                    />
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div>
                      <div className="flex items-center gap-1 mb-0.5">
                        <span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" />
                        <span className="text-gray-400">Investors</span>
                      </div>
                      <p className="font-mono text-gray-200">{dist.investor_holdings.toLocaleString()} RST</p>
                      <p className="text-gray-600">{dist.investor_count} holders</p>
                    </div>
                    <div>
                      <div className="flex items-center gap-1 mb-0.5">
                        <span className="w-2 h-2 rounded-full bg-gray-600 inline-block" />
                        <span className="text-gray-400">Available</span>
                      </div>
                      <p className="font-mono text-gray-200">{dist.public_pool_remaining.toLocaleString()} RST</p>
                      <p className="text-gray-600">{publicPct}% remaining</p>
                    </div>
                    <div>
                      <div className="flex items-center gap-1 mb-0.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                        <span className="text-gray-400">Tech Co.</span>
                      </div>
                      <p className="font-mono text-gray-200">{dist.tech_holdings.toLocaleString()} RST</p>
                    </div>
                    <div>
                      <div className="flex items-center gap-1 mb-0.5">
                        <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                        <span className="text-gray-400">Governance</span>
                      </div>
                      <p className="font-mono text-gray-200">{dist.gov_holdings.toLocaleString()} RST</p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-600">Tokens not yet initialized for this bot.</p>
            )}

            {/* Performance Summary */}
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Performance Summary
                <span className="ml-2 text-gray-700 normal-case font-normal">
                  ({profile.run_count} backtest run{profile.run_count !== 1 ? "s" : ""})
                </span>
              </p>
              {profile.run_count === 0 ? (
                <p className="text-sm text-gray-500">
                  No backtest runs yet. Run this bot in Bot Arena to generate performance data.
                </p>
              ) : (
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: "Avg Sharpe",  value: profile.avg_sharpe?.toFixed(3) ?? "—", accent: profile.avg_sharpe >= 1 ? "text-emerald-400" : profile.avg_sharpe >= 0.3 ? "text-yellow-400" : "text-red-400" },
                    { label: "Avg PnL",     value: profile.avg_pnl != null ? (profile.avg_pnl >= 0 ? `+$${fmtMoney(profile.avg_pnl)}` : `-$${fmtMoney(Math.abs(profile.avg_pnl))}`) : "—", accent: profile.avg_pnl >= 0 ? "text-emerald-400" : "text-red-400" },
                    { label: "Best PnL",    value: profile.best_pnl != null ? `${profile.best_pnl > 0 ? "+" : profile.best_pnl < 0 ? "-" : ""}$${fmtMoney(Math.abs(profile.best_pnl))}` : "—", accent: profile.best_pnl == null || profile.best_pnl === 0 ? "text-gray-400" : profile.best_pnl > 0 ? "text-emerald-400" : "text-red-400" },
                  ].map(({ label, value, accent }) => (
                    <div key={label} className="rounded-lg bg-gray-800 border border-gray-700 p-3">
                      <p className="text-xs text-gray-500 mb-1">{label}</p>
                      <p className={`text-lg font-bold font-mono ${accent}`}>{value}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Recent Runs Table */}
            {profile.recent_runs.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                  Recent Backtest Runs
                </p>
                <div className="overflow-x-auto rounded-lg border border-gray-700">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-700 bg-gray-800/50">
                        <th className="th">Date</th>
                        <th className="th">Symbol</th>
                        <th className="th">Source</th>
                        <th className="th">PnL</th>
                        <th className="th">Sharpe</th>
                        <th className="th">Win Rate</th>
                        <th className="th">Drawdown</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profile.recent_runs.map(run => (
                        <tr key={run.id} className="border-b border-gray-800 hover:bg-gray-800/40">
                          <td className="td text-gray-500">{fmtDate(run.created_at)}</td>
                          <td className="td font-mono text-gray-300">{run.symbol}</td>
                          <td className="td">
                            <span className="badge bg-gray-700 text-gray-400">
                              {run.data_source === "live" ? "historical data" : run.data_source}
                            </span>
                          </td>
                          <td className="td"><PnlText value={run.final_pnl} /></td>
                          <td className="td font-mono text-gray-300">{run.sharpe_ratio.toFixed(3)}</td>
                          <td className="td font-mono text-gray-300">{(run.win_rate * 100).toFixed(1)}%</td>
                          <td className="td font-mono text-red-400">{(run.max_drawdown * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Buy button */}
            {dist && !(dist.public_pool_remaining > 0) && <p className="text-xs text-gray-400">No public pool tokens are currently available.</p>}
            <div className="border-t border-gray-800 pt-4 flex gap-3">
              <button
                onClick={() => { onBuy(profile); onClose(); }}
                disabled={!dist || !(dist.public_pool_remaining > 0)}
                className="btn-primary flex-1"
              >
                Buy RST Tokens — $0.01 / token
              </button>
              <button
                onClick={onClose}
                className="btn bg-gray-800 hover:bg-gray-700 text-gray-300"
              >
                Close
              </button>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Buy Modal
// ---------------------------------------------------------------------------

function BuyModal({ bot, onClose, onPurchase }) {
  const [amount, setAmount] = useState(1000);
  const cost = (amount * RST_PRICE).toFixed(2);

  function handleBuy() {
    onPurchase({ bot, amount: Number(amount), cost: Number(cost) });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="card w-full max-w-sm space-y-4">
        <h3 className="text-base font-semibold text-gray-100">Buy RST Tokens</h3>
        <p className="text-sm text-gray-400">
          Bot: <span className="text-gray-100 font-medium">{bot.name}</span>
        </p>
        <div>
          <label className="label">Number of Tokens</label>
          <input
            type="number"
            className="input"
            min="1"
            step="1"
            value={amount}
            onChange={e => setAmount(e.target.value)}
          />
        </div>
        <p className="text-sm text-gray-400">
          Cost: <span className="font-mono text-gray-100">${cost}</span>
          <span className="text-gray-600 ml-1">@ ${RST_PRICE}/RST (simulated)</span>
        </p>
        <div className="flex gap-3">
          <button onClick={handleBuy} className="btn-primary flex-1">Confirm Purchase</button>
          <button onClick={onClose} className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 flex-1">Cancel</button>
        </div>
        <p className="text-xs text-gray-600">Simulated purchase — no real money involved.</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sell Modal
// ---------------------------------------------------------------------------

function SellModal({ holding, onClose, onSell }) {
  const [amount, setAmount] = useState(Math.floor(holding.amount / 2) || 1);
  const max    = holding.amount;
  const gross  = (amount * RST_PRICE).toFixed(4);
  const fee    = (gross * EXIT_FEE).toFixed(4);
  const proceeds = (gross - fee).toFixed(4);

  function handleSell() {
    onSell({ botId: holding.botId, amount: Number(amount) });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="card w-full max-w-sm space-y-4">
        <h3 className="text-base font-semibold text-gray-100">Sell RST Tokens</h3>
        <p className="text-sm text-gray-400">
          Bot: <span className="text-gray-100 font-medium">{holding.botName}</span>
        </p>
        <p className="text-xs text-gray-500">
          You hold <span className="font-mono text-gray-300">{holding.amount.toLocaleString()}</span> RST tokens
        </p>
        <div>
          <label className="label">Tokens to Sell</label>
          <input
            type="number"
            className="input"
            min="1"
            max={max}
            step="1"
            value={amount}
            onChange={e => setAmount(Math.min(Number(e.target.value), max))}
          />
        </div>
        <div className="rounded-lg bg-gray-900 border border-gray-700 p-3 space-y-1 text-sm">
          <div className="flex justify-between text-gray-400">
            <span>Gross value</span><span className="font-mono">${gross}</span>
          </div>
          <div className="flex justify-between text-red-400">
            <span>Exit fee (2%)</span><span className="font-mono">−${fee}</span>
          </div>
          <div className="flex justify-between text-gray-100 font-semibold border-t border-gray-700 pt-1 mt-1">
            <span>Credited to wallet</span>
            <span className="font-mono text-emerald-400">${proceeds}</span>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={handleSell} className="btn-danger flex-1">Confirm Sell</button>
          <button onClick={onClose} className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 flex-1">Cancel</button>
        </div>
        <p className="text-xs text-gray-600">2% exit fee. Tokens return to the public pool.</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section A — Available Bots
// ---------------------------------------------------------------------------

function AvailableBotCard({ bot, onBuy, onProfile, availabilityRevision }) {
  const [availability, setAvailability] = useState("checking");

  useEffect(() => {
    const controller = new AbortController();
    setAvailability("checking");
    apiFetch(`/tokenomics/${bot.id}/balances`, { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data) => {
        const balances = data?.balances;
        if (!balances || typeof balances !== "object" || Array.isArray(balances)) throw new Error("Invalid balance response.");
        if (Object.keys(balances).length === 0) {
          if (!controller.signal.aborted) setAvailability("uninitialized");
          return;
        }
        const pool = balances.public_pool;
        if (typeof pool !== "number" || !Number.isFinite(pool) || pool < 0) throw new Error("Invalid public pool balance.");
        if (!controller.signal.aborted) setAvailability(pool > 0 ? "ready" : "empty");
      })
      .catch(() => { if (!controller.signal.aborted) setAvailability("error"); });
    return () => controller.abort();
  }, [bot.id, availabilityRevision]);

  const message = {
    checking: "Checking token availability…",
    uninitialized: "Tokens are not initialized for this bot.",
    empty: "No public pool tokens are currently available.",
    error: "Token availability could not be loaded. Refresh to retry.",
  }[availability];

  return <div onClick={() => onProfile(bot)} className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-3 flex flex-col cursor-pointer hover:border-indigo-600 hover:bg-gray-800/80 transition-colors">
    <div className="flex items-center gap-2 flex-wrap"><span className="text-sm font-semibold text-gray-100 flex-1 min-w-0 truncate">{bot.name}</span><span className="badge badge-blue text-xs">{STRATEGY_LABELS[bot.strategy_key ?? bot.strategy_name] ?? bot.strategy_key ?? bot.strategy_name}</span></div>
    <div className="flex items-center gap-2"><StatusBadge status={bot.status} /></div>
    <div><p className="text-xs text-gray-500">RST Price</p><p className="text-sm font-mono text-gray-200">${RST_PRICE.toFixed(2)} / token</p></div>
    <button type="button" onClick={(event) => { event.stopPropagation(); onProfile(bot); }} className="text-xs text-gray-400 text-left">View profile →</button>
    {message && <p className="text-xs text-gray-400" role="status">{message}</p>}
    <button type="button" onClick={(event) => { event.stopPropagation(); onBuy(bot); }} disabled={availability !== "ready"} className="btn-primary text-sm mt-auto">Buy Tokens</button>
  </div>;
}

function AvailableBots({ bots, loading, error, onBuy, onProfile, availabilityRevision }) {
  const active = bots.filter(b => b.status === "approved" || b.status === "live");

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Available Bots</h2>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error   && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && active.length === 0 && (
        <p className="text-sm text-gray-500">No live bots available yet.</p>
      )}
      {active.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {active.map(bot => <AvailableBotCard key={bot.id} bot={bot} onBuy={onBuy} onProfile={onProfile} availabilityRevision={availabilityRevision} />)}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section B — My Portfolio
// ---------------------------------------------------------------------------

function MyPortfolio({ holdings, onSell }) {
  if (holdings.length === 0) {
    return (
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">My Portfolio</h2>
        <p className="text-sm text-gray-500">
          Your portfolio is empty. Purchase tokens from available bots above.
        </p>
      </div>
    );
  }

  const totalValue = holdings.reduce((sum, h) => sum + h.amount * RST_PRICE, 0);

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-1">My Portfolio</h2>
      <p className="text-xs text-gray-500 mb-3">
        Total value: <span className="font-mono text-gray-200">${totalValue.toFixed(2)}</span>
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="th">Bot</th>
            <th className="th">Tokens Held</th>
            <th className="th">Value</th>
            <th className="th"></th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
              <td className="td font-medium text-gray-100">{h.botName}</td>
              <td className="td font-mono text-gray-300">{h.amount.toLocaleString()}</td>
              <td className="td font-mono text-gray-300">${(h.amount * RST_PRICE).toFixed(2)}</td>
              <td className="td">
                <button onClick={() => onSell(h)} className="btn-danger text-xs px-3 py-1">
                  Sell
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section C — My Earnings
// ---------------------------------------------------------------------------

function MyEarnings({ earnings, totalEarned, loading }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-300">My Earnings</h2>
        {totalEarned > 0 && (
          <span className="text-xs font-mono text-emerald-400 font-semibold">
            Total: ${fmtMoney(totalEarned)}
          </span>
        )}
      </div>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {!loading && earnings.length === 0 && (
        <p className="text-sm text-gray-500">
          No earnings yet — earnings appear here after an admin distributes bot revenue.
          Hold RST tokens to receive your proportional share.
        </p>
      )}
      {!loading && earnings.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="th">Bot</th>
              <th className="th">Quarter</th>
              <th className="th">RST Held</th>
              <th className="th">Earned ($)</th>
              <th className="th">Date</th>
            </tr>
          </thead>
          <tbody>
            {earnings.map((e, i) => (
              <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td font-medium text-gray-100">{e.bot_name}</td>
                <td className="td text-gray-400">{e.quarter || "—"}</td>
                <td className="td font-mono text-gray-300">{Number(e.rst_balance).toLocaleString()}</td>
                <td className="td font-mono text-emerald-400 font-semibold">+${fmtMoney(e.amount)}</td>
                <td className="td text-gray-500 text-xs">{fmtDate(e.distributed_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section D — Wallet
// ---------------------------------------------------------------------------

function Wallet({ walletBalance, purchaseHistory }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Wallet</h2>
      <div className="mb-4">
        <p className="text-xs text-gray-500 uppercase tracking-wider">Wallet Balance</p>
        <p className="text-3xl font-bold text-gray-100 font-mono">
          {walletBalance == null ? "Unavailable" : `$${Number(walletBalance).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`}
        </p>
        <p className="text-xs text-gray-600 mt-0.5">Simulated balance — Phase 1 MVP</p>
      </div>
      {purchaseHistory.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
            Transaction History (this session)
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th">Bot</th>
                <th className="th">Type</th>
                <th className="th">Tokens</th>
                <th className="th">Amount</th>
                <th className="th">Time</th>
              </tr>
            </thead>
            <tbody>
              {purchaseHistory.map((p, i) => (
                <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="td font-medium text-gray-100">{p.botName}</td>
                  <td className="td">
                    <span className={`badge ${p.type === "sell" ? "badge-red" : "badge-blue"}`}>
                      {p.type === "sell" ? "Sell" : "Buy"}
                    </span>
                  </td>
                  <td className="td font-mono text-gray-300">{p.amount.toLocaleString()}</td>
                  <td className={`td font-mono font-semibold ${p.type === "sell" ? "text-emerald-400" : "text-red-400"}`}>
                    {p.type === "sell"
                      ? `+$${p.proceeds?.toFixed(4) ?? "0.00"}`
                      : `-$${p.cost?.toFixed(2) ?? "0.00"}`}
                  </td>
                  <td className="td text-gray-500">{p.time}</td>
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
// Main component
// ---------------------------------------------------------------------------

export default function MarketDashboard() {
  const [bots, setBots]                   = useState([]);
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState(null);

  const [buyTarget, setBuyTarget]         = useState(null);
  const [sellTarget, setSellTarget]       = useState(null);
  const [profileTarget, setProfileTarget] = useState(null);

  const [holdings, setHoldings]           = useState([]);
  const [earnings, setEarnings]           = useState([]);
  const [totalEarned, setTotalEarned]     = useState(0);
  const [earningsLoading, setEarningsLoading] = useState(true);
  const [purchaseHistory, setPurchaseHistory] = useState([]);
  const [walletBalance, setWalletBalance] = useState(null);
  const [purchaseError, setPurchaseError] = useState(null);
  const [availabilityRevision, setAvailabilityRevision] = useState(0);

  function loadHoldings() {
    apiFetch("/tokenomics/my-holdings")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.holdings) {
          setHoldings(data.holdings.map(h => ({
            botId:   h.bot_id,
            botName: h.bot_name,
            amount:  h.amount,
          })));
        }
      })
      .catch(() => {});
  }

  function loadEarnings() {
    setEarningsLoading(true);
    apiFetch("/tokenomics/my-earnings")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setEarnings(data.earnings ?? []);
          setTotalEarned(data.total_earned ?? 0);
        }
      })
      .catch(() => {})
      .finally(() => setEarningsLoading(false));
  }

  useEffect(() => {
    apiFetch("/auth/me")
      .then(r => r.ok ? r.json() : null)
      .then(data => setWalletBalance(data?.wallet_balance ?? null))
      .catch(() => setWalletBalance(null));

    loadHoldings();
    loadEarnings();
  }, []);

  async function fetchBots() {
    setLoading(true);
    try {
      const res = await apiFetch("/bots/");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBots(await res.json());
      setAvailabilityRevision((value) => value + 1);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchBots(); }, []);

  async function handlePurchase({ bot, amount, cost }) {
    setPurchaseError(null);
    try {
      const res = await apiFetch("/tokenomics/purchase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_id: bot.id, amount: Number(amount) }),
      });
      const data = await res.json();
      if (!res.ok) { setPurchaseError(data.detail ?? "Purchase failed"); return; }
      setWalletBalance(data.wallet_balance);
      loadHoldings();
      setAvailabilityRevision((value) => value + 1);
    } catch (e) {
      setPurchaseError(e.message ?? "Network error");
      return;
    }
    const now = new Date().toLocaleTimeString("en-US", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    setPurchaseHistory(prev => [
      { botName: bot.name, type: "buy", amount, cost, time: now },
      ...prev,
    ]);
  }

  async function handleSell({ botId, amount }) {
    setPurchaseError(null);
    let data;
    try {
      const res = await apiFetch("/tokenomics/sell", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_id: botId, amount: Number(amount) }),
      });
      data = await res.json();
      if (!res.ok) { setPurchaseError(data.detail ?? "Sell failed"); return; }
      setWalletBalance(data.wallet_balance);
      loadHoldings();
      setAvailabilityRevision((value) => value + 1);
    } catch (e) {
      setPurchaseError(e.message ?? "Network error");
      return;
    }
    const holding = holdings.find(h => h.botId === botId);
    const now = new Date().toLocaleTimeString("en-US", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    setPurchaseHistory(prev => [
      { botName: holding?.botName ?? botId, type: "sell", amount, proceeds: data.proceeds, time: now },
      ...prev,
    ]);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="page-heading">
        <div>
          <p className="page-kicker">Investor workspace</p>
          <h1>Market</h1>
          <p className="page-subtitle">Explore strategies and manage your simulated portfolio.</p>
        </div>
        <button
          onClick={fetchBots}
          className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
        >
          Refresh
        </button>
      </div>

      <AvailableBots
        bots={bots}
        loading={loading}
        error={error}
        onBuy={bot  => { setPurchaseError(null); setBuyTarget(bot); }}
        onProfile={bot => setProfileTarget(bot)}
        availabilityRevision={availabilityRevision}
      />

      {purchaseError && (
        <div className="card border border-red-800 flex items-center justify-between gap-3">
          <p className="text-sm text-red-400">{purchaseError}</p>
          <button onClick={() => setPurchaseError(null)} className="text-xs text-gray-500 hover:text-gray-300">✕</button>
        </div>
      )}

      <MyPortfolio
        holdings={holdings}
        onSell={h => { setPurchaseError(null); setSellTarget(h); }}
      />

      <MyEarnings earnings={earnings} totalEarned={totalEarned} loading={earningsLoading} />

      <Wallet walletBalance={walletBalance} purchaseHistory={purchaseHistory} />

      {profileTarget && (
        <BotProfileModal
          botId={profileTarget.id}
          onClose={() => setProfileTarget(null)}
          onBuy={bot => { setProfileTarget(null); setBuyTarget(bot); }}
        />
      )}

      {buyTarget && (
        <BuyModal
          bot={buyTarget}
          onClose={() => setBuyTarget(null)}
          onPurchase={handlePurchase}
        />
      )}

      {sellTarget && (
        <SellModal
          holding={sellTarget}
          onClose={() => setSellTarget(null)}
          onSell={handleSell}
        />
      )}
    </div>
  );
}
