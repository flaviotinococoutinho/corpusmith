"""usecases/curate/ — o ATO DE CURADORIA humano (F1, docs/15 · ADR-41).

Até aqui existia UM caminho de escrita (`okf/writer.py`) e ele só era
dirigido por use cases de MÁQUINA: nenhuma operação humana de suceder,
invalidar, fundir, editar, linkar ou desfazer existia no produto — a
resolução acontecia fora do app, editando YAML à mão. Este pacote é o
eixo humano, irmão de `MachinePageUseCase`: mesmo gate inescapável, mesmo
writer, mesma trilha — com PREVIEW obrigatório antes de qualquer efeito.

O registro `ACTS` é a tabela fechada que a facade, a API e o CLI usam para
resolver um nome de ato; acrescentar um ato é acrescentar um arquivo aqui
e uma entrada abaixo — preview, `curation_acts`, endpoint e CLI vêm de
graça, herdados do esqueleto.
"""
from __future__ import annotations
from .base import CurationAct, CurationPreview
from .invalidate import InvalidatePage
from .link import LinkPages, UnlinkPages
from .supersede import SupersedePage
from .undo import UndoCurationAct, UndoNotExpressible

ACTS: dict[str, type[CurationAct]] = {
    "supersede": SupersedePage,
    "invalidate": InvalidatePage,
    "link": LinkPages,
    "unlink": UnlinkPages,
    "undo": UndoCurationAct,
}

__all__ = ["ACTS", "CurationAct", "CurationPreview", "InvalidatePage",
           "LinkPages", "SupersedePage", "UndoCurationAct",
           "UndoNotExpressible", "UnlinkPages"]
