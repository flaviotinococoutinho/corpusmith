// Histórico de atos e desfazer — F-UI.
//
// O `undo` estava completo no backend e inalcançável pelo app porque
// `/curation/history` não tinha método no cliente: sem o `act_id` não havia
// como chamá-lo. O teste central aqui é o do 409 — recusar NOMEANDO o motivo
// é a parte difícil do ato, e engoli-la na interface a desperdiçaria.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "../lib/client";
import { CurationError } from "../lib/daemonClient";
import { ActsHistory } from "./ActsHistory";

const ATOS = [
  { id: 7, act: "merge", params: {}, commit_sha: "abc",
    pages: ["concepts/a.md", "concepts/b.md"], created_at: 1_700_000_000,
    undoes: null, undone_by: null },
  { id: 6, act: "link", params: {}, commit_sha: "def",
    pages: ["concepts/c.md"], created_at: 1_699_000_000,
    undoes: null, undone_by: 8 },
];

describe("ActsHistory", () => {
  beforeEach(() => {
    vi.spyOn(client, "curationHistory").mockResolvedValue({ acts: ATOS });
  });

  it("lista os atos que o app não tinha como enxergar", async () => {
    render(<ActsHistory />);
    expect(await screen.findByText("merge")).toBeDefined();
    expect(screen.getByText("link")).toBeDefined();
  });

  it("desfazer chama o ato `undo` com o act_id daquela linha", async () => {
    const act = vi.spyOn(client, "curationAct").mockResolvedValue({} as any);
    render(<ActsHistory />);
    const botoes = await screen.findAllByRole("button", { name: "desfazer" });
    fireEvent.click(botoes[0]);
    await waitFor(() => expect(act).toHaveBeenCalledWith(
      "undo", { act_id: "7" }, false));
  });

  it("ato já desfeito não oferece desfazer de novo", async () => {
    render(<ActsHistory />);
    // ATOS[1] tem `undone_by: 8` — sobra UM botão, o do ato #7
    const botoes = await screen.findAllByRole("button", { name: "desfazer" });
    expect(botoes).toHaveLength(1);
    expect(screen.getByText("desfeito")).toBeDefined();
  });

  it("409 vira o MOTIVO na tela, não uma falha genérica", async () => {
    vi.spyOn(client, "curationAct").mockRejectedValue(new CurationError(
      409, { detail: "o estado anterior não é alcançável escrevendo para a frente" }));
    render(<ActsHistory />);
    const botoes = await screen.findAllByRole("button", { name: "desfazer" });
    fireEvent.click(botoes[0]);
    expect(await screen.findByText(/não é alcançável escrevendo/)).toBeDefined();
  });
});
