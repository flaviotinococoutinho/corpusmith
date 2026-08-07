// Runner de teste de UI — a dívida que o ADR-41.3 declarou e ninguém tinha.
//
// "não existe runner de teste de UI no desktop (só `tsc --noEmit` no gate)…
// o que isso NÃO prova: que o onClick foi religado." Quatro entregas da
// vitrine estavam atrás dessa garantia declaradamente parcial, e o F-UI, que
// é a maior entrega puramente de interface do projeto, não podia ser a quinta.
//
// Config SEPARADA do `vite.config.mts` de propósito: aquele carrega
// `vite-plugin-electron`, que a cada `vitest` dispararia o build do main e do
// preload — processo de Electron subindo dentro do runner de teste. Aqui só o
// plugin de React, que é o que transforma o JSX dos painéis.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.tsx", "src/**/*.test.ts"],
    restoreMocks: true,
  },
});
