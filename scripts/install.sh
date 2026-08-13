#!/usr/bin/env bash
# Instalação validada do Corpusmith (backend Python + cockpit Electron).
# Guia completo e solução de problemas: docs/12-instalacao.md
#
# Uso:
#   scripts/install.sh                 # backend + desktop
#   scripts/install.sh --backend-only  # só o backend (venv + CLI)
#   scripts/install.sh --with-tests    # roda a suíte (289 testes) ao final
#   scripts/install.sh --with-smoke    # bootstrap+seed+lint+doctor em HOME temporário
#   scripts/install.sh --docker        # valida compose e constrói a imagem
#
# Variáveis:
#   PYTHON=python3.12  força o interpretador do venv (senão: sonda 3.12→3.13→3.11→python3)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
DESKTOP="$ROOT/desktop"

BACKEND_ONLY=0; WITH_TESTS=0; WITH_SMOKE=0; WITH_DOCKER=0
for arg in "$@"; do
  case "$arg" in
    --backend-only) BACKEND_ONLY=1 ;;
    --with-tests)   WITH_TESTS=1 ;;
    --with-smoke)   WITH_SMOKE=1 ;;
    --docker)       WITH_DOCKER=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $arg (use --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '   ✅ %s\n' "$*"; }
warn() { printf '   ⚠️  %s\n' "$*"; }
die()  { printf '   ❌ %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- pré-requisitos
say "Pré-requisitos"
command -v git >/dev/null || die "git é obrigatório (bundle canônico é um repo Git)"
ok "git $(git --version | awk '{print $3}')"
# o bootstrap do bundle faz commit — identidade Git precisa existir
if ! git config --get user.email >/dev/null; then
  warn "git sem user.email — o bootstrap do bundle falha ao commitar."
  warn "configure: git config --global user.email voce@exemplo.com && git config --global user.name 'Seu Nome'"
fi

# ---------------------------------------------------------------- interpretador
# Homebrew Python 3.14 pode falhar no ensurepip (venv nasce sem pip) — por isso
# a sonda cria um venv DE VERDADE num diretório temporário antes de escolher.
probe_python() {
  local cand="$1" tmp
  command -v "$cand" >/dev/null 2>&1 || return 1
  tmp="$(mktemp -d)"
  if "$cand" -m venv "$tmp/v" >/dev/null 2>&1 && [ -x "$tmp/v/bin/pip" ]; then
    rm -rf "$tmp"; return 0
  fi
  rm -rf "$tmp"; return 1
}

say "Interpretador Python (>=3.11, com venv+pip funcionais)"
PY=""
if [ -n "${PYTHON:-}" ]; then
  probe_python "$PYTHON" || die "PYTHON=$PYTHON não cria venv com pip nesta máquina"
  PY="$PYTHON"
else
  for cand in python3.12 python3.13 python3.11 python3; do
    if probe_python "$cand"; then PY="$cand"; break; fi
    command -v "$cand" >/dev/null 2>&1 && warn "$cand existe mas não cria venv com pip — pulando"
  done
fi
[ -n "$PY" ] || die "nenhum Python >=3.11 utilizável encontrado (brew install python@3.12)"
"$PY" - <<'EOF' || die "Python < 3.11 (pyproject exige >=3.11)"
import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)
EOF
ok "usando $PY ($($PY --version 2>&1))"

# ---------------------------------------------------------------- backend
say "Backend — venv + instalação editável"
cd "$BACKEND"
[ -d .venv ] && warn "backend/.venv já existe — reutilizando (apague para recriar)"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q -U pip
.venv/bin/pip install -q -e ".[dev]"
chmod +x scripts/corpusmith scripts/corpusmithctl scripts/pull_models.sh scripts/install_daemon.sh
ok "corpusmith $(.venv/bin/python -c 'import corpusmith; print(corpusmith.__version__)') instalado em backend/.venv"

# ---------------------------------------------------------------- desktop
if [ "$BACKEND_ONLY" -eq 0 ]; then
  say "Desktop — dependências do cockpit Electron"
  command -v npm >/dev/null || die "npm é obrigatório para o desktop (Node 20+; use --backend-only para pular)"
  node - <<'EOF' || die "Node < 20 (CI usa 20; validado com 26)"
process.exit(parseInt(process.versions.node) >= 20 ? 0 : 1)
EOF
  cd "$DESKTOP"
  npm ci --no-audit --no-fund
  npx tsc --noEmit
  ok "npm ci + typecheck OK (node $(node --version))"
fi

# ---------------------------------------------------------------- docker (opcional)
if [ "$WITH_DOCKER" -eq 1 ]; then
  say "Docker — validação do compose e build da imagem"
  cd "$ROOT"
  COMPOSE=""
  if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose";
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
    warn "plugin 'docker compose' ausente; usando docker-compose standalone."
    warn "para habilitar o plugin: mkdir -p ~/.docker/cli-plugins && ln -sf \"\$(command -v docker-compose)\" ~/.docker/cli-plugins/docker-compose"
  else
    die "nem 'docker compose' nem 'docker-compose' encontrados"
  fi
  docker info >/dev/null 2>&1 || die "daemon Docker não está rodando"
  $COMPOSE config -q && ok "compose config válido"
  $COMPOSE build && ok "imagem corpusmith-corpusmith construída"
fi

# ---------------------------------------------------------------- testes (opcional)
if [ "$WITH_TESTS" -eq 1 ]; then
  say "Suíte de testes do backend"
  cd "$BACKEND"
  .venv/bin/python -m pytest tests -q
  ok "suíte verde"
fi

# ---------------------------------------------------------------- smoke (opcional)
if [ "$WITH_SMOKE" -eq 1 ]; then
  say "Smoke em HOME temporário (não toca ~/corpusmith)"
  SMOKE_HOME="$(mktemp -d)/corpusmith-home"
  export CORPUSMITH_HOME="$SMOKE_HOME"
  cd "$ROOT"
  backend/scripts/corpusmith okf bootstrap
  backend/scripts/corpusmith seed
  backend/scripts/corpusmith okf lint
  backend/scripts/corpusmith doctor
  backend/scripts/corpusmith epistemics lint
  rm -rf "$(dirname "$SMOKE_HOME")"
  unset CORPUSMITH_HOME
  ok "bootstrap+seed+lint+doctor+epistemics verdes"
fi

# ---------------------------------------------------------------- próximos passos
say "Instalação concluída — próximos passos"
cat <<'EOF'
   1. backend/scripts/corpusmith okf bootstrap   # cria ~/corpusmith (bundle Git)
   2. backend/scripts/corpusmith seed            # dados pré-definidos (idempotente)
   3. backend/.venv/bin/python -m corpusmith.daemon &   # API em 127.0.0.1:8377
      backend/scripts/corpusmithctl status              # confere o daemon
   4. cd desktop && npm run dev               # cockpit Electron
   Token do handshake: ~/corpusmith/state/daemon.json (header x-corpusmith-auth)
   Guia completo + solução de problemas: docs/12-instalacao.md
EOF
