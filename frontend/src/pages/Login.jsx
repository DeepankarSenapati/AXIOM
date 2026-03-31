import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { roleHome, setToken } from "../auth.js";

export default function Login() {
  const navigate = useNavigate();
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
      navigate(roleHome(data.user.role), { replace: true });
    } catch {
      setError("Network error — is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="text-center space-y-1">
          <p className="text-4xl font-bold tracking-widest text-indigo-400">AXIOM</p>
          <p className="text-sm text-gray-500">Autonomous eXchange for Intelligent Operations & Markets</p>
        </div>

        {/* Card */}
        <div className="card space-y-5">
          <h1 className="text-lg font-semibold text-gray-100">Sign in</h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                className="input"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                className="input"
                type="password"
                placeholder="••••••••"
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

            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          {/* Dev hint */}
          <details className="text-xs text-gray-600">
            <summary className="cursor-pointer hover:text-gray-400 transition-colors">
              Demo credentials
            </summary>
            <div className="mt-2 space-y-1 font-mono bg-gray-800/50 rounded p-2">
              <p>admin@axiom.com / admin123</p>
              <p>tech@botbuilders.com / tech123</p>
              <p>gov@oversight.com / gov123</p>
              <p>buyer@demo.com / buyer123</p>
            </div>
          </details>
        </div>

        <p className="text-center text-xs text-gray-700">Phase 1 — Local simulation only</p>
      </div>
    </div>
  );
}
