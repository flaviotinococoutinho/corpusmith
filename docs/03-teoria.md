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

### 3.3 Heat por Base-Level Activation (ACT-R)
**Anderson & Schooler, "Reflections of the Environment in Memory"
(Psychological Science, 1991)**: a probabilidade de precisar de uma
memória segue lei de potência do histórico de uso. **Anderson et al.,
"An Integrated Theory of the Mind" (Psychological Review, 2004)**
formalizam como Base-Level Activation: `B = ln(Σ tⱼ^−d)`. Guardar todos
os timestamps é caro; usamos a aproximação padrão de aprendizado
otimizado (`kernel/activation.py`):

```
B ≈ ln( n / (1 − d) ) − d·ln(L)        n = usos · L = vida (dias) · d = 0.5
heat = 0.6·σ(B) + 0.2·min(1, cites/5) + 0.2·outcome        ∈ [0, 1]
```

Diferente do decaimento exponencial sobre o ÚLTIMO acesso (v0.8), o BLA
captura o **efeito de espaçamento**: 10 usos ao longo de 3 meses valem
mais que 10 usos num único dia antigo. `first_seen` em `page_heat` dá o
L; σ (logística) mapeia a escala log para score comparável. Saída:
candidatos a promover/arquivar — decisão sempre humana.

### 3.7 Consolidação por recorrência (CLS)
**McClelland, McNaughton & O'Reilly, "Why there are complementary
learning systems in the hippocampus and neocortex" (Psychological
Review, 1995)**: codificação episódica rápida e barata + consolidação
neocortical lenta que extrai estrutura compartilhada. Transposição
(`usecases/consolidate_inbox.py`): `raw/` é o hipocampo (captura sem
custo de modelo); a consolidação SÓ dispara quando há recorrência — e a
recorrência é detectada **deterministicamente** (identificador forte
compartilhado OU ≥2 entidades canônicas em comum, via o anexo do
normalize — sem embeddings). Uma chamada de LLM por CLUSTER, não por
nota; nada é descartado (raw/ e Git são o backstop — rejeitamos o
"esquecimento como default" da proposta original por conflitar com
"invalidar, nunca apagar").

### 3.8 Propagação de staleness (TMS)
**Doyle, "A Truth Maintenance System" (Artificial Intelligence, 1979)**:
crenças carregam justificativas; invalidar uma premissa marca os
dependentes para reexame. Transposição mínima: os in-links do grafo SÃO
as justificativas registradas — `mark_stale`/SUPERSEDE devolvem/notificam
os `dependents` (páginas que citam a depreciada) para revisão humana.
Propagação de suspeita, nunca invalidação em cascata automática.

