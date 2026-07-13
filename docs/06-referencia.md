# 06 · Referência dura

> A tabela da verdade que a skill `docs-sync` audita contra o código.
> Se algo aqui divergir do código, o CÓDIGO vence e este arquivo deve
> ser corrigido (nunca o contrário sem commit no código).

## 1. Regras do Harness

### Conformidade OKF (`harness/okf_conformance.py` + `runner.lint_bundle`)
| Regra | Sev | Gatilho |
|---|---|---|
| `okf.frontmatter_missing` | error | .md não-reservado sem `---` inicial (via lint cru) |
| `okf.frontmatter_invalid` | error | YAML inválido ou `type` ausente (via lint cru) |
| `okf.broken_link` | warn | link interno para alvo inexistente ("pode ser conhecimento futuro") |
| `okf.log_heading` | warn | heading de `log.md` fora de `## YYYY-MM-DD` |
| `okf.reserved_frontmatter` | warn | `index.md` com frontmatter (exceto `okf_version` no raiz) |

Ausência de `# Citations` e de reservados **nunca** gera finding
(conformidade = só o SPEC).

### Política local (`harness/local_policy.py`)
| Regra | Sev | Gatilho |
|---|---|---|
| `policy.privacy_required` | error | página sem `privacy: local_only\|api_allowed` |
| `policy.source_sha_required` | error | `generated_via: api:*\|local:*` sem `source_sha256` |
| `policy.citation_required` | error | `api:*` sem seção `# Citations` com entradas |
| `policy.citation_invalid` | error | refs `[n]` no corpo sem entrada na seção |
| `policy.bad_commit_ref` | error | sha citado (contexto commit/stale_as_of) inexistente no kb |
| `policy.schema_shrink` | error | campo de `## Schema` removido sem `supersedes` |
| `policy.metadata_shrink` | warn | chave de frontmatter perdida (exceto timestamp) |
| `policy.unknown_type` | info | type fora da taxonomia recomendada |
| `policy.release_broken_link` | error | link quebrado em `mode=release` |
| `policy.identifier_invalid` | error (máquina) / warn (humano) | DV de CPF/CNPJ/ISBN/ISSN/ORCID/IBAN inválido |
| `policy.term_noncanonical` | error (máquina, residual) / info (humano, sugestão) | grafia fora do canônico curado |
| `policy.pii_requires_local` | error | PII com DV válido + `privacy: api_allowed` |
| `policy.temporal_order` | error | `invalid_at ≤ valid_at` |
| `policy.schema_required_field` | error | campo obrigatório declarado por `collection_specification` (`applies_to`) ausente na página do tipo |
| `policy.quotation_attribution` | warn (só lint, corpus) | citação conhecida do reference.db presente no corpo sem o sobrenome do autor em lugar nenhum do texto — sem atribuição ou mal-atribuída (v1.2; normas pré-computadas, custo medido < 2s na suíte) |
| `policy.contradiction_candidate` | warn (só lint, corpus) | mesmo identificador forte (doi/isbn/issn/arxiv) em 2+ páginas sem sucessão (`superseded_by`/`supersedes` no grupo ou `invalid_at`); o finding nomeia a página mais entrincheirada (humana > máquina) |

## 2. Endpoints (API local, auth header `x-llmwiki-auth` OU `?auth=`)

