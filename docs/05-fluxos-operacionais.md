# 05 · Fluxos operacionais

> QUANDO e ONDE cada coisa acontece — todos os fluxos fim-a-fim, com os
> pontos de decisão e os artefatos tocados. Notação: `[tabela]` =
> runtime.db/index.db; `(página)` = bundle+Git; `{evento}` = EventBus.

## 0. Ciclo de vida do daemon

```
daemon.main()
 ├─ Settings.load()  (LLMWIKI_CONFIG > default.yaml > defaults; LLMWIKI_HOME)
 ├─ ensure_bundle()  bootstrap idempotente: bundle/{index.md,log.md} + git init + commit
 ├─ connect(runtime.db) + connect(index.db)   ← schema + migrações aqui
 ├─ JobQueue · EventBus · Governor · Slots
 ├─ Worker (thread: lease → REGISTRY[type](s, payload, emit) → done/failed)
 ├─ Scheduler (thread: segunda-feira ⇒ reflect + review_weekly; diário ⇒ embed)
 ├─ issue_token() → state/daemon.json (handshake p/ Electron e CLI)
 └─ uvicorn 127.0.0.1:8377
```

Jobs registrados: `compile_source · consolidate_inbox · ask · embed ·
rerank · leiden · ocr · lora_train · review_weekly · reflect ·
eval_memory · index_rebuild`. Scheduler: segunda ⇒ reflect +
review_weekly; diário ⇒ embed + consolidate_inbox. Dedupe por chave
(ex.: `review:2026-W27`) impede duplicatas na fila.

## 1. Compilar uma fonte (o fluxo mais denso)

Entrada: arquivo em `raw/` — pelo filesystem OU pelo app (v0.11):

```
InboxPanel (dropzone / nota rápida) → POST /cockpit/ingest
  {filename, content|content_base64, subdir?, compile?}
  → IngestSource: slug do nome · sufixo validado (.md/.txt/.pdf/.epub)
    · colisão nunca sobrescreve (-2, -3…) · binário via base64
  → {source.ingested} · compile=true enfileira compile_source na hora
```

O Template Method emite `page.stage` em cada etapa (produce → normalize
→ reconcile → write → done, com o id do job) — o Inbox mostra o stepper
da pipeline ao vivo e, ao final, a coluna "→ Página" (compile_cache.page).

```
CompilerFacade.compile → CompileSource.execute()  [Template Method]
 1. _produce:
    extract(fonte)               .md/.txt direto; .pdf/.epub via subprocesso AGPL
    analyze(texto[:200k])        PRÉ: entidades canônicas da fonte
    router.complete(prompt+anexo)  privacy da fonte decide local×API; sem modelo ⇒ passthrough
 2. esqueleto:
    normalize_machine_body       PÓS: rewrite (grafia) + re-annotate
    _document                    meta: timestamp/valid_at=now, entities, PII⇒local_only
 3. _reconcile → ReconcileCandidate:
    id forte compartilhado? ──sim──► UPDATE (extracted)      [reconcile_log] sempre
    score = .4rank+.3jacc+.3(1-NCD)
      < LO(0.55) ► ADD  · ≥ HI(0.82) ► UPDATE (inferred)
      zona cinzenta ► árbitro LLM local (flag) ► ADD/UPDATE/SUPERSEDE/NOOP (ambiguous)
    NOOP ⇒ retorna sem escrever  ·  SUPERSEDE ⇒ (antiga += superseded_by, invalid_at)
 4. Harness gate ─ error ⇒ HarnessRejection (página NÃO entra)
 5. BundleWriter: lock → (página) → index.md ancestrais → log.md → commit
 6. _after_write: [compile_cache] · rebuild_index (chunks+arestas+entidades+níveis+cites)
    {compile.done}
```

Idempotência ponta a ponta: recompilar a mesma fonte produz o mesmo corpo
(rewrite idempotente) e cache por sha marca o status no Inbox.

## 1b. Consolidar por recorrência (CLS, v0.10)

Job diário (ou sob demanda): a alternativa barata ao compile 1-a-1
quando o inbox acumula notas do mesmo tema.

