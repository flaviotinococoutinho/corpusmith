"""NextActions (v1.8, R3 do plano docs/13) — a FILA ÚNICA de próxima ação.

Unifica num só lugar, ranqueado por densidade valor/custo (o MESMO VoI da
economia de atenção — `PlanAttention`), tudo o que o núcleo já sabe que
merece a atenção do curador e hoje mora em superfícies concorrentes (UX-1):

- REVISÕES espaçadas vencidas (ACT-R, zona de esforço produtivo);
- LACUNAS do Harness (perguntas abertas, páginas contestadas, stale);
- INBOX a consolidar (captura barata ainda não absorvida);
- PONTES FRÁGEIS do grafo (persistência 0-dim: dois blocos reais por um
  fio fraco — "linke estes temas");
- CONTRADIÇÕES candidatas (AGM: mesmo identificador forte em 2+ páginas
  sem sucessão).

Cada item traz ORIGEM, VALOR e CUSTO e leva a UMA ação — é o "inbox de
curadoria" que SUBSTITUI (não soma) as chamadas-para-ação espalhadas.
PROPÕE, nunca decide: o gate humano continua soberano. É projeção pura e
reconstruível (nenhuma escrita); o ranking é densidade valor/custo desc —
a fila inteira ordenada, sem orçamento — com teto e flag `truncated` para
não afogar a interface.
"""
from __future__ import annotations
from .base import UseCase
from .plan_attention import gap_items, inbox_items, review_items
from ..harness.local_policy import check_corpus
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..settings import Settings

MAX_ACTIONS = 40
_BRIDGE_VALUE = 0.7
_BRIDGE_COST = 3.0            # editar um link é barato
_CONTRADICTION_VALUE = 0.85  # duas versões da mesma verdade convivendo
_CONTRADICTION_COST = 8.0    # ler ambas e decidir supersede/merge

# origem legível por tipo de item (a interface rotula sem reinterpretar)
_ORIGIN = {
    "review": "revisão espaçada",
    "question": "pergunta aberta",
    "contested": "página contestada",
    "stale": "conhecimento a revalidar",
    "inbox": "captura não absorvida",
    "bridge": "ponte frágil no grafo",
    "contradiction": "contradição candidata",
}
# o que o clique faz — a interface roteia por `action.type`, não decide
_ACTION_TYPE = {
    "review": "read", "question": "answer", "contested": "resolve",
    "stale": "review", "inbox": "compile",
}


# ---------------------------------------------------------- F1-PR6
# Ofertas de ATO por item: o que o clique pode ABRIR, com os parâmetros já
# derivados do que o item carrega. Função de módulo SEPARADA de propósito —
# a Fase 3 reescreve o ranking e as fontes deste arquivo, e assim substitui
# uma função em vez do módulo (colisão mapeada em docs/15 §6).
#
# `params` é o que já se sabe; `needs` é o que o humano ainda escolhe no
# dialog. A soma dos dois TEM de construir o ato — há teste por
# `inspect.signature` provando isso, para as assinaturas não migrarem para
# o .tsx, onde nenhum teste de backend as alcança.
#
# Silêncio deliberado: kinds sem ato saem com lista VAZIA em vez de uma
# oferta que falharia. `stale` e `contested` são os casos tentadores —
# os parâmetros de `invalidate` fecham, mas invalidar afirma que o fato
# EXPIROU NO MUNDO, coisa que "precisa de revisão" (stale) e "deu beco"
# (contested) nunca afirmaram. O ato certo para eles é o EditPage do
# F1-PR3. Oferecer aqui seria pôr uma mentira datada a um clique do gate.
def acts_for(item: dict) -> list[dict]:
    """Ofertas de ato para um item da fila (lista vazia = só navegação)."""
    kind = item.get("kind")
    action = item.get("action") or {}
    if kind == "bridge":
        src, dst = action.get("src"), action.get("dst")
        if not src or not dst or src == dst:
            return []
        # a direção do par vem de `a < b` no leiden — lexicográfica, não
        # semântica. Oferecer os dois sentidos evita escolher em silêncio.
        return [{"act": "link", "params": {"src": src, "dst": dst},
                 "needs": [], "label": f"Linkar {_titleize(src)} → "
                                       f"{_titleize(dst)}"},
                {"act": "link", "params": {"src": dst, "dst": src},
                 "needs": [], "label": f"Linkar {_titleize(dst)} → "
                                       f"{_titleize(src)}"}]
    if kind == "contradiction":
        pages = [p for p in (action.get("pages") or []) if p]
        alvo = item.get("target")
        ofertas = [{"act": "invalidate", "params": {"page": alvo},
                    "needs": [], "label": "Invalidar esta página"}]
        # supersede exige DUAS páginas distintas; com uma só, `page ==
        # successor` levantaria ValueError já no plano
        if len({*pages}) >= 2:
            ofertas.insert(0, {
                "act": "supersede",
                "params": {"successor": alvo},
                "needs": ["page"],
                "label": "Suceder uma das páginas em conflito",
                "options": {"page": [p for p in pages if p != alvo]}})
        return ofertas
    return []