```
GET  /                           (sem auth; raiz HATEOAS: mapa _links de todo o serviço)
GET  /health                     (sem auth; ok · version · instance)
GET  /health/full                (v0.16: instância{snowflake,pid,uptime} · process{rss,cpu,threads}
                                  · queue{by_state,oldest_age} · stacks{bytes,wal,integrity,tables}/banco
                                  · bus{subscribers} · config{gerações} · resources{disk} · budget)
GET  /status                     · GET/POST /jobs · GET /events (SSE)
POST /jobs/{id}/cancel           (v1.3: queued→cancelled; leased→cancel_requested)
POST /jobs/{id}/retry            (failed/dead_lettered/cancelled → queued)
POST /ask                        {query, deep?, local_only?, as_of?}
GET  /cockpit/dashboard          · GET /cockpit/inbox
POST /cockpit/ingest             {filename, content|content_base64, subdir?, compile?}
GET  /cockpit/stats              (by_type · heat_buckets · outcomes · outcomes_per_day)
GET  /cockpit/pages              · GET /cockpit/page?path=
POST /cockpit/page/stale         {path}
POST /cockpit/promote            {kind, title, content, source?, privacy?, description?, tags?}
GET  /cockpit/memory             · GET /cockpit/quality?mode=
GET  /cockpit/ledger/today
POST /cockpit/outcome            {verdict, ask_id?, note?, pages?}
GET  /cockpit/eval               · GET /cockpit/authorities
GET  /cockpit/reflect            · GET /cockpit/review · POST /cockpit/review/commit
POST /cockpit/freeze             {path, force?, reason?} — 409 quando um gate veta
POST /cockpit/recycle            {path} — 404 se não está na base fria
GET  /cockpit/cold               (count · compression_saved · recycles · entries)
GET  /cockpit/graph              (Fase 5: nós+arestas+pontes p/ o grafo visual)
GET  /cockpit/insights           (gaps · topology{+structure∈disperso|focado|
                                  diverso, communities, evenness} · activity · classifiers)
GET  /cockpit/gaps               (v1.1: lacunas estruturais{déficit, pergunta-ponte,
                                  representantes} + articuladores por intermediação)
GET  /cockpit/dictionary         (enums vivos: tipos, origens, confiança, autoridades)
GET  /cockpit/traces · /cockpit/trace?ask_id=   (proveniência página→stream)
GET/POST /cockpit/tags           (contagens; POST {from, to?} renomeia/funde/remove)
GET/POST /cockpit/config         (seções TUNABLE: flags·ask·memory·policy·consolidate;
                                  aplica A QUENTE + persiste em overrides.yaml; v0.16:
                                  valida tipo/domínio, grava geração no ring config_history
                                  e devolve history_id+trace_id; 400 = guard recusou)
GET  /cockpit/config/history     (linhagem: até 30 gerações, mais recente = vigente)
POST /cockpit/config/rollback    (retorna à geração ANTERIOR; 409 sem anterior)
POST /cockpit/state              (v0.18: {load 1..5*, focus?, energy?,
                                  time_available_min?, note?} — declarado, TTL 8h)
GET  /cockpit/cognition          (estado · perfil · strategy_weights · calibração
                                  Brier/bins · observações pendentes)
POST /cockpit/cognition/observe  (varredura metacognitiva; também job semanal)
GET  /cockpit/cognition/observations ?status=proposed|accepted|rejected|suspended
POST /cockpit/cognition/observations/review {id, action} — aceite aplica
                                  suggestion via linhagem (404 id, 400 action)
GET  /cockpit/attention          ?minutes= (default: do estado ou 60) → plano
                                  com reason por item; carga alta ⇒ blocos ≤15min
POST /cognitive/goals            (v0.19: {title*, root*, intent?, priority?,
                                  horizon_days?, time_available_min?,
                                  depth_desired?{7 dimensões 0..3}, excluded?,
                                  pinned?} — 404 raiz inexistente)
GET  /cognitive/goals · /cognitive/goals/{id}
POST /cognitive/projections      ({goal_id, policy?, pin?, exclude?} → gates
                                  duros + score decomposto + orçamento; NOVA
                                  projeção a cada revisão — versões imutáveis)
GET  /cognitive/projections/{id}
POST /cognitive/sessions         ({projection_id, mode∈understand|apply|retain|
                                  critique|transfer|resume})
GET  /cognitive/sessions/{id}    (_links refletem o estado: active⇒attempt/
                                  suspend/complete; suspended⇒resume)
POST /cognitive/sessions/{id}/attempts   ({item*, exercise, confidence_before*
                                  ∈[0,1] ANTES, result∈success|partial|failure,
                                  answer?} → acessibilidade + agenda + gap)
POST /cognitive/sessions/{id}/feedback   ({scope*, verdict*, target?, note?} —
                                  evento imutável; vocabulários fechados)
POST /cognitive/sessions/{id}/suspend    ({reason?, next_step?} → ResumeCapsule;
                                  409 se não-active)
POST /cognitive/sessions/{id}/resume     (409 se não-suspended)
POST /cognitive/sessions/{id}/complete
GET  /cognitive/reviews/due      · POST /cognitive/reviews/{id}/complete
GET  /cognitive/goals/{id}/progress  (v0.20: profundidade declarada×validada
                                  por dimensão; sem instrumento ⇒ measurable=false)
POST /cognitive/experiences      ({type∈11 tipos Efklides, intensity 1..5,
                                  session_id?, item?, note?})
POST/GET /cognitive/analogies    (contrato exige mappings E breaks; 400 sem ruptura)
POST /cognitive/analogies/{id}/promote  (gate humano → PromoteToMemory)
GET  /cognitive/curation         (CurationProjection: stale/contested/questions
                                  sob a ótica dos objetivos ativos; leitura pura)
GET  /cognitive/metrics          (Brier, delayed recall, apply/transfer, recorrência,
                                  review completion, latência de retomada)
GET  /cognitive/prompt           ?exercise=&title=&item= (template determinístico
                                  + scaffolding com fading pela streak do item)
GET  /cognitive/episodes         (v0.21: linha do tempo episódica das sessões)
GET  /cockpit/pipelines          (v0.17: specs + last_run; seed builtin no mount)
POST /cockpit/pipelines          {name, description?, stages:[{job,payload?,on_error?}]}
                                 (400 = validação estrutural recusou)
DELETE /cockpit/pipelines?name=  (404 se não existe)
POST /cockpit/pipelines/run      {name} → job `pipeline` na fila (404 se não existe)
GET  /cockpit/pipelines/runs     ?name=&limit= (filme: estado por estágio + trace)
GET  /cockpit/reference          (v0.22: contagens + facts; seed no mount)
POST /cockpit/reference          ({terms?, quotations?, facts?} — upsert; 400 forma)
POST /cockpit/reference/check    ({text, author?} → matches + misattributions)
GET  /cockpit/behavior · POST /cockpit/behavior/reset-streams
GET  /cockpit/export             ?format=zip|json|md &include_local &types &tag
                                 (local_only fica de fora por default; manifesto)
```

