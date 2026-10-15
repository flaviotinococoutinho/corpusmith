# 12 — Instalação e verificação do ambiente

> **Altitude:** fluxo · **Status:** vivo

Este guia prepara o backend Python, o cockpit Electron e o armazenamento
local. O instalador é [`scripts/install.sh`](../scripts/install.sh).

Os registros anteriores deste guia incluem execução em macOS arm64
(2026-07) e Linux x86_64 (2026-08). As versões e medições citadas pertencem
a essas verificações. Os comandos abaixo refletem os scripts versionados;
a instalação deve ser verificada novamente no seu ambiente.

## 0. O que é instalado

| Componente | Local | Conteúdo |
|---|---|---|
| Backend | `backend/.venv` | daemon FastAPI e CLI `corpusmith` |
| Cockpit | `desktop/node_modules` | dependências de Electron, Vite e React |
| Dados | `~/corpusmith` ou `$CORPUSMITH_HOME` | bundle Git, bancos SQLite e handshake |
| Docker opcional | imagem construída do backend | daemon e dados em volume |

Os comandos deste guia partem da raiz do repositório. Para obter o código:

```bash
git clone https://github.com/flaviotinococoutinho/corpusmith.git
cd corpusmith
```

## 1. Requisitos (versões validadas)

| Ferramenta | Requisito | Observação |
|---|---|---|
| Python | 3.11 ou posterior, com `venv` e `pip` funcionais | Python 3.12.12 foi usado na validação registrada; veja §7.1 |
| Node.js | 20 ou posterior | exigido para instalar e executar o cockpit |
| Git | instalado e com identidade configurada | o bootstrap do bundle cria um commit |
| Docker e Compose | opcionais para o daemon em container | `just verify` também usa `docker compose config -q` |
| Ollama | opcional | necessário para os modelos locais; veja §6 |
| Rust e Cargo | opcionais para o backend Python | necessários para construir e testar os componentes nativos |
| `just` | opcional | oferece os atalhos do `justfile` |

Para conferir a identidade Git, execute `git config user.name` e
`git config user.email`. Se estiverem ausentes, configure os valores usados
nos seus commits antes do bootstrap.

A memória necessária depende do modelo escolhido. As medições em máquina
com 8 GB estão em §6. Elas não constituem um requisito mínimo de memória
para toda carga de trabalho.

## 2. Caminho rápido

Instale os componentes e execute os testes do backend e o smoke de runtime:

```bash
scripts/install.sh --with-tests --with-smoke
```

O script também instala as dependências do desktop e executa o typecheck.
O smoke usa um diretório temporário próprio. Para executar todas as
verificações locais do projeto, siga §5.

| Opção | Efeito |
|---|---|
| `--backend-only` | pula a instalação do desktop |
| `--with-tests` | executa a suíte do backend |
| `--with-smoke` | executa bootstrap, seed, lint, doctor e lint epistêmico em dados temporários |
| `--docker` | valida o Compose e constrói a imagem |
| `PYTHON=python3.12` | variável de ambiente que seleciona o interpretador |

Sem `PYTHON`, o script testa candidatos criando um ambiente virtual
com `pip`. Isso permite rejeitar interpretadores cuja criação de `venv`
falha, como no caso de §7.1.

## 3. Caminho manual (o que o script faz)

Crie o ambiente virtual e instale o backend. O subshell mantém o terminal
na raiz do repositório:

```bash
(
  cd backend
  python3.12 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -e ".[dev]"
  chmod +x scripts/corpusmith scripts/corpusmithctl scripts/pull_models.sh scripts/install_daemon.sh
)
```

Crie o bundle e carregue os dados iniciais:

```bash
backend/scripts/corpusmith okf bootstrap
backend/scripts/corpusmith seed
```

O bootstrap cria o armazenamento em `~/corpusmith`. Para escolher outro
local, defina `CORPUSMITH_HOME` antes desses comandos e use o mesmo valor
em todos os processos que acessam os dados.

Execute o daemon em um terminal:

```bash
backend/.venv/bin/python -m corpusmith.daemon
```

Em outro terminal, na raiz do repositório, confira o status e abra o cockpit:

```bash
backend/scripts/corpusmithctl status
(cd desktop && npm ci && npm run dev)
```

O daemon usa `127.0.0.1:8377` por padrão. O cockpit lê o endereço e o token
no handshake em `state/daemon.json`.

Para instalar os extras opcionais no mesmo ambiente:

```bash
(cd backend && .venv/bin/pip install -e ".[parsers]")
(cd backend && .venv/bin/pip install -e ".[ml]")
```

`parsers` acrescenta os leitores de PDF e EPUB, executados em subprocesso
fora do binário empacotado. `ml` acrescenta sqlite-vec, igraph e leidenalg.

## 4. Caminho Docker

Valide a configuração e inicie o daemon:

```bash
docker compose config -q
docker compose up -d
docker compose exec corpusmith cat /data/state/daemon.json
```

O serviço usa o volume `corpusmith-data` e publica a porta 8377 apenas em
`127.0.0.1`. O arquivo de handshake contém o token de acesso à API.

Para iniciar também o serviço Ollama:

```bash
docker compose --profile ml up -d
```

Iniciar o Ollama não baixa os modelos. Se o plugin `docker compose` estiver
ausente, consulte §7.2.

## 5. Verificação — prove que a instalação funcionou

Na raiz do repositório, execute o conjunto local:

```bash
just verify
```

Sem `just`, execute os comandos equivalentes. Cada subshell retorna à raiz:

```bash
(cd backend && .venv/bin/python -m pytest tests -q)
(cd desktop && npx tsc --noEmit)
(cd desktop && npm test)
docker compose config -q
(cd backend && .venv/bin/python -m corpusmith.cli epistemics lint)
(cd backend && .venv/bin/python -m corpusmith.cli ontology lint)
```

Espere zero falhas nos testes, nenhum erro no typecheck ou na configuração
Compose e nenhum finding de erro nos linters. A lista de verificações está
em `architecture.toml [gate]`; `test_pr0_gate.py` compara esse contrato com
a CI e o `justfile`. A CI também executa verificações em ambientes próprios,
incluindo os componentes Rust e a construção e execução do binário PyInstaller.

A suíte isola chamadas ao Ollama por configuração em `tests/conftest.py`.
Use a saída do pytest para conferir resultados e skips. Para consultar a
versão e as contagens atuais dos registros, execute `just context`.

### Smoke de runtime

O instalador executa este smoke com `--with-smoke`. Para inspecionar as
operações manualmente, use dados temporários:

```bash
(
  export CORPUSMITH_HOME="$(mktemp -d)/corpusmith-smoke"
  backend/scripts/corpusmith okf bootstrap
  backend/scripts/corpusmith seed
  backend/scripts/corpusmith okf lint
  backend/scripts/corpusmith doctor
  backend/scripts/corpusmith epistemics lint
)
```

O bootstrap deve criar o bundle. O lint deve concluir sem erros e o doctor
deve retornar `"ok": true`. O subshell não altera o `CORPUSMITH_HOME` do
terminal principal; os dados temporários ficam disponíveis para inspeção.

### Smoke da API

Com o daemon de §3 em execução, leia o token do mesmo diretório de dados:

```bash
TOKEN="$(backend/.venv/bin/python -c 'import json, os; from pathlib import Path; home = Path(os.environ.get("CORPUSMITH_HOME", "~/corpusmith")).expanduser(); print(json.loads((home / "state/daemon.json").read_text())["token"])')"
curl -s -H "x-corpusmith-auth: $TOKEN" http://127.0.0.1:8377/health/full

curl -s -X POST -H "x-corpusmith-auth: $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"qual o preço do xilofone de titânio em Vega"}' \
  http://127.0.0.1:8377/ask
```

O health deve retornar `"ok": true`. Numa base que não cobre a pergunta,
o resultado esperado do `/ask` é `"answer": null` e `"abstained": true`.
Se o corpus recuperar conteúdo relacionado, inspecione as evidências em vez
de presumir esse resultado. Perguntas cobertas pelos dados iniciais podem
produzir uma resposta extrativa com `"via": "local:extractive"`.

A abstenção depende de uma heurística. Uma resposta aceita não constitui
prova de correção factual; veja [Contratos epistêmicos](11-epistemic-contracts.md).

## 6. Daemon como serviço (macOS e Linux) e modelos locais

Instale o serviço ou baixe os modelos de forma explícita:

```bash
backend/scripts/install_daemon.sh
backend/scripts/pull_models.sh
```

No macOS, o instalador cria o LaunchAgent `com.corpusmith.daemon`.
No Linux, cria a unidade systemd de usuário `corpusmith-daemon`. Consulte-a
com `systemctl --user status corpusmith-daemon` e os logs com
`journalctl --user -u corpusmith-daemon`.

Se não houver sessão systemd de usuário, o script informa a falha de ativação.
Use o daemon em primeiro plano, conforme §3, ou Docker, conforme §4.

### 6.1 O modelo de chat é uma ESCADA, não um nome fixo (ADR-42)

`models.local.chat` define uma ordem de preferência. O roteador escolhe a
primeira entrada instalada cujos pesos caibam na fração de memória
`memory_fraction`, cujo padrão é `0.6`. Consulte os candidatos em
[`backend/config/default.yaml`](../backend/config/default.yaml).

Inspecione a escolha e os motivos de recusa:

```bash
backend/scripts/corpusmith models
```

`ausente` indica modelo não instalado. `nao_cabe` indica pesos acima do
orçamento. O comando retorna código 1 se não houver modelo utilizável.
O roteador não baixa modelos durante uma consulta.

