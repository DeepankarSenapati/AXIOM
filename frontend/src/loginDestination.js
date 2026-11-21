import { roleHome } from "./auth.js";

// Only return to known in-app pages; never turn login state into an external redirect.
const PAGES = new Set(["/", "/admin", "/dashboard", "/lab", "/arena", "/leaderboard", "/history", "/tokenomics", "/governance", "/governance-co", "/tech", "/market"]);

export function loginDestination(from, role) {
  if (!from || typeof from.pathname !== "string" || !PAGES.has(from.pathname) || from.pathname === "/") {
    return roleHome(role);
  }
  return {
    pathname: from.pathname,
    search: typeof from.search === "string" && from.search.startsWith("?") ? from.search : "",
    hash: typeof from.hash === "string" && from.hash.startsWith("#") ? from.hash : "",
  };
}
