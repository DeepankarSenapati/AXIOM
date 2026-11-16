import { useEffect, useState } from "react";
import { apiFetch } from "../auth.js";

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

function RoleBadge({ role }) {
  const map = {
    admin: "badge-red",
    tech_company: "badge-blue",
    governance_company: "badge-yellow",
    token_holder: "badge-green",
  };
  return (
    <span className={`badge ${map[role] ?? "bg-gray-700 text-gray-400"}`}>
      {role ?? "unknown"}
    </span>
  );
}

function StatCard({ label, value, sub }) {
  return (
    <div className="card stat-card flex flex-col gap-1">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-3xl font-bold text-gray-100">{value ?? "—"}</p>
      {sub && <p className="text-xs text-gray-600">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section A — Platform Overview
// ---------------------------------------------------------------------------

function PlatformOverview({ bots, users, stats, platformRevenue, loading }) {
  const pendingCount = bots.filter(b => b.status === "pending_approval").length;
  const feeDisplay = platformRevenue
    ? `$${Number(platformRevenue.total_fees_collected).toFixed(2)}`
    : "—";
  const feeSub = platformRevenue
    ? `from ${platformRevenue.event_count} distribution${platformRevenue.event_count !== 1 ? "s" : ""}`
    : null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <StatCard label="Total Bots" value={loading ? "—" : bots.length} />
      <StatCard label="Pending Approvals" value={loading ? "—" : pendingCount} />
      <StatCard label="Total Users" value={loading ? "—" : users.length} />
      <StatCard
        label="Backtest Runs"
        value={loading ? "—" : (stats?.total_backtest_runs ?? "—")}
      />
      <StatCard
        label="Platform Revenue"
        value={loading ? "—" : feeDisplay}
        sub={loading ? null : feeSub}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section B — Pending Bot Approvals
// ---------------------------------------------------------------------------

function PendingApprovals({ bots, onRefresh }) {
  const [actioning, setActioning] = useState(null);
  const [actionError, setActionError] = useState(null);
  const pending = bots.filter(b => b.status === "pending_approval");

  async function handleAction(botId, action) {
    setActioning(botId);
    setActionError(null);
    try {
      const res = await apiFetch(`/admin/bots/${botId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `HTTP ${res.status}`);
      }
      onRefresh();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setActioning(null);
    }
  }

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">
        Pending Bot Approvals
        {pending.length > 0 && (
          <span className="ml-2 badge badge-yellow">{pending.length}</span>
        )}
      </h2>
      {actionError && (
        <p className="text-xs text-red-400 mb-2">{actionError}</p>
      )}
      {pending.length === 0 ? (
        <p className="text-sm text-gray-500">No bots awaiting approval</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="th">Bot Name</th>
              <th className="th">Strategy</th>
              <th className="th">Description</th>
              <th className="th">Submitted</th>
              <th className="th">Actions</th>
            </tr>
          </thead>
          <tbody>
            {pending.map(bot => (
              <tr key={bot.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td font-medium text-gray-100">{bot.name}</td>
                <td className="td">
                  <span className="badge badge-blue">{bot.strategy_key ?? bot.strategy_name}</span>
                </td>
                <td className="td text-gray-400 max-w-xs truncate">
                  {bot.description || <span className="text-gray-600">—</span>}
                </td>
                <td className="td text-gray-500">{fmt(bot.created_at)}</td>
                <td className="td">
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleAction(bot.id, "approve")}
                      disabled={actioning === bot.id}
                      className="btn text-xs px-3 py-1 bg-green-700 hover:bg-green-600 text-white rounded"
                    >
                      {actioning === bot.id ? "…" : "Approve"}
                    </button>
                    <button
                      onClick={() => handleAction(bot.id, "reject")}
                      disabled={actioning === bot.id}
                      className="btn-danger text-xs px-3 py-1"
                    >
                      {actioning === bot.id ? "…" : "Reject"}
                    </button>
                  </div>
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
// Section C — All Bots
// ---------------------------------------------------------------------------

function AllBots({ bots, loading, error }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">All Bots</h2>
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
              <th className="th">Description</th>
              <th className="th">Submitted</th>
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
                <td className="td text-gray-400 max-w-xs truncate">
                  {bot.description || <span className="text-gray-600">—</span>}
                </td>
                <td className="td text-gray-500">{fmt(bot.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section D — User Management
// ---------------------------------------------------------------------------

function UserManagement({ users, loading, error }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">User Management</h2>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && users.length === 0 && (
        <p className="text-sm text-gray-500">No users found.</p>
      )}
      {users.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="th">Email</th>
              <th className="th">Role</th>
              <th className="th">Company</th>
              <th className="th">Wallet Balance</th>
              <th className="th">Status</th>
              <th className="th">Joined</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td text-gray-100">{user.email}</td>
                <td className="td">
                  <RoleBadge role={user.role} />
                </td>
                <td className="td text-gray-400">{user.company_name || <span className="text-gray-600">—</span>}</td>
                <td className="td font-mono text-gray-300">
                  ${Number(user.wallet_balance ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
                <td className="td">
                  {user.is_active !== false
                    ? <span className="badge badge-green">Active</span>
                    : <span className="badge badge-red">Inactive</span>}
                </td>
                <td className="td text-gray-500">{fmt(user.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AdminDashboard() {
  const [bots, setBots] = useState([]);
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [platformRevenue, setPlatformRevenue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [botsError, setBotsError] = useState(null);
  const [usersError, setUsersError] = useState(null);

  async function fetchAll() {
    setLoading(true);

    // Bots
    try {
      const res = await apiFetch("/admin/bots");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBots(await res.json());
      setBotsError(null);
    } catch (e) {
      setBotsError(e.message);
    }

    // Users
    try {
      const res = await apiFetch("/admin/users");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setUsers(await res.json());
      setUsersError(null);
    } catch (e) {
      setUsersError(e.message);
    }

    // Stats
    try {
      const res = await apiFetch("/admin/stats");
      if (res.ok) setStats(await res.json());
    } catch {
      // stats are optional
    }

    // Platform revenue
    try {
      const res = await apiFetch("/admin/platform-revenue");
      if (res.ok) setPlatformRevenue(await res.json());
    } catch {
      // optional
    }

    setLoading(false);
  }

  useEffect(() => { fetchAll(); }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="page-heading">
        <div>
          <p className="page-kicker">Platform overview</p>
          <h1>Admin Dashboard</h1>
          <p className="page-subtitle">Your command center for the AXIOM ecosystem.</p>
        </div>
        <button
          onClick={fetchAll}
          className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
        >
          Refresh
        </button>
      </div>

      {/* A — Platform Overview */}
      <PlatformOverview bots={bots} users={users} stats={stats} platformRevenue={platformRevenue} loading={loading} />

      {/* B — Pending Approvals */}
      <PendingApprovals bots={bots} onRefresh={fetchAll} />

      {/* C — All Bots */}
      <AllBots bots={bots} loading={loading} error={botsError} />

      {/* D — User Management */}
      <UserManagement users={users} loading={loading} error={usersError} />
    </div>
  );
}
