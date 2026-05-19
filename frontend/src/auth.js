const TOKEN_KEY = "axiom_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  window.location.href = "/login";
}

export function getUser() {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    // Pad base64 to a multiple of 4
    const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function isAuthenticated() {
  const user = getUser();
  if (!user) return false;
  // exp is in seconds since epoch
  if (user.exp && Date.now() / 1000 > user.exp) {
    logout();
    return false;
  }
  return true;
}

export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Drop-in replacement for fetch() that:
 * - Automatically attaches the Bearer token
 * - Calls logout() and redirects to /login on any 401 response
 */
export async function apiFetch(url, options = {}) {
  const headers = { ...authHeaders(), ...(options.headers ?? {}) };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    logout();
    throw new Error("Session expired — please log in again");
  }
  return res;
}

/** Map role → home route */
export function roleHome(role) {
  const map = {
    admin: "/admin",
    tech_company: "/tech",
    governance_company: "/governance-co",
    token_holder: "/market",
  };
  return map[role] ?? "/dashboard";
}
