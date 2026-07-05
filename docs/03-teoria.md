# 03 · Fundamentos teóricos

> POR QUE as escolhas funcionam. Cada fundamento cita o paper de origem,
> a implementação (`kernel/` — stdlib pura, protegida por teste de
> arquitetura) e o ponto exato de uso. A seção final explica a disciplina
> de transposição: como um resultado teórico vira mecanismo aqui.

## 1. Teoria da informação (`kernel/information.py`)

### 1.1 Normalized Compression Distance
**Cilibrasi & Vitányi, "Clustering by Compression", IEEE Transactions on
Information Theory, 2005.** A distância de informação de Kolmogorov é
incomputável; a NCD a aproxima com um compressor real:

```
NCD(x,y) = (C(xy) − min(C(x),C(y))) / max(C(x),C(y))
```

Dois textos sobre o mesmo objeto do mundo se explicam mutuamente ⇒
comprimem juntos ⇒ NCD baixa. **Uso**: terceiro sinal da escada de
reconciliação (`ReconcileCandidate._compression_affinity`):

```
score = 0.4·rank(FTS título) + 0.3·Jaccard(entidades) + 0.3·(1 − NCD)
```

Por que importa: é determinístico, custa um `zlib.compress`, não depende
de modelo nem embedding, e é imune a paráfrase superficial (que derruba
Jaccard de termos mas não a compressibilidade mútua).

### 1.2 Entropia de Shannon como incerteza de retrieval
**Shannon, "A Mathematical Theory of Communication", 1948**; parentesco
moderno: **Kuhn, Gal & Farquhar, "Semantic Uncertainty" (ICLR 2023)** —
entropia sobre distribuições de saída como sinal de confiabilidade.
**Uso**: entropia normalizada [0,1] da distribuição de scores RRF
fundidos (`EvidenceStreams.fuse` → campo `uncertainty` em toda resposta
do `/ask`). Interpretação: massa concentrada num item = o sistema sabe
onde está a resposta; massa espalhada = está chutando. O Cockpit exibe o
chip "~ incerta" acima de 0.85. Complementa (não substitui) a abstenção:
o sistema pode responder E confessar dúvida.

### 1.3 Surprisal (conteúdo de informação)
**−log₂ p(e)** — a formulação original do que o IR conhece como IDF.
**Uso**: o stream de entidades do `/ask` pondera cada entidade pelo seu
conteúdo de informação (`AskMemory._entity_stream`): uma entidade
presente em 1 de 1000 páginas informa ~10 bits; presente em todas,
0 bits. Evita que `JSON` (onipresente) domine `leidenalg` (raríssima) na
recuperação por entidade.

### 1.4 Hedge / multiplicative weights
**Freund & Schapire, "A Decision-Theoretic Generalization of On-Line
Learning and an Application to Boosting", JCSS 1997** (algoritmo Hedge;
família dos multiplicative weights, com arrependimento sublinear
garantido contra o melhor expert fixo). **Uso**: cada stream de retrieval
(`global`, `fts`, `dense`, `entity`, `descend`) é um *expert*; o desfecho
do usuário é a perda (useful = −1, dead_end/corrected = +1);
`w ← w·exp(−η·loss)` com η=0.25 e **clamp [0.5, 2.0]** — o clamp preserva
exploração (nenhum stream é silenciado para sempre; o mundo muda).
Cadeia completa: `ask_provenance` registra página→stream na consulta;
`RecordOutcome._update_stream_credit` aplica o Hedge; `stream_weights`
multiplica a contribuição RRF na próxima fusão.

## 2. Topologia (`kernel/topology.py`)

### 2.1 Persistência 0-dimensional sobre filtração de pesos
**Edelsbrunner, Letscher & Zomorodian, "Topological Persistence and
Simplification", Discrete & Computational Geometry, 2002.** Varremos as
arestas do grafo de conhecimento do peso mais ALTO ao mais BAIXO
(filtração descendente); cada aresta que UNE dois componentes é um evento
de morte em H₀. A leitura curatorial: **arestas que unem componentes
GRANDES a pesos BAIXOS são pontes frágeis** — dois blocos substanciais de
conhecimento que só se falam por um fio fraco.

Implementação: union-find com path compression + tamanhos
(`component_persistence`); `fragile_bridges` filtra fusões com
`small_side ≥ 2` e ordena por peso ascendente. Persistido em
`graph_bridges` pelo `DetectCommunities`; exposto no painel Qualidade
("🌉 linke mais estes dois temas"). Custo: O(E log E) — nada de
bibliotecas de TDA.

