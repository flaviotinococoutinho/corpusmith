// O primeiro teste de UI do projeto — F-UI.
//
// O ADR-41.3 declarou a lacuna com precisão: "não existe runner de teste de UI
// no desktop (só `tsc --noEmit` no gate)… o que isso NÃO prova: que o onClick
// foi religado." Quatro entregas da vitrine ficaram atrás dessa garantia
// parcial, e o F-UI — que é quase inteiramente onClick — não podia ser a
// quinta.
//
// Por isso os testes daqui NÃO conferem texto e cor: conferem que o gesto
// chega ao cliente. Um teste que só afirma que o cabeçalho diz "Integridade"
// passaria com o botão desligado, que é exatamente o defeito em questão.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "../lib/client";
import { DoctorPanel } from "./DoctorPanel";

const COM_ORFAO = {
  ok: false,
  counts: { error: 1, warn: 1 },
  repaired: null,
  findings: [
    { inv: "INV-001", severity: "error" as const,
      message: "3 página(s) no índice sem arquivo no bundle" },
    { inv: "INV-004", severity: "warn" as const,
      message: "mapa de padrões mais velho que o HEAD" },
  ],
  derivations: {
    index: { state: "fresh" },
    graph_map: { state: "stale", reason: "o índice mudou" },
  },
};

describe("DoctorPanel", () => {
  beforeEach(() => {
    vi.spyOn(client, "doctor").mockResolvedValue(COM_ORFAO as any);
    vi.spyOn(client, "doctorRepair").mockResolvedValue(
      { ...COM_ORFAO, ok: true, findings: [], counts: { error: 0, warn: 0 },
        repaired: { mode: "full", pages: 12 } } as any);
  });

  it("mostra os findings que só existiam no terminal", async () => {
    render(<DoctorPanel />);
    expect(await screen.findByText(/INV-001/)).toBeDefined();
    expect(screen.getByText(/INV-004/)).toBeDefined();
    expect(screen.getByText(/3 página\(s\) no índice/)).toBeDefined();
  });

  it("o botão de reparo CHAMA o endpoint de reparo", async () => {
    const { getByRole } = render(<DoctorPanel />);
    const botao = await waitFor(() =>
      getByRole("button", { name: /Reparar/ }) as HTMLButtonElement);
    expect(botao.disabled).toBe(false);
    fireEvent.click(botao);
    await waitFor(() => expect(client.doctorRepair).toHaveBeenCalledOnce());
  });

  it("sem finding reparável o botão não promete reparo", async () => {
    vi.spyOn(client, "doctor").mockResolvedValue({
      ...COM_ORFAO,
      findings: [COM_ORFAO.findings[1]],       // só INV-004, fora de REPAIRABLE
    } as any);
    const { getByRole } = render(<DoctorPanel />);
    const botao = await waitFor(() =>
      getByRole("button", { name: /Reparar/ }) as HTMLButtonElement);
    expect(botao.disabled).toBe(true);
  });

  it("daemon fora do ar vira estado visível, não tela em branco", async () => {
    vi.spyOn(client, "doctor").mockRejectedValue(new Error("ECONNREFUSED"));
    render(<DoctorPanel />);
    expect(await screen.findByText(/não foi possível consultar/)).toBeDefined();
  });
});
