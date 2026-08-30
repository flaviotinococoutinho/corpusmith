# 12 — Instalação e verificação do ambiente

> Guia **validado em máquina real** (macOS arm64, 2026-07; revalidado em
> Linux x86_64, 2026-08 — bootstrap, seed, lint, doctor, epistemics, daemon
> e `/ask`): cada comando daqui foi executado e o resultado esperado
> registrado. O instalador automatizado é
> [`scripts/install.sh`](../scripts/install.sh); este documento é a versão
> explicada + solução de problemas.

## 0. O que é instalado

| Componente | Onde | O quê |
|---|---|---|
| backend (`corpusmith`) | `backend/.venv` | daemon FastAPI + CLI (`corpusmith`, `corpusmithctl`) |
| desktop (cockpit) | `desktop/node_modules` | Electron + Vite + React |
| dados do usuário | `~/corpusmith` (ou `$CORPUSMITH_HOME`) | bundle Git + 5 bancos SQLite + handshake |
| Docker (opcional) | imagem `corpusmith-corpusmith` | daemon containerizado, dados no volume |

## 1. Requisitos (versões validadas)

| Ferramenta | Mínimo | Validado com | Nota |
|---|---|---|---|
| Python | 3.11 | **3.12.12** | 3.14.6 do Homebrew falhou (§7.1) |
| Node.js | 20 | 26.3.1 | só para o desktop |
| git | qualquer recente | 2.54 | precisa de `user.email`/`user.name` (o bundle commita) |
| RAM | 8 GB | **8 GB** (Mac14,3) | define QUAL modelo local roda (§6); 16 GB+ para o preferido |
| Docker + Compose | Compose v2 | 29.2 / Compose 5.1.4 | opcional (§4) |
| Ollama | — | 0.32.1 | **opcional**: sem modelo utilizável tudo degrada para extrativo/abstenção (verificado) |
| Rust (cargo) | — | 1.9x | opcional: compute plane nativo (ADR-39); sem ele roda o fallback Python |
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
chmod +x scripts/corpusmith scripts/corpusmithctl scripts/pull_models.sh scripts/install_daemon.sh

# primeira execução (cria ~/corpusmith; use CORPUSMITH_HOME para outro lugar)
scripts/corpusmith okf bootstrap           # → "bundle criado"
scripts/corpusmith seed                    # → seed ok: {'terms': 7, 'quotations': 3, 'facts': 11}
                                        #   (+pipelines; golden eval: {'pages': 7, 'cases': 12})

# daemon
.venv/bin/python -m corpusmith.daemon &    # → "corpusmith daemon em http://127.0.0.1:8377"
scripts/corpusmithctl status               # → pending_jobs, budget, instance

# desktop (outro terminal)
cd desktop && npm ci && npm run dev     # cockpit conecta via handshake
```

Extras opcionais do backend: `pip install -e ".[parsers]"` (PDF/EPUB,
AGPL — fica fora do binário) e `".[ml]"` (sqlite-vec, igraph/leiden).

## 4. Caminho Docker

```bash
docker compose config -q     # valida o arquivo
docker compose up -d         # build + daemon; bootstrap+seed automáticos no boot
docker compose exec corpusmith cat /data/state/daemon.json   # host/porta/token
docker compose --profile ml up -d   # + Ollama em rede interna
```

A porta publica **só em 127.0.0.1** — local-first vale também no Docker.
Se `docker compose` (plugin) não existir mas `docker-compose` sim, ver §7.2.

## 5. Verificação — prove que a instalação funcionou

Gate completo (o mesmo do CI e do `AGENTS.md` §2; a lista é presa por
`architecture.toml [gate]` + `test_pr0_gate.py` — atalho: `just verify`):

```bash
cd backend && .venv/bin/python -m pytest tests -q   # → todos passam (858 na v2.0)
cd desktop && npx tsc --noEmit                      # → sem erros
cd desktop && npm test                              # → smoke da UI verde
docker compose config -q                            # → sem saída = ok
cd backend && .venv/bin/python -m corpusmith.cli epistemics lint  # → 23 mecanismo(s)
cd backend && .venv/bin/python -m corpusmith.cli ontology lint    # → sem erros
```

A CI roda ainda `cargo test --workspace --manifest-path native/Cargo.toml`
(kernels nativos — 8 passed) e constrói+executa o binário PyInstaller.
A contagem da suíte cresce a cada versão; o que importa é **zero falhas**.

A suíte é **hermética**: não conversa com o Ollama da máquina
(`tests/conftest.py` aponta o roteador para uma porta morta). Isso é
proposital — antes o resultado dependia de quais modelos o dev tinha
instalado, e 25 testes ficavam vermelhos numa máquina com Ollama de pé e
o modelo da config ausente.

Smoke de runtime (não destrutivo — use um HOME descartável):

```bash
export CORPUSMITH_HOME=/tmp/corpusmith-smoke
backend/scripts/corpusmith okf bootstrap    # bundle criado
backend/scripts/corpusmith seed             # seed ok (idempotente)
backend/scripts/corpusmith okf lint         # 0 finding(s), 0 erro(s)
backend/scripts/corpusmith doctor           # {"ok": true, ...}
backend/scripts/corpusmith epistemics lint  # 23 mecanismo(s) na v2.0; os avisos
    # `mechanism_promised` são dívida DECLARADA (contrato prometido em doc
    # e ainda não escrito) — não são erro de instalação
