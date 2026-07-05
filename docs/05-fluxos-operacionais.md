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

Jobs registrados: `compile_source · ask · embed · rerank · leiden · ocr ·
lora_train · review_weekly · reflect · eval_memory · index_rebuild`.
Dedupe por chave (ex.: `review:2026-W27`) impede duplicatas na fila.

## 1. Compilar uma fonte (o fluxo mais denso)

Entrada: arquivo em `raw/` (Inbox mostra novo/stale/compilado por sha).
`InboxPanel → POST /jobs {compile_source, path}` ou CLI `enqueue`.

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
 → {memory.promoted} · resposta {pages, commit}
```

Variante: cartão de abstenção no chat oferece "capturar como pergunta
aberta" (kind=question) — lacuna vira memória endereçável.

## 5. Depreciar / suceder

- **`mark_stale`** (Explorer): grava `stale_as_of=<head do kb>` — tempo
  de código; página segue respondível, marcada 🟡.
- **SUPERSEDE** (reconciliador): antiga ganha `superseded_by` +
  `invalid_at` — tempo de mundo; some das respostas com `as_of`
  posterior, permanece para consultas históricas e no Git.

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
| job compile_source | Compiler.compile | CompileSource (+ReconcileCandidate) |
| job index_rebuild · CLI okf index | Compiler.rebuild_index | RebuildIndex |
| job leiden | Compiler.detect_communities | DetectCommunities |
| POST /cockpit/promote | Curation.promote | PromoteToMemory |
| POST /cockpit/page/stale | Curation.mark_stale | MarkPageStale |
| GET /cockpit/quality · CLI okf lint | Curation.lint | LintBundle |
| GET /cockpit/review | Curation.weekly_review | ComputeWeeklyReview |
| job review_weekly | Curation.publish_review | PublishWeeklyReview |
| job reflect | Curation.reflect | ReflectOnUsage |
| GET /cockpit/reflect | Curation.reflect_candidates | usage_candidates (puro) |
