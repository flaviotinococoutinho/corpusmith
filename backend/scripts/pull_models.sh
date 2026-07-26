#!/usr/bin/env bash
# Baixa os modelos locais adequados A ESTA máquina (ADR-42).
#
# O modelo de chat não é fixo: a config declara uma ESCADA de preferência
# e o roteador escolhe em tempo de execução a primeira entrada instalada
# que caiba em `memory_fraction` da RAM. Este script faz a AQUISIÇÃO
# correspondente — baixa o maior modelo da escada que a máquina consegue
# rodar, em vez de baixar um que só vai paginar.
#
# Tamanhos declarados (pesos, medidos no registry em 2026-07):
#   qwen3-vl:8b-instruct  6.14 GB   → pede ~16 GB de RAM
#   qwen3-vl:4b-instruct  3.30 GB   → pede ~8 GB
#   qwen3-vl:2b-instruct  1.89 GB   → alcança máquinas menores
#
# Override explícito: LLMWIKI_CHAT_MODEL / LLMWIKI_EMBED_MODEL.
set -euo pipefail

EMBED="${LLMWIKI_EMBED_MODEL:-nomic-embed-text}"
FRACTION="${LLMWIKI_MEMORY_FRACTION:-0.6}"

if ! command -v ollama >/dev/null; then
  echo "ollama não encontrado — instale em https://ollama.com" >&2
  exit 1
fi

ram_bytes() {
  if [[ "$(uname)" == "Darwin" ]]; then sysctl -n hw.memsize
  else awk '/MemTotal/ {print $2 * 1024}' /proc/meminfo
  fi
}

pick_chat() {
  # maior entrada cujos pesos caibam em FRACTION * RAM
  local budget
  budget=$(awk -v r="$(ram_bytes)" -v f="$FRACTION" 'BEGIN{printf "%.0f", r*f}')
  local -a names=(qwen3-vl:8b-instruct qwen3-vl:4b-instruct qwen3-vl:2b-instruct)
  local -a sizes=(6140000000 3300000000 1890000000)
  for i in "${!names[@]}"; do
    if (( budget >= sizes[i] )); then echo "${names[i]}"; return 0; fi
  done
  return 1
}

CHAT="${LLMWIKI_CHAT_MODEL:-}"
if [[ -z "$CHAT" ]]; then
  if ! CHAT=$(pick_chat); then
    echo "AVISO: nenhum modelo de chat da escada cabe em ${FRACTION} da RAM" >&2
    echo "  ($(ram_bytes) bytes totais). Sem chat local, /ask degrada para" >&2
    echo "  extrativo/abstenção — comportamento suportado, não é falha." >&2
    echo "  Force um modelo com LLMWIKI_CHAT_MODEL=<tag> se quiser tentar." >&2
    CHAT=""
  fi
fi

if [[ -n "$CHAT" ]]; then
  ollama pull "$CHAT"
fi
ollama pull "$EMBED"
echo "modelos prontos: ${CHAT:-<nenhum chat>}, $EMBED"

# mostra a resolução efetiva — a fonte da verdade é o roteador, não este script
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$HERE/../.venv/bin/python" ]]; then
  "$HERE/../.venv/bin/python" -m llmwiki.cli models || true
fi
