# 04 · Tecnologias e contratos de infraestrutura

> COM O QUE o sistema é feito — e, mais importante, o CONTRATO que cada
> tecnologia cumpre. Trocar a tecnologia preservando o contrato é sempre
> permitido; violar o contrato nunca é.

## 1. Armazenamento

### SQLite (runtime.db + index.db)
- **Contrato**: `runtime/db.py:connect()` é a ÚNICA porta — aplica WAL,
  `synchronous=NORMAL`, row_factory, o schema idempotente
  (`CREATE IF NOT EXISTS` de `db/schema_*.sql`) e as migrações
  (`_migrate`: ALTERs guardados por `PRAGMA table_info`). Qualquer
  consumidor conecta sem cerimônia.
- **Dois bancos, dois destinos**: `runtime.db` é operacional (fila,
  eventos, ledger, heat, outcomes, proveniência) — perdê-lo perde
  histórico operacional, não conhecimento. `index.db` é 100% DERIVADO —
  apagar e rodar `okf index` reconstrói tudo (chunks, FTS, arestas,
  entidades, níveis, pontes).
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
- Handshake do daemon: `~/llmwiki/state/daemon.json` (porta + token
  efêmero, chmod 600).

## 2. Backend Python

| Tecnologia | Papel | Contrato/nota |
|---|---|---|
| **pydantic v2** | `OKFFrontMatter` (extra="allow", timestamp/valid_at/invalid_at coagidos a datetime), `Settings` | validação na borda; kernel NÃO usa pydantic (teste de arquitetura) |
| **python-frontmatter** | parse/dump YAML+Markdown | `dumps` serializa datetimes como ISO (mode="json" no model_dump) |
| **FastAPI + uvicorn** | API local (127.0.0.1) | auth por token efêmero em header `x-llmwiki-auth` OU `?auth=` (EventSource não envia headers) |
| **sse-starlette** | `GET /events` | eventos do bus com keepalive ping 15s |
| **httpx** | CLI→daemon, router→Ollama/Anthropic | timeouts explícitos sempre |
| **GitPython** | GitStore | ver §1 |
| **stdlib pura** | `kernel/`, `normalize/` | re, zlib, math, unicodedata, datetime — garantido por AST scan |

### Threading e concorrência
Worker/Scheduler são threads daemon; `JobQueue`/`EventBus` protegem o
SQLite compartilhado com locks Python (CPython ≥3.11: sqlite3
threadsafety=3). Slots por classe de job: `heavy` (compile, lora,
leiden, ocr) = 1; `light` = 2.

### Extras opcionais (nunca requisitos)
- `llmwiki[parsers]` — pymupdf4llm, ebooklib (**AGPL**): executados em
  SUBPROCESSO por `ingestion/extract.py`; **jamais no binário
  PyInstaller** (excludes explícitos no build.spec).
- `llmwiki[ml]` — sqlite-vec, igraph, leidenalg: Leiden de verdade e
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
  preload/contextBridge (`window.llmwiki.handshake()`).
- **daemonClient.ts**: singleton com `connect()` (poll de /health),
  header de auth, e um método por endpoint. EventSource usa `?auth=`.
- **Vite**: config em `vite.config.mts` (ESM-only por causa do plugin
  Tailwind v4) com `vite-plugin-electron` buildando main+preload CJS.
- **Painéis**: Dashboard, ChatEvidence (+PromoteDialog), Inbox, Explorer,
  Quality, Processes — todos consomem apenas o daemonClient.

## 5. Implantação

- **PyInstaller onedir** (`build.spec`): `dist/llmwiki-server/`;
  hiddenimports para uvicorn/sse; datas = config + schemas SQL; AGPL
  excluído.
- **electron-builder**: `extraResources` embute o sidecar em
  `resources/backend/`; macOS exige hardenedRuntime + notarização (o
  Gatekeeper mata sidecar não assinado).
- **launchd** (`launchd/com.llmwiki.daemon.plist` +
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
