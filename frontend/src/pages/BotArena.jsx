import { Component, useEffect, useRef, useState } from "react";
import {
  AreaChart, Area,
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

// One colour per bot in the arena comparison chart
const BOT_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#3b82f6", "#a855f7", "#14b8a6"];

const CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"];
const INDIAN_SYMBOLS = [
  { value: "RELIANCE.NS",   label: "RELIANCE.NS — Reliance Industries" },
  { value: "TCS.NS",        label: "TCS.NS — Tata Consultancy Services" },
  { value: "INFY.NS",       label: "INFY.NS — Infosys" },
  { value: "HDFCBANK.NS",   label: "HDFCBANK.NS — HDFC Bank" },
  { value: "WIPRO.NS",      label: "WIPRO.NS — Wipro" },
  { value: "^NSEI",         label: "^NSEI — NIFTY 50 Index" },
  { value: "TATAMOTORS.NS", label: "TATAMOTORS.NS — Tata Motors" },
  { value: "BAJFINANCE.NS", label: "BAJFINANCE.NS — Bajaj Finance" },
  { value: "ICICIBANK.NS",  label: "ICICIBANK.NS — ICICI Bank" },
  { value: "ADANIENT.NS",   label: "ADANIENT.NS — Adani Enterprises" },
  { value: "SBIN.NS",       label: "SBIN.NS — State Bank of India" },
  { value: "HINDUNILVR.NS", label: "HINDUNILVR.NS — Hindustan Unilever" },
];

function isIndian(symbol) {
  return symbol.endsWith(".NS") || symbol.startsWith("^");
}

function SymbolSelect({ value, onChange }) {
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      <optgroup label="Crypto (via Binance)">
        {CRYPTO_SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
      </optgroup>
      <optgroup label="Indian Stocks (via NSE)">
        {INDIAN_SYMBOLS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </optgroup>
    </select>
  );
}

// ---------------------------------------------------------------------------
// CSV export helpers
// ---------------------------------------------------------------------------

function exportArenaCSV(summary) {
  const header = ["Rank", "Bot", "Strategy", "Final PnL", "End Cash", "Trades", "Win Rate", "Sharpe", "Max DD"];
  const lines = [
    header.join(","),
    ...summary.map((r, idx) => [
      idx + 1,
      `"${r.name}"`,
      `"${r.strategy}"`,
      r.finalPnl.toFixed(2),
      r.endCash.toFixed(2),
      r.trades,
      r.winRate !== null ? r.winRate + "%" : "—",
      r.sharpe.toFixed(2),
      (r.maxDrawdown * 100).toFixed(2) + "%",
    ].join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `axiom_arena_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportBacktestCSV(records) {
  const header = ["Date", "Action", "Price", "Qty", "PnL", "Cash After", "Reason"];
  const lines = [
    header.join(","),
    ...records.map((r) => [
      `"${new Date(r.timestamp).toLocaleString()}"`,
      r.action_type,
      Number(r.price ?? 0).toFixed(2),
      Number(r.quantity ?? 0).toFixed(4),
      Number(r.pnl ?? 0).toFixed(2),
      Number(r.cash_after ?? 0).toFixed(2),
      `"${(r.reason ?? "").replace(/"/g, "'")}"`,
    ].join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `axiom_backtest_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function PnlBadge({ value }) {
  if (value > 0) return <span className="badge badge-green">+{value.toFixed(2)}</span>;
  if (value < 0) return <span className="badge badge-red">{value.toFixed(2)}</span>;
  return <span className="badge badge-yellow">0.00</span>;
}

function Spinner() {
  return (
    <div className="flex items-center gap-3 py-8 justify-center">
      <div style={{
        width: 32, height: 32, border: '4px solid #334155',
        borderTopColor: '#6366f1', borderRadius: '50%',
        animation: 'spin 0.8s linear infinite'
      }} />
      <span className="text-slate-400 text-sm">Running simulation...</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function winRate(records) {
  const trades = records.filter((r) => r.action_type === "BUY" || r.action_type === "SELL");
  if (trades.length === 0) return null;
  // A trade "wins" if portfolio PnL improved vs the previous record
  let wins = 0;
  for (let i = 1; i < records.length; i++) {
    if (
      (records[i].action_type === "BUY" || records[i].action_type === "SELL") &&
      Number(records[i].pnl ?? 0) > Number(records[i - 1].pnl ?? 0)
    ) wins++;
  }
  return ((wins / trades.length) * 100).toFixed(1);
}

// ---------------------------------------------------------------------------
// Single-bot equity area chart
// ---------------------------------------------------------------------------

function EquityCurve({ records, startCash }) {
  if (!records || records.length === 0) return null;
  const cash = Number(startCash) || 10000;

  const data = records.map((r, i) => ({
    tick: i + 1,
    equity: parseFloat((cash + Number(r.pnl ?? 0)).toFixed(2)),
    pnl: parseFloat(Number(r.pnl ?? 0).toFixed(2)),
    action: r.action_type,
    time: new Date(r.timestamp).toLocaleTimeString(),
  }));

  const min = Math.min(...data.map((d) => d.equity));
  const max = Math.max(...data.map((d) => d.equity));
  const finalPnl = data[data.length - 1]?.pnl ?? 0;
  const isProfit = finalPnl >= 0;
  const color = isProfit ? "#10b981" : "#ef4444";

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-xs space-y-1">
        <p className="text-gray-400">Tick {d.tick} · {d.time}</p>
        <p className="text-gray-100">Equity: <span className="font-mono font-semibold">${d.equity.toFixed(2)}</span></p>
        <p className={d.pnl >= 0 ? "text-emerald-400" : "text-red-400"}>PnL: {d.pnl >= 0 ? "+" : ""}{d.pnl.toFixed(2)}</p>
        <p className="text-gray-500">
          Action:{" "}
          <span className={d.action === "BUY" ? "text-emerald-400" : d.action === "SELL" ? "text-red-400" : "text-yellow-400"}>
            {d.action}
          </span>
        </p>
      </div>
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-300">Equity Curve</h4>
        <span className={`text-sm font-mono font-semibold ${isProfit ? "text-emerald-400" : "text-red-400"}`}>
          {isProfit ? "+" : ""}{finalPnl.toFixed(2)} PnL
        </span>
      </div>
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="eg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="tick" tick={{ fontSize: 10, fill: "#6b7280" }} tickLine={false} axisLine={{ stroke: "#374151" }} />
            <YAxis domain={[min * 0.999, max * 1.001]} tick={{ fontSize: 10, fill: "#6b7280" }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v.toFixed(0)}`} width={62} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={cash} stroke="#4b5563" strokeDasharray="4 2" />
            <Area type="monotone" dataKey="equity" stroke={color} strokeWidth={2} fill="url(#eg)" dot={false} activeDot={{ r: 4, fill: color, stroke: "#111827" }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Multi-bot comparison: overlaid equity curves + summary table
// ---------------------------------------------------------------------------

function ArenaComparison({ results, bots, startCash }) {
  const entries = Object.entries(results);
  if (entries.length === 0) return null;
  const cash = Number(startCash) || 10000;

  // Build merged tick-by-tick dataset: [{tick:1, botId1: equity, botId2: equity, ...}]
  const maxLen = Math.max(...entries.map(([, r]) => r.trade_records.length));
  const merged = Array.from({ length: maxLen }, (_, i) => {
    const row = { tick: i + 1 };
    entries.forEach(([botId, res]) => {
      const rec = res.trade_records[i];
      row[botId] = rec ? parseFloat((cash + Number(rec.pnl ?? 0)).toFixed(2)) : null;
    });
    return row;
  });

  const ComparisonTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-xs space-y-1">
        <p className="text-gray-400 mb-1">Tick {label}</p>
        {payload.map((p) => (
          <p key={p.dataKey} style={{ color: p.color }}>
            {p.name}: <span className="font-mono">${Number(p.value).toFixed(2)}</span>
          </p>
        ))}
      </div>
    );
  };

  // Summary table data — sorted by final PnL descending
  const summary = entries.map(([botId, res], idx) => {
    const bot = bots.find((b) => b.id === botId);
    const wr = winRate(res.trade_records);
    return {
      botId,
      name: bot?.name ?? botId.slice(0, 8),
      strategy: bot?.strategy_name ?? "—",
      finalPnl: Number(res.final_pnl ?? 0),
      trades: res.total_trades,
      startCash: res.start_cash,
      endCash: Number(res.end_cash ?? 0),
      winRate: wr,
      sharpe: Number(res.sharpe_ratio ?? 0),
      maxDrawdown: Number(res.max_drawdown ?? 0),
      color: BOT_COLORS[idx % BOT_COLORS.length],
    };
  }).sort((a, b) => b.finalPnl - a.finalPnl);

  return (
    <div className="space-y-6 pt-2 border-t border-gray-800">
      {/* Comparison chart */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-300">Equity Curve Comparison</h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={merged} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="tick" tick={{ fontSize: 10, fill: "#6b7280" }} tickLine={false} axisLine={{ stroke: "#374151" }} />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v.toFixed(0)}`} width={62} />
              <Tooltip content={<ComparisonTooltip />} />
              <Legend
                formatter={(value) => {
                  const bot = bots.find((b) => b.id === value);
                  return <span className="text-xs text-gray-300">{bot?.name ?? value.slice(0, 8)}</span>;
                }}
                wrapperStyle={{ paddingTop: 8 }}
              />
              <ReferenceLine y={cash} stroke="#4b5563" strokeDasharray="4 2" label={{ value: "Start", fill: "#6b7280", fontSize: 10 }} />
              {entries.map(([botId], idx) => (
                <Line
                  key={botId}
                  type="monotone"
                  dataKey={botId}
                  name={bots.find((b) => b.id === botId)?.name ?? botId.slice(0, 8)}
                  stroke={BOT_COLORS[idx % BOT_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary comparison table */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-300">Results Summary</h3>
          <button
            type="button"
            onClick={() => exportArenaCSV(summary)}
            className="px-3 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 border border-gray-600 transition-colors"
          >
            Export CSV
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th">Rank</th>
                <th className="th">Bot</th>
                <th className="th">Strategy</th>
                <th className="th">Final PnL</th>
                <th className="th">End Cash</th>
                <th className="th">Trades</th>
                <th className="th">Win Rate</th>
                <th className="th">Sharpe</th>
                <th className="th">Max DD</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((s, rank) => (
                <tr key={s.botId} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="td">
                    <span className="font-bold" style={{ color: s.color }}>#{rank + 1}</span>
                  </td>
                  <td className="td font-medium text-gray-100">
                    <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ backgroundColor: s.color }} />
                    {s.name}
                  </td>
                  <td className="td"><span className="badge badge-blue">{s.strategy}</span></td>
                  <td className="td"><PnlBadge value={s.finalPnl} /></td>
                  <td className="td font-mono">${Number(s.endCash ?? 0).toFixed(2)}</td>
                  <td className="td">{s.trades}</td>
                  <td className="td">
                    {s.winRate !== null
                      ? <span className={parseFloat(s.winRate) >= 50 ? "text-emerald-400" : "text-red-400"}>{s.winRate}%</span>
                      : <span className="text-gray-600">—</span>}
                  </td>
                  <td className="td font-mono">
                    <span className={s.sharpe >= 1 ? "text-emerald-400" : s.sharpe < 0 ? "text-red-400" : "text-gray-300"}>
                      {s.sharpe.toFixed(2)}
                    </span>
                  </td>
                  <td className="td font-mono">
                    <span className={s.maxDrawdown < -0.1 ? "text-red-400" : "text-gray-300"}>
                      {(s.maxDrawdown * 100).toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trade log table
// ---------------------------------------------------------------------------

function TradeTable({ records, showExportCSV = false }) {
  const [expanded, setExpanded] = useState(false);
  if (!records || records.length === 0) return <p className="text-sm text-gray-500">No trades recorded.</p>;

  const shown = expanded ? records : records.slice(0, 10);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium text-gray-400">Trade Log</h4>
        <div className="flex items-center gap-2">
          {showExportCSV && (
            <button
              type="button"
              onClick={() => exportBacktestCSV(records)}
              className="px-2 py-0.5 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 border border-gray-600 transition-colors"
            >
              Export CSV
            </button>
          )}
          {records.length > 10 && (
            <button onClick={() => setExpanded((e) => !e)} className="text-xs text-indigo-400 hover:text-indigo-300">
              {expanded ? "Show less" : `Show all ${records.length}`}
            </button>
          )}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="th">Action</th>
              <th className="th">Symbol</th>
              <th className="th">Qty</th>
              <th className="th">Price</th>
              <th className="th">Cash After</th>
              <th className="th">PnL</th>
              <th className="th">Reason</th>
              <th className="th">Time</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td">
                  {r.action_type === "BUY" && <span className="badge badge-green">BUY</span>}
                  {r.action_type === "SELL" && <span className="badge badge-red">SELL</span>}
                  {r.action_type === "HOLD" && <span className="badge badge-yellow">HOLD</span>}
                </td>
                <td className="td font-mono">{r.symbol}</td>
                <td className="td">{Number(r.quantity ?? 0).toFixed(4)}</td>
                <td className="td">{Number(r.price ?? 0).toFixed(2)}</td>
                <td className="td">{Number(r.cash_after ?? 0).toFixed(2)}</td>
                <td className="td"><PnlBadge value={Number(r.pnl ?? 0)} /></td>
                <td className="td text-gray-500 text-xs max-w-xs truncate">{r.reason}</td>
                <td className="td text-gray-500 text-xs">{new Date(r.timestamp).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error boundary — prevents a render crash from showing a blank page
// ---------------------------------------------------------------------------

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="p-6">
          <div className="card border border-red-800 space-y-2">
            <p className="text-sm font-semibold text-red-400">Something went wrong in Bot Arena</p>
            <p className="text-xs text-gray-500 font-mono">{this.state.error.message}</p>
            <button
              className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs"
              onClick={() => this.setState({ error: null })}
            >
              Dismiss
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function BotArenaPage() {
  const [bots, setBots] = useState([]);
  const [botsLoading, setBotsLoading] = useState(true);

  const [btBotId, setBtBotId] = useState("");
  const [btSymbol, setBtSymbol] = useState("BTC/USDT");
  const [btCandles, setBtCandles] = useState(100);
  const [btStartPrice, setBtStartPrice] = useState(50000);
  const [btCash, setBtCash] = useState(10000);
  const [btDataSource, setBtDataSource] = useState("mock");
  const [btTimeframe, setBtTimeframe] = useState("1d");
  const [btResult, setBtResult] = useState(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btError, setBtError] = useState(null);

  const [arenaSelectedIds, setArenaSelectedIds] = useState([]);
  const [arenaSymbol, setArenaSymbol] = useState("BTC/USDT");
  const [arenaCandles, setArenaCandles] = useState(100);
  const [arenaStartPrice, setArenaStartPrice] = useState(50000);
  const [arenaCash, setArenaCash] = useState(10000);
  const [arenaDataSource, setArenaDataSource] = useState("mock");
  const [arenaTimeframe, setArenaTimeframe] = useState("1d");
  const [arenaResult, setArenaResult] = useState(null);
  const [arenaLoading, setArenaLoading] = useState(false);
  const [arenaError, setArenaError] = useState(null);

  // Per-bot symbol overrides: maps bot_id -> symbol string (empty = use global)
  const [botSymbols, setBotSymbols] = useState({});
  const arenaResultsRef = useRef(null);

  const safeNum = (val, fallback) => { const n = parseFloat(val); return isNaN(n) ? fallback : n; };

  useEffect(() => {
    fetch("/bots/")
      .then((r) => r.json())
      .then((data) => { setBots(data); if (data.length > 0) setBtBotId(data[0].id); })
      .catch(console.error)
      .finally(() => setBotsLoading(false));
  }, []);

  async function handleBacktest(e) {
    e.preventDefault();
    setBtLoading(true); setBtError(null); setBtResult(null);
    try {
      const res = await fetch(`/arena/backtest/${btBotId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: btSymbol,
          num_candles: safeNum(btCandles, 100),
          start_price: safeNum(btStartPrice, 50000),
          starting_cash: safeNum(btCash, 10000),
          data_source: btDataSource,
          timeframe: btTimeframe,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setBtError(JSON.stringify(data.detail || data)); return; }
      setBtResult(data);
    } catch (e) {
      setBtError(e.message || "Network error");
    } finally {
      setBtLoading(false);
    }
  }

  function toggleArenaBot(id) {
    setArenaSelectedIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
    // Clean up any override when bot is deselected
    setBotSymbols((prev) => {
      if (arenaSelectedIds.includes(id)) {
        const next = { ...prev };
        delete next[id];
        return next;
      }
      return prev;
    });
  }

  function setBotSymbolOverride(botId, symbol) {
    setBotSymbols((prev) => {
      if (!symbol) {
        const next = { ...prev };
        delete next[botId];
        return next;
      }
      return { ...prev, [botId]: symbol };
    });
  }

  async function handleArena(e) {
    e.preventDefault();
    if (arenaSelectedIds.length === 0) return;
    setArenaLoading(true); setArenaError(null); setArenaResult(null);
    // Only include overrides that are non-empty
    const activeOverrides = {};
    Object.entries(botSymbols).forEach(([id, sym]) => {
      if (sym && arenaSelectedIds.includes(id)) activeOverrides[id] = sym;
    });
    try {
      const res = await fetch("/arena/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bot_ids: arenaSelectedIds,
          symbol: arenaSymbol,
          num_candles: safeNum(arenaCandles, 100),
          start_price: safeNum(arenaStartPrice, 50000),
          starting_cash: safeNum(arenaCash, 10000),
          data_source: arenaDataSource,
          timeframe: arenaTimeframe,
          ...(Object.keys(activeOverrides).length > 0 ? { bot_symbols: activeOverrides } : {}),
        }),
      });
      const data = await res.json();
      if (!res.ok) { setArenaError(JSON.stringify(data.detail || data)); return; }
      setArenaResult(data);
      setTimeout(() => arenaResultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } catch (e) {
      setArenaError(e.message || "Network error");
    } finally {
      setArenaLoading(false);
    }
  }

  const noBots = !botsLoading && bots.length === 0;
  const selectedBots = bots.filter((b) => arenaSelectedIds.includes(b.id));

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-bold text-gray-100">Bot Arena</h1>

      {/* ── Single Bot Backtest ── */}
      <div className="card space-y-4">
        <h2 className="text-base font-semibold text-gray-200">Single Bot Backtest</h2>
        {botsLoading && <p className="text-sm text-gray-500">Loading bots…</p>}
        {noBots && <p className="text-sm text-gray-500">No bots found. Create one on the Dashboard first.</p>}
        {!botsLoading && !noBots && (
          <form onSubmit={handleBacktest} className="space-y-3">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <div>
                <label className="label">Bot</label>
                <select className="input" value={btBotId} onChange={(e) => setBtBotId(e.target.value)}>
                  {bots.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.strategy_name})</option>)}
                </select>
              </div>
              <div>
                <label className="label">Symbol</label>
                <SymbolSelect value={btSymbol} onChange={(sym) => {
                  setBtSymbol(sym);
                  if (isIndian(sym)) setBtDataSource("live");
                }} />
              </div>
              <div><label className="label">Candles</label><input className="input" type="number" min="10" max="1000" value={btCandles} onChange={(e) => setBtCandles(e.target.value)} /></div>
              <div><label className="label">Start Price ($)</label><input className="input" type="number" min="1" value={btStartPrice} onChange={(e) => setBtStartPrice(e.target.value)} disabled={btDataSource === "live"} /></div>
              <div><label className="label">Starting Cash ($)</label><input className="input" type="number" min="100" value={btCash} onChange={(e) => setBtCash(e.target.value)} /></div>
              <div>
                <label className="label">Data Source</label>
                <select className="input" value={btDataSource} onChange={(e) => setBtDataSource(e.target.value)} disabled={isIndian(btSymbol)}>
                  <option value="mock">Mock (simulated)</option>
                  <option value="live">Live</option>
                </select>
              </div>
              {btDataSource === "live" && (
                <div>
                  <label className="label">Timeframe</label>
                  <select className="input" value={btTimeframe} onChange={(e) => setBtTimeframe(e.target.value)}>
                    <option value="1h">1 Hour</option>
                    <option value="4h">4 Hours</option>
                    <option value="1d">1 Day</option>
                  </select>
                </div>
              )}
            </div>
            {btDataSource === "live" && (
              <p className="text-xs text-indigo-400">
                {isIndian(btSymbol)
                  ? `Using real ${btSymbol} data from NSE via yfinance`
                  : `Using real ${btSymbol} data from Binance`}
              </p>
            )}
            <div className="flex items-center gap-3">
              <button type="submit" className="btn-primary" disabled={btLoading}>{btLoading ? "Running…" : "Run Backtest"}</button>
            </div>
          </form>
        )}
        {btError && <p className="text-sm text-red-400">{btError}</p>}
        {btLoading && <Spinner />}
        {btResult && (
          <div className="space-y-4 pt-2 border-t border-gray-800">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                { label: "Total Trades", value: btResult.total_trades },
                { label: "Start Cash", value: `$${Number(btResult.start_cash ?? 0).toFixed(2)}` },
                { label: "End Cash", value: `$${Number(btResult.end_cash ?? 0).toFixed(2)}` },
                { label: "Final PnL", value: <PnlBadge value={Number(btResult.final_pnl ?? 0)} /> },
                { label: "Sharpe", value: Number(btResult.sharpe_ratio ?? 0).toFixed(2) },
                { label: "Max DD", value: `${(Number(btResult.max_drawdown ?? 0) * 100).toFixed(1)}%` },
              ].map(({ label, value }) => (
                <div key={label} className="bg-gray-800 rounded p-3">
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className="text-lg font-semibold text-gray-100">{value}</p>
                </div>
              ))}
            </div>
            <EquityCurve records={btResult.trade_records} startCash={Number(btResult.start_cash) || 10000} />
            <TradeTable records={btResult.trade_records} showExportCSV={true} />
          </div>
        )}
      </div>

      {/* ── Arena (multiple bots) ── */}
      <div className="card space-y-4">
        <h2 className="text-base font-semibold text-gray-200">Arena — Run Multiple Bots</h2>
        {botsLoading && <p className="text-sm text-gray-500">Loading bots…</p>}
        {noBots && <p className="text-sm text-gray-500">No bots found. Create one on the Dashboard first.</p>}
        {!botsLoading && !noBots && (
          <form onSubmit={handleArena} className="space-y-4">
            <div>
              <label className="label">Select Bots</label>
              <div className="flex flex-wrap gap-2 mt-1">
                {bots.map((b) => {
                  const selected = arenaSelectedIds.includes(b.id);
                  return (
                    <button key={b.id} type="button" onClick={() => toggleArenaBot(b.id)}
                      className={`px-3 py-1 rounded text-sm border transition-colors ${selected ? "bg-indigo-700 border-indigo-500 text-white" : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500"}`}>
                      {b.name}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Per-bot symbol overrides */}
            {selectedBots.length > 0 && (
              <div className="rounded-lg border border-gray-700 bg-gray-800/40 p-3 space-y-3">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Per-bot symbol overrides (optional)</p>
                <p className="text-xs text-gray-500">Leave blank to use the global symbol below. Set a different symbol to run that bot on a separate market.</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {selectedBots.map((bot) => (
                    <div key={bot.id} className="flex items-center gap-2">
                      <label className="text-xs text-gray-300 whitespace-nowrap min-w-0 flex-shrink-0 w-32 truncate" title={`Override symbol for ${bot.name}`}>
                        {bot.name}:
                      </label>
                      <select
                        className="input text-xs py-1 flex-1"
                        value={botSymbols[bot.id] ?? ""}
                        onChange={(e) => setBotSymbolOverride(bot.id, e.target.value)}
                      >
                        <option value="">— use global —</option>
                        <optgroup label="Crypto (via Binance)">
                          {CRYPTO_SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
                        </optgroup>
                        <optgroup label="Indian Stocks (via NSE)">
                          {INDIAN_SYMBOLS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                        </optgroup>
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div>
                <label className="label">Symbol</label>
                <SymbolSelect value={arenaSymbol} onChange={(sym) => {
                  setArenaSymbol(sym);
                  if (isIndian(sym)) setArenaDataSource("live");
                }} />
              </div>
              <div><label className="label">Candles</label><input className="input" type="number" min="10" max="1000" value={arenaCandles} onChange={(e) => setArenaCandles(e.target.value)} /></div>
              <div><label className="label">Start Price ($)</label><input className="input" type="number" min="1" value={arenaStartPrice} onChange={(e) => setArenaStartPrice(e.target.value)} disabled={arenaDataSource === "live"} /></div>
              <div><label className="label">Starting Cash ($)</label><input className="input" type="number" min="100" value={arenaCash} onChange={(e) => setArenaCash(e.target.value)} /></div>
              <div>
                <label className="label">Data Source</label>
                <select className="input" value={arenaDataSource} onChange={(e) => setArenaDataSource(e.target.value)} disabled={isIndian(arenaSymbol)}>
                  <option value="mock">Mock (simulated)</option>
                  <option value="live">Live</option>
                </select>
              </div>
              {arenaDataSource === "live" && (
                <div>
                  <label className="label">Timeframe</label>
                  <select className="input" value={arenaTimeframe} onChange={(e) => setArenaTimeframe(e.target.value)}>
                    <option value="1h">1 Hour</option>
                    <option value="4h">4 Hours</option>
                    <option value="1d">1 Day</option>
                  </select>
                </div>
              )}
            </div>
            {arenaDataSource === "live" && (
              <p className="text-xs text-indigo-400">
                {isIndian(arenaSymbol)
                  ? `Using real ${arenaSymbol} data from NSE via yfinance`
                  : `Using real ${arenaSymbol} data from Binance`}
              </p>
            )}
            <button type="submit" className="btn-primary" disabled={arenaLoading || arenaSelectedIds.length === 0}>
              {arenaLoading ? "Running Arena…" : `Run Arena (${arenaSelectedIds.length} bot${arenaSelectedIds.length !== 1 ? "s" : ""})`}
            </button>
          </form>
        )}
        {arenaError && <p className="text-sm text-red-400">{arenaError}</p>}
        {arenaLoading && <Spinner />}
        {arenaResult && (
          <>
            <div ref={arenaResultsRef} />
            <ArenaComparison results={arenaResult.results} bots={bots} startCash={Number(arenaCash) || 10000} />
            {/* Individual trade logs, collapsible per bot */}
            <div className="space-y-4 pt-2 border-t border-gray-800">
              <h3 className="text-sm font-semibold text-gray-300">Individual Trade Logs</h3>
              {Object.entries(arenaResult.results).map(([botId, res], idx) => {
                const bot = bots.find((b) => b.id === botId);
                return (
                  <details key={botId} className="bg-gray-800/50 rounded-lg">
                    <summary className="px-4 py-2 cursor-pointer text-sm font-medium text-gray-300 flex items-center gap-2 select-none">
                      <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: BOT_COLORS[idx % BOT_COLORS.length] }} />
                      {bot?.name ?? botId.slice(0, 8)}
                      <span className="ml-auto"><PnlBadge value={res.final_pnl ?? 0} /></span>
                    </summary>
                    <div className="px-4 pb-4 pt-2">
                      <TradeTable records={res.trade_records} />
                    </div>
                  </details>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function BotArena() {
  return (
    <ErrorBoundary>
      <BotArenaPage />
    </ErrorBoundary>
  );
}
