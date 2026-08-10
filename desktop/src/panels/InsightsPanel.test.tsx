// X1+X2 — o carimbo do mapa chega à superfície dos indicadores.
//
// O backend registra desde o F2-PR1 QUEM produziu o mapa (leiden ou o
// fallback de componentes) e DE QUANDO ele é; insights/gaps descartavam o
// carimbo e o painel não tinha como dizer. Estes testes fixam o que o
// `tsc` não prova: que o badge aparece, e que o caso enganoso (fallback
// silencioso de componentes) é dito em voz alta.
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { client } from "../lib/client";
import { InsightsPanel } from "./InsightsPanel";

const BASE = {
  gaps: { questions: [], orphans: [], contested: [], stale: [],
          cold_count: 0, eval: [] },
  topology: { nodes: 0, edges: 0, components: 1, largest_component_pct: 0,
              avg_degree: 0, bridges: [], communities: 0,
              structure: "incipiente", evenness: 0 },
  activity: { events_per_day: [], top_events: [] },
  classifiers: { by_type: [], by_privacy: [], by_origin: [],
                 by_confidence: [] },
};

function montar(freshness: unknown) {
  vi.spyOn(client, "connect").mockResolvedValue(undefined as any);
  vi.spyOn(client, "insights").mockResolvedValue(
    { ...BASE, freshness } as any);
  vi.spyOn(client, "traces").mockResolvedValue({ traces: [] } as any);
  vi.spyOn(client, "gaps").mockResolvedValue(
    { gaps: [], articulators: [], communities: 0, freshness } as any);
  return render(<InsightsPanel />);
}

describe("badge de frescor dos indicadores (X1+X2)", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("diz em voz alta quando o mapa veio do fallback de componentes", async () => {
    montar({ partition_backend: "components", centrality_backend: "none",
             computed_at: 1754800000, bundle_head: "abc123" });
    expect(await screen.findByText(/partição por/)).toBeTruthy();
    expect(await screen.findByText(/sem \[ml\]/)).toBeTruthy();
  });

  it("mapa nunca computado não passa por mapa atual", async () => {
    montar({ partition_backend: "none", centrality_backend: "none",
             computed_at: null, bundle_head: null });
    expect(await screen.findByText(/mapa nunca computado/)).toBeTruthy();
  });
});
