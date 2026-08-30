# 04 · Tecnologias e contratos de infraestrutura

> COM O QUE o sistema é feito — e, mais importante, o CONTRATO que cada
> tecnologia cumpre. Trocar a tecnologia preservando o contrato é sempre
> permitido; violar o contrato nunca é.

## 1. Armazenamento

### SQLite (5 bancos: runtime · index · cold · cognitive · reference)
- **Contrato**: `runtime/db.py:connect()` é a ÚNICA porta — aplica WAL,
  `synchronous=NORMAL`, row_factory, o schema idempotente
  (`CREATE IF NOT EXISTS` de `db/schema_*.sql`) e as migrações
  (`_migrate`: ALTERs guardados por `PRAGMA table_info`). Qualquer
  consumidor conecta sem cerimônia. (A spec BC-ENG-001 §5.2 propõe uma
  `StoragePolicy` por store — hoje o `synchronous` é uniforme; ver
  [`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md) §5.2.)
- **Cinco bancos, autoridades distintas** (`DB_SCHEMAS` em `runtime/db.py`):
  `runtime.db` operacional (fila, eventos, ledger, heat, outcomes,
  proveniência); `index.db` 100% DERIVADO — apagar e rodar `okf index`
  reconstrói tudo (chunks, FTS, arestas, entidades, níveis, pontes);
  `cold.db` base fria compactada (v0.12); `cognitive.db` experiência
  cognitiva separada (v0.19); `reference.db` referência do mundo
  relacional (v0.22). Só `index.db` é projeção sem autoridade; os demais
  guardam estado não-derivável. Detalhe de tabelas: [`06-referencia.md`](06-referencia.md) §3.
- **FTS5**: virtual tables `chunks_fts` e `fts_levels` com
  `content=`-tables + triggers de sincronização. bm25() nativo (menor =
  melhor). Consultas sempre via `fts_terms()` (quote + OR + stopwords
  pt/en + números preservados).
- **Versão mínima**: 3.42 (usa `unixepoch('subsec')` em defaults).

### Git (GitPython) — o knowledge base
- **Contrato** (`okf/git_store.py`): `commit()` (stage tudo, retorna sha
  ou None se limpo), `has_commit(sha)` (valida referências citadas),
  `head()`. Repo separado do repo do código — o kb do usuário tem
  histórico próprio.
- Usado como: trilha de auditoria, backstop de reversibilidade, fonte do
  histórico por página (`git log -- bundle/<path>` no Explorer).

### Sistema de arquivos
- Bundle OKF = diretório de Markdown (legível sem o sistema).
- Lock de escrita inter-processo: `fcntl.flock` em `.write.lock`
  (daemon × CLI concorrentes).
- Handshake do daemon: `~/corpusmith/state/daemon.json` (porta + token
  efêmero, chmod 600).

## 2. Backend Python

| Tecnologia | Papel | Contrato/nota |
|---|---|---|
| **pydantic v2** | `OKFFrontMatter` (extra="allow", timestamp/valid_at/invalid_at coagidos a datetime), `Settings` | validação na borda; kernel NÃO usa pydantic (teste de arquitetura) |
| **python-frontmatter** | parse/dump YAML+Markdown | `dumps` serializa datetimes como ISO (mode="json" no model_dump) |
| **FastAPI + uvicorn** | API local (127.0.0.1) | auth por token efêmero em header `x-corpusmith-auth` OU `?auth=` (EventSource não envia headers) |
| **sse-starlette** | `GET /events` | eventos do bus com keepalive ping 15s |
| **httpx** | CLI→daemon, router→Ollama/Anthropic | timeouts explícitos sempre |
| **GitPython** | GitStore | ver §1 |
| **stdlib pura** | `kernel/`, `normalize/` | re, zlib, math, unicodedata, datetime — garantido por AST scan |

### Threading e concorrência
Worker/Scheduler são threads daemon; `JobQueue`/`EventBus` protegem o
SQLite compartilhado com locks Python (CPython ≥3.11: sqlite3
threadsafety=3). Slots por classe de job: `heavy` (compile, lora,
leiden, ocr, pipeline) = 1; `light` = 2.

### Extras opcionais (nunca requisitos)
- `corpusmith[parsers]` — pymupdf4llm, ebooklib (**AGPL**): executados em
  SUBPROCESSO por `ingestion/extract.py`; **jamais no binário
  PyInstaller** (excludes explícitos no build.spec).
- `corpusmith[ml]` — sqlite-vec, igraph, leidenalg: Leiden de verdade e
  vetores; fallbacks stdlib cobrem a ausência.

## 3. Modelos (models/router.py)

Ordem de decisão do `complete()`:
1. privacidade `local_only` ⇒ NUNCA API (poda dura);
2. orçamento: `Governor.allow_api()` sobre o ledger do dia
   (`budget.daily_usd`);
3. disponibilidade: Ollama local (`/api/tags` como health) → API
   Anthropic (ANTHROPIC_API_KEY) → `ModelUnavailable` (quem chama decide
   o fallback — o ask tem o extrativo, o compile tem o passthrough).

Retorno `{"text", "via", "usd"}`; `via` (`local:<m>` | `api:<m>`)
alimenta `generated_via` — a proveniência nasce no router. Toda chamada
de API grava tokens/USD no `ledger`.

## 4. Desktop (Electron + Vite + React + Tailwind v4)

- **Processo**: main (`electron/main.ts`) sobe o sidecar
  (`sidecar.ts`: binário PyInstaller empacotado OU venv em dev OU
  conecta a daemon já vivo), lê o handshake e o expõe ao renderer via
  preload/contextBridge (`window.corpusmith.handshake()`).
- **daemonClient.ts**: singleton com `connect()` (poll de /health),
  header de auth, e um método por endpoint. EventSource usa `?auth=`.
- **live.ts** (v0.11): UMA assinatura SSE compartilhada por todos os
  painéis + snapshot de /status em polling — alimenta a StatusBar global
  (daemon · fila · orçamento · ticker de eventos) e os steppers de
  pipeline do Inbox/Processos via os eventos `page.stage`.
- **Vite**: config em `vite.config.mts` (ESM-only por causa do plugin
  Tailwind v4) com `vite-plugin-electron` buildando main+preload CJS.
- **Painéis** (13 abas em `App.tsx:TABS`): Estado (Dashboard), Consulta
  (ChatEvidence +PromoteDialog), Inbox, Corpus (Explorer), Grafo, Indicadores
  (Insights), Memória, Cognição, Foco, Curadoria, Qualidade, Processos,
  Integridade (Doctor, F-UI) — todos consomem apenas o daemonClient. *(A consolidação em 3 níveis —
  essencial/análise/avançado — é a frente UX-2 do backlog.)*

## 5. Implantação

- **PyInstaller onedir** (`build.spec`): `dist/corpusmith-server/`;
  hiddenimports para uvicorn/sse; datas = config + schemas SQL; AGPL
  excluído.
- **electron-builder**: `extraResources` embute o sidecar em
  `resources/backend/`; macOS exige hardenedRuntime + notarização (o
  Gatekeeper mata sidecar não assinado).
- **launchd** (`launchd/com.corpusmith.daemon.plist` +
  `scripts/install_daemon.sh`): daemon como LaunchAgent com KeepAlive.
- **justfile**: bootstrap, models, daemon, test, lint, index, sidecar,
  app — o operador não decora comandos.

## 6. Regras de ouro da infraestrutura

1. Nenhuma dependência nova sem justificar contra o fallback stdlib.
2. Nada de rede em caminho crítico local (Ollama é localhost; API é
   opt-in por privacidade+orçamento).
3. Artefato derivado nunca é fonte de verdade (index.db, page_overlay,
   communities, graph_bridges — todos recomputáveis).
4. Todo segredo é efêmero e local (token por sessão do daemon; nunca em
   arquivo versionado).
5. Migração de schema é idempotente e roda em todo connect() — não
   existe "script de migração a lembrar".
