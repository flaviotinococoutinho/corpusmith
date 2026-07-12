# LLM Wiki — v1.1

Knowledge base **OKF local-first** com daemon de compilação/consulta e
**Cockpit de Memória Agêntica** no Electron.

> **Documentação conceitual completa em [`docs/`](docs/README.md)** —
> conceitos, metodologias, fundamentos teóricos (com papers), tecnologias,
> fluxos operacionais, referência dura e a matriz de sinergias. Mantida
> sincronizada com o código pela skill local `/docs-sync`
> (`.claude/skills/docs-sync/SKILL.md`).

## Arquitetura v0.9 — imutável no centro, mutável na borda

```
kernel/      ← IMUTÁVEL: stdlib pura, zero I/O (matemática e invariantes)
normalize/   ← puro: detectores, gazetteer, máscaras (dado, não infra)
cognitive/   ← puro (v0.19): Cognitive Experience Domain — gates, score,
               working set, sessão, prática espaçada (testável sem infra)
okf/ harness/← domínio canônico: modelo OKF, writer, regras (muda devagar)
usecases/    ← aplicação: 1 classe = 1 operação = 1 método público execute()
facades/     ← orquestração: Memory · Compiler · Curation · Cognition
jobs/ api/ cli · desktop/   ← adapters: a camada MAIS mutável (fila, HTTP, UI)
```

**Dois domínios, contratos explícitos (v0.19)**: a memória governa o
que é conhecido; o *Cognitive Control Plane* governa o que entra em
foco; a experiência governa como se explora; o feedback governa como a
experiência melhora. A dependência é UNIDIRECIONAL (a memória nunca
importa `cognitive/` — asserção de arquitetura) e a jornada inteira
(objetivo → projeção → sessão → tentativa → cápsula → revisão) deixa o
canônico **byte-idêntico** (invariante testado).

As regras não são convenção — são **asserções** (`tests/test_architecture.py`):

- *functional core, imperative shell*: qualquer `import sqlite3/httpx/
  subprocess/fastapi/git` em `kernel/` ou `normalize/` quebra a suíte;
- **Object Calisthenics**: todo `UseCase` tem exatamente UM método público
  (`execute`) — verificado por introspecção; coleções de primeira classe
  (`Findings`, `EvidenceStreams`) no lugar de listas nuas;
- **Template Method (GoF)**: `MachinePageUseCase.execute()` é o esqueleto
  IMUTÁVEL de toda página de máquina (sanduíche → reconcile → gate →
  writer); o teste garante que nenhuma subclasse (compile, review,
  community) consegue sobrescrevê-lo — só preencher hooks (OCP/LSP);
- **camadas**: `api/` só importa `facades/`; `usecases/` nunca importam
  `facades/`, `api/`, `jobs/` nem framework HTTP (Dependency Rule);
- **domínio sem transporte** (v0.16): `okf/ harness/ usecases/ facades/
  retrieval/ runtime/` não importam fastapi/uvicorn/sse/httpx/socket —
  falar com o mundo é privilégio de `api/`, `cli`, `daemon` e `models/`.

## Novidades da v0.16 — requisitos não funcionais como código

- **Identidade snowflake** (`kernel/identity.py`, puro): 41b tempo · 6b
  módulo · 6b algoritmo · 10b seq; `ask_id` É o trace decodificável;
  todo `page.stage` carrega `trace_id`+`span`; jobs herdam o trace do
  worker; o daemon tem identidade de instância por boot (ADR-16).
- **Configuração como linhagem** (ADR-14): ajustes passam por
  `TuneConfig` — validação de tipo/domínio, probe com reversão
  automática e geração gravada no ring `config_history` (30 entradas;
  a mais velha cai); `POST /cockpit/config/rollback` volta à anterior
  em O(1). Card "Linhagem da configuração" na Curadoria.
- **Health profunda + HATEOAS** (ADR-15): `GET /` é o mapa navegável do
  serviço; `GET /health/full` reporta instância, processo, fila, cada
  stack de dados (bytes/WAL/integridade/tabelas), barramento, recursos
  e orçamento — pulso 🩺 na StatusBar.
- **Seleção adaptativa de algoritmo** (ADR-17): consolidação troca
  pares O(n²) por índice invertido + 9 bandas LSH acima de
  `consolidate.pairwise_max` — exato por casa de pombos (hamming ≤ 8
  sempre compartilha banda), zero falso negativo.
