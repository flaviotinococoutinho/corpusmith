# 13 · Plano avançado — Experiência de Memória, Curadoria e Classificação

> **Especialidade deste documento:** produto + epistemologia aplicada +
> experiência de usuário. Não é um ADR (nenhuma decisão foi *tomada*
> ainda) nem código — é um **plano priorizado** de para onde levar a
> experiência, consistente com a entrega atual (v1.7). Cada receita é
> mapeada a um mecanismo REAL do produto e a um contrato de
> `epistemics.toml`. Governança das decisões: quando uma fase começar,
> vira ADR.

Fontes internas: [`01`](01-conceitos.md) · [`03`](03-teoria.md) ·
[`07`](07-sinergias.md) · [`09`](09-backlog.md) · [`10`](10-engenharia-ai-friendly.md)
· [`11`](11-epistemic-contracts.md). Inspiração externa (conceitos, NÃO
código): langextract, SymRAG, all-agentic-architectures, science-skills,
crewAI, n8n, flatbuffers, StringZilla, opendataloader/chandra, SocratiCode.

---

## 0. Tese central

O brain-compiler já **calcula muito mais sinal do que mostra**. O backend
produz, hoje, com teste: valor de informação (VoI = lacuna × conectividade),
pesos Hedge por stream, entropia de retrieval, recuperabilidade ACT-R
(BLA), calibração Brier, intermediação de Brandes, lacunas estruturais,
envelopes de generalização e 13 contratos epistemológicos. A **experiência**
expõe uma fração disso como apoio à decisão, em 12 abas planas com jargão
(UX-1/UX-2 abertos).

O norte deste plano é **um só**: *tornar visível e acionável o sinal que o
sistema já computa — sem nunca decidir pelo humano.* Toda receita abaixo
fecha o laço entre um cálculo que já existe e uma decisão de memória,
curadoria ou classificação que hoje é cega. Isso respeita o invariante mais
profundo do produto (o LLM/heurística é cercado; o humano decide) e ataca
os itens de UX abertos com fundamento, não com maquiagem.

---

## 1. Auditoria de consistência conceitual (estado v1.7)

### 1.1 O que está sólido (não mexer)
- **Separação de eixos** confiança epistemológica × acessibilidade
  cognitiva × prioridade — três vocabulários distintos, byte-identidade
  do canônico testada. É a maior força conceitual; qualquer receita
  DEVE preservá-la.
- **Sanduíche determinístico** cercando o LLM; precisão>recall na
  escrita; invalidar-nunca-apagar; canônico≠projeção.
- **Garantias relativas** (nenhuma universal) formalizadas em
  `epistemics.toml` com lint — o produto já sabe declarar o que NÃO
  garante. Toda receita nova entra com contrato.

### 1.2 Tensões e lacunas reais (o que o plano ataca)
| # | Achado | Evidência | Natureza |
|---|---|---|---|
| C-1 | **Sinal computado, decisão cega**: VoI, Hedge, BLA, Brier, entropia existem mas quase não aparecem no momento da decisão de curadoria | `cognitive/scoring.py` (VoI), `record_outcome.py` (Hedge), `kernel/activation.py` (BLA) vs. `CurationPanel.tsx` | lacuna de experiência |
| C-2 | **12 superfícies concorrentes de "o que fazer agora"** | `App.tsx:16-28` (12 abas); UX-1/UX-2 abertos (`09` §backlog) | atrito |
| C-3 | **Proveniência grossa**: citação é por página `[n]`, não por *span* — o usuário não vê QUAL trecho fundamenta a afirmação | `ask_memory.py` `_invalid_citations` valida `[n]`→página; nenhum offset de caractere | lacuna de confiança |
| C-4 | **Classificação em silos**: tipo OKF, tags, comunidades, entidades, confiança, privacidade, camadas T1-T3 existem mas não há uma superfície FACETADA que os componha | `06` §tipos/§tabelas; sem view facetada | lacuna de navegação |
| C-5 | **Retrieval de custo fixo**: toda pergunta paga os mesmos streams; o produto tem a teoria (economia de atenção, governor) mas não ROTEIA por custo/complexidade | `ask_memory.py` roda streams incondicionalmente (exceto `--deep`) | oportunidade econômica |
| C-6 | **Pipelines sem inspeção**: `pipeline_runs` guarda estágios/spans mas o painel Processos não deixa inspecionar entrada/saída por estágio nem re-executar | `06` §pipeline_runs; `ProcessesPanel.tsx` | curadoria operacional cega |
| C-7 | **Superfícies anunciadas sem UI**: analogias e CurationProjection (UX-5) | `09` §UX-5 | dívida de anúncio |

