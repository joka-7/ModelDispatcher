import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During local development the SPA runs on Vite's dev server and proxies API
// calls to the FastAPI backend on :8000. In the container image the built assets
// are served by FastAPI itself, so the proxy is a dev-only concern.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