- **Pipelines configuráveis** (v0.17, ADR-18): orquestração como DADO —
  specs declarativos em `pipelines` (runtime.db) compõem jobs
  registrados com `on_error: stop|continue` e passagem `"$prev.chave"`;
  registry injetado por DIP; trace por run + span por estágio; builtin
  `absorver-inbox`/`manutencao-semanal`/`qualidade-total`; card 🔗 no
  painel Processos. O sanduíche epistêmico segue DENTRO de cada job.

## Novidades da v0.18 — convívio cognitivo (ADR-19)

- **Estado declarado (CLT, Sweller)**: carga/foco/energia 1..5 + minutos,
  TTL 8h → neutro; carga alta encolhe a entrega do `/ask` (5 evidências,
  512 tokens, concisão). Nada é inferido de comportamento.
- **Resposta adaptativa**: estratégias de explicação são experts de um
  terceiro laço Hedge (roleta ∝ peso à EXP3); perfil DECLARADO
  (`profile.preferred_strategy`) vence o observado; chip 🧭 no chat.
- **Calibração (Brier 1950)**: confiança×desfecho ⇒ Brier,
  overconfidence e curva de confiabilidade (`kernel/calibration.py`).
- **Metacognição com gate humano (Flavell)**: mineração determinística
  (estratégia campeã, correlação carga×erro, excesso de confiança) com
  suporte mínimo e dedupe; aceitar aplica a sugestão PELA LINHAGEM de
  config (source=metacog, guard+rollback) — observado só vira declarado
  com consentimento. Job semanal `metacog`.
- **Economia de atenção**: "melhor investimento dos próximos N minutos"
  — revisões no ponto de esforço produtivo (ganho 4p(1−p) sobre o
  P(recall) ACT-R, Bjork), lacunas do Harness e inbox, na mochila
  gulosa por densidade valor/custo com `reason` por item.
- **Painel 🧭 Cognição**: declarar estado, planejar atenção, calibração,
  estratégias e observações — o cockpit da metacognição.
- Rejeitados com razão: learning styles/VARK (Pashler 2008), inferência
  emocional, incorporação automática de perfil.

## Novidades da v0.19 — Cognitive Experience Domain (ADR-20…29)

- **Separação dura**: confiança epistemológica (canônico) ≠
  acessibilidade cognitiva (escada de 7 níveis em `cognitive.db`);
  falhar numa recuperação NUNCA toca o bundle/index (testado byte a
  byte). Quatro famílias de peso — nunca um "weight" único.
- **Jornada vertical completa**: FocusGoal (profundidade em 7
  dimensões) → CognitiveProjection (hard gates nomeados → score
  decomposto+explicado → orçamento explícito; política versionada com
  snapshot) → CognitiveWorkingSet limitado → CognitiveSession (modos
  understand/apply/retain/critique/transfer) → RetrievalAttempt
  (confiança ANTES de conferir) → feedback imutável tipado →
  ReviewSchedule (spaced-v1: falha confiante volta primeiro) →
  ResumeCapsule (suspender/retomar sem resíduo de atenção).
- **API /cognitive/*** com HATEOAS por estado; eventos
  focus.*/cognitive.*/retrieval.*/review.*; trace snowflake por
  projeção e sessão (módulos focus/session).
- **Painel 🎯 Foco**: setup → mapa focal (score bar, badges
  epistemológicas SEPARADAS da prioridade, razões, 📌/🚫 com
  re-projeção imutável) → sessão de recuperação ativa → revisões.
- **Propriedades testadas**: monotonicidade do foco, orçamento nunca
  cresce ao encolher, gate de privacidade vence prioridade máxima,
  superseded nunca entra, cápsula preserva contexto, canônico intacto.
- **v0.20 (ADR-30)**: profundidade validada por dimensão (dimensão sem
  instrumento diz que não mede); experiências metacognitivas declaradas
  (11 tipos Efklides, eventos revisáveis); analogias com contrato que
  RECUSA equivalência exata (breaks obrigatórios) e promoção só por
  gate humano; CurationProjection; métricas §17 (Brier, delayed recall,
  apply/transfer, recorrência, latência de retomada); prompts de
  exercício determinísticos.

## Novidades da v1.1 — leitura de rede de texto (InfraNodus próprio, ADR-34)

- **Intermediação de Brandes** (`kernel/topology.py`, puro): o
  articulador do discurso é quem LIGA blocos, não o mais citado — o nó
  por onde passam as geodésicas. Alimenta o "tamanho por influência"
  do grafo e os representantes das lacunas.
- **Lacunas estruturais** — o diferencial: a ponte frágil aponta o fio
  FRACO que existe; a lacuna aponta o fio AUSENTE. Dois blocos grandes
  que quase nunca se conectam, medidos pelo DÉFICIT sob o modelo de
  configuração (a mesma hipótese nula da modularidade do Leiden). Cada
  lacuna vira uma **pergunta-ponte** determinística ("como A se
  relaciona com B?") capturável como `question` (fecha o laço de
  sensemaking: topologia → pergunta → nó → nova topologia).