### 3.9b Limiar de recuperação e esquecimento validado (ACT-R + MDL)
A equação de recuperação do ACT-R (**Anderson et al. 2004**) fecha o
ciclo do BLA (§3.3): `P(recall) = 1/(1+e^((τ−B)/s))`. Em vez de um corte
arbitrário de score, o critério de DEMOÇÃO para a base fria é o próprio
modelo cognitivo prever que a memória não seria recuperada
(`kernel/activation.py:retrieval_probability`; τ=0, s=0.4, corte 0.05).
A compactação segue o **Minimum Description Length (Rissanen, "Modeling
by Shortest Data Description", Automatica 1978)**: o digest indexável é
o modelo; o corpo zlib é o resíduo dado o modelo — a informação
recuperável ao custo mínimo de descrição. O desenho da hierarquia ecoa
os níveis de um LSM-tree e a hipótese geracional de GC: o que esfria
desce de camada barato; o que é referenciado sobe de volta.

### 3.9 Contradição e entrincheiramento (AGM)
**Alchourrón, Gärdenfors & Makinson, "On the Logic of Theory Change"
(Journal of Symbolic Logic, 1985)**: revisão racional de crenças exige
um ordenamento de entrincheiramento epistêmico. Sem provador de teoremas
sobre prosa, adotamos AGM como ESPECIFICAÇÃO: expansão=ADD,
contração=`stale`/`invalid_at`, revisão=SUPERSEDE — e a detecção de
contradição é determinística (`policy.contradiction_candidate`): mesmo
identificador forte em 2+ páginas sem relação de sucessão. O finding
nomeia a página mais entrincheirada (humana > máquina); a resolução é
sempre do humano ou do reconciliador. O postulado de Recovery é
substituído pelo versionamento Git (estado anterior auditável sem
comprometer a consistência atual).

### 3.4 Descida hierárquica L0→L1→L2
Directory Recursive Retrieval (OpenViking) reduzido ao essencial: L0 =
descrições de página, L1 = headings, L2 = chunks. FTS em L0 escolhe
diretórios; FTS em L1 dentro deles escolhe páginas; `trajectory` é
devolvida e exibida (transparência do caminho de memória). Determinístico
e barato — e a razão de existir do filtro de stopwords: OR sobre
"do/com/qual" em L0 casava tudo e matava a abstenção.

### 3.4b Personalized PageRank multi-hop (HippoRAG)
**Gutiérrez et al., "HippoRAG: Neurobiologically Inspired Long-Term
Memory for Large Language Models" (NeurIPS 2024, arXiv:2405.14831)**:
retrieval associativo via PPR semeado pelas entidades da pergunta sobre
o grafo de conhecimento — o análogo da separação de padrões hipocampal.
Transposição (`kernel/graphwalk.py` + stream `graph` no ask): seeds =
páginas casadas por entidade (pesos surprisal com suavização add-one);
arestas ponderadas pela escala de confiança; damping 0.5 (massa presa
aos seeds — associação, não deriva). Alcança fatos a um ou mais saltos
de link que NENHUM termo da pergunta tocaria; o Hedge treina o crédito
do stream como o de qualquer outro.

### 3.4c SimHash como assinatura de recorrência (Charikar)
**Charikar, "Similarity Estimation Techniques from Rounding Algorithms"
(STOC 2002)**: a distância de Hamming entre sketches de 64 bits aproxima
a dissimilaridade dos conjuntos de shingles. `kernel/sketch.py` (blake2b,
determinístico entre processos) dá à consolidação um sinal de
NEAR-DUPLICATA em O(1) por par: quase-cópias convergem mesmo sem nenhuma
entidade curada em comum (hamming ≤ 8).

**Bandas LSH exatas (v0.16)** — a versão de Indyk-Motwani do LSH usa
bandas probabilísticas; aqui o mesmo truque vira GARANTIA pela casa de
pombos: fatiando os 64 bits em 9 bandas, um par com hamming ≤ 8 tem no
máximo 8 bandas "sujas" — logo ao menos uma banda idêntica, e indexar
por (índice, valor) de banda recupera todo par candidato sem tocar os
n² (`kernel/sketch.py::bands`, `ConsolidateInbox._candidate_pairs`).
Junto com o índice invertido por id forte/entidade, a geração de
candidatos cobre EXATAMENTE o predicado `converges_with`: zero falso
negativo, falsos positivos re-verificados (propriedade testada com
pares aleatórios em `test_v16.py`). A troca pares↔índice acontece em
`consolidate.pairwise_max` (seleção adaptativa de algoritmo).

### 3.4d Sugestão de links (A-mem, determinístico)
**Xu et al., "A-mem: Agentic Memory for LLM Agents" (arXiv:2502.12110)**:
memória nova gera links Zettelkasten para vizinhas e evolui o contexto
delas. Versão sem LLM (`retrieval/related.py`): vizinhas por
sobreposição de entidades ponderada por surprisal, EXCLUINDO as já
linkadas — o que sobra é o link que falta; o Explorer exibe
"Relacionadas (linke?)" com as entidades compartilhadas.

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

## 6. Camada cognitiva (v0.18) — o convívio formalizado

**Carga cognitiva — Sweller, "Cognitive load during problem solving"
(Cognitive Science, 1988)**: capacidade de processamento é limitada e
varia. Transposição (`usecases/cognitive_state.py`): estado DECLARADO
(carga/foco/energia 1..5 + minutos, TTL 8h → neutro) e
`delivery_budget` determinístico — carga alta encolhe evidências,
tokens e impõe concisão. Nada é inferido de comportamento: sinal
humano é de primeira classe e dado sensível fica sob consentimento.

**Calibração — Brier (Monthly Weather Review, 1950); Lichtenstein,
Fischhoff & Phillips (1982)**: o previsor é a própria memória —
p = 1−uncertainty da fusão, o = desfecho `useful`. `kernel/calibration.py`
dá Brier, overconfidence (confiança média − acerto) e a curva de
confiabilidade por bins; o padrão humano de excesso de confiança vira
observação metacognitiva com números na frase, nunca rótulo.

**Resposta adaptativa — Hedge (Freund & Schapire 1997) + exploração à
EXP3 (Auer et al. 2002)**: estratégias de explicação (direta, analogia-
primeiro, exemplo-primeiro, teoria-primeiro, decomposição) são experts;
o desfecho treina `strategy_weights` (terceiro laço do mesmo kernel);
a seleção é roleta ∝ peso — estratégia boa aparece mais, nenhuma é
silenciada. `profile.preferred_strategy` ≠ "auto" desliga a roleta:
declarado vence observado (FR-14.3).

**Dificuldade desejável — Bjork (1994); Roediger & Karpicke, "The power
of testing memory" (2006)**: revisar rende mais no esforço-com-sucesso.
`kernel/attention.py::review_gain` = 4p(1−p) sobre o P(recall) ACT-R —
a variância de Bernoulli: máxima incerteza, máxima informação por
minuto, pico em p=0.5; trivial (p≈1) e perdido (p≈0) rendem pouco.

**Economia de atenção — mochila gulosa por densidade (Dantzig 1957)**:
`fill_budget` ordena candidatos (revisões, perguntas abertas,
contestadas, stale, inbox) por valor/custo e enche o orçamento
declarado; sob carga alta só blocos pequenos (CLT × knapsack). Cada
item carrega `reason` — recomendação sem porquê não sobe à interface.

**Metacognição — Flavell (1979); Nelson & Narens (1990)**: o par
monitoramento→controle vira `ObserveMetacognition` (mineração SQL
determinística com suporte mínimo e dedupe; correlação fraseada como
correlação) → gate humano `ReviewObservation` — aceitar aplica a
sugestão PELA LINHAGEM de configuração (TuneConfig source=metacog):
o observado só vira declarado com consentimento, auditável e
reversível. Rejeitado de propósito: "learning styles" (VARK) — sem
suporte empírico (Pashler et al., "Learning styles: concepts and
evidence", 2008); aqui preferência é peso treinado por desfecho.
