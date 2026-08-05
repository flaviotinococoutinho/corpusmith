"""Recursos empacotados vs. em árvore de código (PR-0.1).

Três módulos resolviam caminho de recurso contando `parents[]` a partir de
`__file__`: o schema SQL (`runtime/db.py`), o `config/default.yaml`
(`settings.py`) e o `epistemics.toml` (`harness/epistemics.py`). Isso funciona
na árvore de código e **quebra dentro do binário do PyInstaller**, que põe os
`datas` sob `_internal/` — um nível diferente do que a contagem espera.

Medido no binário empacotado, depois de corrigidos os defeitos de construção:

    FileNotFoundError: .../llmwiki-server/db/schema_runtime.sql

O arquivo estava em `.../llmwiki-server/_internal/db/schema_runtime.sql`. O
daemon morria antes de abrir a porta — e ninguém tinha visto porque o binário
**nunca chegou a ser construído** (a receita falhava antes, ver `build.spec`).

`sys._MEIPASS` é o idioma do PyInstaller para "onde os recursos foram parar".
Fora do binário ele não existe, e cada chamador diz de onde contar na árvore.
"""
from __future__ import annotations
import sys
from pathlib import Path


def frozen() -> bool:
    """Rodando de dentro de um binário empacotado?"""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resource(*partes: str, source_root: Path) -> Path:
    """Caminho de um recurso empacotado.

    `source_root` é onde o recurso vive na ÁRVORE DE CÓDIGO — quem chama sabe
    disso e o caminho fica explícito, em vez de escondido numa contagem de
    `parents[]` que ninguém revalida quando um módulo muda de lugar.
    """
    if frozen():
        return Path(sys._MEIPASS).joinpath(*partes)   # noqa: SLF001
    return source_root.joinpath(*partes)