- **Estrutura do discurso**: a base é classificada em `disperso`
  (ilhas), `focado` (1–2 temas dominam) ou `diverso` (equilibrado e
  ligado) — entropia normalizada dos tamanhos de comunidade ×
  conectividade. Tudo determinístico; LLM nenhum. `GET /cockpit/gaps`
  + seção 🔗 no painel Indicadores.

## Coordenação dos dados — fundamentos (kernel/)

- **NCD — Cilibrasi & Vitányi, *Clustering by Compression* (IEEE Trans.
  Inf. Theory, 2005)**: distância de compressão normalizada como terceiro
  sinal do reconciliador (`0.4·rank + 0.3·Jaccard + 0.3·(1−NCD)`) —
  paráfrase do mesmo objeto comprime junto; determinístico, sem modelo.
- **Entropia de Shannon (1948)** sobre a distribuição RRF fundida =
  `uncertainty` [0,1] em toda resposta do `/ask` (parente do *semantic
  entropy*, Kuhn et al. 2023): massa espalhada ⇒ "não sei onde está a
  resposta" — o Cockpit exibe o chip "~ incerta".
- **Surprisal (−log p)**: o stream de entidades pondera cada entidade pelo
  seu conteúdo de informação — entidade rara vale mais que a onipresente
  (é o IDF na formulação original).
- **Hedge — Freund & Schapire (JCSS, 1997)**: cada stream de retrieval
  (fts, dense, entity, descend, global) é um *expert*; os desfechos
  `useful/dead_end` do usuário são as perdas; `stream_weights` converge por
  *multiplicative weights* (com clamp [0.5, 2.0] para nunca silenciar um
  stream) e realimenta a fusão RRF — a proveniência página→stream fica em
  `ask_provenance`.
- **Persistência 0-dimensional — Edelsbrunner, Letscher & Zomorodian
  (Discrete & Comput. Geometry, 2002)**: filtração descendente de pesos
  sobre o grafo de conhecimento; arestas que unem blocos GRANDES a pesos
  BAIXOS são as **pontes frágeis** (`graph_bridges`) — o painel Qualidade
  mostra "estes dois temas se falam por um fio: linke mais".

## Novidades da v0.8

- **`normalize/`** (stdlib puro, zero deps novas): o sanduíche determinístico
  em volta do LLM — PRÉ anota entidades canônicas no prompt, PÓS reescreve
  grafia curada (`postgres → PostgreSQL`) SÓ em páginas de máquina, com
  regiões protegidas (fences, inline code, blockquotes, alvos de link,
  `# Citations`) e idempotência garantida por teste. Datas/quantidades nunca
  são reescritas: viram anexo (`entities:` + `page_entities` no index.db).
- **Checksums anti-alucinação**: CPF/CNPJ (numérico e alfanumérico 2026),
  ISBN-10/13, ISSN, ORCID, IBAN — identificador inválido em página de
  máquina é `policy.identifier_invalid` (error). PII com checksum válido
  força `privacy: local_only` (`policy.pii_requires_local`).
- **Controle de autoridade**: gazetteer curado vive no bundle como páginas
  `type: authority_record` (aliases + QID) — corrigir grafia é um commit.
- **Reconciliação** ADD/UPDATE/SUPERSEDE/NOOP no compile: identificador
  forte compartilhado (DOI/ISBN/arXiv/sha) decide deterministicamente;
  similaridade depois; LLM local só na zona cinzenta (flag). Auditoria em
  `reconcile_log`.
- **Bi-temporalidade**: `valid_at`/`invalid_at` tipados (tempo de MUNDO;
  `stale_as_of` continua tempo de código); o `/ask` extrai `as_of` da
  pergunta e despriosiza evidência fora da validade; SUPERSEDE grava
  `superseded_by` + `invalid_at` — invalidar, nunca apagar.
- **Grafo com confiança**: `graph_edges.confidence` pesa o Leiden; arestas
  `inferred` por co-menção de entidade; super-hubs (p99) fora do
  particionamento; páginas `communities/*.md` (`community_summary`) geradas.
- **Heat/outcomes/reflect**: `✅ útil · 🚫 beco · ✏️ corrigi` no chat →
  `ask_outcomes`; reflect semanal recalcula `page_heat` e o overlay
  `preferred/tentative/contested` que ajusta a fusão RRF (+15%/−20%);
  correção vira memória nova no inbox (`raw/correcoes/`).
