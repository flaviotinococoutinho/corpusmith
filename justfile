# LLM Wiki — automação de montagem (Parte V §10.4)

default:
    @just --list

# venv + instalação editável do backend (com extras de dev)
bootstrap:
    cd backend && python3 -m venv .venv && \
      .venv/bin/pip install -U pip && \
      .venv/bin/pip install -e ".[dev]"
    chmod +x backend/scripts/llmwiki backend/scripts/llmwikictl \
      backend/scripts/pull_models.sh backend/scripts/install_daemon.sh

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
