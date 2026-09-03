#!/usr/bin/env bash
# Instala o daemon como serviço do usuário: launchd (macOS) ou systemd (Linux).
# Antes da auditoria de 2026-08 só existia o ramo macOS — em Linux o caminho
# era "suba na mão ou use Docker", sem o script dizer isso a ninguém.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "$HERE/.." && pwd)"

case "$(uname -s)" in
  Darwin)
    PLIST_SRC="$BACKEND/launchd/com.corpusmith.daemon.plist"
    PLIST_DST="$HOME/Library/LaunchAgents/com.corpusmith.daemon.plist"
    mkdir -p "$HOME/corpusmith/logs" "$HOME/Library/LaunchAgents"
    sed -e "s|__BACKEND__|$BACKEND|g" -e "s|__HOME__|$HOME|g" \
        "$PLIST_SRC" > "$PLIST_DST"
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    launchctl load "$PLIST_DST"
    echo "daemon instalado: $PLIST_DST"
    ;;
  Linux)
    UNIT_SRC="$BACKEND/systemd/corpusmith-daemon.service"
    UNIT_DST="$HOME/.config/systemd/user/corpusmith-daemon.service"
    mkdir -p "$HOME/.config/systemd/user"
    sed "s|__BACKEND__|$BACKEND|g" "$UNIT_SRC" > "$UNIT_DST"
    # `systemctl --user` exige uma sessão systemd de usuário (DBus). Em
    # container/SSH sem lingering ela pode não existir — a unidade fica
    # escrita e o script FALHA ALTO dizendo o que resta, em vez de fingir.
    if systemctl --user daemon-reload 2>/dev/null; then
      systemctl --user enable --now corpusmith-daemon.service
      echo "daemon instalado: $UNIT_DST"
      echo "status: systemctl --user status corpusmith-daemon"
      echo "logs:   journalctl --user -u corpusmith-daemon -f"
    else
      echo "unidade escrita em $UNIT_DST, mas 'systemctl --user' não está" >&2
      echo "disponível nesta sessão (sem sessão systemd de usuário)." >&2
      echo "habilite depois com: systemctl --user enable --now corpusmith-daemon" >&2
      echo "ou rode direto: $BACKEND/.venv/bin/python -m corpusmith.daemon" >&2
      exit 1
    fi
    ;;
  *)
    echo "SO não suportado: $(uname -s)." >&2
    echo "rode direto: $BACKEND/.venv/bin/python -m corpusmith.daemon" >&2
    exit 1
    ;;
esac