- **Descida hierárquica** L0/L1 (`page_levels` + `fts_levels`) com
  `trajectory` visível no painel de evidências.
- **Abstenção** (LongMemEval): sem cobertura, `abstained: true` + `gaps` —
  nunca resposta fabricada. **Eval de memória** em 5 categorias
  (extract · multi_session · temporal · update · abstain) contra
  `bundle/harness/golden_eval.jsonl`, com barras no painel Qualidade.

- **Bundle OKF versionado em Git** (`~/llmwiki/knowledge/bundle/`): páginas
  Markdown com frontmatter tipado, `index.md`/`log.md` reservados, escrita
  exclusivamente via `BundleWriter` (gate do Harness).
- **Harness em duas camadas**: conformidade OKF (só o SPEC — `# Citations`
  é SHOULD, nunca emite finding) × política local (privacy obrigatório,
  `source_sha256` só para páginas geradas por máquina, citações exigidas só
  para conteúdo `api:*`).
- **Runtime**: fila de jobs SQLite + worker + scheduler + governor de
  orçamento de API + eventos SSE; índice FTS5 (+denso opcional) derivado.
- **Cockpit**: Dashboard → Consulta com Evidências → Inbox → Wiki →
  Qualidade → Processos, com o botão **⭐ Promover para memória**
  (`generated_via: human:promote`, sem exigência de `source_sha256`).

## Instalação

**Local (desenvolvimento e uso diário):**

```bash
just bootstrap                      # venv + pip install -e backend[dev]
backend/scripts/llmwiki okf bootstrap
backend/scripts/llmwiki seed        # dados pré-definidos (idempotente):
                                    # referência do mundo + pipelines builtin
just daemon &                       # API em 127.0.0.1:8377 (token efêmero)
cd desktop && npm i && npm run dev  # cockpit Electron
```

**Docker (daemon empacotado; desktop conecta de fora):**

```bash
docker compose up -d                # build + daemon; bootstrap+seed automáticos
docker compose exec llmwiki cat /data/state/daemon.json   # host/porta/token
docker compose --profile ml up -d   # + Ollama (modelos locais) em rede interna
```

Dados no volume `llmwiki-data` (bundle Git + 5 bancos SQLite + handshake);
a porta publica só em 127.0.0.1 — local-first vale também no Docker.
Backlog fechado e portas abertas: [`docs/09-backlog.md`](docs/09-backlog.md).

## Montagem (detalhe)

```bash
just bootstrap        # venv + pip install -e backend[dev]
just models           # ollama pull (opcional — tudo degrada p/ modo extrativo)
just test             # 217 testes de contrato/arquitetura/golden bundles
just daemon &         # sobe em 127.0.0.1:8377 com token efêmero
backend/scripts/llmwikictl status
backend/scripts/llmwiki okf lint        # 0 erros num bundle recém-bootstrapado
cd desktop && npm i && npm run dev      # cockpit (Electron + Vite)
```

O bundle é bootstrapado automaticamente pelo daemon (ou `llmwiki okf
bootstrap`): `index.md` raiz com frontmatter contendo **apenas**
`okf_version`, `log.md` com headings ISO, commit inicial.

## Estrutura

```
backend/
  src/llmwiki/
    okf/        document, links, bundle, index_file, log_file, git_store, writer,
                bootstrap, authorities (gazetteer do bundle, v0.8)
    normalize/  model, masking, grammar, gazetteer, engine +
                detectors/{dates,quantities,identifiers,standards,geo}   (v0.8 §3)
    harness/    findings, okf_conformance (SPEC), local_policy (política),
                runner (lint_bundle), eval_memory (5 categorias, v0.8 §10)
    runtime/    db (+migrate), queue, slots, events, governor, scheduler, worker
    jobs/       compile (sanduíche §6.1), ask (temporal/abstenção §6.2),
                reconcile (§5), reflect (§8), review, leiden (§7), embed,
                rerank, ocr, lora
    retrieval/  fts (rebuild_index incremental + entidades + níveis),
                descend, dense, related, streams (fusão RRF+Hedge)
    models/     router (local Ollama × API Anthropic, privacidade + orçamento)
    api/        system (auth header OU ?auth=), cockpit (+outcome/eval/
                authorities/reflect, v0.8 §11)
    daemon.py · cli.py · settings.py (flags + get)
  db/           schema_runtime.sql · schema_index.sql (tabelas v0.8 §2.1)
  config/       default.yaml (privacy.default: local_only · flags v0.8)
  build.spec    PyInstaller onedir (AGPL fora do binário)
desktop/
  electron/     main, preload, sidecar (handshake via state/daemon.json)
  src/panels/   Dashboard(+candidatos reflect), ChatEvidence(+desfechos,
                as_of, trajetória, abstenção), PromoteDialog, Inbox,
                Explorer(+filtro authority), Quality(+5 barras de eval),
                Processes
  src/lib/      daemonClient (extensões do cockpit + v0.8), client (singleton)
```

