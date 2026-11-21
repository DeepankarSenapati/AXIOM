import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { setToken } from "../auth.js";
import { loginDestination } from "../loginDestination.js";
import { BrandMark } from "../components/Brand.jsx";

const DEMO_ACCOUNTS = [
  { role: "Admin", email: "admin@axiom.com", password: "admin123" },
  { role: "Tech company", email: "tech@botbuilders.com", password: "tech123" },
  { role: "Governance", email: "gov@oversight.com", password: "gov123" },
  { role: "Buyer", email: "buyer@demo.com", password: "buyer123" },
];

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Login failed");
        return;
      }
      setToken(data.access_token);
      navigate(loginDestination(location.state?.from, data.user.role), { replace: true });
    } catch {
      setError("Network error — is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <section className="login-story" aria-label="About AXIOM">
        <div className="login-brand"><BrandMark className="brand-mark" /><span className="brand-name">AXIOM<span className="brand-period">.</span></span><span className="login-brand-caption">INTELLIGENT MARKETS</span></div>
        <div className="login-story-content">
          <div className="eyebrow"><span className="eyebrow-line" /> THE AXIOM PLATFORM <span className="eyebrow-number">/ 01</span></div>
          <h1>Better thinking.<br /><span>Smarter systems.</span></h1>
          <p>Explore the future of algorithmic markets in one intelligent workspace.</p>
          <div className="login-visual" aria-hidden="true">
            <div className="visual-label"><span>STRATEGY / SIGNAL</span><span>SIMULATED ENVIRONMENT</span></div>
            <svg viewBox="0 0 600 180" preserveAspectRatio="none">
              <defs><linearGradient id="signal-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#c9f77d" stopOpacity=".18"/><stop offset="1" stopColor="#c9f77d" stopOpacity="0"/></linearGradient></defs>
              <path d="M0 145 L35 138 58 142 87 117 110 125 145 112 176 119 210 90 239 100 274 83 301 91 334 63 369 75 400 54 433 64 464 38 500 48 532 23 565 29 600 8 V180 H0Z" fill="url(#signal-fill)" />
              <path d="M0 145 L35 138 58 142 87 117 110 125 145 112 176 119 210 90 239 100 274 83 301 91 334 63 369 75 400 54 433 64 464 38 500 48 532 23 565 29 600 8" fill="none" stroke="#c9f77d" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            </svg>
            <div className="visual-bottom"><span>RESEARCH</span><span>SIMULATE</span><span>GOVERN</span></div>
          </div>
        </div>
        <div className="login-story-footer"><span>BUILT FOR SYSTEMATIC THINKING</span><span>AXIOM ©</span></div>
      </section>

      <section className="login-access">
        <div className="login-access-top"><span>AXIOM / WORKSPACE</span><span className="simulation-pill"><span className="status-dot" /> SIMULATION</span></div>
        <div className="login-form-wrap">
          <div className="eyebrow"><span className="eyebrow-line" /> WORKSPACE ACCESS</div>
          <h2>Welcome back<span className="brand-period">.</span></h2>
          <p className="login-intro">Sign in to your workspace to continue.</p>

          <form onSubmit={handleSubmit} className="login-form">
            <div>
              <label className="label" htmlFor="login-email">Email address</label>
              <input
                id="login-email"
                className="input"
                type="email"
                placeholder="you@example.com"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div>
              <label className="label" htmlFor="login-password">Password</label>
              <input
                id="login-password"
                className="input"
                type="password"
                placeholder="••••••••"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <p className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded px-3 py-2">
                {error}
              </p>
            )}

            <button type="submit" className="btn-primary login-submit" disabled={loading}>
              {loading ? "Signing in…" : "Enter workspace"} <span aria-hidden="true">↗</span>
            </button>
          </form>
          <details className="demo-credentials">
            <summary>Explore demo credentials <span aria-hidden="true">+</span></summary>
            <div className="demo-credentials-list">
              <p>Choose an account to fill the form, then enter the workspace.</p>
              {DEMO_ACCOUNTS.map((account) => <button key={account.email} type="button" onClick={() => {
                setEmail(account.email);
                setPassword(account.password);
                setError(null);
              }} aria-label={`Fill ${account.role} demo credentials`}>
                <span><strong>{account.role}</strong><small>{account.email} / {account.password}</small></span>
                <span aria-hidden="true">USE ↗</span>
              </button>)}
            </div>
          </details>
        </div>
        <div className="login-access-footer"><span>LOCAL SIMULATION ONLY</span><span>NO REAL ORDERS</span></div>
      </section>
    </div>
  );
}