```
CompilerFacade.consolidate_inbox → ConsolidateInbox.execute()
 1. pendentes: raw/* fora do compile_cache (sha) → extract + analyze
    ⇒ assinatura determinística {ids fortes, entidades canônicas}
 2. cluster (union-find): convergem se compartilham id forte
    OU ≥ min_shared(2) entidades — SEM embeddings, SEM LLM
 3. cada cluster ≥ min_cluster(2) → _ConsolidatedPage [Template Method]:
    UMA chamada de LLM por cluster (fallback: concatenação por fonte);
    meta: sources=[...], source_sha256 = sha dos shas, privacy = a MAIS
    restritiva das fontes
 4. _after_write: compile_cache para CADA fonte · rebuild_index
 → {pending, clusters, pages, left}   (sem recorrência ⇒ fica pendente)
```

## 1c. Pipeline configurável (orquestração como dado, v0.17)

```
POST /cockpit/pipelines {name, stages:[{job, payload?, on_error?}]}
 → validação estrutural (slug, 1–20 estágios, sem recursão,
   on_error ∈ stop|continue) → upsert em [pipelines]
POST /cockpit/pipelines/run {name}
 → job `pipeline` na fila (slot heavy)
 → jobs/pipeline.py injeta o REGISTRY real → RunPipeline
   1. fail-fast: todo estágio referencia job existente? senão NADA roda
   2. trace snowflake do run · linha em [pipeline_runs]
   3. para cada estágio: span próprio · payload resolve "$prev.chave"
      do resultado anterior · handler roda inline · evento
      pipeline.stage (running→done|failed)
   4. falhou? on_error=stop encerra (state=failed);
      continue segue (state final=partial)
   5. pipeline.done + filme completo em [pipeline_runs] (últimos 200)
Builtin (seed idempotente no mount): absorver-inbox ·
manutencao-semanal · qualidade-total — card 🔗 no painel Processos
(▶ rodar, encadeamento, último estado, filme dos runs)
```

## 2. Perguntar (`/ask`)

```
MemoryFacade.ask → AskMemory.execute()
 1. analyze(pergunta)      simetria pergunta↔memória: mesmo normalizador
    → as_of (data na pergunta) · question_entities
 2. streams (EvidenceStreams, crédito Hedge de [stream_weights]):
    global   se panorâmica sem entidade → community_summaries (GraphRAG)
    fts      FTS5 sobre chunks (stopwords filtradas)
    dense    se deep e embeddings existem
    entity   páginas por entidade, ponderadas por surprisal (−log p)
    descend  L0→L1 com trajectory (flag retrieval.descend)
 3. fuse: RRF·crédito → overlay (preferred ×1.15 / contested ×0.8)
    → partição temporal por as_of → top-8 · uncertainty (entropia)
 4. abstenção: sem hits ou top < ask.abstain_threshold
    ⇒ {answer:null, abstained:true, gaps} — nunca fabrica
 5. efeitos: [page_heat.reads++] · [ask_provenance página→stream]
 6. compor: router (citações obrigatórias se api:*; sem seção ⇒ blocked)
    ou fallback extrativo local com # Citations
 → {answer, via, blocked, abstained, ask_id, uncertainty, evidence,
    gaps, as_of, trajectory}
```

## 3. Desfecho → aprendizado (o laço fechado)

```
ChatEvidencePanel: ✅ útil | 🚫 beco | ✏️ corrigi(nota)
 → POST /cockpit/outcome → RecordOutcome.execute()
    [ask_outcomes] sempre
    Hedge: streams que trouxeram as páginas julgadas
           useful ⇒ w·e^{+.25} · beco/corrigido ⇒ w·e^{−.25}, clamp [0.5,2]
           → [stream_weights] (entra na PRÓXIMA fusão)
    corrected+nota ⇒ (raw/correcoes/<ts>.md)  ← o erro vira item do Inbox
```

Semanalmente (`reflect`): `[ask_outcomes]` agregados por página →
`[page_overlay]` preferred/tentative/contested (3+ desfechos decidem) e
`[page_heat.score]` recalculado com decaimento — o overlay muda o ranking
do ask; os candidatos aparecem no Dashboard e na revisão.

## 4. Promover para memória (humano)