```

Smoke da API (daemon rodando):

```bash
TOKEN=$(python3 -c "import json,os;print(json.load(open(os.path.expandvars('$CORPUSMITH_HOME/state/daemon.json')))['token'])")
curl -s -H "x-corpusmith-auth: $TOKEN" http://127.0.0.1:8377/health/full | head
# → {"ok": true, "instance": {...}, "stacks": {"runtime.db": {"integrity": "ok", ...}}}

curl -s -X POST -H "x-corpusmith-auth: $TOKEN" -H "Content-Type: application/json" \
     -d '{"query":"qual o preço do xilofone de titânio em Vega"}' http://127.0.0.1:8377/ask
# → {"answer": null, "abstained": true, "gaps": [...], "via": "none"}
#   ← abstenção honesta: NADA na base cobre a pergunta
```

Atenção ao escolher a pergunta de teste: desde a v1.6.3 o `seed` traz 7
páginas avaliáveis (golden eval), então perguntas que TOCAM esse conteúdo
respondem extrativo (`"via": "local:extractive"`) — inclusive "pergunta sem
cobertura", que casa com a página *Abstenção epistêmica* que descreve o
próprio mecanismo. Os dois desfechos são instalação sadia; fabricação é que
nunca acontece.

```bash
```

## 6. Daemon como serviço (macOS e Linux) e modelos locais

```bash
backend/scripts/install_daemon.sh    # macOS: launchd agent (com.corpusmith.daemon)
                                     # Linux: unidade systemd DE USUÁRIO
                                     #   (systemctl --user status corpusmith-daemon;
                                     #    logs: journalctl --user -u corpusmith-daemon)
