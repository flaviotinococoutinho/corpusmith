// A colisão como decisão humana — F3-PR1 (RFC-003).
//
// O que estes testes fixam é o CONTRATO do gesto: uma resposta COLLISION
// nunca pode virar "✅ criado" (a mentira do log, na tela), e cada escolha
// humana precisa CHEGAR ao cliente com a resolução certa — que é o que o
// `tsc` não prova e o defeito original explorava.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "../lib/client";
import { PromoteDialog } from "./PromoteDialog";

const COLISAO = {
  op: "COLLISION" as const, kind: "semantic",
  target: "concepts/docker.md", score: 1.0,
  reason: "já existe uma página neste caminho",
  options: ["update", "new_slug"],
};

function montar() {
  return render(<PromoteDialog content="anotações" source="chat"
                               onClose={() => {}} />);
}

async function promover() {
  fireEvent.change(screen.getByPlaceholderText("Título"),
                   { target: { value: "Docker" } });
  fireEvent.click(screen.getByRole("button", { name: "Promover" }));
}

describe("PromoteDialog — colisão", () => {
  beforeEach(() => {
    vi.spyOn(client, "promote").mockResolvedValue(COLISAO as any);
  });

  it("COLLISION nunca vira '✅ criado'", async () => {
    montar();
    await promover();
    expect(await screen.findByText(/Já existe memória/)).toBeDefined();
    expect(screen.queryByText(/✅/)).toBeNull();
    expect(screen.getByText("concepts/docker.md")).toBeDefined();
  });

  it("'escrever sobre' re-chama com resolution=update e o target", async () => {
    const promote = vi.spyOn(client, "promote")
      .mockResolvedValueOnce(COLISAO as any)
      .mockResolvedValueOnce({ op: "UPDATE", kind: "semantic",
                               pages: ["concepts/docker.md"] } as any);
    montar();
    await promover();
    fireEvent.click(await screen.findByRole(
      "button", { name: /Escrever sobre a existente/ }));
    await waitFor(() => expect(promote).toHaveBeenLastCalledWith(
      expect.objectContaining({ resolution: "update",
                                target: "concepts/docker.md" })));
    expect(await screen.findByText(/salvo/)).toBeDefined();
  });

  it("'página separada' re-chama com resolution=new_slug", async () => {
    const promote = vi.spyOn(client, "promote")
      .mockResolvedValueOnce(COLISAO as any)
      .mockResolvedValueOnce({ op: "ADD", kind: "semantic",
                               pages: ["concepts/docker-2.md"] } as any);
    montar();
    await promover();
    fireEvent.click(await screen.findByRole(
      "button", { name: /Criar como página separada/ }));
    await waitFor(() => expect(promote).toHaveBeenLastCalledWith(
      expect.objectContaining({ resolution: "new_slug" })));
    expect(await screen.findByText("concepts/docker-2.md")).toBeDefined();
  });

  it("sem colisão o fluxo antigo segue intacto", async () => {
    vi.spyOn(client, "promote").mockResolvedValue(
      { op: "ADD", kind: "semantic", pages: ["concepts/docker.md"] } as any);
    montar();
    await promover();
    expect(await screen.findByText(/salvo/)).toBeDefined();
  });
});