```
PromoteDialog → POST /cockpit/promote → CurationFacade.promote
 → PromoteToMemory: kind→(type,pasta) · slug do título
   página humana: generated_via human:promote, SEM source_sha256,
   privacy escolhido, SEM reescrita de corpo
 → BundleWriter (gate: privacy obrigatório, PII força local)
 → rebuild_index incremental (v0.14: respondível JÁ, sem esperar compile)
 → {memory.promoted} · resposta {pages, commit}
```

`mark_stale` também reindexa na hora (a flag stale vive em chunks) e a
reidratação recusa quando a página voltou ao bundle por outra via
(guarda quente×frio: purga a entrada fria obsoleta, nunca sobrescreve
conteúdo mais novo).

Variante: cartão de abstenção no chat oferece "capturar como pergunta
aberta" (kind=question) — lacuna vira memória endereçável.

## 5. Depreciar / suceder

- **`mark_stale`** (Explorer): grava `stale_as_of=<head do kb>` — tempo
  de código; página segue respondível, marcada 🟡. **TMS (v0.10)**: o
  resultado lista os `dependents` (páginas que citam a depreciada) para
  revisão — propagação de suspeita, nunca cascata automática.
- **SUPERSEDE** (reconciliador): antiga ganha `superseded_by` +
  `invalid_at` — tempo de mundo; some das respostas com `as_of`
  posterior, permanece para consultas históricas e no Git. Emite
  `{supersede.dependents}` quando a antiga tem citadores.

## 5b. Congelar e reciclar (base fria, v0.12)

```
FREEZE (T2→T3): Dashboard 🧊 / POST /cockpit/freeze → FreezeMemory
 gates: tipo protegido? dependentes (TMS)? overlay preferred?
        P(recall) ACT-R > corte? ócio < mínimo?     qualquer um ⇒ 409
 passa ⇒ [cold_memories] digest+strong_ids+corpo zlib9
        → writer.remove (log Freeze + commit) → rebuild_index
RECYCLE (T3→T2): três portas
 a) /ask abstém → cold_search(digest) → cold_matches na resposta
    (memory.auto_recycle ⇒ reidrata a melhor e re-consulta UMA vez)
 b) reconciliador: id forte de fonte nova casa memória fria ⇒ op RECYCLE
    (template reidrata e ATUALIZA sobre ela — nunca duplica)
 c) humano: ♻️ no Dashboard/Chat → POST /cockpit/recycle
 reidratação = writer.write normal (Harness + log Recall + commit),
 frontmatter ganha `recycled: n`, heat reacende, cold entry sai
```

## 5c. Ajustar configuração de negócio (linhagem + rollback, v0.16)

```
POST /cockpit/config {seção:{chave:valor}}
 → CurationFacade.tune_config → TuneConfig
   1. valida tipo/domínio contra o snapshot vigente
      (número no lugar de bool? chave desconhecida? seção fora das
       TUNABLE? → 400, NADA muda, nenhuma linha gravada)
   2. banco virgem? grava geração-zero (source=baseline)
   3. Settings.tune(): muta as seções vivas + persiste overrides.yaml
   4. probe (round-trip do modelo) — falhou? reverte o snapshot
      anterior sozinho + linha source=rollback + 400
   5. linha no ring [config_history] (delta + snapshot + trace
      snowflake; >30 ⇒ a mais velha cai) → evento config.tuned
Problema notado DEPOIS (job falhando, retrieval degradado):
POST /cockpit/config/rollback → RollbackConfig
 → reaplica o snapshot da geração ANTERIOR (O(1)) e grava o retorno
   como nova geração (a linhagem nunca anda para trás, o estado sim)
 → 409 se não há geração anterior · botão ↩️ no card "Linhagem da
   configuração" (Curadoria); StatusBar mostra 🩺 /health/full
```

## 6. Revisão semanal

```
GET /cockpit/review → ComputeWeeklyReview (PURO: nada escrito)
  novas páginas · órfãos (sem in-link) · stale · decisões · perguntas ·
  top tags · candidatos do reflect
POST /cockpit/review/commit → job review_weekly → PublishWeeklyReview
  [Template Method] → (reviews/<semana>.md) generated_via local:review
```

## 7. Comunidades + topologia (`leiden`)