Resposta do `/ask`: `{answer, via, blocked, abstained, ask_id,
identity{ts_ms,iso,module,algorithm,seq}, uncertainty,
evidence[{page,resource,body,stale}], gaps, as_of,
trajectory[{dir,picked}]}`. O `ask_id` é um snowflake renderizado
(módulo=ask, algoritmo=rrf) — decodificável por `kernel.identity.parse`.

HATEOAS (v0.16): `/`, `/health`, `/health/full`, `/status`,
`/cockpit/dashboard`, `/cockpit/page`, `/cockpit/config*` carregam
`_links{rel:{href}}` — navegação por relação, não por URL montada.

## 3. Tabelas

**runtime.db**: `jobs` · `events` · `ledger` · `compile_cache` ·
`ask_outcomes(verdict∈useful|dead_end|corrected)` ·
`page_heat(reads,cites,last_seen,first_seen,score)` ·
`reconcile_log(op∈ADD|UPDATE|SUPERSEDE|NOOP|RECYCLE)` · `eval_runs` ·
`ask_provenance(ask_id,page,stream)` · `stream_weights(stream,weight)` ·
`config_history(trace_id, changes json, snapshot json,
source∈cockpit|cli|baseline|rollback, note)` — ring de 30: o
`TuneConfig` poda além do limite; a vigente é a linha mais recente ·
`pipelines(name, spec json, builtin)` ·
`pipeline_runs(pipeline, trace_id, state∈running|done|partial|failed,
stages json, started_at, finished_at)` — últimos 200 (v0.17) ·
`cognitive_state(load 1..5, focus, energy, time_available_min, note)`
— últimas 200 declarações (v0.18) ·
`ask_context(ask_id PK, strategy, load, confidence)` ·
`strategy_weights(strategy, weight)` ·
`metacog_observations(kind∈strategy|load|calibration, statement,
support, confidence, evidence json, suggestion json,
status∈proposed|accepted|rejected|suspended)`

**cognitive.db** (v0.19 — Cognitive Experience Domain, SEPARADO: só
referências a páginas, zero conteúdo canônico; projeções
reconstruíveis): `focus_goals(id snowflake, goal json, status)` ·
`cognitive_projections(id, goal_id, policy json SNAPSHOT, working_set
json, trace_id)` · `cognitive_sessions(id, state∈active|suspended|
completed, session json c/ steps+capsule)` ·
`retrieval_attempts(session_id, item, exercise, confidence_before,
result, …)` · `accessibility(item PK, level∈escada de 7, streak,
attempts)` — NUNCA é confiança epistemológica ·
`review_schedules(item, due_at, interval_days, algorithm=spaced-v1,
reason, status∈due|done|cancelled)` · `cognitive_feedback` (evento
imutável, só INSERT) · `metacog_experiences(type, intensity 1..5,
status∈declared|revised|retracted)` · `analogies(id, analogy json,
status∈draft|kept|promoted|discarded, feedback_score)` (v0.20)