Nenhuma tensão é uma inconsistência *lógica* — são lacunas entre a
riqueza do núcleo e a superfície. É exatamente onde receita externa bem
escolhida rende mais.

---

## 2. Receitas mineradas (conceito externo → mecanismo interno)

> Critério: extrair **conceito, estrutura de dados, experiência ou
> disciplina** — nunca código. Cada receita respeita local-first,
> canônico≠projeção, LLM cercado, garantia relativa, gate humano.

### R1 · Grounding por span (de **langextract**)
- **O que é lá:** cada extração carrega um `char_interval` (offset exato
  na fonte); extração não localizável no texto ⇒ `char_interval=None` e é
  filtrada. Visualização destaca o span na origem.
- **Mapeia em:** o sanduíche determinístico (`normalize`/`page_entities`)
  e as citações do `/ask`.
- **Receita:** ao anotar entidades (`index_entities`) e ao validar
  citações, carregar o **offset do span** no canônico. A citação `[n]`
  passa a apontar não só a página mas o **trecho**; o chat destaca o span;
  entidade sem span localizável vira `ambiguous` (já é o vocabulário!).
  É o "grounding" que torna a proveniência *verificável a olho*.
- **Custo:** P1 · 3 pontos (coluna `span_start/span_end` em
  `page_entities`/citações — schema index.db aditivo; API; highlight no
  `ChatEvidencePanel`).
- **Risco:** offsets referenciam o canônico — se o bundle mudar, o span
  precisa ser reproyetado; mitiga-se ancorando no `bundle_head` do índice
  (INV-002 já garante convergência). **Rejeitar:** o few-shot do
  langextract via LLM como fonte de schema — o produto usa gazetteer
  determinístico; grounding sim, extração-por-LLM-como-autoridade não.

### R2 · Roteamento econômico por complexidade (de **SymRAG** + Adaptive RAG do catálogo)
- **O que é lá:** um `SystemControlManager` roteia entre caminho
  simbólico/neural por **complexidade da consulta** e estado de recurso;
  limiares dinâmicos; caminhos caros só quando a consulta justifica.
- **Mapeia em:** os 6 streams do `/ask` + o Governor + a economia de
  atenção (VoI). É a versão *retrieval* da escada determinística da
  reconciliação.
- **Receita:** classificar a consulta por complexidade (nº de entidades,
  presença de marcador temporal/global, comprimento) — já temos os sinais
  em `analyze()` — e **rotear**: consulta simples paga fts+entity;
  consulta multi-hop/temporal ativa graph-PPR+descend; `dense` só sob
  orçamento. O custo estimado aparece ao usuário (economia visível). Entra
  como **contrato novo** `retrieval_cost_routing` (heurística, garantia
  relativa ao golden set; fallback = rodar todos os streams).
- **Custo:** P1 · 3 pontos (roteador puro em `retrieval/`, instrumentado
  pelos perfis de estágio que já existem — ADR-39; contrato).
- **Risco:** rotear errado degrada recall. Mitiga: fallback "rodar tudo"
  quando a incerteza da classificação for alta; medir no golden
  (Recall@K não pode cair). **Rejeitar:** monitoramento de CPU/GPU a
  100ms do SymRAG — peso operacional que o local-first não paga; roteia-se
  por complexidade da consulta e orçamento do dia, não por telemetria de
  hardware em tempo real.

### R3 · Fila única de próxima ação, ranqueada por valor×custo (de **n8n** + VoI interno + UX-1)
- **O que é lá (n8n):** uma lista de execuções onde cada item é
  inspecionável (entrada/saída por nó), re-executável, com estado
  explícito.
- **Mapeia em:** UX-1 (as "8 superfícies concorrentes"), a economia de
  atenção (`PlanAttention`, já calcula VoI e monta mochila gulosa) e
  `pipeline_runs`.
- **Receita:** **UMA** fila "Próxima ação" que unifica: lacunas do Harness,
  inbox a consolidar, revisões espaçadas vencidas, pontes frágeis do grafo,
  contradições candidatas, memórias frias reidratáveis. Cada item mostra
  **origem, valor (VoI) e custo (min)** — exatamente o que `PlanAttention`
  já produz — e leva à ação com um clique. É o "inbox de curadoria" que
  fecha C-1 e C-2 de uma vez.
- **Custo:** P1 · 3 pontos (agrega fontes que já existem numa view; painel
  novo OU seção-topo do Dashboard; nada de novo cálculo).
- **Risco:** virar mais uma aba concorrente. Mitiga: ela SUBSTITUI as
  chamadas-para-ação espalhadas (é requisito do UX-1), não soma.