```
DetectCommunities.execute()
 1. grafo ponderado: arestas por confiança (1.0/0.5/0.15)
    + co-menção de entidade (2..30 páginas) a peso inferred·0.5
 2. pontes frágeis: persistência 0-dim → [graph_bridges] (top-10)
 3. hubs > p99 fora; Leiden (extra [ml]) ou componentes; hubs pós-hoc
 4. → [communities] · páginas (communities/<slug>.md) via Template Method
    rótulo/resumo por LLM local com fallback determinístico
```

## 8. Avaliar a memória (`eval_memory`)

```
EvaluateMemory: para cada caso de bundle/harness/golden_eval.jsonl
  AskMemory local-only (com as_of do caso)
  abstain: passa ⟺ abstained=true
  demais: recall@5 nas expect_pages ∧ expect_regex na resposta ∧ ¬abstained
 → [eval_runs] por categoria → barras no QualityPanel (GET /cockpit/eval)
```

## 9. Auditoria de qualidade

`llmwiki okf lint` e `GET /cockpit/quality` usam a MESMA fonte
(`CurationFacade.lint → LintBundle → HarnessRunner.lint_bundle`, que
varre arquivos CRUS — malformados viram findings, nunca são engolidos).
Quality agrega ainda: eval por categoria, pontes frágeis, órfãos, stale,
cobertura de privacy.

## 10. Implantação (release macOS)

```
pyinstaller build.spec            → backend/dist/llmwiki-server/ (onedir)
cd desktop && npm run build       → tsc --noEmit + vite build + electron-builder
assinar + notarizar               (hardenedRuntime; sidecar não assinado morre)
smoke: app abre com daemon morto (read-only) · sobe daemon ·
       okf lint limpo · ask --local responde
```

## 11. Mapa endpoint → facade → use case

| Endpoint | Facade | Use case |
|---|---|---|
| POST /ask | Memory.ask | AskMemory |
| POST /cockpit/outcome | Memory.record_outcome | RecordOutcome |
| GET /cockpit/eval · job eval_memory | Memory.evaluate | EvaluateMemory |
| POST /cockpit/ingest | Compiler.ingest | IngestSource |
| job compile_source | Compiler.compile | CompileSource (+ReconcileCandidate) |
| job consolidate_inbox | Compiler.consolidate_inbox | ConsolidateInbox (+_ConsolidatedPage) |
| job index_rebuild · CLI okf index | Compiler.rebuild_index | RebuildIndex |
| job leiden | Compiler.detect_communities | DetectCommunities |
| POST /cockpit/promote | Curation.promote | PromoteToMemory |
| POST /cockpit/page/stale | Curation.mark_stale | MarkPageStale |
| GET /cockpit/quality · CLI okf lint | Curation.lint | LintBundle |
| GET /cockpit/review | Curation.weekly_review | ComputeWeeklyReview |
| job review_weekly | Curation.publish_review | PublishWeeklyReview |
| job reflect | Curation.reflect | ReflectOnUsage |
| GET /cockpit/reflect | Curation.reflect_candidates | usage_candidates (puro) |
| POST /cockpit/freeze | Curation.freeze | FreezeMemory |
| POST /cockpit/recycle | Curation.recycle | RecycleMemory |
| GET /cockpit/cold | Curation.cold | cold_stats (puro) |
| POST /cockpit/tags | Curation.rename_tag | RenameTag |
| GET /cockpit/export | Curation.export | ExportMemory |
| GET graph/insights/dictionary/traces | — (observatório, leitura pura) | retrieval/observatory.py |
| GET /cockpit/config | — (leitura pura) | Settings.snapshot |
| POST /cockpit/config | Curation.tune_config | TuneConfig |
| POST /cockpit/config/rollback | Curation.rollback_config | RollbackConfig |
| GET /cockpit/config/history | Curation.config_history | config_history (puro) |
| GET /cockpit/pipelines | Compiler.pipelines | list_pipelines (puro) |
| POST /cockpit/pipelines | Compiler.save_pipeline | SavePipeline |
| DELETE /cockpit/pipelines | Compiler.delete_pipeline | DeletePipeline |
| job pipeline | Compiler.run_pipeline (REGISTRY injetado) | RunPipeline |
| GET /cockpit/pipelines/runs | Compiler.pipeline_runs | pipeline_runs (puro) |
| GET / · /health · /health/full | — (sistema, api/system.py) | — |
