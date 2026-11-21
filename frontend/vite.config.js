import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// These page URLs overlap API proxy prefixes. Only HTML navigations to the
// exact page paths should reach the SPA; nested endpoints still reach FastAPI.
const pagePaths = new Set(["/admin", "/tech", "/arena", "/tokenomics", "/governance", "/governance-co"]);

function apiProxy() {
  return {
    target: "http://127.0.0.1:8000",
    bypass(req) {
      const path = (req.url ?? "").split("?")[0].replace(/\/+$/, "") || "/";
      const mode = req.headers["sec-fetch-mode"];
      const html = req.headers.accept?.split(",").some((value) => value.trim().startsWith("text/html"));
      if ((req.method === "GET" || req.method === "HEAD") && (!mode || mode === "navigate") && html && pagePaths.has(path)) {
        return "/index.html";
      }
    },
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/bots": apiProxy(),
      "/arena": apiProxy(),
      "/tokenomics": apiProxy(),
      "/governance": apiProxy(),
      "/auth": apiProxy(),
      "/admin": apiProxy(),
      "/tech": apiProxy(),
      "/health": apiProxy(),
    },
  },
});
