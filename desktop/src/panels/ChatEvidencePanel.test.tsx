// P-4 (ADR-52) — o selo de sustentação aparece quando a base é rasa.
//
// O defeito que motivou o mecanismo: um único chunk ⇒ uncertainty 0 ⇒
// NENHUM aviso — certeza máxima no momento mais fraco. O badge de
// sustentação fraca é o que o usuário vê no lugar do silêncio.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { client } from "../lib/client";
import { ChatEvidencePanel } from "./ChatEvidencePanel";

const RESPOSTA_RASA = {
  answer: "Resposta confiante sobre zeppelins [1].",
  via: "local:extractive", blocked: false, abstained: false,
  uncertainty: 0.0,
  support: { score: 0.21, components: { distinct_pages: 0.33,
    corroborating_streams: 0.33, grounded_fraction: 0, freshness: 0.17 } },
  evidence: [{ page: "concepts/unico.md", body: "…", stale: false,
               superseded: false, spans: [] }],
  gaps: [], trajectory: [],
};

describe("selo de sustentação (P-4)", () => {
  it("base rasa com certeza máxima mostra sustentação fraca", async () => {
    vi.spyOn(client, "ask").mockResolvedValue(RESPOSTA_RASA as any);
    render(<ChatEvidencePanel />);
    fireEvent.change(screen.getByPlaceholderText(/Pergunte à sua base/),
                     { target: { value: "zeppelins" } });
    fireEvent.click(screen.getByText("Perguntar"));
    expect(await screen.findByText(/sustentação fraca/)).toBeTruthy();
  });
});