## Aceite da v0.7 (verificado por teste)

- [x] arquivo sem `---` → `okf.frontmatter_missing` (error); YAML inválido →
      `okf.frontmatter_invalid` (error) — ambos via `lint_bundle` varrendo cru
- [x] `timestamp` ISO no arquivo, `datetime` no parse (roundtrip)
- [x] promoção humana passa sem `source_sha256`; `privacy` obrigatório
- [x] página `api:*` sem `# Citations` → bloqueada (política, não conformidade)
- [x] reservados validados quando presentes; ausência nunca invalida
- [x] promote cria página + `Creation` no `log.md` + commit + evento
      `memory.promoted`
- [x] `llmwiki okf lint` == painel Qualidade (mesma fonte: `lint_bundle`)

## Aceite da v0.8 (verificado por teste — `test_normalize.py` + `test_v08.py`)

- [x] pacote `normalize/` sem dependência nova; checksums com vetores-golden
      (CPF 529.982.247-25, CNPJ alfanumérico 12.ABC.345/01DE-35 do SERPRO,
      ISBN-10/13, ISSN, ORCID, IBAN); idempotência `rewrite(rewrite(x))==rewrite(x)`
- [x] "postgres"/"nodejs."/"NIPS 2017" → `PostgreSQL`/`Node.js.`/`NeurIPS 2017`
      com fence intocada (verificado ponta a ponta no compile)
- [x] ISBN/CPF com DV inválido em página de máquina → bloqueio no Harness
- [x] CPF válido + `api_allowed` → `policy.pii_requires_local`
- [x] mesmo DOI em duas fontes → `UPDATE` no `reconcile_log`
- [x] `/ask` com data → `as_of` + filtro de validade; sem cobertura →
      `abstained: true` com `gaps`
- [x] `eval_memory` grava as categorias em `eval_runs`; painel Qualidade
      mostra as 5 barras; `abstain` só passa com abstenção real
- [x] `reflect` popula `page_heat`/`page_overlay`; página `contested` afunda
      na fusão do `/ask`; Dashboard exibe candidatos
- [x] migração idempotente: bancos v0.7 ganham `graph_edges.confidence` e
      `chunks.valid_at/invalid_at` no primeiro `connect()`

## Notas de implementação (desvios conscientes dos docs)

- `OKFDocument.loads` remove o BOM antes de `frontmatter.loads` (não só na
  detecção) — senão arquivo com BOM parseava com metadata vazia.
- Auth aceita token válido em **qualquer** um dos canais (header ou
  `?auth=`), não "header primeiro": EventSource não envia headers e um
  header errado não pode vetar um `?auth=` correto.
- `InboxPanel` envia o caminho **relativo ao kb** (`raw/...`) no
  `compile_source`; o daemon resolve contra o kb (o doc montava um caminho
  absoluto inválido no frontend).
- `vite.config.mts` (não `.ts`): o plugin do Tailwind v4 é ESM-only e o
  pacote precisa continuar CJS para o main do Electron.
- Parsers AGPL (`pymupdf4llm`, `ebooklib`) só via extra `llmwiki[parsers]`,
  executados em subprocesso (`ingestion/extract.py`) — nunca no binário.

Desvios da v0.8:

- `rewrite()` só aplica matches `extracted` (o doc incluía `inferred`, mas o
  próprio doc marca semver como "anexo apenas; nunca reescreve" — alinhamos
  reescrita e finding pelo mesmo critério; precisão > recall).
- Termos de FTS filtram stopwords pt/en: OR sobre "do/com/qual" casava
  qualquer página via descida L0 e matava a ABSTENÇÃO.
- Score da fusão é RRF puro (~1/61 no topo): `ask.abstain_threshold`
  default é 0.0 (abstém sem evidência); o 0.05 sugerido no doc abstinha
  sempre nessa escala.
- `router.complete("reconcile", prompt, privacy_local_only=True)` do doc →
  assinatura real `router.complete(prompt, privacy="local_only")`; idem
  `s.index_db/s.runtime_db` → `s.app_support / "*.db"` e `fts_pages` →
  `chunks_fts` agregado por página.
- A correção (`✏️ corrigi`) vira arquivo em `raw/correcoes/` — o inbox real
  do projeto — em vez do job `capture_note` inexistente citado no doc.
