"""PracticalCases — "que caso prático sustenta este conceito?" (V5).

**A consulta.** Lê as arestas TIPADAS (`graph_edges.rel`, escritas por ato
humano) nas duas direções: o conceito que declara `applies_to` um caso, e
o caso que declara `exemplifies` um conceito. Exigir que o curador escreva
sempre do lado "certo" seria burocracia disfarçada de ontologia — ele
escreve do lado em que está, e a consulta junta.

Link SEM relação não entra: "estas duas páginas se falam" não é "esta se
aplica àquela", e misturar as duas devolveria o grafo inteiro como
resposta prática.

**A medição, e é ela que dá o nome ao pacote.** A RFC-004 §6 declarou três
condições para reabrir o nível da AFIRMAÇÃO (o nível 3, vazio, da escada
de `docs/28`), e a primeira é **medir uma consulta que a granularidade de
página responde errado, em vez de imaginá-la**. Esta é a consulta. O custo
é medido assim: uma página-alvo que carrega DOIS OU MAIS sujeitos fortes
distintos (identificadores e normas — a mesma noção de sujeito da RFC-005)
torna "aplica-se a esta página" ambíguo: não se sabe a qual afirmação o
conceito se aplica. A fração dessas é o número — não a opinião — que a
reentrada pede.

O que a medição NÃO é: prova de que o nível 3 vale a pena. É evidência do
CUSTO da granularidade atual sobre as arestas que existem hoje. Zero
aresta ⇒ `ambiguous_fraction: None`, nunca `0.0`: "medido e ótimo" e "nada
medido" não podem ter a mesma cara (a lição da V4).
"""
from __future__ import annotations

from .base import UseCase
from ..kernel.semantics import RELACOES, inversa_de
from ..runtime.db import connect
from ..settings import Settings

#: Sujeitos fortes que tornam uma página "multi-assunto" para efeito da
#: medição. É a MESMA lista de kinds da RFC-005/V1 (identificador
#: acadêmico e norma) porque é a mesma noção de sujeito — inventar uma
#: segunda aqui seria criar dois donos da palavra "sujeito".
_KINDS_DE_SUJEITO = ("identifier", "standard")


class PracticalCases(UseCase):
    """Casos práticos de um conceito + a medição do custo do nível."""

    def __init__(self, settings: Settings, page: str):
        self._settings = settings
        self._page = page

    def execute(self) -> dict:
        idx = connect(self._settings.app_support / "index.db")
        try:
            saindo = [dict(r) for r in idx.execute(
                "SELECT dst AS page, rel FROM graph_edges "
                "WHERE src = ? AND rel IS NOT NULL", (self._page,))]
            entrando = [dict(r) for r in idx.execute(
                "SELECT src AS page, rel FROM graph_edges "
                "WHERE dst = ? AND rel IS NOT NULL", (self._page,))]
            casos = self._juntar(saindo, entrando)
            medicao = self._medir(idx, casos)
        finally:
            idx.close()
        return {"page": self._page, "cases": casos, "measurement": medicao}

    def _juntar(self, saindo: list[dict], entrando: list[dict]) -> list[dict]:
        """`via` diz de que lado a declaração foi feita — o leitor precisa
        saber se foi o conceito que reivindicou o caso ou o contrário."""
        casos = [{"page": r["page"], "rel": r["rel"], "via": "direta"}
                 for r in saindo if r["rel"] in RELACOES]
        casos += [{"page": r["page"], "rel": r["rel"], "via": "inversa"}
                  for r in entrando
                  if r["rel"] in RELACOES and inversa_de(r["rel"])]
        return sorted(casos, key=lambda c: (c["page"], c["rel"]))

    def _medir(self, idx, casos: list[dict]) -> dict:
        """O custo da granularidade de PÁGINA, em número (RFC-004 §6)."""
        nota = ("fração das páginas-alvo que carregam 2+ sujeitos fortes: "
                "nelas, 'aplica-se a esta página' não diz a QUAL afirmação "
                "o conceito se aplica — é o custo medido de o nível da "
                "afirmação (docs/28, nível 3) ainda não existir")
        if not casos:
            return {"edges": 0, "ambiguous_targets": 0,
                    "ambiguous_fraction": None, "note": nota}
        ambiguos = 0
        for caso in casos:
            sujeitos = idx.execute(
                "SELECT COUNT(DISTINCT e.canonical) n FROM page_entities pe "
                "JOIN entities e ON e.id = pe.entity_id "
                f"WHERE pe.page = ? AND e.authority IN "
                f"({','.join('?' * len(_KINDS_DE_SUJEITO))})",
                (caso["page"], *_KINDS_DE_SUJEITO)).fetchone()["n"]
            if sujeitos >= 2:
                ambiguos += 1
        return {"edges": len(casos), "ambiguous_targets": ambiguos,
                "ambiguous_fraction": round(ambiguos / len(casos), 4),
                "note": nota}
