"""Rotas dos atos de curadoria (F1-PR1) — montadas à parte.

`api/cockpit.py` já tem 640 linhas e é tocado por quase todo pacote da
Fase 1; montar os atos aqui (mesmo precedente de `mount_cockpit`) faz os
PRs seguintes acrescentarem ato sem disputar aquele arquivo.

`dry_run` é OBRIGATÓRIO no corpo, sem default silencioso: um ato que
escreve porque o cliente esqueceu um campo é exatamente o oposto do que
esta fase existe para construir.
"""
from __future__ import annotations
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from ..facades.curation_acts import CurationActsFacade
from ..kernel.curation import UndoNotExpressible
from ..settings import Settings


class CurationActBody(BaseModel):
    """Borda TIPADA: nada de dict cru atravessando camada (AGENTS.md §5)."""
    act: str
    params: dict = {}
    dry_run: bool


def mount_curation(app: FastAPI, s: Settings, bus, auth) -> None:
    facade = CurationActsFacade(s)

    @app.get("/curation/acts", dependencies=[Depends(auth)])
    def kinds():
        """Os atos disponíveis — tabela fechada, para a UI não adivinhar."""
        return {"acts": facade.kinds()}

    @app.get("/curation/history", dependencies=[Depends(auth)])
    def history(limit: int = 30):
        return {"acts": facade.history(limit)}

    @app.post("/curation/act", dependencies=[Depends(auth)])
    def run_act(body: CurationActBody):
        try:
            if body.dry_run:
                return facade.preview(body.act, body.params)
            return facade.act(
                body.act, body.params,
                notify=lambda t, d: bus.emit("curation", t, d))
        except UndoNotExpressible as e:
            # 409: o estado anterior existe, mas não é alcançável por
            # escrita para a frente — recusar nomeando o motivo é mais
            # honesto que escolher em silêncio qual invariante cede
            raise HTTPException(409, str(e))
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        except FileNotFoundError as e:
            raise HTTPException(404, f"página não encontrada: {e}")
