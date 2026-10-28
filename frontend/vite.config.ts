import { defineConfig, loadEnv, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, ".", "API_").API_PROXY_TARGET || "http://localhost:8000";
  const apiProxy = (): ProxyOptions => ({
    target,
    changeOrigin: false,
    configure(proxy) {
      proxy.on("proxyReq", (proxyRequest, request) => {
        // FastAPI validates the browser-facing Host itself. Forwarded
        // authority/client headers are deliberately not part of that contract.
        for (const header of ["forwarded", "x-forwarded-host", "x-forwarded-for", "x-forwarded-proto"]) {
          proxyRequest.removeHeader(header);
        }
        if (request.headers.host) proxyRequest.setHeader("host", request.headers.host);
      });
    },
  });
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
      allowedHosts: ["platform.local.example.test"],
      proxy: {
        "/api": apiProxy(),
        "/health": apiProxy(),
        "/ready": apiProxy(),
      },
    },
  };
});

