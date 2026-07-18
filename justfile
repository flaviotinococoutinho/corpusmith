# LLM Wiki — automação de montagem (Parte V §10.4)

default:
    @just --list

# venv + instalação editável do backend (com extras de dev)
# PY: interpretador do venv (Homebrew 3.14 pode falhar no ensurepip —
# use `just bootstrap python3.12` ou `scripts/install.sh`, que sonda sozinho)
bootstrap PY="python3":
    cd backend && {{PY}} -m venv .venv && \
      .venv/bin/pip install -U pip && \
      .venv/bin/pip install -e ".[dev]"
    chmod +x backend/scripts/llmwiki backend/scripts/llmwikictl \
      backend/scripts/pull_models.sh backend/scripts/install_daemon.sh

# instalação completa validada (backend + desktop + smoke) — docs/12-instalacao.md
install:
    scripts/install.sh --with-tests --with-smoke

# gate único do AGENTS.md §2: testes + typecheck do cockpit + compose
verify:
    cd backend && .venv/bin/python -m pytest tests -q
    cd desktop && npx tsc --noEmit
    docker compose config -q

# baixa modelos locais (Ollama)
models:
    backend/scripts/pull_models.sh

# sobe o daemon em foreground
daemon:
    backend/.venv/bin/python -m llmwiki.daemon

# testes de contrato (golden bundles)
test:
    cd backend && .venv/bin/pytest -q

# lint do bundle (mesma fonte do painel Qualidade)
lint:
    backend/scripts/llmwiki okf lint

# reconstrói o index.db
index:
    backend/scripts/llmwiki okf index

# empacota o sidecar (PyInstaller onedir)
sidecar:
    cd backend && .venv/bin/pip install pyinstaller && \
      .venv/bin/pyinstaller build.spec

# app desktop em modo dev
app:
    cd desktop && npm run dev
