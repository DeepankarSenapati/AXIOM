import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// These page URLs overlap API proxy prefixes. Only HTML navigations to the
// exact page paths should reach the SPA; nested endpoints still reach FastAPI.
const pagePaths = new Set(["/admin", "/tech", "/arena", "/tokenomics", "/governance", "/governance-co"]);
const apiPort = process.env.AXIOM_DEMO_API_PORT ?? "8000";
if (!/^\d+$/.test(apiPort) || Number(apiPort) < 1 || Number(apiPort) > 65535) {
  throw new Error("AXIOM_DEMO_API_PORT must be a valid TCP port");
}
const demoNonce = process.env.AXIOM_DEMO_READINESS_NONCE;
if (demoNonce && !/^[a-f0-9]{32}$/.test(demoNonce)) {
  throw new Error("AXIOM_DEMO_READINESS_NONCE must be a 32-character hex value");
}

function demoReadiness() {
  return {
    name: "axiom-demo-readiness",
    configureServer(server) {
      if (!demoNonce) return;
      server.middlewares.use((req, res, next) => {
        if (req.method === "GET" && req.url?.split("?")[0] === "/__axiom_demo_ready") {
          res.statusCode = 200;
          res.setHeader("Content-Type", "text/plain; charset=utf-8");
          res.end(demoNonce);
          return;
        }
        next();
      });
    },
  };
}

function apiProxy() {
  return {
    target: `http://127.0.0.1:${apiPort}`,
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
  plugins: [react(), demoReadiness()],
  define: { __AXIOM_DEMO_SESSION__: JSON.stringify(demoNonce ?? null) },
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