Na medição registrada em máquina com 8 GB, os pesos do
`qwen3-vl:8b-instruct` excederam o orçamento. A variante
`qwen3-vl:2b-instruct` foi a alternativa de menor consumo indicada pelo guia.
Tamanho dos pesos não inclui todos os custos da execução; confirme o consumo
e a latência na sua carga.

### 6.2 Variantes *thinking* precisam de orçamento de tokens

Na medição com `qwen3-vl:4b`, um `num_predict` curto consumiu o orçamento no
campo `thinking` e devolveu `response` vazio com `done_reason: "length"`.
O roteador trata a resposta vazia como `ModelUnavailable`.

Outra medição em máquina com 8 GB e 13% de memória livre registrou 41 s
para `num_predict=64`. Ela mostra que caber no orçamento de pesos não basta
para assegurar a latência do `/ask`. As variantes `-instruct` evitam o custo
do campo `thinking`, mas ainda exigem verificação de recursos e tempo.

Sem modelo utilizável, o caminho do `/ask` usa o extrativo ou a abstenção.
Durante chamadas demoradas, foi observada indisponibilidade temporária do
`/health`; use os logs para distinguir demora de modelo de falha do daemon.

## 7. Solução de problemas (encontrados de verdade)

### 7.1 `python3 -m venv` falha no ensurepip (Homebrew Python 3.14)

O sintoma registrado é `CalledProcessError` em `ensurepip`, com ambiente
virtual sem `pip`. Foi observado com Python 3.14.6 do Homebrew no macOS.

Use um interpretador que crie o ambiente completo:

```bash
brew install python@3.12
PYTHON=python3.12 scripts/install.sh
```

### 7.2 `docker: unknown command: docker compose`

O CLI pode estar sem o plugin Compose, mesmo com `docker-compose` instalado.
O instalador aceita o binário standalone. Para usá-lo diretamente:

```bash
docker-compose config -q
docker-compose up -d
```

### 7.3 API responde `401 {"detail": "token inválido"}`

Use `x-corpusmith-auth: <token>`. EventSource usa `?auth=<token>` porque
não envia headers customizados. A API não usa `Authorization: Bearer`
para esse token. Leia novamente `state/daemon.json` após reiniciar o daemon,
pois o token muda a cada inicialização.

### 7.4 `POST /ask` responde `422`

O campo obrigatório do JSON é `query`. Os campos opcionais são `deep`,
`local_only` e `as_of`. Enviar `question` no lugar de `query` não atende ao
contrato. A resposta de validação indica o campo inválido ou ausente.

### 7.5 Bootstrap falha ao commitar

Confira `git config user.name` e `git config user.email`. O bundle é um
repositório Git próprio e o bootstrap precisa de identidade para criar o
commit inicial. A imagem Docker já configura uma identidade.

### 7.6 Porta 8377 ocupada

Confira qual processo usa a porta antes de iniciar outro daemon. O handshake
identifica uma instância por diretório de dados. Pare o serviço anterior ou
altere `server.port` por configuração. No macOS, o serviço usa
`~/Library/LaunchAgents/com.corpusmith.daemon.plist`.

### 7.7 `/ask` se abstém em base recém-instalada

`abstained: true` com `gaps` informa que a evidência recuperada não passou
no critério de resposta. Confira os dados carregados pelo `seed`, compile
conteúdo pela Inbox e consulte de novo. O conjunto inicial não cobre
perguntas arbitrárias.

### 7.8 Ollama de pé, mas o modelo da config não existe

Se aparecer `HTTPStatusError: 404` em chamadas ao Ollama, confira os modelos
instalados e a resolução do roteador:

```bash
backend/scripts/corpusmith models
curl -s http://127.0.0.1:11434/api/tags
```

Para baixar o modelo selecionado pelo script, execute
`backend/scripts/pull_models.sh`. O processo `ollama serve` pode estar ativo
sem que o modelo configurado esteja instalado.

### 7.9 Índice de geração antiga depois de atualizar

Se o doctor apontar `INV-002` e indicar reconstrução de índice, execute:

```bash
backend/scripts/corpusmith backup create
backend/scripts/corpusmith doctor --repair
```

`index.db` é uma projeção reconstruível; o doctor só repara os itens que a
implementação declara reparáveis. Após atualizar o código, reinicie o daemon
para carregar a nova versão:

```bash
# macOS
launchctl kickstart -k gui/$(id -u)/com.corpusmith.daemon

# Linux
systemctl --user restart corpusmith-daemon
```

Confira a versão em `GET /health`.

### 7.10 `corpusmithctl`: "daemon não responde … handshake órfão"

Uma interrupção abrupta pode deixar `state/daemon.json` apontando para um
processo encerrado. Inicie o daemon de novo, em primeiro plano ou pelo
serviço. No encerramento normal, o processo remove o próprio handshake.
