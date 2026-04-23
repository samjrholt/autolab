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


export default defineConfig({
  plugins: [tailwindcss(), react()],
  base: "/static/",
  build: {
    outDir: path.resolve(__dirname, "../src/autolab/server/static"),
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      ...Object.fromEntries(apiPrefixes.map((prefix) => [prefix, "http://localhost:8000"])),
      "/events": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});