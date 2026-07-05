from __future__ import annotations
import re

_RULES = [
    (re.compile(r"[“”]"), '"'),      # aspas curvas → retas (docs técnicos)
    (re.compile(r"[‘’]"), "'"),
    (re.compile(r"…"), "..."),            # …
    (re.compile(r" "), " "),              # NBSP
    (re.compile(r"[ \t]{2,}"), " "),           # espaços múltiplos
    (re.compile(r" +$", re.M), ""),            # trailing spaces
]

def fix_typography(text: str) -> str:
    """Só é aplicada em páginas de máquina, fora das regiões protegidas
    (o engine mascara antes). Grafia de marca vence capitalização de início de
    frase por convenção: 'iOS', 'macOS', 'gRPC' permanecem — o gazetteer já
    devolve a forma oficial em qualquer posição."""
    for rx, rep in _RULES:
        text = rx.sub(rep, text)
    return text
