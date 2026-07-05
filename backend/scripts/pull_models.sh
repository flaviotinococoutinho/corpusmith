#!/usr/bin/env bash
# Baixa os modelos locais configurados (Ollama precisa estar instalado)
set -euo pipefail
CHAT="${LLMWIKI_CHAT_MODEL:-qwen2.5:7b-instruct}"
EMBED="${LLMWIKI_EMBED_MODEL:-nomic-embed-text}"
if ! command -v ollama >/dev/null; then
  echo "ollama não encontrado — instale em https://ollama.com" >&2
  exit 1
fi
ollama pull "$CHAT"
ollama pull "$EMBED"
echo "modelos prontos: $CHAT, $EMBED"
