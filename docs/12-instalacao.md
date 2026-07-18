# 12 — Instalação e verificação do ambiente

> Guia **validado em máquina real** (macOS arm64, 2026-07): cada comando
> daqui foi executado e o resultado esperado registrado. O instalador
> automatizado é [`scripts/install.sh`](../scripts/install.sh); este
> documento é a versão explicada + solução de problemas.

## 0. O que é instalado

| Componente | Onde | O quê |
|---|---|---|
| backend (`llmwiki`) | `backend/.venv` | daemon FastAPI + CLI (`llmwiki`, `llmwikictl`) |
| desktop (cockpit) | `desktop/node_modules` | Electron + Vite + React |
| dados do usuário | `~/llmwiki` (ou `$LLMWIKI_HOME`) | bundle Git + 5 bancos SQLite + handshake |
| Docker (opcional) | imagem `brain-compiler-llmwiki` | daemon containerizado, dados no volume |

## 1. Requisitos (versões validadas)

| Ferramenta | Mínimo | Validado com | Nota |
|---|---|---|---|
| Python | 3.11 | **3.12.12** | 3.14.6 do Homebrew falhou (§7.1) |
| Node.js | 20 | 26.3.1 | só para o desktop |
| git | qualquer recente | 2.54 | precisa de `user.email`/`user.name` (o bundle commita) |
| Docker + Compose | Compose v2 | 29.2 / Compose 5.1.4 | opcional (§4) |
| Ollama | — | não instalado | **opcional**: sem ele tudo degrada para modo extrativo/abstenção (verificado) |
| `just` | — | não usado | opcional: o `justfile` é só açúcar sobre os comandos abaixo |

## 2. Caminho rápido

```bash
scripts/install.sh --with-tests --with-smoke   # instala backend+desktop e prova que funcionou
```

Flags: `--backend-only` (sem Electron) · `--docker` (valida compose + build)
· `PYTHON=python3.12` (força interpretador). O script **sonda** o Python
criando um venv real antes de escolher — imune ao problema do §7.1.

## 3. Caminho manual (o que o script faz)

```bash
# backend
cd backend
python3.12 -m venv .venv                # ver §7.1 antes de usar python3
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev]"
chmod +x scripts/llmwiki scripts/llmwikictl scripts/pull_models.sh scripts/install_daemon.sh

# primeira execução (cria ~/llmwiki; use LLMWIKI_HOME para outro lugar)
scripts/llmwiki okf bootstrap           # → "bundle criado"
scripts/llmwiki seed                    # → seed ok: {'terms': 7, 'quotations': 3, 'facts': 11} (+pipelines)

# daemon
.venv/bin/python -m llmwiki.daemon &    # → "llmwiki daemon em http://127.0.0.1:8377"
scripts/llmwikictl status               # → pending_jobs, budget, instance

# desktop (outro terminal)
cd desktop && npm ci && npm run dev     # cockpit conecta via handshake
```

Extras opcionais do backend: `pip install -e ".[parsers]"` (PDF/EPUB,
AGPL — fica fora do binário) e `".[ml]"` (sqlite-vec, igraph/leiden).

## 4. Caminho Docker

```bash
docker compose config -q     # valida o arquivo
docker compose up -d         # build + daemon; bootstrap+seed automáticos no boot
docker compose exec llmwiki cat /data/state/daemon.json   # host/porta/token
docker compose --profile ml up -d   # + Ollama em rede interna
```

A porta publica **só em 127.0.0.1** — local-first vale também no Docker.
Se `docker compose` (plugin) não existir mas `docker-compose` sim, ver §7.2.

## 5. Verificação — prove que a instalação funcionou

Gate completo (o mesmo do CI e do `AGENTS.md` §2 — `just verify` roda os três):

```bash
cd backend && .venv/bin/python -m pytest tests -q   # → 289 passed
cd desktop && npx tsc --noEmit                      # → sem erros
docker compose config -q                            # → sem saída = ok
```

Smoke de runtime (não destrutivo — use um HOME descartável):

