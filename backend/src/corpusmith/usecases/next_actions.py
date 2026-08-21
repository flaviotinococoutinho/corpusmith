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
from .plan_attention import (gap_items, inbox_items, paginas_vivas,
                             review_items)
from ..harness.local_policy import check_corpus
from ..kernel.vitality import filtrar
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..runtime.verdicts import pattern_key, suppressed_keys
from ..settings import Settings

MAX_ACTIONS = 40
_BRIDGE_VALUE = 0.7
_BRIDGE_COST = 3.0            # editar um link é barato
_CONTRADICTION_VALUE = 0.85  # duas versões da mesma verdade convivendo
_CONTRADICTION_COST = 8.0    # ler ambas e decidir supersede/merge

# F4-PR3b (RFC-005): o conflito factual é MAIS acionável que a coexistência
# genérica — há um número nomeado, com span, para conferir. A densidade
# valor/custo (o critério real de ordenação) sobe pelo CUSTO, não pelo
# valor: conferir `12 km` contra `20 km` em dois spans não custa o que
# custa ler duas páginas inteiras e decidir sucessão. Subir o VALOR acima
# de 0.85 poria um limiar explicitamente NÃO calibrado (a tolerância de 1%)
# a governar o item de maior VoI do produto inteiro — alegar mais do que se
# mediu. O custo é a parcela que a evidência sustenta.
_FACTUAL_VALUE = 0.85        # o MESMO: o detector não mede importância
_FACTUAL_COST = 3.0          # conferir um número em dois spans

# desde o F4-PR3b `check_corpus` emite DOIS códigos; quem itera precisa
# despachar por regra. Fail-closed: regra desconhecida não vira item.
_KIND_POR_REGRA = {"policy.contradiction_candidate": "contradiction",
                   "policy.factual_conflict": "factual_conflict"}
_VOI_POR_KIND = {"contradiction": (_CONTRADICTION_VALUE, _CONTRADICTION_COST),
                 "factual_conflict": (_FACTUAL_VALUE, _FACTUAL_COST)}

# origem legível por tipo de item (a interface rotula sem reinterpretar)
_ORIGIN = {
    "review": "revisão espaçada",
    "question": "pergunta aberta",
    "low_yield": "página de baixo rendimento",
    "stale": "conhecimento a revalidar",
    "inbox": "captura não absorvida",
    "bridge": "ponte frágil no grafo",
    "contradiction": "contradição candidata",
    "factual_conflict": "conflito factual",
}
# o que o clique faz — a interface roteia por `action.type`, não decide
_ACTION_TYPE = {
    "review": "read", "question": "answer", "low_yield": "resolve",
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
# oferta que falharia — `question`, `inbox` e `review` continuam navegando.
# E o que se RECUSA a oferecer é decisão semântica, não técnica (em todos
# os casos os parâmetros fechariam): `invalidate` para stale/contested
# afirmaria que o fato EXPIROU NO MUNDO, coisa que "precisa de revisão" e
# "deu beco" nunca declararam; `unlink` para ponte destruiria justamente o
# fio que o item pede para reforçar. Desde o F1-PR3, stale e contested
# oferecem `edit` — corrigir o corpo não afirma nada sobre o mundo.
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
    if kind in ("contradiction", "factual_conflict"):
        pages = [p for p in (action.get("pages") or []) if p]
        alvo = item.get("target")
        ofertas = [{"act": "invalidate", "params": {"page": alvo},
                    "needs": [], "label": "Invalidar esta página"}]
        # supersede e merge exigem DUAS páginas distintas; com uma só,
        # `page == successor`/`page == into` levantaria ValueError já no plano
        if len({*pages}) >= 2:
            outras = [p for p in pages if p != alvo]
            ofertas.insert(0, {
                "act": "supersede",
                "params": {"successor": alvo},
                "needs": ["page"],
                "label": "Suceder uma das páginas em conflito",
                "options": {"page": outras}})
            # F1-PR5: `merge` vem PRIMEIRO — é a única das três resoluções
            # que não pede a ninguém para abandonar texto (o corpo da outra
            # entra integral na região declarada). O próprio finding lista
            # as duas saídas; esta é a que preserva mais informação, então é
            # ela que o clique principal do item abre.
            ofertas.insert(0, {
                "act": "merge",
                "params": {"into": alvo},
                "needs": ["page"],
                "label": "Fundir uma das páginas nesta",
                "options": {"page": outras}})
        if kind == "factual_conflict":
            # F4-PR3b: para um NÚMERO divergente, fundir é a saída errada e
            # `merge` era o clique principal. A fusão põe os dois valores na
            # mesma página, e a guarda de faixa de `kernel/factual.py` então
            # descarta a dimensão inteira: a divergência deixa de ser
            # DETECTÁVEL sem ter sido corrigida. Corrigir o corpo (`edit`)
            # é o gesto certo — não afirma nada sobre o mundo, só conserta o
            # texto. Vai à frente; `merge` continua na lista, porque duas
            # versões da mesma fonte às vezes são isso mesmo, e o preview do
            # MergePages passa a declarar a perda (RFC-005 §5.3).
            ofertas.insert(0, {
                "act": "edit", "params": {"page": alvo}, "needs": [],
                "label": "Corrigir o número nesta página"})
        return ofertas
    if kind in ("low_yield", "stale"):
        # F1-PR3: o ato que estes kinds pediam existe agora. Corrigir o
        # corpo NÃO afirma nada sobre o mundo — é o gesto certo para "deu
        # beco" e para "precisa de revisão", ao contrário de `invalidate`,
        # que segue fora por afirmar expiração que nenhum dos dois declara.
        alvo = item.get("target")
        if alvo:
            # `body` não é um campo curto como `page`: é o texto inteiro. A
            # oferta DECLARA isso (`multiline`) e de onde o valor inicial
            # vem (`prefill`), em vez de a interface saber o nome do ato —
            # sem prefill, o campo abriria vazio e aplicar APAGARIA a
            # página que o usuário quis corrigir.
            return [{"act": "edit", "params": {"page": alvo},
                     "needs": ["body"], "multiline": ["body"],
                     "prefill": {"body": {"page": alvo, "field": "body"}},
                     "label": "Corrigir o corpo da página"}]
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
        "ORDER BY weight LIMIT 30")]
    idx.close()
    # F3-PR2: a ponte liga DUAS páginas — se qualquer ponta foi aposentada, o
    # item pede para linkar um endereço que já não aceita trabalho. E o
    # veredito humano ("esta ponte não vale") passa a suprimir com `until`,
    # jamais DELETE: o job `leiden` recomputa `graph_bridges` do zero e um
    # DELETE seria desfeito na próxima execução, trazendo de volta o item que
    # o usuário acabou de rejeitar.
    vivas_ = paginas_vivas(settings)
    suprimidos = suppressed_keys(settings, "bridge")
    out = []
    for r in rows:
        if r["src"] not in vivas_ or r["dst"] not in vivas_:
            continue
        if pattern_key([r["src"], r["dst"]]) in suprimidos:
            continue
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
    # o LIMIT da SQL subiu para 30 porque agora há descarte (pontas mortas,
    # vereditos): cortar 10 ANTES do filtro devolveria menos de 10 pontes
    # vivas sempre que houvesse uma rejeitada no topo
    return out[:10]


