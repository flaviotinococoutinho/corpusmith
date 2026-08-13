"""UndoCurationAct — arrepender-se sem sair do produto (F1-PR2, ADR-41).

O rito é o ponto delicado desta fase, e é deliberadamente o INVERSO do
óbvio. `git revert` no worktree colocaria bytes no disco ANTES do gate do
Harness (`BundleWriter.write` roda o gate e SÓ ENTÃO escreve), e recuperar
de uma rejeição exigiria `checkout`/`reset` — exatamente as operações que
"invalidar-nunca-apagar" proíbe. Pior: `GitStore.commit` faz `add(A=True)`
sobre o kb inteiro, então um revert rejeitado e não limpo entraria no
PRÓXIMO commit de qualquer ato.

Portanto o undo NÃO reverte: ele LÊ o conteúdo anterior no commit pai do
ato, monta os `OKFDocument`s e passa pelo `write()` normal. O desfazer vira
**escrita para a frente** — gateada como qualquer outra, com um commit novo
e o commit desfeito ainda alcançável no histórico. E ele mesmo é registrado
como um ATO NOVO (`undoes`), nunca apagando a linha do ato original
(`undone_by`): invalidar-nunca-apagar vale também para o arrependimento.

LIMITE DECLARADO — desfazer uma CRIAÇÃO não é expressável aqui. Uma página
que não existia no commit pai só poderia ser "restaurada" removendo-a, e
`BundleWriter.remove` não roda o Harness: "gate inescapável" e "um commit"
deixariam de valer juntos. Em vez de escolher em silêncio qual invariante
cede, este ato RECUSA com motivo nomeado e aponta a saída legítima
(suceder ou invalidar a página criada). Nenhum ato da Fase 1 cria página,
então o limite hoje é teórico — mas é o PR que cria o primeiro que terá de
decidir, e não um usuário surpreendido.
"""
from __future__ import annotations
import json
from .base import CurationAct, CurationPreview
from ...kernel.curation import UndoNotExpressible
from ...okf.document import OKFDocument
from ...runtime.db import connect
from ...settings import Settings


class UndoCurationAct(CurationAct):
    ACT = "undo"
    LOG_KIND = "Update"

    def __init__(self, settings: Settings, act_id: int, *, notify=None):
        super().__init__(settings, notify)
        self._act_id = int(act_id)
        self._alvo: dict | None = None

    # ------------------------------------------------------------- leitura
    def _target(self) -> dict:
        if self._alvo is None:
            rt = connect(self._settings.app_support / "runtime.db")
            linha = rt.execute(
                "SELECT id, act, commit_sha, pages, undone_by "
                "FROM curation_acts WHERE id = ?", (self._act_id,)).fetchone()
            rt.close()
            if linha is None:
                raise KeyError(f"ato {self._act_id} não existe")
            self._alvo = dict(linha)
            self._alvo["pages"] = json.loads(self._alvo["pages"] or "[]")
        return self._alvo

    def _params(self) -> dict:
        return {"act_id": self._act_id}

    def _restaurados(self) -> tuple[list[OKFDocument], list[str]]:
        """Documentos com o conteúdo do commit PAI + páginas cujo estado
        anterior era 'ausente' (não expressável)."""
        alvo = self._target()
        if not alvo["commit_sha"]:
            raise UndoNotExpressible(
                f"ato {self._act_id} não tem commit associado (nada mudou "
                "no canônico) — não há o que desfazer")
        # A trilha é PROJEÇÃO (runtime.db, declarado não-reconstruível e
        # restaurável de backup); o Git é a AUTORIDADE. Quando as duas
        # discordam — runtime.db restaurado de um backup mais novo que o
        # bundle, por exemplo — o sha registrado pode não existir. Sem esta
        # guarda o GitPython vazava um ValueError cru ("SHA … could not be
        # resolved"), que virava 400 com mensagem interna: o DoD (AGENTS §9)
        # exige erro com código estável, e semanticamente isto é 409.
        if not self._writer.git.has_commit(alvo["commit_sha"]):
            raise UndoNotExpressible(
                f"o commit do ato {self._act_id} "
                f"({alvo['commit_sha'][:8]}) não existe neste repositório — "
                "a trilha (runtime.db) e o histórico (Git) divergiram, "
                "provavelmente por restauração de backup. O Git é a "
                "autoridade: nada será tocado.")
        pai = self._writer.git.parent_of(alvo["commit_sha"])
        if pai is None:
            raise UndoNotExpressible(
                "o ato é o commit raiz do bundle — não há estado anterior")
        docs, ausentes = [], []
        for page in alvo["pages"]:
            antes = self._writer.git.read_at(pai, f"bundle/{page}")
            if antes is None:
                ausentes.append(page)
                continue
            docs.append(OKFDocument.loads(page, antes))
        return docs, ausentes

    # --------------------------------------------------------------- hooks
    def _plan(self) -> CurationPreview:
        alvo = self._target()
        if alvo["undone_by"]:
            raise ValueError(
                f"ato {self._act_id} já foi desfeito pelo ato "
                f"{alvo['undone_by']}")
        docs, ausentes = self._restaurados()
        if ausentes:
            raise UndoNotExpressible(
                "desfazer a CRIAÇÃO de página não é expressável por escrita "
                f"para a frente: {', '.join(ausentes)}. Saída legítima: "
                "suceder ou invalidar a página criada (o histórico Git "
                "preserva tudo de qualquer modo).")
        # aviso honesto: um undo antigo sobrescreve trabalho posterior. O
        # diff do preview MOSTRA o que se perde; a nota NOMEIA o risco.
        posteriores = [d.rel_path for d in docs
                       if self._writer.git.changed_since(
                           alvo["commit_sha"], f"bundle/{d.rel_path}")]
        nota = (f"restaura o estado anterior ao ato {self._act_id} "
                f"({alvo['act']}) por escrita para a frente — o commit "
                f"{(alvo['commit_sha'] or '')[:8]} continua no histórico")
        if posteriores:
            nota += ("; ATENÇÃO: " + ", ".join(posteriores) +
                     " mudou depois deste ato — o diff mostra o que será "
                     "sobrescrito")
        preview = self._preview_write(docs, self.ACT, note=nota)
        return preview

    def _apply(self, preview: CurationPreview) -> dict:
        alvo = self._target()
        docs, _ = self._restaurados()
        resultado = self._writer.write(
            docs, log_kind=self.LOG_KIND,
            log_message=f"desfeito o ato {self._act_id} ({alvo['act']})",
            commit_message=f"undo: ato {self._act_id} ({alvo['act']})")
        return {**resultado, "undone_act": self._act_id}

    def _record_extra(self, conn, act_id: int) -> None:
        """Liga os dois lados do arrependimento na MESMA transação da
        trilha: o undo aponta para o que desfez e o original é MARCADO
        como desfeito — nunca apagado."""
        conn.execute("UPDATE curation_acts SET undoes = ? WHERE id = ?",
                     (self._act_id, act_id))
        conn.execute("UPDATE curation_acts SET undone_by = ? WHERE id = ?",
                     (act_id, self._act_id))