### R4 · Classificação facetada + memória por entidade (de **crewAI** entity memory + facets do catálogo)
- **O que é lá:** memória por entidade e por papel como *views* distintas
  sobre o mesmo acervo; classes de extração com atributos.
- **Mapeia em:** os eixos de classificação já existentes (tipo, tags,
  comunidade Leiden, entidade canônica, confiança, privacidade, T1-T3,
  validade temporal, acessibilidade cognitiva) — hoje em silos (C-4).
- **Receita:** um **modelo de facetas** que COMPÕE os eixos numa só
  superfície de navegação/triagem (Wiki/Explorer), e uma **view por
  entidade**: "tudo que a base sabe sobre X" — páginas, fatos do
  reference.db, confiança, staleness, comunidade — com as arestas do grafo.
  É experiência de *classificação* e de *memória associativa* ao mesmo
  tempo, reusando entidades+grafo que já alimentam o stream `graph`.
- **Custo:** P2 · 4 pontos (view facetada é consulta sobre índice
  existente; entity-view reusa `page_entities`+`graph_edges`; painel).
- **Risco:** criar um 8º vocabulário de classificação. Mitiga: facetas são
  **projeção** dos eixos existentes, nunca um rótulo novo canônico
  (canônico≠projeção). **Rejeitar:** memória "por papel/agente" do crewAI
  como estado canônico — o produto é single-writer humano; papel de agente
  é caso de uso futuro (porta MCP, ADR-15), não classificação do acervo.

### R5 · Catálogo de receitas de composição (de **all-agentic-architectures**)
- **O que é lá:** 35 padrões agênticos num "textbook executável", API
  uniforme `.run(task)`, e — nota notável — a disciplina central é
  *"LLMs commit to categorical features and Python composes the deciding
  signal"*, **idêntica** ao princípio do brain-compiler ("sinais para a
  heurística; significado para o Python").
- **Mapeia em:** pipelines v0.17 (`pipelines.spec`, builtin) + docs/07
  (sinergias). Vários padrões do catálogo **já existem** aqui sob outro
  nome: Corrective RAG = abstenção+base fria; Adaptive RAG = R2; Reflexion
  = reflect/metacog; Constitutional AI = regras do Harness; Dry-Run =
  gate humano; GraphRAG = comunidades Leiden + stream graph; Agent
  Workflow Memory = os próprios pipelines.
- **Receita:** documentar as sinergias como um **catálogo tipado de
  receitas** (padrão → mecanismo do produto → pipeline builtin), e
  adicionar 2-3 pipelines builtin que faltam como composição (ex.:
  "verificação de crença" = reconcile→contradiction_candidate→gate;
  "triagem socrática" ver R7). É doc + specs declarativos — custo baixo,
  valor conceitual alto (torna o produto legível como catálogo).
- **Custo:** P2 · 2 pontos (doc + specs builtin idempotentes; zero motor
  novo). **Rejeitar:** importar padrões que violam invariantes (Cellular
  Automata, RLHF self-improvement como autoridade) — entram na matriz de
  não-adoção com razão.

### R6 · Skill como unidade operacional de conhecimento (de **science-skills** / SKILL.md)
- **O que é lá:** `SKILL.md` = frontmatter YAML + instruções markdown +
  `scripts/` + `references/`; skills descobríveis e invocáveis por agente,
  versionadas, com camada de override.
- **Mapeia em:** os tipos OKF `skill`/`runbook` (que já existem!) + o
  context pack (ADR-39 §18.4, planejado) + pipelines.
- **Receita:** dar ao tipo `skill` um **contrato de frontmatter**
  (inputs, outputs, when_to_use, related_pipeline) que o Harness valida —
  transformando uma página `skill` de texto passivo em **unidade
  operacional descobrível**: o daemon lista skills aplicáveis a um
  objetivo, e uma skill pode *apontar* um pipeline executável. Fecha o
  laço conhecimento↔operação sem que o Rust/agente decida nada (a
  execução continua gateada). Casa com a porta MCP (ADR-15).
- **Custo:** P2 · 3 pontos (regra de política nova `policy.skill_contract`
  no Harness; campo no frontmatter; listagem na API). **Rejeitar:**
  instalação de skills via npx/plugin externo do science-skills — o
  produto é local-first e curado no bundle; skill é PÁGINA versionada em
  Git, não pacote externo.

### R7 · Experiência socrática na prática cognitiva (de **SocratiCode** + Reflexion)
- **O que é lá:** ensinar por PERGUNTAS antes de respostas (método
  socrático); Reflexion guarda reflexões verbais em memória episódica.