```bash
export LLMWIKI_HOME=/tmp/llmwiki-smoke
backend/scripts/llmwiki okf bootstrap    # bundle criado
backend/scripts/llmwiki seed             # seed ok (idempotente)
backend/scripts/llmwiki okf lint         # 0 finding(s), 0 erro(s)
backend/scripts/llmwiki doctor           # {"ok": true, ...}
backend/scripts/llmwiki epistemics lint  # 7 mecanismo(s), 0 finding(s)
```

Smoke da API (daemon rodando):

```bash
TOKEN=$(python3 -c "import json,os;print(json.load(open(os.path.expandvars('$LLMWIKI_HOME/state/daemon.json')))['token'])")
curl -s -H "x-llmwiki-auth: $TOKEN" http://127.0.0.1:8377/health/full | head
# → {"ok": true, "instance": {...}, "stacks": {"runtime.db": {"integrity": "ok", ...}}}

curl -s -X POST -H "x-llmwiki-auth: $TOKEN" -H "Content-Type: application/json" \
     -d '{"query":"pergunta sem cobertura"}' http://127.0.0.1:8377/ask
# → {"answer": null, "abstained": true, "gaps": [...]}  ← abstenção honesta é o esperado
```

## 6. Daemon como serviço (macOS) e modelos locais

```bash
backend/scripts/install_daemon.sh    # launchd agent (com.llmwiki.daemon)
backend/scripts/pull_models.sh       # ollama pull qwen2.5:7b-instruct + nomic-embed-text
```

Sem Ollama o `/ask` **não quebra**: responde extrativo ou se abstém
(`abstained: true`) — comportamento verificado nesta máquina sem Ollama.

## 7. Solução de problemas (encontrados de verdade)

### 7.1 `python3 -m venv` falha no ensurepip (Homebrew Python 3.14)

Sintoma: `CalledProcessError` dentro de `ensurepip` ao criar o venv — o
venv nasce sem `pip`. Observado com Python 3.14.6 do Homebrew (macOS).
**Correção**: use `python3.12` (ou 3.13/3.11): `brew install python@3.12`
e `PYTHON=python3.12 scripts/install.sh`. O instalador já sonda e pula
interpretadores quebrados sozinho.

### 7.2 `docker: unknown command: docker compose`

O CLI do Docker está sem o plugin Compose v2, mas o binário standalone
existe (Homebrew instala `docker-compose`). **Correção**:

```bash
mkdir -p ~/.docker/cli-plugins
ln -sf "$(command -v docker-compose)" ~/.docker/cli-plugins/docker-compose
docker compose version    # → Docker Compose version 5.x
```

### 7.3 API responde `401 {"detail": "token inválido"}`

O header de auth é **`x-llmwiki-auth: <token>`** (ou `?auth=<token>` —
existe porque EventSource não envia headers), **não** `Authorization:
Bearer`. O token efêmero vive em `$LLMWIKI_HOME/state/daemon.json` e muda
a cada boot do daemon.

### 7.4 `POST /ask` responde `422`

Contrato do corpo: `{"query": str, "deep"?: bool, "local_only"?: bool,
"as_of"?: str}` — o campo é `query` (não `question`). O 422 aponta o
campo faltante; corpo malformado nunca vira 500 (coberto por
`tests/test_api_validation.py`).

### 7.5 Bootstrap falha ao commitar

O bundle é um repo Git e o bootstrap faz o commit inicial — configure
`git config --global user.email … && git config --global user.name …`
(no Docker a imagem já configura).

### 7.6 Porta 8377 ocupada

Só existe UMA instância por HOME (`state/daemon.json` é o handshake).
Pare a antiga (`launchctl unload ~/Library/LaunchAgents/com.llmwiki.daemon.plist`
ou mate o processo) ou mude `server.port` via override de config.

### 7.7 `/ask` se abstém em base recém-instalada

Não é erro: `abstained: true` com `gaps` é o contrato de abstenção
(LongMemEval) — a base seedada ainda não tem cobertura para perguntas
livres. Compile conteúdo (inbox → `compile`) e pergunte de novo.
