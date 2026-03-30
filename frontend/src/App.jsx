import { NavLink, Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import BotArena from "./pages/BotArena.jsx";
import Tokenomics from "./pages/Tokenomics.jsx";
import Governance from "./pages/Governance.jsx";
import History from "./pages/History.jsx";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: "⬛" },
  { to: "/arena", label: "Bot Arena", icon: "⚔️" },
  { to: "/history", label: "History", icon: "🕐" },
  { to: "/tokenomics", label: "Tokenomics", icon: "🪙" },
  { to: "/governance", label: "Governance", icon: "🗳️" },
];

export default function App() {
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
        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
          Phase 1 — Local MVP
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
        </Routes>
      </main>
    </div>
  );
}
