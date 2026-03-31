import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { authHeaders, getUser, isAuthenticated, logout } from "./auth.js";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import BotArena from "./pages/BotArena.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Governance from "./pages/Governance.jsx";
import History from "./pages/History.jsx";
import Login from "./pages/Login.jsx";
import MarketDashboard from "./pages/MarketDashboard.jsx";
import TechDashboard from "./pages/TechDashboard.jsx";
import Tokenomics from "./pages/Tokenomics.jsx";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: "⬛" },
  { to: "/arena", label: "Bot Arena", icon: "⚔️" },
  { to: "/history", label: "History", icon: "🕐" },
  { to: "/tokenomics", label: "Tokenomics", icon: "🪙" },
  { to: "/governance", label: "Governance", icon: "🗳️" },
];

const ROLE_LABELS = {
  admin: "Admin",
  tech_company: "Tech Co.",
  governance_company: "Gov Co.",
  token_holder: "Token Holder",
};

// ---------------------------------------------------------------------------
// ProtectedRoute — redirects to /login if not authenticated
// ---------------------------------------------------------------------------

function ProtectedRoute({ children }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

// ---------------------------------------------------------------------------
// Layout with sidebar (only shown when authenticated)
// ---------------------------------------------------------------------------

function AppLayout() {
  const user = getUser();
  const roleLabel = ROLE_LABELS[user?.role] ?? user?.role ?? "Unknown";

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-5 border-b border-gray-800">
          <span className="text-lg font-bold text-indigo-400 tracking-widest">AXIOM</span>
          <p className="text-xs text-gray-500 mt-0.5">Bot Trading Platform</p>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-700 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
                }`
              }
            >
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User info + logout */}
        <div className="px-4 py-3 border-t border-gray-800 space-y-2">
          {user && (
            <div className="space-y-0.5">
              <p className="text-xs text-gray-100 truncate">{user.email}</p>
              <span className="inline-block text-xs px-2 py-0.5 rounded-full bg-indigo-900 text-indigo-300 font-medium">
                {roleLabel}
              </span>
            </div>
          )}
          <button
            onClick={logout}
            className="w-full text-left text-xs text-gray-500 hover:text-red-400 transition-colors py-1"
          >
            Sign out →
          </button>
          <p className="text-xs text-gray-700">Phase 1 — Local MVP</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/arena" element={<BotArena />} />
          <Route path="/history" element={<History />} />
          <Route path="/tokenomics" element={<Tokenomics />} />
          <Route path="/governance" element={<Governance />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/tech" element={<TechDashboard />} />
          <Route path="/market" element={<MarketDashboard />} />
        </Routes>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />

      {/* Protected — everything else */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