**reference.db** (v0.22 — referência DO MUNDO, relacional, separada):
`ref_terms(canonical UNIQUE, kind∈entity|person|standard|toponym,
aliases json)` · `ref_quotations(quote, author, source, norm UNIQUE)` ·
`ref_facts(kind∈law|equation|axiom|logic_rule, name, statement, domain,
UNIQUE(kind,name))`. Precedência no gazetteer: authority_record >
ref_terms > SEEDS (colisão por canonical OU alias); import invalida o
cache HEAD do gazetteer.

**cold.db** (base fria, v0.12 — NÃO derivado; conteúdo compactado):
`cold_memories(page, digest, strong_ids, body_z zlib9, meta_json,
frozen_at, frozen_commit, activation, recall_p, recycles)` · `cold_fts`
(FTS sobre digest, para o recall de fallback).

**index.db** (derivado): `chunks(+valid_at,invalid_at)` · `chunks_fts` ·
`graph_edges(+confidence)` · `communities` · `embeddings` · `entities` ·
`page_entities(confidence,data)` · `page_levels(level∈0,1)` ·
`fts_levels` · `page_overlay(status∈preferred|tentative|contested)` ·
`graph_bridges(src,dst,weight,small_side,large_side)` ·
`page_index_state(page,sha)` + `index_meta` (índice INCREMENTAL v0.13:
só páginas com sha alterado reindexam; fingerprint do gazetteer força
full automático; `rebuild_index(s, full=True)` disponível)

Migrações em `runtime/db.py:_migrate`: `graph_edges.confidence`,
`chunks.valid_at/invalid_at`, `page_heat.first_seen` (backfill =
`last_seen`), `compile_cache.page` (destino da compilação, Inbox).

Eventos da pipeline (SSE): todo `MachinePageUseCase` emite `page.stage`
(`produce → normalize → reconcile → write → done`, com `id` do job) —
o Inbox e o painel Processos renderizam o stepper ao vivo; ingestão
emite `source.ingested`. Tracing (v0.16): cada execução do template
carrega UM `trace_id` snowflake e cada stage um `span` próprio (spans
ordenam lexicográfica = temporalmente); eventos de job levam o
`trace_id` da execução (o `emit` do worker injeta); ajustes de config
emitem `config.tuned`/`config.rolled_back` com trace.

## 4. Jobs (REGISTRY em `jobs/__init__.py`)

`compile_source · consolidate_inbox · ask · embed · rerank · leiden ·
ocr · lora_train · review_weekly · reflect · eval_memory ·
index_rebuild · pipeline · metacog` — contrato
`run(settings, payload, emit) -> dict`.
Slots heavy: compile_source, lora_train, leiden, ocr, pipeline.
Scheduler: segunda ⇒ reflect + review_weekly + metacog; diário ⇒
embed + consolidate_inbox. O job `pipeline` injeta o REGISTRY no
`RunPipeline` (DIP) e roda os estágios inline no MESMO slot.

## 5. Configuração (`config/default.yaml` + Settings)

```yaml
home: ~/llmwiki                 # LLMWIKI_HOME sobrepõe
privacy: {default: local_only, rules: [{pattern, privacy}...]}
budget:  {daily_usd: 2.0}
policy:  {citation_required: true}
flags:   {retrieval.descend: true, reconcile.llm_arbiter: false}
ask:     {abstain_threshold: 0.0}
models:  {local: {ollama...}, api: {anthropic...}}
worker:  {heavy_slots: 1, light_slots: 2, poll_seconds: 1.0}
```

Helpers: `s.path(nome)` · `s.app_support` · `s.resolve_privacy(rel)` ·
`s.flag(nome)` · `s.get("a.b", default)` · `s.with_overrides(**kw)`.

Consolidação: `consolidate.{min_shared, min_cluster, pairwise_max=32}` —
acima de `pairwise_max` fontes pendentes, a clusterização troca pares
O(n²) por índice invertido (id forte, entidade) + 9 bandas LSH do
SimHash (seleção adaptativa v0.16; geração de candidatos EXATA).

