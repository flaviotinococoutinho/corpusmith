"""Integração da instalação — auditoria executada (2026-08, re-mira).

Dois defeitos encontrados EXERCITANDO o caminho de instalação (bootstrap →
seed → daemon → ctl), não lendo código:

1. handshake órfão fazia `corpusmithctl status` despejar ~70 linhas de
   traceback do httpx em vez de um diagnóstico — e órfão era o caso COMUM,
   porque o daemon nunca removia `state/daemon.json` ao terminar;
2. o shutdown limpo agora remove o próprio handshake, mas SÓ o próprio:
   entre a liberação da porta e o unlink outro daemon pode ter subido e
   reescrito o arquivo — apagar o dele seria roubar o handshake de um
   processo vivo (CLI e Electron ficariam cegos para um daemon de pé).
"""
from __future__ import annotations
import ast
import json
import socket
from pathlib import Path

import pytest

from corpusmith import cli
from corpusmith.api.system import retire_handshake
from corpusmith.settings import Settings


def _porta_fechada() -> int:
    """Uma porta que o SO acabou de liberar — conexão será recusada."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


# ------------------------------------------------- 1. diagnóstico no CLI
def test_ctl_com_handshake_orfao_diagnostica_em_vez_de_traceback(
        tmp_path, monkeypatch):
    home = tmp_path / "corpusmith"
    (home / "state").mkdir(parents=True)
    (home / "state" / "daemon.json").write_text(json.dumps(
        {"port": _porta_fechada(), "host": "127.0.0.1", "token": "x"}))
    monkeypatch.setenv("CORPUSMITH_HOME", str(home))
    monkeypatch.delenv("CORPUSMITH_CONFIG", raising=False)

    with pytest.raises(SystemExit) as ei:
        cli.main(["status"])

    msg = str(ei.value)
    assert "não responde" in msg      # diagnóstico, não stacktrace…
    assert "daemon.json" in msg       # …que aponta o artefato órfão…
    assert "just daemon" in msg       # …e o ato de reparo


# --------------------------------------- 2. retirada do próprio handshake
def test_shutdown_limpo_remove_o_proprio_handshake(tmp_path):
    s = Settings(home=tmp_path / "c")
    hs = s.app_support / "daemon.json"
    hs.write_text(json.dumps({"token": "meu"}))
    retire_handshake(s, "meu")
    assert not hs.exists()


def test_retirada_nao_rouba_handshake_de_daemon_mais_novo(tmp_path):
    s = Settings(home=tmp_path / "c")
    hs = s.app_support / "daemon.json"
    hs.write_text(json.dumps({"token": "do_novo"}))
    retire_handshake(s, "meu")        # o meu já foi reescrito pelo novo
    assert hs.exists()                # o handshake do vivo fica


def test_retirada_e_idempotente_e_tolera_lixo(tmp_path):
    s = Settings(home=tmp_path / "c")
    retire_handshake(s, "meu")        # sem arquivo: silêncio
    hs = s.app_support / "daemon.json"
    hs.write_text("{lixo")            # corrompido: também silêncio
    retire_handshake(s, "meu")
    assert hs.exists()                # não sabe de quem é ⇒ não apaga


def test_daemon_chama_a_retirada_no_finally():
    """A retirada precisa estar LIGADA ao shutdown do daemon — um helper
    testado que ninguém chama seria teatro (mutação: remover a chamada)."""
    src = (Path(cli.__file__).parent / "daemon.py").read_text()
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    chamadas = [c.func.id
                for t in ast.walk(fn) if isinstance(t, ast.Try)
                for n in t.finalbody for c in ast.walk(n)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)]
    assert "retire_handshake" in chamadas
