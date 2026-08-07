// Cancelar e reexecutar job — F-UI.
//
// Dois defeitos distintos aqui. O botão "↻" chamava `enqueue(type, payload)`:
// criava um job NOVO em vez de reexecutar aquele, deixando o antigo `failed`
// para sempre, zerando o rastro de tentativas e furando o dedupe — enquanto
// `POST /jobs/{id}/retry` existia e ninguém chamava. E cancelar não existia
// na interface, embora `POST /jobs/{id}/cancel` esteja lá desde a v1.2.
//
// A tabela também só conhecia quatro dos oito estados da fila, e os quatro
// que faltavam são justamente os que dizem o que fazer: `retry_scheduled`
// (esperar), `dead_lettered` (só manual), `cancelled`, `cancel_requested`.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "../lib/client";
import { ProcessesPanel } from "./ProcessesPanel";

const JOBS = [
  { id: "j-queued", type: "compile", state: "queued", attempts: 0 },
  { id: "j-leased", type: "leiden", state: "leased", attempts: 1 },
  { id: "j-dead", type: "embed", state: "dead_lettered", attempts: 3,
    error: "estourou as tentativas" },
  { id: "j-done", type: "reflect", state: "done", attempts: 1 },
];

function montar() {
  vi.spyOn(client, "connect").mockResolvedValue(undefined as any);
  vi.spyOn(client, "jobs").mockResolvedValue({ jobs: JOBS });
  vi.spyOn(client, "pipelines").mockResolvedValue({ pipelines: [] } as any);
  vi.spyOn(client, "pipelineRuns").mockResolvedValue({ runs: [] } as any);
  vi.spyOn(client, "events").mockReturnValue(
    { close() {} } as unknown as EventSource);
  return render(<ProcessesPanel />);
}

describe("ProcessesPanel", () => {
  beforeEach(() => {
    vi.spyOn(client, "cancelJob").mockResolvedValue({} as any);
    vi.spyOn(client, "retryJob").mockResolvedValue({} as any);
  });

  it("reexecutar chama /jobs/{id}/retry, não um enqueue novo", async () => {
    const enfileirar = vi.spyOn(client, "enqueue");
    montar();
    const linha = (await screen.findByText("j-dead")).closest("tr")!;
    fireEvent.click(linha.querySelector("button[title^='reexecutar']")!);
    await waitFor(() =>
      expect(client.retryJob).toHaveBeenCalledWith("j-dead"));
    expect(enfileirar).not.toHaveBeenCalled();
  });

  it("cancelar chama /jobs/{id}/cancel", async () => {
    montar();
    const linha = (await screen.findByText("j-queued")).closest("tr")!;
    fireEvent.click(linha.querySelector("button[title='cancelar agora']")!);
    await waitFor(() =>
      expect(client.cancelJob).toHaveBeenCalledWith("j-queued"));
  });

  it("só oferece o que a fila aceita naquele estado", async () => {
    montar();
    await screen.findByText("j-done");
    const acoes = (id: string) => {
      const tr = screen.getByText(id).closest("tr")!;
      return Array.from(tr.querySelectorAll("button")).map(
        b => b.getAttribute("title") ?? "");
    };
    // `done` não é cancelável nem reexecutável — o backend responderia 409
    expect(acoes("j-done")).toHaveLength(0);
    // `leased` só aceita o cancelamento COOPERATIVO
    expect(acoes("j-leased").join()).toMatch(/pedir cancelamento/);
    expect(acoes("j-leased").join()).not.toMatch(/reexecutar/);
    // `dead_lettered` só volta por reexecução manual
    expect(acoes("j-dead").join()).toMatch(/reexecutar/);
  });

  it("409 da fila aparece como motivo em vez de botão inerte", async () => {
    vi.spyOn(client, "cancelJob").mockRejectedValue(
      new Error("/jobs/j-queued/cancel: 409"));
    montar();
    const linha = (await screen.findByText("j-queued")).closest("tr")!;
    fireEvent.click(linha.querySelector("button[title='cancelar agora']")!);
    expect(await screen.findByText(/409/)).toBeDefined();
  });
});