Configuração de negócio (v0.16): mutações passam por
`usecases/configure_system.TuneConfig` (validação de tipo/domínio →
aplica → probe → linha no ring `config_history`); `RollbackConfig`
reaplica o snapshot da geração anterior. `Settings.tune()` continua
sendo o mecanismo baixo (mutação + overrides.yaml) — não chame direto
fora de testes.

Camada cognitiva (v0.18): seções TUNABLE novas `profile`
({preferred_strategy: auto|<estratégia>, formalism, analogies}) e
`cognitive` ({state_ttl_hours: 8, high_load: 4, min_support: 5});
estratégias = direta · analogia-primeiro · exemplo-primeiro ·
teoria-primeiro · decomposicao (`usecases/cognitive_state.STRATEGIES`);
kernel novo: `calibration.py` (brier_score, overconfidence,
calibration_bins) e `attention.py` (review_gain = 4p(1−p),
fill_budget guloso por densidade).

Identidade (v0.16, `kernel/identity.py`): snowflake 63 bits =
41b ms desde 2026-01-01 · 6b módulo (MODULES) · 6b algoritmo
(ALGORITHMS) · 10b sequência/ms; `render()` = 13 chars Crockford
base32 com ordem lexicográfica = temporal; `parse()` decodifica;
`factory(módulo, algoritmo)` compartilha o gerador por processo
(unicidade entre instâncias); relógio para trás é clampado e estouro
de sequência avança 1 ms lógico.

## 6. Tipos OKF recomendados

`concept · academic_paper · runbook · decision · learning_note · skill ·
review · question · architectural_alert · breaking_change ·
collection_specification · schema_specification · field_profile ·
message_channel · feature_flag · infrastructure_specification ·
personal_reflection · reference · authority_record · community_summary`

Mapa do promote: semantic→concept/concepts · decision→decisions ·
runbook→runbooks · skill→career/skills · question→questions ·
alert→architectural_alert/alerts.

## 7. Frontmatter

**Tipados** (`okf/document.py`): `type*` · `title` · `description` ·
`resource` · `tags` · `timestamp` · `valid_at` · `invalid_at` ·
`superseded_by` · `sensitive_data` · `entities`.
**Extensões toleradas** (extra="allow"): `privacy` · `generated_via` ·
`source` · `sources` (lista, páginas consolidadas) · `source_sha256` ·
`confidence` · `supersedes` · `stale_as_of` · `canonical` · `aliases` ·
`authority` · `qid` · `applies_to` + `required_fields`
(collection_specification) · `okf_version` (raiz).

## 8. Detectores do normalize/

| Detector | subkinds | Reescreve? |
|---|---|---|
| identifiers | cpf, cnpj, doi, arxiv, isbn, issn, orcid, cve, uuid, semver(inferred), iban, git_sha | sim (extracted, DV não-inválido) |
| standards | iso, nbr, rfc, nist, ieee, eu_reg, regulator | sim |
| entity (gazetteer) | stack, publisher, publication, org (+authority_records) | sim |
| dates | date (pt/en/numérico/ISO/ano-mês) | NUNCA — anexo `{"iso"}` |
| quantities | qty (tabela UNITS, conversão SI) | NUNCA — anexo `{"si"}` |
| geo | country, uf(ancorada), cep, address(inferred) | NUNCA |

Prioridade em sobreposição: identifier 5 > standard 4 > date 3 >
quantity 2 > geo/entity 1 (mais longo vence; empate → prioridade).
PII sensível: cpf, cnpj, iban (com DV válido).

## 9. Camadas e regras de import (test_architecture.py)

```
kernel/, normalize/     PURO: proibido sqlite3, httpx, subprocess, fastapi,
                        uvicorn, git, requests, frontmatter, yaml, pydantic,
                        sse_starlette, socket, urllib, pathlib
usecases/               proibido: fastapi, facades, api, jobs
api/                    proibido: usecases, jobs (só facades)
okf/ harness/ usecases/ facades/ retrieval/ runtime/
                        proibido TRANSPORTE (v0.16): fastapi, uvicorn,
                        sse_starlette, socket, httpx, requests, urllib
UseCase                 métodos públicos ⊆ {execute}
MachinePageUseCase      subclasses não sobrescrevem execute
```

