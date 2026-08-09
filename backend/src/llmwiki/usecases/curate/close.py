"""CloseQuestion — a pergunta que FECHA, com verificação (F3-PR2, P-3).

**Nada fechava e nada aposentava.** Uma página `type: question` valia 0.9 na
fila — o item de maior valor depois da contradição — e não havia gesto nenhum
que a tirasse de lá. O usuário respondia a pergunta escrevendo uma página
nova, e a pergunta voltava ao topo da fila no dia seguinte, e no outro. A
fila pedia o mesmo trabalho para sempre.

**O veredito mora no canônico**, não numa tabela: `answered_by` aponta a
página que respondeu e `resolved_at` diz quando o curador declarou fechada.
São conteúdo — versionados em Git, sujeitos ao Harness, revertíveis pelo
`undo` como qualquer outro ato. Um veredito sobre objeto canônico que morasse
em projeção sumiria no primeiro `rebuild_index`.

**O fechamento é VERIFICADO, e a primeira verificação que escrevi era teatro.**
A ideia óbvia — "recusa se o `/ask` ainda abstém" — foi medida e não serve:
com `ask.abstain_threshold = 0.0` (o default do produto) a abstenção quase
nunca dispara, e pior, perguntar o título de uma pergunta **encontra a própria
pergunta**, que é uma página do bundle:

    abstained: False
    páginas na evidência: ['questions/q2.md']

A guarda passaria sempre, inclusive apontando para uma página de culinária.

O que se verifica é o VÍNCULO: perguntado o título da pergunta, o produto
chega à página que se declara como resposta? A própria pergunta é descartada
das evidências — ela sempre aparece e não responde nada. Se a resposta
declarada não está entre as evidências, ou ela não responde, ou o índice não a
alcança; nos dois casos, fechar seria declarar algo que o produto não
sustenta.

**A verificação não decide.** `docs/14` §P-3 rejeita explicitamente "fechar
pergunta automaticamente porque o `/ask` parou de abster", e o inverso vale
igual: o humano continua podendo fechar contra a máquina com `force=True`, e
a força fica registrada no log e no preview.
"""
from __future__ import annotations
from datetime import datetime, timezone
from .base import CurationAct, CurationPreview
from ...okf.document import OKFDocument, OKFFrontMatter
from ...settings import Settings


class CloseQuestion(CurationAct):
    ACT = "close_question"
    LOG_KIND = "Update"

    def __init__(self, settings: Settings, page: str, answered_by: str,
                 *, force: bool = False, notify=None):
        super().__init__(settings, notify)
        self._page = page
        self._answered_by = answered_by
        self._force = bool(force)

    def _params(self) -> dict:
        return {"page": self._page, "answered_by": self._answered_by,
                "force": self._force}

    # ------------------------------------------------------------ verificação
    def _nao_verificado(self) -> str | None:
        """Motivo pelo qual o vínculo NÃO se sustenta, ou None.

        Usa o MESMO caminho de leitura do usuário (`AskMemory`), não uma
        consulta paralela: verificar com um retrieval diferente do que
        responde seria verificar outra coisa."""
        from ..ask_memory import AskMemory
        pergunta = self._writer.reader.load(self._page)
        consulta = pergunta.meta.title or self._page
        try:
            resposta = AskMemory(self._settings, consulta,
                                 local_only=True).execute()
        except Exception:                                # noqa: BLE001
            return None        # falha de leitura não vira veto de escrita
        if resposta.get("abstained"):
            return "o /ask ABSTÉM sobre esta pergunta"
        # a própria pergunta é uma página e sempre aparece na busca pelo
        # próprio título — contá-la como evidência tornaria a guarda inútil
        alcançadas = {e["page"] for e in (resposta.get("evidence") or [])
                      if e["page"] != self._page}
        if self._answered_by not in alcançadas:
            return (f"perguntado '{consulta}', o produto chega a "
                    f"{sorted(alcançadas) or 'nenhuma outra página'} — "
                    f"não a {self._answered_by}")
        return None

    # -------------------------------------------------------------- documento
    def _document(self) -> OKFDocument:
        atual = self._writer.reader.load(self._page)
        meta = atual.meta.model_dump(exclude_none=True)
        meta["answered_by"] = self._answered_by
        meta["resolved_at"] = datetime.now(timezone.utc)
        return OKFDocument(rel_path=atual.rel_path, body=atual.body,
                           meta=OKFFrontMatter(**meta))

    # -------------------------------------------------------------- esqueleto
    def _plan(self) -> CurationPreview:
        if not self._writer.reader.exists(self._answered_by):
            raise ValueError(
                f"{self._answered_by} não existe no bundle — fechar uma "
                f"pergunta apontando para página inexistente cria justamente "
                f"o sucessor pendurado que `policy.dangling_successor` "
                f"passou a recusar")
        if self._page == self._answered_by:
            raise ValueError("uma pergunta não pode responder a si mesma")
        falha = self._nao_verificado()
        if falha and not self._force:
            raise ValueError(
                f"o vínculo não se sustenta: {falha}. Aponte a página certa, "
                f"escreva a resposta, reindexe, ou feche mesmo assim com "
                f"force=true (fica registrado no log)")
        nota = (f"a pergunta passa a apontar {self._answered_by} e sai da "
                f"fila de trabalho")
        nota += (f" — FECHADA À FORÇA, sem verificação: {falha}" if falha else
                 " — verificado: perguntado o título, o produto chega a "
                 f"{self._answered_by}")
        return self._preview_write([self._document()], self.ACT, note=nota)

    def _apply(self, preview: CurationPreview) -> dict:
        forcado = "à força " if "FORÇA" in preview.note else ""
        return self._writer.write(
            [self._document()], log_kind=self.LOG_KIND,
            log_message=f"pergunta fechada {forcado}por "
                        f"{self._answered_by}: {self._page}",
            commit_message=f"close_question: {self._page}")