def contradiction_items(settings: Settings) -> list[dict]:
    """Contradições candidatas e conflitos factuais (AGM, `check_corpus`).

    O candidato genérico diz *"estas páginas citam a mesma fonte e ninguém
    declarou sucessão"* — o curador abre as duas e frequentemente conclui
    que não há conflito. O conflito factual (F4-PR3b, RFC-005) diz *"este
    número diverge, nestes spans"*: é o mesmo sujeito com evidência
    apontada, e por isso item PRÓPRIO.

    **Despacho por regra, fail-closed.** Até o F4-PR3b `check_corpus`
    emitia um código só e iterar sem olhar `f.rule` era seguro. Deixou de
    ser: sem o despacho, o conflito factual entraria na fila DISFARÇADO de
    coexistência — mesmo rótulo, mesmo custo, mesma chave de supressão — e
    a entrega "a fila distingue os dois" sairia não-entregue com a suíte
    verde."""
    reader = BundleReader(settings.path("knowledge") / "bundle")
    docs = list(reader.iter_concepts())
    # NAMESPACE POR KIND, sem herança. `suppressed_keys` é chaveado por
    # (kind, pattern_key), então o item novo já nasce com silêncio próprio.
    # Herdar o silêncio do candidato genérico seria repetir a dívida do
    # ADR-41.5 que o F3-PR2 pagou: um veredito sobre UMA relação apagando
    # outra que ninguém julgou. Rejeitar "estas páginas coexistem" é juízo
    # sobre a convivência; não diz nada sobre o número divergente.
    suprimidos = {k: suppressed_keys(settings, k) for k in _VOI_POR_KIND}
    itens: list[dict] = []
    for f in check_corpus(docs, reader):
        kind = _KIND_POR_REGRA.get(f.rule)
        if kind is None:
            continue                      # regra nova não vira item sozinha
        pages = f.meta.get("pages", [f.path])
        # F3-PR2: "já olhei, é falso positivo" precisa CALAR o item — senão
        # a contradição de maior VoI volta ao topo da fila toda vez e ensina
        # o usuário a ignorar a fila inteira
        if pattern_key(pages) in suprimidos[kind]:
            continue
        valor, custo = _VOI_POR_KIND[kind]
        itens.append({
            "kind": kind, "target": f.path,
            "title": _titleize(f.path), "origin": _ORIGIN[kind],
            "value": valor, "cost_min": custo,
            "reason": f.message,
            "action": {"type": "resolve-contradiction", "pages": pages,
                       "identifier": f.meta.get("identifier")}})
    # Mesmas páginas, dois itens: o factual é estritamente mais informativo
    # (traz o número, a dimensão e os spans) e abre o mesmo repertório de
    # atos. Deixar os dois põe o MESMO trabalho duas vezes no topo da fila.
    # Quando as divergentes são um SUBCONJUNTO do grupo, as chaves diferem e
    # os dois ficam — e isso é correto: a coexistência com a terceira página
    # não foi tratada por nada.
    factuais = {pattern_key(i["action"]["pages"]) for i in itens
                if i["kind"] == "factual_conflict"}
    return [i for i in itens
            if i["kind"] != "contradiction"
            or pattern_key(i["action"]["pages"]) not in factuais]


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