- **Mapeia em:** a prática cognitiva (`CognitiveSession` modos
  understand/apply/retain/critique/transfer), as **pergunta-ponte** que as
  lacunas estruturais já geram (`structural_gaps` → question) e a agenda
  espaçada.
- **Receita:** um **modo de sessão socrático** que, em vez de entregar a
  resposta, apresenta a **pergunta-ponte** da lacuna estrutural (que o
  sistema já computa!) e registra a tentativa ANTES de conferir — é
  retrieval practice puro, e usa sinal que hoje só aparece no grafo. As
  reflexões episódicas já existem (Efklides, v0.20).
- **Custo:** P2 · 3 pontos (modo novo reusa lacunas+sessão+prática;
  superfície no painel Cognição/Foco). **Rejeitar:** gerar perguntas por
  LLM sem lastro — as perguntas vêm das lacunas DETERMINÍSTICAS do grafo
  (senão vira alucinação socrática).

### R8 · Ingestão estruturada com proveniência de região (de **opendataloader-pdf** / **chandra**)
- **O que é lá:** parser de PDF → árvore estruturada JSON (tabelas, ordem
  de leitura), com foco em sanitização/segurança.
- **Mapeia em:** `ingestion/extract.py` (já isolado em subprocesso para os
  parsers AGPL) + o sanduíche + R1 (grounding).
- **Receita:** fazer a extração de PDF/EPUB devolver uma **árvore
  estruturada com proveniência por região** (página/bloco), que vira a
  proveniência de span do R1 na compilação — e reforçar a **sanitização
  anti-injection** do conteúdo ingerido (o AGENTS.md §7 já trata `raw/`
  como não-confiável; aqui vira barreira no parser). Casa langextract
  (span) + opendataloader (região) num só fluxo.
- **Custo:** P3 · 4 pontos (depende do extra `[parsers]`; Fase 3 do
  compute plane). **Rejeitar:** trocar o modelo OCR do produto por chandra
  (dependência pesada de modelo; local-first não paga sem gatilho medido).

### R9 · Disciplina de evolução de schema (de **flatbuffers**)
- **O que é lá:** campos com id estável, deprecação em vez de remoção,
  defaults — evolução de schema sem quebrar leitores antigos, zero-copy.
- **Mapeia em:** o protocolo v1 do worker nativo (ADR-39 Fase 4), os
  envelopes de generalização e `pipelines.spec` (JSON em coluna, §5.5 do
  `10`).
- **Receita:** adotar a **disciplina** (nunca renomear/remover campo;
  deprecar com default; `payload_schema_version` já existe nos envelopes)
  como regra escrita no protocolo do worker e nos JSON-em-coluna — não a
  biblioteca. Endurece a Fase 4 antes de ela existir.
- **Custo:** P3 · 1 ponto (regra de doc + teste de compat). **Rejeitar:**
  adotar FlatBuffers como serialização (Arrow/JSON já cobrem; §7 do `10` já
  decidiu o layout por tamanho de lote).

### R10 · Sketch/algoritmo byte-level para Fase 3 (de **StringZilla**)
- **O que é lá:** operações SIMD sobre strings sem alocação (busca,
  hashing, hamming).
- **Mapeia em:** `braincore-text` (Fase 3, planejada) e `braincore-sketch`.
- **Receita:** SE a Fase 3 for medida como hotspot (ADR-39 exige
  benchmark antes de migrar), a **abordagem** byte-level/alloc-free é a
  referência de design — sem adicionar a dependência (o produto tem sua
  própria `braincore-sketch`). Puramente uma nota de arquitetura para
  quando/se a Fase 3 entrar.
- **Custo:** P3 · 0 pontos agora (referência). **Rejeitar:** a dependência
  em si (viola o orçamento; a lógica é própria).

### Notas
- **hermes-agent**: não acessível publicamente na verificação; provável
  fork pessoal. Dobrado na porta MCP/agent-loop (ADR-15) — sem receita
  inventada sobre repo não lido.
- **n8n** (R3) e **crewAI** (R4) entram pelo CONCEITO (log inspecionável;
  memória-como-view), não pela stack.

---

## 3. Ranking de receitas (valor × custo × consistência)

