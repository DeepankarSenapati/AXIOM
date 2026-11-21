import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { getUser, isAuthenticated, logout } from "./auth.js";
import { BrandMark, NavIcon } from "./components/Brand.jsx";

const AdminDashboard = lazy(() => import("./pages/AdminDashboard.jsx"));
const BotArena = lazy(() => import("./pages/BotArena.jsx"));
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Governance = lazy(() => import("./pages/Governance.jsx"));
const GovernanceDashboard = lazy(() => import("./pages/GovernanceDashboard.jsx"));
const History = lazy(() => import("./pages/History.jsx"));
const Leaderboard = lazy(() => import("./pages/Leaderboard.jsx"));
const Login = lazy(() => import("./pages/Login.jsx"));
const SurvivalLab = lazy(() => import("./pages/SurvivalLab.jsx"));
const MarketDashboard = lazy(() => import("./pages/MarketDashboard.jsx"));
const TechDashboard = lazy(() => import("./pages/TechDashboard.jsx"));
const Tokenomics = lazy(() => import("./pages/Tokenomics.jsx"));

function PageLoading() {
  return <div className="page-loading" role="status"><span aria-hidden="true" />Loading page…</div>;
}

// ---------------------------------------------------------------------------
// Role-aware navigation
// ---------------------------------------------------------------------------

const NAV_ADMIN = [
  { to: "/admin", label: "Admin", icon: "admin" },
  { to: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { to: "/lab", label: "Survival Lab", icon: "lab" },
  { to: "/arena", label: "Bot Arena", icon: "arena" },
  { to: "/leaderboard", label: "Leaderboard", icon: "leaderboard" },
  { to: "/history", label: "History", icon: "history" },
  { to: "/tokenomics", label: "Tokenomics", icon: "tokenomics" },
  { to: "/governance", label: "Governance", icon: "governance" },
];

const NAV_TECH = [
  { to: "/tech", label: "My Bots", icon: "tech" },
  { to: "/lab", label: "Survival Lab", icon: "lab" },
  { to: "/arena", label: "Bot Arena", icon: "arena" },
  { to: "/leaderboard", label: "Leaderboard", icon: "leaderboard" },
  { to: "/history", label: "History", icon: "history" },
];

const NAV_GOV = [
  { to: "/governance-co", label: "Gov Dashboard", icon: "governance" },
  { to: "/lab", label: "Survival Lab", icon: "lab" },
  { to: "/governance", label: "Governance Voting", icon: "governance" },
  { to: "/leaderboard", label: "Leaderboard", icon: "leaderboard" },
  { to: "/history", label: "History", icon: "history" },
];

const NAV_MARKET = [
  { to: "/market", label: "Market", icon: "market" },
  { to: "/lab", label: "Survival Lab", icon: "lab" },
  { to: "/leaderboard", label: "Leaderboard", icon: "leaderboard" },
  { to: "/governance", label: "Governance", icon: "governance" },
  { to: "/history", label: "History", icon: "history" },
];

function getNavForRole(role) {
  switch (role) {
    case "admin":            return NAV_ADMIN;
    case "tech_company":     return NAV_TECH;
    case "governance_company": return NAV_GOV;
    case "token_holder":     return NAV_MARKET;
    default:                 return NAV_ADMIN;
  }
}

const ROLE_LABELS = {
  admin: "Admin",
  tech_company: "Tech Co.",
  governance_company: "Gov Co.",
  token_holder: "Token Holder",
};

// ---------------------------------------------------------------------------
// RoleHome — redirects each role to its home route
// ---------------------------------------------------------------------------

function RoleHome() {
  const user = getUser();
  const homes = {
    admin: "/admin",
    tech_company: "/tech",
    governance_company: "/governance-co",
    token_holder: "/market",
  };
  return <Navigate to={homes[user?.role] ?? "/dashboard"} replace />;
}

// ---------------------------------------------------------------------------
// RoleGuard — redirects to role home if the current user's role is not in `roles`
// ---------------------------------------------------------------------------

function RoleGuard({ roles, children }) {
  const user = getUser();
  if (!roles.includes(user?.role)) {
    return <RoleHome />;
  }
  return children;
}

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
  const nav = getNavForRole(user?.role);
  const location = useLocation();
  const currentPage = nav.find((item) => item.to === location.pathname)?.label ?? "Workspace";
  const initials = (user?.email?.[0] ?? "A").toUpperCase();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <BrandMark className="brand-mark" />
          <div>
            <span className="brand-name">AXIOM<span className="brand-period">.</span></span>
            <span className="brand-caption">INTELLIGENT MARKETS</span>
          </div>
        </div>
        <div className="sidebar-section-label">WORKSPACE <span>01</span></div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {nav.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `sidebar-link${isActive ? " is-active" : ""}`
              }
            >
              <NavIcon name={icon} />
              <span>{label}</span>
              <span className="nav-arrow" aria-hidden="true">↗</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="environment-card">
            <div className="environment-card-top"><span className="status-dot" /> SIMULATION MODE</div>
            <p>Practice, explore, and evaluate without real orders.</p>
            <span className="environment-card-foot">LOCAL ENVIRONMENT <span>↗</span></span>
          </div>
          <div className="sidebar-version"><span>AXIOM / PLATFORM</span><span>V 01</span></div>
        </div>
      </aside>
      <div className="workspace">
        <header className="workspace-header">
          <div className="breadcrumbs"><span>WORKSPACE</span><span className="breadcrumb-slash">/</span><strong>{currentPage}</strong></div>
          <div className="header-actions">
            <span className="simulation-pill"><span className="status-dot" /> SIMULATION</span>
            <div className="header-user" title={user?.email}>
              <span className="user-avatar">{initials}</span>
              <span className="user-details"><strong>{roleLabel}</strong><small>{user?.email}</small></span>
            </div>
            <button type="button" onClick={logout} className="sign-out">Sign out <span aria-hidden="true">↗</span></button>
          </div>
        </header>
        <main className="page-content">
        <Suspense fallback={<PageLoading />}>
        <Routes>
          {/* Role-based home redirect */}
          <Route path="/" element={<RoleHome />} />

          {/* Shared routes (all authenticated roles) */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/lab" element={<SurvivalLab />} />
          <Route path="/arena" element={<BotArena />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/history" element={<History />} />
          <Route path="/tokenomics" element={<Tokenomics />} />
          <Route path="/governance" element={<Governance />} />

          {/* Role-specific dashboards */}
          <Route
            path="/admin"
            element={
              <RoleGuard roles={["admin"]}>
                <AdminDashboard />
              </RoleGuard>
            }
          />
          <Route
            path="/tech"
            element={
              <RoleGuard roles={["tech_company"]}>
                <TechDashboard />
              </RoleGuard>
            }
          />
          <Route
            path="/governance-co"
            element={
              <RoleGuard roles={["governance_company"]}>
                <GovernanceDashboard />
              </RoleGuard>
            }
          />
          <Route
            path="/market"
            element={
              <RoleGuard roles={["token_holder"]}>
                <MarketDashboard />
              </RoleGuard>
            }
          />
        </Routes>
        </Suspense>
        </main>
      </div>
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
      <Route path="/login" element={<Suspense fallback={<PageLoading />}><Login /></Suspense>} />

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
