"""Ponto de entrada do binário empacotado (PR-0.1).

O `build.spec` apontava direto para `src/corpusmith/daemon.py`, e o PyInstaller
executa o arquivo indicado como `__main__` — sem pacote pai. Como `daemon.py`
usa imports RELATIVOS (`from . import __version__`), o binário construía e
morria na primeira linha:

    ImportError: attempted relative import with no known parent package

Medido: o `.dmg` que um terceiro instalasse subiria o sidecar, ele sairia com
código 1, e o app cairia no `SidecarFailure` — indistinguível de "venv
ausente". Ninguém percebeu porque **nada nunca executou o binário**: a receita
`just sidecar` já falhava antes, na construção.

Este arquivo existe para ser o `__main__`: import ABSOLUTO, que carrega
`corpusmith` como pacote de verdade.
"""
from corpusmith.daemon import main

if __name__ == "__main__":
    main()
