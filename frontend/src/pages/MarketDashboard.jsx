import { useEffect, useState } from "react";
import { authHeaders, getUser } from "../auth.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RST_PRICE = 0.01; // $0.01 per token (simulated)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STRATEGY_LABELS = {
  simple_ma: "MA",
  rsi: "RSI",
  bollinger_bands: "BB",
  macd: "MACD",
  momentum: "MOM",
};

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
          <button onClick={handleBuy} className="btn-primary flex-1">
            Confirm Purchase
          </button>
          <button onClick={onClose} className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 flex-1">
            Cancel
          </button>
        </div>
        <p className="text-xs text-gray-600">
          Simulated purchase — no real money involved. Phase 1 MVP.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section A — Available Bots (card grid)
// ---------------------------------------------------------------------------

function AvailableBots({ bots, loading, error, onBuy }) {
  const active = bots.filter(b => b.status === "approved" || b.status === "live");

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Available Bots</h2>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && active.length === 0 && (
        <p className="text-sm text-gray-500">No live bots available yet</p>
      )}
      {active.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {active.map(bot => (
            <div
              key={bot.id}
              className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-3 flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-gray-100 flex-1 min-w-0 truncate">
                  {bot.name}
                </span>
                <span className="badge badge-blue text-xs">
                  {STRATEGY_LABELS[bot.strategy_key ?? bot.strategy_name] ?? bot.strategy_key ?? bot.strategy_name}
                </span>
              </div>

              {/* Status */}
              <div className="flex items-center gap-2">
                <StatusBadge status={bot.status} />
              </div>

              {/* Price */}
              <div>
                <p className="text-xs text-gray-500">RST Price</p>
                <p className="text-sm font-mono text-gray-200">${RST_PRICE.toFixed(2)} / token</p>
              </div>

              {/* Buy button */}
              <button
                onClick={() => onBuy(bot)}
                className="btn-primary text-sm mt-auto"
              >
                Buy Tokens
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section B — My Portfolio
// ---------------------------------------------------------------------------

function MyPortfolio({ holdings }) {
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
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
              <td className="td font-medium text-gray-100">{h.botName}</td>
              <td className="td font-mono text-gray-300">{h.amount.toLocaleString()}</td>
              <td className="td font-mono text-gray-300">${(h.amount * RST_PRICE).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section C — Wallet
// ---------------------------------------------------------------------------

function Wallet({ walletBalance, purchaseHistory }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Wallet</h2>
      <div className="mb-4">
        <p className="text-xs text-gray-500 uppercase tracking-wider">Wallet Balance</p>
        <p className="text-3xl font-bold text-gray-100 font-mono">
          ${Number(walletBalance ?? 10000).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </p>
        <p className="text-xs text-gray-600 mt-0.5">Simulated balance — Phase 1 MVP</p>
      </div>

      {purchaseHistory.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
            Simulated Purchase History
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th">Bot</th>
                <th className="th">Tokens</th>
                <th className="th">Cost</th>
                <th className="th">Time</th>
              </tr>
            </thead>
            <tbody>
              {purchaseHistory.map((p, i) => (
                <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="td font-medium text-gray-100">{p.botName}</td>
                  <td className="td font-mono text-gray-300">{p.amount.toLocaleString()}</td>
                  <td className="td font-mono text-gray-300">${p.cost.toFixed(2)}</td>
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
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Local state for simulated purchases
  const [buyTarget, setBuyTarget] = useState(null);
  const [holdings, setHoldings] = useState([]); // [{ botId, botName, amount }]
  const [purchaseHistory, setPurchaseHistory] = useState([]);
  const [walletBalance, setWalletBalance] = useState(null);

  // Load wallet balance from /auth/me
  useEffect(() => {
    fetch("/auth/me", { headers: authHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.wallet_balance !== undefined) {
          setWalletBalance(data.wallet_balance);
        } else {
          setWalletBalance(10000);
        }
      })
      .catch(() => setWalletBalance(10000));
  }, []);

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

  function handlePurchase({ bot, amount, cost }) {
    // Deduct from wallet (local state)
    setWalletBalance(prev => Math.max(0, (prev ?? 10000) - cost));

    // Add to holdings
    setHoldings(prev => {
      const existing = prev.find(h => h.botId === bot.id);
      if (existing) {
        return prev.map(h =>
          h.botId === bot.id ? { ...h, amount: h.amount + amount } : h
        );
      }
      return [...prev, { botId: bot.id, botName: bot.name, amount }];
    });

    // Record history
    const now = new Date().toLocaleTimeString("en-US", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    setPurchaseHistory(prev => [
      { botName: bot.name, amount, cost, time: now },
      ...prev,
    ]);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Market</h1>
        <button
          onClick={fetchBots}
          className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
        >
          Refresh
        </button>
      </div>

      {/* A — Available Bots */}
      <AvailableBots
        bots={bots}
        loading={loading}
        error={error}
        onBuy={bot => setBuyTarget(bot)}
      />

      {/* B — My Portfolio */}
      <MyPortfolio holdings={holdings} />

      {/* C — Wallet */}
      <Wallet walletBalance={walletBalance} purchaseHistory={purchaseHistory} />

      {/* Buy Modal */}
      {buyTarget && (
        <BuyModal
          bot={buyTarget}
          onClose={() => setBuyTarget(null)}
          onPurchase={handlePurchase}
        />
      )}
    </div>
  );
}