| Rank | Receita | Grupo | Valor p/ usuário | Custo | Fecha |
|---|---|---|---|:--:|---|
| 1 | **R3** Fila única de próxima ação (VoI visível) | Experiência | altíssimo | P1·3 | C-1, C-2, UX-1 |
| 2 | **R1** Grounding por span | Memória | alto (confiança) | P1·3 | C-3 |
| 3 | **R2** Roteamento econômico | Memória/Infra | alto (custo/latência) | P1·3 | C-5 |
| 4 | **R4** Classificação facetada + entidade | Classificação | alto | P2·4 | C-4 |
| 5 | **R6** Skill operacional | Curadoria | médio-alto | P2·3 | laço conhecimento↔operação |
| 6 | **R5** Catálogo de receitas | Curadoria/doc | médio (legibilidade) | P2·2 | C-6 (doc), coesão |
| 7 | **R7** Modo socrático | Cognição | médio | P2·3 | UX-5 (prática) |
| 8 | **R9** Disciplina de schema | Infra | médio (robustez) | P3·1 | endurece Fase 4 |
| 9 | **R8** Ingestão estruturada | Memória | médio | P3·4 | depende Fase 3 |
| 10 | **R10** Byte-level Fase 3 | Infra | baixo agora | P3·0 | referência |

---

## 4. Plano em 4 fases (incremental, cada fase termina verde)

Compatível com a entrega atual: nada de big-bang; cada fase é um PR com
gate verde (pytest+tsc+compose+epistemics lint), contrato novo em
`epistemics.toml` quando aplicável, e ADR ao iniciar.

### Fase A — **Sinal visível** (o maior ganho de UX pelo menor custo)
Receitas **R3 + R1**. Entrega: (1) a **fila única "Próxima ação"**
ranqueada por VoI/custo, substituindo as chamadas-para-ação espalhadas
(UX-1); (2) **grounding por span** na evidência do `/ask` (citação aponta
o trecho; highlight no chat). Sem cálculo novo — expõe o que já existe.
- Backend: view agregadora (sem tabela nova); colunas de span aditivas no
  index.db (reconstruível); API read-only via facade.
- Contrato: nenhum novo (R3 usa VoI já contratado); R1 documenta
  proveniência de span como reforço do sanduíche.
- DoD: Recall@K do golden inalterado; byte-identidade intacta; painel
  passa no tsc; a fila mostra origem+valor+custo por item.

### Fase B — **Economia de retrieval** (R2)
Roteador de custo por complexidade da consulta, com custo estimado
visível e fallback "rodar tudo". Contrato novo `retrieval_cost_routing`
(heurística, garantia relativa ao golden; failure modes declarados).
- DoD: Recall@K não cai no golden; latência p50 do `/ask` simples melhora
  (medida pelo `bench ask` do ADR-39); contrato passa no lint.

### Fase C — **Classificação e memória associativa** (R4 + R6)
Modelo de facetas (projeção dos eixos existentes) + view por entidade +
contrato de frontmatter para `skill` (`policy.skill_contract` no Harness).
- DoD: facetas são projeção (nenhum rótulo canônico novo); entity-view
  reusa índice; skill inválida gera finding; suíte verde.

### Fase D — **Catálogo, socrático e endurecimento** (R5 + R7 + R9)
Catálogo tipado de receitas (doc `07` + 2-3 pipelines builtin), modo de
sessão socrático baseado nas pergunta-ponte determinísticas, e a
disciplina de evolução de schema escrita no protocolo do worker.
- DoD: pipelines builtin idempotentes; modo socrático usa lacunas reais
  (sem LLM como fonte de pergunta); teste de compat de schema.

**R8/R10** ficam para quando a Fase 3 do compute plane (ingestão nativa)
for medida como hotspot — porta declarada, sem antecipar.

---

## 5. Invariantes que o plano protege (checagem)

Toda receita foi filtrada por: local-first (nada exige rede) · canônico ≠
projeção (facetas, spans, fila são PROJEÇÕES reconstruíveis) · LLM/heurística
cercada (roteamento e perguntas vêm de sinal determinístico; decisão de
curadoria continua humana) · garantia relativa (R2 entra com contrato, não
promete recall universal) · invalidar-nunca-apagar (nenhuma receita apaga)
· gate humano para efeito cognitivo (fila e socrático PROPÕEM, não aplicam).

O que **não** fazer, com razão (matriz de não-adoção): extração-por-LLM
como autoridade (langextract) · telemetria de hardware a 100ms (SymRAG) ·
memória canônica por papel de agente (crewAI) · skills como pacote externo
(science-skills) · troca do OCR por modelo pesado (chandra) · FlatBuffers/
StringZilla como dependências · padrões agênticos que violam invariantes
(Cellular Automata, self-improvement como autoridade).

---

## 6. Próximo passo

Recomendação: **começar pela Fase A** — é o maior ganho de experiência
(resolve UX-1 e a proveniência) pelo menor custo e risco, e não adiciona
nenhum cálculo novo (só expõe o que o núcleo já computa). Ao iniciar,
vira ADR-40 e um PR com gate verde.