## 10. Use cases e facades

CLI ganha (v0.14): `llmwiki cold` · `llmwiki freeze <page> [--force]` ·
`llmwiki recycle <page>`; `ask` exibe incerteza alta e memórias frias
compatíveis na abstenção. Painel novo: 🧠 Memória (4 camadas + base
fria). Processos: jobs falhos têm ↻ reexecutar (payload na listagem).
Removido: retrieval/fusion.py (substituído por streams desde a v0.9).

**Memory**: AskMemory · RecordOutcome · EvaluateMemory.
**Compiler**: IngestSource (entrada pelo app → raw/) · CompileSource ·
ConsolidateInbox (+`_ConsolidatedPage`) · ReconcileCandidate ·
RebuildIndex · DetectCommunities.
**Curation**: PromoteToMemory · MarkPageStale (+`dependents_of` puro) ·
FreezeMemory · RecycleMemory (+`cold_search`/`cold_by_strong_id`/
`cold_stats` puros) · RenameTag · ExportMemory · LintBundle ·
ComputeWeeklyReview · PublishWeeklyReview · ReflectOnUsage
(+ `usage_candidates` puro).

Observatório (Fase 5, consultas puras em `retrieval/observatory.py`):
`graph_data` · `insights` · `dictionary` · `traces`/`trace`. Config viva:
`Settings.tune()` muta as seções TUNABLE compartilhadas (efeito imediato
— use cases leem via get()/flag() no execute) e persiste em
`app_support/overrides.yaml`, que o `Settings.load()` reaplica no boot.

Reconciliador ganha a operação `RECYCLE` (memória fria com o mesmo id
forte é reidratada e ATUALIZADA em vez de duplicada); o Template Method
executa a reidratação antes do write. Migração: `reconcile_log` é
recriada quando o CHECK antigo não aceita `RECYCLE` (dados preservados).

Derivados do bundle (gazetteer + schemas de tipo) são cacheados por
`(kb, HEAD)` em `okf/authorities.py` — toda escrita commita, então o
HEAD é chave de invalidação perfeita (~92× mais rápido no hit).

## 11. Constantes calibráveis

| Constante | Valor | Onde |
|---|---|---|
| RRF k | 60 | retrieval/streams.py |
| Reconcile HI / LO | 0.82 / 0.55 | usecases/reconcile_candidate.py |
| Pesos reconcile | 0.4 rank · 0.3 jaccard · 0.3 (1−NCD) | idem |
| Hedge η / clamp | 0.25 / [0.5, 2.0] | kernel/information.py |
| Overlay boost | preferred ×1.15 · contested ×0.8 | retrieval/streams.py |
| Heat (BLA) | 0.6·σ(BLA) + 0.2·min(1, cites/5) + 0.2·outcome; BLA ≈ ln(n/(1−d)) − d·ln(L), d=0.5 | usecases/reflect_usage.py + kernel/activation.py |
| Candidatos reflect | promote > 0.6 · archive < 0.15 (e 90d sem uso) | usecases/reflect_usage.py |
| Consolidação (CLS) | min_shared=2 entidades OU id forte; min_cluster=2 | usecases/consolidate_inbox.py |
| Esquecimento (ACT-R) | P(recall)=σ((B−τ)/s); τ=0 · s=0.4 · corte 0.05 · ócio mínimo 90d | config `memory.*` + kernel/activation.py |
| Tipos protegidos do freeze | authority_record · collection_specification (+ dependentes TMS vetam sempre) | usecases/cold_memory.py |
| PPR (HippoRAG) | damping 0.5 · 20 iterações · top-12 · seeds com add-one | kernel/graphwalk.py + ask |
| SimHash near-dup | 64 bits · shingle 3 palavras · hamming ≤ 8 converge | kernel/sketch.py + consolidate |
| Relacionadas (A-mem) | top-5 por Σ n·surprisal, excluindo já-linkadas | retrieval/related.py (`GET /cockpit/page`.related) |
| Pesos de aresta | extracted 1.0 · inferred 0.5 · ambiguous 0.15 | usecases/detect_communities.py |
| Co-menção | 2..30 páginas, peso 0.25 | idem |
| Hub p99, mínimo | max(p99, 8) | idem |
| Chunk | 1200 chars | retrieval/fts.py |
| Chip incerteza (UI) | > 0.85 | ChatEvidencePanel |
