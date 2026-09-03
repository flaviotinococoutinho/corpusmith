"""ComputeStability — a projeção "o que menos muda" (RFC-006, V3).

**Camadas, e por que cada pedaço mora onde mora.** A REGRA (sentidos de
mudança separados, exclusões, ordenação) é pura e vive em
`kernel/stability.py`; a LEITURA de história é do `GitStore` (okf, onde o
Git pode existir); este use case é só a casca: lê as duas fontes, chama o
kernel e persiste a projeção — nenhuma decisão de domínio acontece aqui.

**Fonte declarada: bundle + Git, e NADA de runtime.db.** A escolha compra
uma propriedade: a projeção é 100% re-derivável do canônico (INV-DATA-003
vale para ela como vale para o índice). Misturar `reconcile_log` ou
`curation_acts` daria um número "mais rico" que não se reconstrói de um
clone — e `backup_restore` deixaria de conseguir prometer o que promete.

**Custo, dito em voz alta.** `git log --name-only` percorre a história
inteira a cada execução — O(commits). Para corpus local isso é milissegundos;
se um dia doer, o resíduo de custo é a fase F7 (rebaixada de propósito na
fila da RFC-006 §6), e a resposta é incremental a partir do checkpoint, não
cache escondido aqui.

**Frescor de graça.** A derivação `stability` está declarada em
`kernel/checkpoints.py:DERIVATIONS` — o doctor a verifica, o CLI a lista e
a obsolescência transitiva a considera, sem invariante novo. `absent` não é
defeito (instalação nova); `stale` significa "o bundle andou desde o último
cálculo", e a resposta é re-executar este use case.
"""
from __future__ import annotations
from dataclasses import asdict
from .base import UseCase
from ..kernel.stability import consolidar
from ..okf.bundle import BundleReader
from ..okf.git_store import GitStore
from ..runtime.checkpoints import record
from ..runtime.db import connect
from ..settings import Settings

#: O GitStore versiona `kb/` inteiro; as páginas vivem em `kb/bundle/`.
_PREFIXO_BUNDLE = "bundle/"


class ComputeStability(UseCase):
    """Recomputa e persiste `page_stability`; devolve o ranking.

    Idempotente e determinística para o mesmo HEAD — rodar duas vezes
    produz a mesma tabela e o mesmo checkpoint. `limit` corta só o RETORNO
    (a persistência é sempre completa: a projeção serve outros leitores)."""

    def __init__(self, settings: Settings, *, limit: int | None = None):
        self._settings = settings
        self._limit = max(1, int(limit)) if limit else None

    def execute(self) -> dict:
        kb = self._settings.path("knowledge")
        reader = BundleReader(kb / "bundle")
        frontmatter = {d.rel_path: d.meta.model_dump(exclude_none=True)
                       for d in reader.iter_concepts()}
        # projeção é LEITURA: sem repositório, a resposta é "sem história"
        # — jamais `git init` por efeito colateral (GitStore.__init__
        # inicializa; achado de QA adversarial)
        if (kb / ".git").exists():
            git = GitStore(kb)
            head = git.head()
            historico = {
                caminho[len(_PREFIXO_BUNDLE):]: registro
                for caminho, registro in git.edit_history().items()
                if caminho.startswith(_PREFIXO_BUNDLE)}
        else:
            head, historico = None, {}
        ranking = consolidar(historico, frontmatter)

        if head is not None:
            self._persistir(ranking, head)
            record(self._settings, "stability", head,
                   detail={"pages": len(ranking)})

        visiveis = ranking[:self._limit] if self._limit else ranking
        return {"pages": len(ranking), "head": head,
                "stability": [asdict(e) for e in visiveis]}

    def _persistir(self, ranking, head: str) -> None:
        idx = connect(self._settings.app_support / "index.db")
        try:
            idx.execute("DELETE FROM page_stability")
            idx.executemany(
                "INSERT INTO page_stability(rel_path, edits, first_commit_at,"
                " last_edit_at, lifecycle, computed_from) VALUES (?,?,?,?,?,?)",
                [(e.rel_path, e.edicoes, e.primeira_em, e.ultima_em,
                  e.ciclo, head) for e in ranking])
            idx.commit()
        finally:
            idx.close()
