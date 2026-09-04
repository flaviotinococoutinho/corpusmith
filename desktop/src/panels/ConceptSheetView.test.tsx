// Q-1 — a ficha do conceito na tela, e o que ela NÃO pode deixar de dizer.
//
// `tsc --noEmit` prova o shape e não prova nada sobre significado: uma
// ficha que renderize `computed: false` com a mesma frase de "nada
// observado" passa o typecheck e mente na tela. É o mesmo buraco que o
// F-UI mediu com o `onClick` desligado — por isso estes casos são vitest,
// não tipos.
//
// Os dois enganosos, que são o motivo deste arquivo existir:
//
//   1. "ainda não calculado" ≠ "nada observado" — o primeiro não diz nada
//      sobre página nenhuma; o segundo é um resultado;
//   2. `not_measured` e as `misinterpretations` são CONTEÚDO: a pergunta
//      "quanto ganho?" é a que o leitor traz, e a ficha a recusa na tela,
//      não numa página que ninguém abre.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ConceptSheet } from "../lib/daemonClient";
import { ConceptSheetView } from "./ConceptSheetView";

const VAZIA: ConceptSheet = {
  page: "concepts/x.md",
  title: "X",
  cost: { read_minutes: 2, words: 12, how: "leitura estimada a 150 palavras/min" },
  stability: {
    computed: false, edits: null, lifecycle: null, last_edit_at: null,
    computed_from: null, freshness: null, refresh: "corpusmith stability",
    means: "quieto no eixo de EDIÇÃO — nunca 'correto' nem 'aprovado'",
  },
  difficulty: {
    computed: false, score: null, measured: false, reason: "", components: {},
    refresh: "corpusmith difficulty",
    means: "sem sinal NÃO é fácil de explicar: é nada observado",
  },
  applications: {
    page: "concepts/x.md", cases: [],
    measurement: { edges: 0, ambiguous_targets: 0, ambiguous_fraction: null,
                   note: "fração das páginas-alvo com 2+ sujeitos fortes" },
  },
  lens: {
    computed: false, entities: [], total: 0, qualified: 0, level: "mention",
    means: "as entidades são MENÇÕES no texto", refresh: "corpusmith okf index",
  },
  divergence: {
    computed: false, conflicts: [],
    means: "desacordo DETECTADO entre páginas — não diz qual delas está certa",
    refresh: "corpusmith difficulty",
  },
  guarantees: [{
    mechanism_id: "editorial_stability", guarantee: "deterministic",
    relative_to: "a história do Git",
    misinterpretations: ["estável não é verdadeiro"],
  }],
  not_measured: ["GANHO de adotar a ideia — o produto não tem instrumento"],
  prose_enabled: false,
  prose: null,
};

/** A mesma ficha, com o refresh JÁ rodado e nada observado. */
const CALCULADA: ConceptSheet = {
  ...VAZIA,
  stability: { ...VAZIA.stability, computed: true, edits: 1,
               lifecycle: "viva", computed_from: "abc1234def",
               freshness: { state: "fresh", reason: "" } },
  difficulty: { ...VAZIA.difficulty, computed: true, score: 0,
                measured: false, reason: "" },
  lens: { ...VAZIA.lens, computed: true },
  divergence: { ...VAZIA.divergence, computed: true },
};

describe("os dois vazios da ficha do conceito", () => {
  it("projeção nunca calculada diz isso, e diz o comando que calcula", () => {
    render(<ConceptSheetView sheet={VAZIA} />);
    expect(screen.getAllByText(/ainda não calculado/).length)
      .toBeGreaterThanOrEqual(3);              // estabilidade, trava, lente
    expect(screen.getAllByText("corpusmith stability").length).toBe(1);
    // e NÃO diz a frase do outro vazio
    expect(screen.queryByText(/nada observado sobre esta página/)).toBeNull();
  });

  it("projeção calculada sem sinal diz 'nada observado', não 'não calculado'",
     () => {
    render(<ConceptSheetView sheet={CALCULADA} />);
    expect(screen.getByText(/nada observado sobre esta página/)).toBeTruthy();
    expect(screen.queryByText(/ainda não calculado/)).toBeNull();
    expect(screen.getByText(/nenhum desacordo detectado/)).toBeTruthy();
  });

  it("projeção velha é dita velha, não servida como se fosse de agora", () => {
    render(<ConceptSheetView sheet={{
      ...CALCULADA,
      stability: { ...CALCULADA.stability,
                   freshness: { state: "stale", reason: "o bundle andou" } },
    }} />);
    expect(screen.getByText(/projeção stale/)).toBeTruthy();
  });
});

describe("o que a ficha recusa dizer, dito na própria ficha", () => {
  it("o que NÃO foi medido é conteúdo, não rodapé escondido", () => {
    render(<ConceptSheetView sheet={CALCULADA} />);
    expect(screen.getByText(/GANHO de adotar a ideia/)).toBeTruthy();
    expect(screen.getByLabelText("O que esta ficha NÃO mede")).toBeTruthy();
  });

  it("cada número vem com a ressalva do mecanismo ao lado", () => {
    render(<ConceptSheetView sheet={CALCULADA} />);
    expect(screen.getByText(/quieto no eixo de EDIÇÃO/)).toBeTruthy();
    expect(screen.getByText(/não diz qual delas está certa/)).toBeTruthy();
    expect(screen.getByText(/estável não é verdadeiro/)).toBeTruthy();
  });

  it("'sob qual lente' declara o salto de nível (menção → página)", () => {
    render(<ConceptSheetView sheet={{
      ...CALCULADA,
      lens: { ...CALCULADA.lens, computed: true, total: 1, qualified: 1,
              entities: [{ canonical: "Entropia (física)", base: "Entropia",
                           sense: "física", authority: "concept",
                           kind: "entity", ambiguous: false, mentions: 3 }] },
    }} />);
    expect(screen.getByText(/MENÇÕES no texto/)).toBeTruthy();
    expect(screen.getByText("(física)")).toBeTruthy();
  });

  it("'onde diverge' nomeia a outra página, nunca o lado certo", () => {
    render(<ConceptSheetView sheet={{
      ...CALCULADA,
      divergence: { ...CALCULADA.divergence, computed: true, conflicts: [{
        rule: "policy.contradiction_candidate", identifier: "10.1000/xyz",
        with_pages: ["concepts/b.md"], message: "sem sucessão" }] },
    }} />);
    expect(screen.getByText("concepts/b.md")).toBeTruthy();
    expect(screen.getByText("10.1000/xyz")).toBeTruthy();
  });
});