backend/scripts/pull_models.sh       # baixa o modelo adequado A ESTA máquina
```

Em Linux sem sessão systemd de usuário (container, SSH sem *lingering*) o
script escreve a unidade e **falha alto** dizendo o que resta — o caminho
manual (`python -m corpusmith.daemon`) e o Docker (§4) continuam valendo.

### 6.1 O modelo de chat é uma ESCADA, não um nome fixo (ADR-42)

`models.local.chat` declara uma **ordem de preferência**. Em tempo de
execução o roteador escolhe a primeira entrada que esteja **instalada** e
cujos pesos **caibam** em `memory_fraction` (default `0.6`) da RAM total:

| Candidato | Pesos | Pede |
|---|---|---|
| `qwen3-vl:8b-instruct` | 6,14 GB | ~16 GB de RAM |
| `qwen3-vl:4b-instruct` | 3,30 GB | ~8 GB |
| `qwen3-vl:4b` | 3,30 GB | ~8 GB (variante *thinking*, ver §6.2) |
| `qwen3-vl:2b-instruct` | 1,89 GB | máquinas menores |
| `qwen2.5:7b-instruct` | 4,70 GB | compat com instalações < v1.9 |

Duas regras deliberadas:

- **o roteador nunca baixa modelo sozinho** — uma consulta não pode
  disparar download de gigabytes; aquisição é ato explícito
  (`pull_models.sh`);
- **pedir modelo maior que a RAM não é otimismo, é paginação** — por isso
  o orçamento veta em vez de tentar.

Inspecione a decisão (e por que cada candidato foi recusado):

```bash
backend/scripts/corpusmith models
# → {"resolved_chat": "qwen3-vl:4b", "ram_total_gb": 8.59,
#    "memory_budget_gb": 5.15,
#    "ladder": [{"candidate": "qwen3-vl:8b-instruct", "status": "ausente"}, ...]}
```

Numa máquina de 8 GB o `8b-instruct` é recusado mesmo se estiver baixado
(`status: "nao_cabe"`) — 6,14 GB de pesos não entram em 5,15 GB de
orçamento. Exit code 1 significa "nenhum modelo utilizável".

### 6.2 Variantes *thinking* precisam de orçamento de tokens

Medido no `qwen3-vl:4b`: com `num_predict` curto o modelo gasta todo o
orçamento no campo `thinking` e devolve `response` **vazio** com
`done_reason: "length"`. Como `reconcile_candidate` pede 32 tokens e
`detect_communities` 160, isso é alcançável de verdade. O roteador trata
resposta vazia como `ModelUnavailable` — degrada para o extrativo em vez
de propagar vazio como se fosse síntese. Prefira as variantes
`-instruct`, que não gastam orçamento raciocinando.

**Caber em disco não é caber em uso.** Medido na máquina de 8 GB com o
modelo residente e memória livre em 13%: `num_predict=64` levou **41 s**
(~1,5 tok/s). Com o orçamento real do `/ask` (1024–1536 tokens) isso
estoura o timeout de 300 s do roteador, que vira `ModelUnavailable` e
degrada para o extrativo. Ou seja: o veto por tamanho (§6.1) é condição
necessária, não suficiente — numa máquina de 8 GB o caminho realista para
ter síntese local é o `qwen3-vl:2b-instruct` (1,89 GB, sem *thinking*).
Sintoma correlato: uma chamada dessas **bloqueia o daemon** por dezenas
de segundos (o `/health` fica sem responder até ela terminar).

Sem modelo utilizável o `/ask` **não quebra**: responde extrativo ou se
abstém (`abstained: true`) — verificado tanto sem Ollama quanto com
Ollama de pé e modelo ausente.

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

O header de auth é **`x-corpusmith-auth: <token>`** (ou `?auth=<token>` —
existe porque EventSource não envia headers), **não** `Authorization:
Bearer`. O token efêmero vive em `$CORPUSMITH_HOME/state/daemon.json` e muda
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
Pare a antiga (`launchctl unload ~/Library/LaunchAgents/com.corpusmith.daemon.plist`
ou mate o processo) ou mude `server.port` via override de config.

### 7.7 `/ask` se abstém em base recém-instalada

Não é erro: `abstained: true` com `gaps` é o contrato de abstenção
(LongMemEval) — nunca resposta fabricada. A base seedada cobre só as 7
páginas do golden eval (v1.6.3); qualquer pergunta fora delas se abstém.
Compile conteúdo (inbox → `compile`) e pergunte de novo.

### 7.8 Ollama de pé, mas o modelo da config não existe

Sintoma (encontrado nesta máquina): jobs `embed` falhando em série e
`HTTPStatusError: 404 ... /api/embeddings` ou `/api/generate` no log.
`ollama serve` responde no socket, então a instalação *parecia* sadia —
mas o modelo pedido nunca foi baixado. Diagnostique com:

```bash
backend/scripts/corpusmith models            # resolved_chat: null ⇒ nada utilizável
curl -s http://127.0.0.1:11434/api/tags   # o que existe de fato
```

**Correção**: `backend/scripts/pull_models.sh` (escolhe pela RAM, §6.1).
A partir do ADR-42 esse estado degrada em vez de estourar: o roteador só
considera modelo instalado e converte falha de modelo em
`ModelUnavailable`. Antes, o `HTTPStatusError` vazava e derrubava o
`/ask` com 500.

### 7.9 Índice de geração antiga depois de atualizar

Sintoma: `doctor` com `ok: false` e `INV-002 … índice de geração antiga
(g2:… ≠ g4:…) — rebuild`. Uma versão nova mudou a chave de geração do
índice. `index.db` é **projeção** reconstruível do bundle (INV-DATA-003),
então o reparo é seguro:

```bash
backend/scripts/corpusmith backup create    # opcional, mas barato
backend/scripts/corpusmith doctor --repair  # → ok: true
```

Depois de atualizar, **reinicie o daemon** — o processo antigo continua
com o código velho em memória e pode responder 500 ao ler dados já
migrados: `launchctl kickstart -k gui/$(id -u)/com.corpusmith.daemon`
(macOS) ou `systemctl --user restart corpusmith-daemon` (Linux).
Confirme com `curl -s .../health` que `version` é a esperada.

### 7.10 `corpusmithctl`: "daemon não responde … handshake órfão"

Sintoma (encontrado exercitando este guia): o daemon caiu sem passar pelo
shutdown limpo (SIGKILL, crash, queda da máquina) e `state/daemon.json`
ficou para trás apontando uma porta morta. O CLI diagnostica em vez de
estourar traceback — e a mensagem já diz o reparo: suba o daemon de novo
(`just daemon`, ou o serviço do §6). O shutdown limpo remove o próprio
handshake (e SÓ o próprio: um daemon novo que tenha reescrito o arquivo
nunca perde o dele para o antigo que está saindo).
