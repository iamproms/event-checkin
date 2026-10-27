import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, ".", "API_").API_PROXY_TARGET || "http://localhost:8000";
  return {
    plugins: [react()],
    build: { rollupOptions: { input: {
      main: "index.html",
      platform: "platform.html",
      platformConsole: "platform-console.html",
      workspace: "workspace.html",
      gate: "gate.html",
      domains: "domains.html",
      events: "events.html",
      branding: "branding.html",
      register: "register.html",
    } } },
    server: {
      proxy: {
        "/api": target,
        "/health": target,
        "/ready": target,
      },
    },
  };
});

