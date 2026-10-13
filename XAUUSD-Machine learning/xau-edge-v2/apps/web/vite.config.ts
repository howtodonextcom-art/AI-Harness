import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: the Vite server proxies the API and the WebSocket to the Python service (one origin in prod).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8200",
      "/ws": { target: "ws://127.0.0.1:8200", ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false, target: "es2022" },
});
