import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server proxies /api to the FastAPI backend so the browser sees one origin
// (session cookies + CSRF work the same as behind the production reverse proxy).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000", changeOrigin: true },
    },
  },
});