### 2.2 Percolação prática no grafo
Duas defesas contra a degeneração topológica clássica de grafos de
co-ocorrência (um gigante conectado sem estrutura):
- **teto anti-hub na origem**: co-menção só gera arestas para entidades
  presentes em 2..30 páginas;
- **exclusão de super-hubs** (p99 de grau, mínimo 8) antes do
  particionamento, com atribuição pós-hoc por maioria de vizinhança
  (padrão graphify `--exclude-hubs`).

## 3. Heurísticas de coordenação

### 3.1 Reciprocal Rank Fusion
**Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion outperforms
Condorcet and individual rank learning methods", SIGIR 2009.**
`score(d) = Σ_streams w_s/(k + rank_s(d))` com k=60. Robusta porque só
usa POSIÇÕES (escalas de score incomensuráveis entre FTS bm25, cosseno
denso e contagem de entidades não precisam ser calibradas). Estendida
aqui com o peso de crédito `w_s` do Hedge (§1.4) e o boost de overlay
(preferred ×1.15, contested ×0.8).

### 3.2 Escada de reconciliação (mem0, formalizada)
Decisões na ordem do custo epistêmico: (1) identificador forte
compartilhado — determinístico, `confidence: extracted`; (2) similaridade
composta com cortes HI=0.82 / LO=0.55 — `inferred`; (3) árbitro LLM
LOCAL apenas na zona cinzenta [LO, HI) e atrás de flag — `ambiguous`;
(4) empate sem árbitro ⇒ ADD (precisão > recall: duplicar é reversível,
fundir errado destrói). Toda decisão é logada (`reconcile_log`).

### 3.3 Heat com decaimento exponencial
**Anderson & Schooler, "Reflections of the Environment in Memory",
Psychological Science 1991** (a curva de esquecimento racional: a
probabilidade de precisar de uma memória decai como lei de potência do
tempo desde o último uso — base do modelo ACT-R). Aproximação prática:

```
heat = 0.5·decay(last_seen)·log(1+reads) + 0.3·log(1+cites) + 0.2·outcome
decay = 2^(−dias/30)          # meia-vida de 30 dias
```

Logaritmos evitam que páginas viciadas em leitura dominem; o termo de
desfecho injeta qualidade (não só frequência). Saída: candidatos a
promover/arquivar — decisão sempre humana.

### 3.4 Descida hierárquica L0→L1→L2
Directory Recursive Retrieval (OpenViking) reduzido ao essencial: L0 =
descrições de página, L1 = headings, L2 = chunks. FTS em L0 escolhe
diretórios; FTS em L1 dentro deles escolhe páginas; `trajectory` é
devolvida e exibida (transparência do caminho de memória). Determinístico
e barato — e a razão de existir do filtro de stopwords: OR sobre
"do/com/qual" em L0 casava tudo e matava a abstenção.

### 3.5 Roteamento global × local (GraphRAG)
**Edge et al., "From Local to Global: A Graph RAG Approach to
Query-Focused Summarization", arXiv:2404.16130 (Microsoft).** Perguntas
panorâmicas ("visão geral", "principais temas") sem entidade detectada
priorizam as páginas `community_summary` (map-reduce sobre sumários);
perguntas com entidade seguem o fluxo local. Detector: regex de
marcadores + `question_entities == ∅`.

### 3.6 Eval de memória em 5 categorias
**Wu et al., "LongMemEval", arXiv:2410.10813** (e LoCoMo como
antecedente): extração, raciocínio multi-sessão, raciocínio temporal,
atualização de conhecimento e **abstenção** — a categoria que separa
sistemas honestos de chatbots confiantes. Transposição: golden set
JSONL versionado no bundle, correção por recall@5 + regex na resposta +
flag de abstenção, resultados por categoria em `eval_runs`.

## 4. A disciplina de transposição

Como um paper vira mecanismo aqui (o critério que filtrou o que entrou):

1. **Reduzir ao invariante**: da persistência topológica só precisamos de
   H₀ sobre uma filtração — union-find resolve; nada de complexos
   simpliciais.
2. **Preferir o determinístico**: NCD antes de embedding; regex+checksum
   antes de NER neural; componentes ponderados como fallback do Leiden.
3. **Custo proporcional ao valor**: tudo roda em milissegundos numa
   máquina pessoal; nenhuma dependência nova (kernel é stdlib).
4. **Falha graciosa**: sem Ollama → extrativo; sem leidenalg →
   componentes; sem embeddings → FTS só. Cada camada teórica é um BOOST,
   nunca um requisito.
5. **Fechar o laço**: teoria sem feedback é decoração — Hedge, heat e
   overlay existem porque conectam o julgamento humano de volta ao
   ranking.
