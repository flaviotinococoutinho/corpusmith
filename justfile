# Corpusmith — automação de montagem (Parte V §10.4)

default:
    @just --list

# venv + instalação editável do backend (com extras de dev)
# PY: interpretador do venv (Homebrew 3.14 pode falhar no ensurepip —
# use `just bootstrap python3.12` ou `scripts/install.sh`, que sonda sozinho)
bootstrap PY="python3":
    cd backend && {{PY}} -m venv .venv && \
      .venv/bin/pip install -U pip && \
      .venv/bin/pip install -e ".[dev]"
    chmod +x backend/scripts/corpusmith backend/scripts/corpusmithctl \
      backend/scripts/pull_models.sh backend/scripts/install_daemon.sh

# instalação completa validada (backend + desktop + smoke) — docs/12-instalacao.md
install:
    scripts/install.sh --with-tests --with-smoke

# gate único do AGENTS.md §2 (imposto por architecture.toml [gate] e
# cruzado por test_pr0_gate.py — o gate tem UMA fonte, não quatro)
verify:
    cd backend && .venv/bin/python -m pytest tests -q
    cd desktop && npx tsc --noEmit
    cd desktop && npm test
    docker compose config -q
    cd backend && .venv/bin/python -m corpusmith.cli epistemics lint
    cd backend && .venv/bin/python -m corpusmith.cli ontology lint

# mapa determinístico do repositório para humanos e agentes (docs/10 §18.4):
# camadas, gate, invariantes, NFRs, registros, rotas, jobs, ADRs, docs, fila.
# Docs vivos citam ESTE comando em vez de cravar contagens (test_docs_contract).
context:
    cd backend && .venv/bin/python -m corpusmith.cli context

# baixa modelos locais (Ollama)
models:
    backend/scripts/pull_models.sh

# sobe o daemon em foreground
daemon:
    backend/.venv/bin/python -m corpusmith.daemon

# testes de contrato (golden bundles)
test:
    cd backend && .venv/bin/pytest -q

# lint do bundle (mesma fonte do painel Qualidade)
lint:
    backend/scripts/corpusmith okf lint

# reconstrói o index.db
index:
    backend/scripts/corpusmith okf index

# empacota o sidecar (PyInstaller onedir)
sidecar:
    cd backend && .venv/bin/pip install pyinstaller && \
      .venv/bin/pyinstaller build.spec

# app desktop em modo dev
app:
    cd desktop && npm run dev
