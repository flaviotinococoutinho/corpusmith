"""A escada de reconciliação — F3-PR0 / RFC-002.

**Este arquivo não existia.** A escada que decide ADD/UPDATE/SUPERSEDE sobre a
página canônica — a decisão mais consequente do produto, porque é a única que
pode criar duas páginas vivas para o mesmo objeto do mundo — nunca teve teste
próprio. É por isso que o degrau de similaridade pôde ficar morto da v0.9 ao
F3-PR0 sem que nada acusasse: `MIN(bm25(...))` estourava em toda execução,
`except Exception` engolia, e o resultado ("nenhum candidato") era idêntico ao
de uma busca bem-sucedida e vazia.

Os testes abaixo separam justamente isso: *procurei e não há* de *não consegui
procurar*.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from corpusmith.okf.authorities import load_gazetteer, normalize_machine_body
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.document import OKFDocument
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.usecases.reconcile_candidate import (HI, LO, ReconcileCandidate,
                                                  log_decision)

from conftest import write_page


CORPO = """# Distância de compressão normalizada

A NCD de Cilibrasi e Vitányi mede quanto dois textos se explicam: se o
compressor aproveita um para codificar o outro, eles falam do mesmo objeto.
É um sinal barato, sem modelo, e imune a paráfrase superficial.
Usada aqui como terceiro termo do escore de similaridade da reconciliação.
"""


def _commit(kb: Path, mensagem: str = "fixture") -> None:
    from corpusmith.okf.git_store import GitStore
    GitStore(kb).commit(mensagem)


def _candidato(settings, bundle: Path, rel_path: str, title: str, corpo: str):
    """Documento + report como o pipeline os monta (produce → normalize)."""
    gaz = load_gazetteer(BundleReader(bundle))
    body, report = normalize_machine_body(corpo, gaz)
    doc = OKFDocument(rel_path=rel_path,
                      meta={"type": "concept", "title": title,
                            "privacy": "local_only"},
                      body=body)
    return doc, report


@pytest.fixture
def indexado(settings, kb, bundle):
    """Bundle com uma página real, commitado e indexado — índice FRESCO.

    O `authority_record` não é enfeite: entidades só existem quando alguém as
    curou no bundle, e o termo Jaccard do escore vale 0 sem elas. Um fixture
    sem autoridade nenhuma mediria uma base vazia e concluiria coisa errada
    sobre os cortes (ver `test_os_tres_sinais_precisam_concordar`)."""
    write_page(bundle, "concepts/ncd.md",
               "---\ntype: concept\ntitle: Distância de compressão "
               "normalizada\nprivacy: local_only\n---\n" + CORPO)
    write_page(bundle, "concepts/aut-ncd.md",
               "---\ntype: authority_record\ntitle: NCD\n"
               "canonical: Distância de compressão normalizada\n"
               "aliases: [NCD]\nprivacy: local_only\n---\n"
               "# NCD\n\nRegistro de autoridade do termo.\n")
    _commit(kb)
    rebuild_index(settings)
    return settings


# --------------------------------------------------- o degrau ressuscitado
def test_similaridade_encontra_a_pagina_quase_igual(indexado, bundle):
    """O degrau que esteve morto: uma página quase idêntica é ENCONTRADA.

    Falsificável — com `MIN(bm25(...))` de volta, `matches` sai vazio e o
    escore cai a 0.0. Foi assim por três versões."""
    doc, report = _candidato(indexado, bundle, "concepts/ncd-2.md",
                             "Distância de compressão normalizada", CORPO)
    ato = ReconcileCandidate(indexado, doc, report)
    decisao = ato.execute()
    assert ato.similarity_error is None, ato.similarity_error
    assert decisao["score"] > LO, decisao
    assert decisao["op"] == "UPDATE"
    assert decisao["target"] == "concepts/ncd.md"


def test_texto_sem_relacao_nao_e_confundido(indexado, bundle):
    """O degrau ressuscitado precisa também saber dizer NÃO — senão a
    correção teria trocado um falso negativo por um falso positivo."""
    doc, report = _candidato(
        indexado, bundle, "concepts/receita.md", "Bolo de fubá cremoso",
        "# Bolo de fubá\n\nFubá, leite, ovos, queijo. Assar 40 minutos.\n")
    decisao = ReconcileCandidate(indexado, doc, report).execute()
    assert decisao["op"] == "ADD"
    assert decisao["target"] is None
    assert decisao["score"] < LO


def test_a_consulta_de_similaridade_nao_estoura(indexado, bundle):
    """Guarda direta contra a regressão exata: `bm25` dentro de agregado.

    Vale a redundância com o teste de comportamento — este nomeia a causa,
    e é o que um leitor futuro encontra ao procurar pela mensagem do erro."""
    doc, report = _candidato(indexado, bundle, "concepts/x.md",
                             "Distância de compressão", CORPO)
    ato = ReconcileCandidate(indexado, doc, report)
    ato.execute()
    assert ato.similarity_error is None
    assert "bm25" not in (ato.similarity_error or "")


def test_pagina_com_muitos_chunks_ocupa_uma_posicao_so(indexado, bundle,
                                                       settings):
    """A deduplicação por página não é detalhe de implementação.

    O escore usa `1/(1+position)`; sem deduplicar, uma página longa ocuparia
    várias posições do top-N, empurraria as concorrentes para fora e ainda
    inflaria o próprio termo posicional. O `MIN(...)+GROUP BY` original
    pretendia fazer isso — e era exatamente o que o tornava inexecutável."""
    longa = CORPO + "\n\n".join(
        f"## Seção {i}\n\nDistância de compressão normalizada aplicada ao "
        f"parágrafo {i}: o compressor aproveita um texto para codificar o "
        f"outro e o ganho vira medida de afinidade entre os dois documentos."
        for i in range(20))
    write_page(bundle, "concepts/longa.md",
               "---\ntype: concept\ntitle: Compressão em muitos "
               "pedaços\nprivacy: local_only\n---\n" + longa)
    _commit(settings.path("knowledge"))
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    try:
        n = idx.execute("SELECT COUNT(*) c FROM chunks WHERE page=?",
                        ("concepts/longa.md",)).fetchone()["c"]
    finally:
        idx.close()
    assert n > 1, "fixture inútil: a página precisa ter vários chunks"
    doc, report = _candidato(settings, bundle, "concepts/novo.md",
                             "Distância de compressão normalizada", CORPO)
    ato = ReconcileCandidate(settings, doc, report)
    ato.execute()
    paginas = [p for _s, p in ato._by_similarity(
        connect(settings.app_support / "index.db"))]
    assert len(paginas) == len(set(paginas)), paginas


def test_os_tres_sinais_precisam_concordar(settings, kb, bundle):
    """Sem entidade curada, corpo IDÊNTICO empaca em ~0.69 e não vira UPDATE.

    Medido, e é a propriedade que os cortes codificam: o teto sem acordo de
    entidades é `0.4·1 + 0.3·0 + 0.3·(1−NCD)` ≈ 0.7, abaixo de HI=0.82. A
    consequência prática é conservadora e deliberada — sem o terceiro sinal a
    escada cai na zona cinzenta e, sem árbitro, escreve página nova marcada
    `ambiguous` em vez de sobrescrever a existente (precisão > recall).

    Fixar isto por teste é o que impede alguém de "consertar" HI para 0.65
    achando que o degrau estava fraco: ele não está fraco, ele está exigindo
    que os três sinais concordem."""
    write_page(bundle, "concepts/ncd.md",
               "---\ntype: concept\ntitle: Distância de compressão "
               "normalizada\nprivacy: local_only\n---\n" + CORPO)
    _commit(kb)
    rebuild_index(settings)
    doc, report = _candidato(settings, bundle, "concepts/ncd-2.md",
                             "Distância de compressão normalizada", CORPO)
    decisao = ReconcileCandidate(settings, doc, report).execute()
    assert LO < decisao["score"] < HI, decisao["score"]
    assert decisao["op"] == "ADD"
    assert decisao["confidence"] == "ambiguous"
    assert "zona cinzenta" in decisao["reason"]


# ------------------------------------------- projeção usada como autoridade
def test_indice_atrasado_e_reindexado_antes_de_decidir(indexado, bundle,
                                                       settings):
    """B2 da auditoria: `index.db` é PROJEÇÃO e a escada o usa como
    AUTORIDADE. Uma página escrita e não indexada some da busca, e o mesmo
    identificador forte vira DUAS páginas canônicas vivas.

    Falsificável — sem a pré-condição, o `op` volta a ser ADD."""
    write_page(bundle, "concepts/doi.md",
               "---\ntype: concept\ntitle: Artigo com DOI\n"
               "privacy: local_only\n---\n"
               "# Artigo\n\nPublicado como 10.1000/xyz123.\n")
    _commit(settings.path("knowledge"), "página nova, índice NÃO refeito")

    doc, report = _candidato(
        settings, bundle, "concepts/doi-2.md", "O mesmo artigo",
        "# O mesmo artigo\n\nO identificador é 10.1000/xyz123.\n")
    ato = ReconcileCandidate(settings, doc, report)
    decisao = ato.execute()
    assert ato.index_stale is None, "a reindexação devia ter deixado fresco"
    assert decisao["op"] == "UPDATE"
    assert decisao["target"] == "concepts/doi.md"
    assert decisao["score"] == 1.0


def test_atraso_irreparavel_marca_a_decisao(indexado, bundle, monkeypatch):
    """Quando nem reindexar resolve, a decisão DIZ que saiu de um índice
    atrasado — em vez de sair como se a busca tivesse sido conclusiva.

    `confidence` cai para `ambiguous`, que é o vocabulário que o produto já
    usa para "não me trate como certeza"."""
    import corpusmith.usecases.reconcile_candidate as rc
    monkeypatch.setattr(rc.ReconcileCandidate, "_atraso",
                        staticmethod(lambda _v: "stale"))
    doc, report = _candidato(indexado, bundle, "concepts/z.md",
                             "Assunto sem nenhuma relação com o bundle",
                             "# Z\n\nTexto sobre jardinagem em varanda.\n")
    ato = ReconcileCandidate(indexado, doc, report)
    decisao = ato.execute()
    assert ato.index_stale == "stale"
    assert decisao["op"] == "ADD"
    assert decisao["confidence"] == "ambiguous"
    assert "atrasado" in decisao["reason"]
    assert decisao["index_stale"] == "stale"


def test_o_atraso_vai_para_a_trilha_de_auditoria(indexado, bundle,
                                                 monkeypatch):
    """"Quantas decisões saíram de um índice atrasado?" tem de ser consulta,
    não suposição — senão o diagnóstico morre no objeto em memória."""
    import corpusmith.usecases.reconcile_candidate as rc
    monkeypatch.setattr(rc.ReconcileCandidate, "_atraso",
                        staticmethod(lambda _v: "absent"))
    doc, report = _candidato(indexado, bundle, "concepts/w.md",
                             "Outro assunto qualquer",
                             "# W\n\nTexto sobre marcenaria.\n")
    decisao = ReconcileCandidate(indexado, doc, report).execute()
    log_decision(indexado, "concepts/w.md", decisao)
    rt = connect(indexado.app_support / "runtime.db")
    try:
        linha = rt.execute("SELECT signals FROM reconcile_log "
                           "ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        rt.close()
    assert json.loads(linha["signals"])["index_stale"] == "absent"


def test_indice_fresco_nao_paga_reindexacao(indexado, bundle, monkeypatch):
    """A pré-condição não pode virar um `rebuild_index` por documento.

    Sem esta guarda, ingerir N documentos custaria N reconstruções — e a
    correção de um defeito de correção viraria um defeito de desempenho numa
    máquina de 8 GB."""
    import corpusmith.usecases.reconcile_candidate as rc
    chamadas = []
    import corpusmith.retrieval.fts as fts
    original = fts.rebuild_index
    monkeypatch.setattr(fts, "rebuild_index",
                        lambda *a, **k: (chamadas.append(1),
                                         original(*a, **k))[1])
    doc, report = _candidato(indexado, bundle, "concepts/q.md",
                             "Distância de compressão normalizada", CORPO)
    rc.ReconcileCandidate(indexado, doc, report).execute()
    assert chamadas == [], "índice já estava fresco — nada a reconstruir"


# ------------------------------------------------- higiene da reindexação
def test_rebuild_index_fecha_a_conexao_mesmo_falhando(settings, kb, bundle,
                                                      monkeypatch):
    """Achado CONFIRMADO em `docs/17`: o único `close()` estava no caminho de
    sucesso. Uma exceção no meio deixava a conexão viva com transação aberta,
    e a escrita seguinte respondia `database is locked` — com a causa a uma
    indexação de distância do sintoma.

    Passa a importar mais desde o F3-PR0: a pré-condição de frescor chama
    `rebuild_index` de DENTRO do caminho de escrita, onde a conexão vazada
    travaria o próprio ato que a provocou."""
    write_page(bundle, "concepts/a.md",
               "---\ntype: concept\ntitle: A\nprivacy: local_only\n---\n# A\n")
    _commit(kb)
    import corpusmith.retrieval.fts as fts

    def _explode(_s, idx, *, full):
        # A ESCRITA antes do erro é o que torna o teste capaz de reprovar:
        # conexão vazada sem transação aberta não tranca nada, e a primeira
        # versão deste teste passava com e sem o `finally` — teatro. Com a
        # transação aberta, medido: `OperationalError: database is locked`.
        idx.execute("INSERT OR REPLACE INTO index_meta(key,value) "
                    "VALUES ('probe','x')")
        raise RuntimeError("falha no meio da indexação")

    monkeypatch.setattr(fts, "_rebuild", _explode)
    with pytest.raises(RuntimeError, match="falha no meio"):
        fts.rebuild_index(settings)
    # a prova é escrever DEPOIS: com a conexão vazada isto esperava o timeout
    # de 3 s e respondia `OperationalError: database is locked`
    idx = connect(settings.app_support / "index.db")
    try:
        idx.execute("INSERT OR REPLACE INTO index_meta(key,value) "
                    "VALUES ('probe','1')")
        idx.commit()
    finally:
        idx.close()


# ------------------------------------------------------- limiares vivos
def test_os_cortes_hi_lo_voltam_a_ser_alcancaveis(indexado, bundle):
    """`HI`/`LO` eram parâmetros de código morto: com `matches` sempre vazio,
    nenhum escore jamais os cruzava. O teste fixa que a faixa é atingível —
    sem isso, calibrá-los seria calibrar nada."""
    doc, report = _candidato(indexado, bundle, "concepts/ncd-3.md",
                             "Distância de compressão normalizada", CORPO)
    ato = ReconcileCandidate(indexado, doc, report)
    escores = [s for s, _p in ato._by_similarity(
        connect(indexado.app_support / "index.db"))]
    assert escores, "nenhum candidato — o degrau voltou a morrer"
    assert max(escores) >= HI, escores
