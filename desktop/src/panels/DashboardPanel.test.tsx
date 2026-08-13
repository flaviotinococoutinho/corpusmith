// O veredito sobre padrão, na fila — F3-PR2 (P-3).
//
// A fila oferecia sete tipos de item e nenhum gesto de "já olhei, não vale".
// Ponte e contradição são padrões COMPUTADOS: o job os recria a cada
// execução, então rejeitar precisa de um registro que sobreviva — e a chave
// desse registro sai das PÁGINAS, nunca do rótulo de comunidade, que é um
// número de época. Estes testes fixam as duas coisas que o `tsc` não prova:
// que o botão chama, e que ele chama com a chave certa.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "../lib/client";
import { DashboardPanel } from "./DashboardPanel";

const PONTE = {
  kind: "bridge", target: "concepts/a.md", title: "A ↔ B",
  origin: "ponte frágil no grafo", value: 0.7, cost_min: 3,
  reason: "fio fraco entre dois blocos reais", acts: [],
  action: { type: "link", src: "concepts/a.md", dst: "concepts/b.md" },
};
const PERGUNTA = {
  kind: "question", target: "questions/q1.md", title: "Uma pergunta",
  origin: "pergunta aberta", value: 0.9, cost_min: 5,
  reason: "pergunta aberta na sua memória", acts: [],
  action: { type: "answer" },
};

function montar(actions: unknown[]) {
  vi.spyOn(client, "connect").mockResolvedValue(undefined as any);
  vi.spyOn(client, "nextActions").mockResolvedValue(
    { actions, total: actions.length, truncated: false } as any);
  // Forma REALISTA do resto do painel: `{}` fazia o render explodir em
  // `.slice` de undefined, e um teste que derruba o componente sob teste não
  // testa a fila — testa o mock.
  vi.spyOn(client, "dashboard").mockResolvedValue({
    pages: 0, chunks: 0, decisions: 0, stale: [], stale_count: 0,
    orphans: [], orphan_count: 0, pending_jobs: 0, by_type: {},
    budget_left_usd: 0, recommended_actions: [] } as any);
  vi.spyOn(client, "reflectCand").mockResolvedValue(
    { promote: [], archive: [], low_yield: [] } as any);
  vi.spyOn(client, "stats").mockResolvedValue({
    by_type: [], heat_buckets: [0, 0, 0, 0, 0],
    outcomes: { useful: 0, dead_end: 0, corrected: 0 },
    outcomes_per_day: [] } as any);
  vi.spyOn(client, "cold").mockResolvedValue({
    count: 0, entries: [], recycles: 0, compression_saved: 0 } as any);
  return render(<DashboardPanel />);
}

describe("fila — veredito sobre padrão computado", () => {
  beforeEach(() => {
    vi.spyOn(client, "patternVerdict").mockResolvedValue(
      { kind: "bridge", key: "k", status: "rejected" } as any);
  });

  it("dispensar manda as PÁGINAS da ponte, não o alvo só", async () => {
    montar([PONTE]);
    fireEvent.click(await screen.findByRole("button", { name: "dispensar" }));
    await waitFor(() => expect(client.patternVerdict).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "bridge", status: "rejected",
        pages: ["concepts/a.md", "concepts/b.md"] })));
  });

  it("adiar manda um `until` no futuro — some agora, volta depois", async () => {
    montar([PONTE]);
    fireEvent.click(await screen.findByRole("button", { name: "adiar" }));
    await waitFor(() => expect(client.patternVerdict).toHaveBeenCalled());
    const arg = (client.patternVerdict as any).mock.calls[0][0];
    expect(arg.status).toBe("deferred");
    expect(arg.until).toBeGreaterThan(Date.now() / 1000);
  });

  it("PÁGINA não recebe veredito de padrão", async () => {
    // Veredito sobre objeto canônico é ato de curadoria (vai ao frontmatter,
    // versionado em Git). Oferecer "dispensar" aqui empurraria um juízo sobre
    // o canônico para uma tabela de projeção — o erro que o P-3 separa.
    montar([PERGUNTA]);
    await screen.findByText("Uma pergunta");
    expect(screen.queryByRole("button", { name: "dispensar" })).toBeNull();
  });

  it("a fila recarrega depois do veredito", async () => {
    montar([PONTE]);
    fireEvent.click(await screen.findByRole("button", { name: "dispensar" }));
    await waitFor(() =>
      expect(client.nextActions).toHaveBeenCalledTimes(2));
  });
});