def _titleize(target: str) -> str:
    """Título legível a partir do rel_path (slug → frase) — barato e puro,
    sem reabrir o bundle (mesmo critério dos sumários de comunidade)."""
    stem = target.rsplit("/", 1)[-1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    return stem.replace("-", " ").replace("_", " ").strip() or target


def _enrich(item: dict) -> dict:
    """Item das três fontes de atenção → item de fila: acrescenta título,
    origem legível e a ação de um clique, preservando value/cost/reason."""
    kind = item["kind"]
    return {**item, "title": _titleize(item["target"]),
            "origin": _ORIGIN.get(kind, kind),
            "action": {"type": _ACTION_TYPE.get(kind, "read"),
                       "target": item["target"]}}


def bridge_items(settings: Settings) -> list[dict]:
    """Pontes frágeis já computadas no leiden e persistidas em index.db
    (`graph_bridges`, recomputável). O valor cresce com o tamanho do bloco
    menor que a ponte segura — reforçar um fio que sustenta muito rende
    mais. Sem grafo indexado ⇒ lista vazia (nenhum item forçado)."""
    idx = connect(settings.app_support / "index.db")
    rows = [dict(r) for r in idx.execute(
        "SELECT src, dst, weight, small_side FROM graph_bridges "
        "ORDER BY weight LIMIT 10")]
    idx.close()
    out = []
    for r in rows:
        ta, tb = _titleize(r["src"]), _titleize(r["dst"])
        value = round(min(0.85, _BRIDGE_VALUE + 0.03 * (r["small_side"] - 2)),
                      3)
        out.append({
            "kind": "bridge", "target": r["src"], "title": f"{ta} ↔ {tb}",
            "origin": _ORIGIN["bridge"], "value": value,
            "cost_min": _BRIDGE_COST,
            "reason": f"fio fraco (peso {r['weight']:.2f}) entre dois blocos "
                      f"reais — linkar fortalece a rede",
            "action": {"type": "link", "src": r["src"], "dst": r["dst"]}})
    return out


def contradiction_items(settings: Settings) -> list[dict]:
    """Contradições candidatas (AGM, `check_corpus`): o mesmo identificador
    forte em 2+ páginas sem relação de sucessão. Alto valor epistêmico; a
    resolução (supersede/merge) é sempre humana. Reusa exatamente a mesma
    detecção do painel Qualidade — fonte única, sem heurística nova."""
    reader = BundleReader(settings.path("knowledge") / "bundle")
    docs = list(reader.iter_concepts())
    out = []
    for f in check_corpus(docs, reader):
        out.append({
            "kind": "contradiction", "target": f.path,
            "title": _titleize(f.path), "origin": _ORIGIN["contradiction"],
            "value": _CONTRADICTION_VALUE, "cost_min": _CONTRADICTION_COST,
            "reason": f.message,
            "action": {"type": "resolve-contradiction",
                       "pages": f.meta.get("pages", [f.path]),
                       "identifier": f.meta.get("identifier")}})
    return out


class NextActions(UseCase):
    """A fila única, ranqueada por densidade valor/custo — o VoI por minuto
    investido, o mesmo critério da mochila gulosa da atenção só que SEM
    orçamento (a fila inteira ordenada, não uma seleção). PROPÕE, não age."""

    def __init__(self, settings: Settings, *, limit: int = MAX_ACTIONS):
        self._settings = settings
        self._limit = limit

    def execute(self) -> dict:
        items = ([_enrich(i) for i in review_items(self._settings)]
                 + [_enrich(i) for i in gap_items(self._settings)]
                 + [_enrich(i) for i in inbox_items(self._settings)]
                 + bridge_items(self._settings)
                 + contradiction_items(self._settings))
        # F1-PR6: cada item declara os atos que o clique pode abrir. Uma
        # linha, antes do sort — a ordenação não muda (teste de guarda).
        items = [{**i, "acts": acts_for(i)} for i in items]
        items.sort(key=lambda i: i["value"] / max(i["cost_min"], 0.1),
                   reverse=True)
        by_origin: dict[str, int] = {}
        for i in items:
            by_origin[i["origin"]] = by_origin.get(i["origin"], 0) + 1
        return {"actions": items[:self._limit], "total": len(items),
                "truncated": len(items) > self._limit,
                "by_origin": by_origin}
