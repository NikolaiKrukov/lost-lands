import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const root = dirname(fileURLToPath(import.meta.url));

function copyMaplibreWorker(): Plugin {
  return {
    name: "copy-maplibre-worker",
    writeBundle() {
      const dist = resolve(root, "dist/assets");
      mkdirSync(dist, { recursive: true });
      const src = resolve(root, "node_modules/maplibre-gl/dist");
      for (const name of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
        copyFileSync(resolve(src, name), resolve(dist, name));
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), copyMaplibreWorker()],
  server: {
    port: 5174,
    proxy: { "/api": "http://127.0.0.1:8010" },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
