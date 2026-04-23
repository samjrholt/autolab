import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";


const apiPrefixes = [
  "/analysis",
  "/status",
  "/resources",
  "/tools",
  "/workflows",
  "/campaigns",
  "/ledger",
  "/records",
  "/estimate",
  "/samples",
  "/verify",
  "/lab",
  "/export",
  "/acceptance",
  "/health",
  "/escalations",
];

const serverPort = Number(process.env.VITE_PORT || 5173);
const apiTarget = process.env.AUTOLAB_API_TARGET || "http://localhost:8000";
const wsTarget = apiTarget.replace(/^http/, "ws");

export default defineConfig({
  plugins: [tailwindcss(), react()],
  base: "/static/",
  build: {
    outDir: path.resolve(__dirname, "../src/autolab/server/static"),
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    port: serverPort,
    proxy: {
      ...Object.fromEntries(apiPrefixes.map((prefix) => [prefix, apiTarget])),
      "/events": {
        target: wsTarget,
        ws: true,
      },
    },
  },
});
