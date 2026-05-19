import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/bots": "http://127.0.0.1:8000",
      "/arena": "http://127.0.0.1:8000",
      "/tokenomics": "http://127.0.0.1:8000",
      "/governance": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/admin": "http://127.0.0.1:8000",
      "/tech": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
