import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import electron from "vite-plugin-electron";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    electron([
      { entry: "electron/main.ts",
        vite: { build: { outDir: "dist-electron",
                         rollupOptions: { external: ["electron"] } } } },
      { entry: "electron/preload.ts",
        onstart: ({ reload }) => reload(),
        vite: { build: { outDir: "dist-electron",
                         rollupOptions: { external: ["electron"] } } } },
    ]),
  ],
  build: { outDir: "dist" },
});
