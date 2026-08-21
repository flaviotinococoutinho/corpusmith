"""F4-PR3b (RFC-005) — o conflito factual sai do instrumento e chega à fila.

O F4-PR3a entregou `kernel/factual.py`: puro, testado e **não ligado a
nada**. Este pacote liga, e a decisão de desenho que RFC-005 §3 tomou é a
que dá precisão de graça: o detector é **refinamento** de
`policy.contradiction_candidate`, não um detector paralelo. O sujeito da
divergência é o grupo de identificador forte que já existe — duas páginas
que citam o mesmo DOI falam da mesma fonte; duas páginas sem nada em comum
que dizem `250 ms` são coincidência léxica.

**O que este pacote NÃO entrega, e o teste registra**: a marca `contested`
no canônico. Medido — `_legado` apaga, `classificar` na releitura assenta,
`merge_confidence` lava. O-2 continua aberto (RFC-005 §5.3).
"""
from __future__ import annotations
import pytest
from corpusmith.harness.local_policy import check_corpus
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index

DOI = "10.1145/3292500.3330648"


def _doc(rel, title, body, **extra):
    extra.setdefault("generated_via", "human:promote")
    if str(extra["generated_via"]).startswith(("api:", "local:")):
        extra.setdefault("source_sha256", "0" * 64)   # policy.source_sha_required
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only", **extra))


def _escreve(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _findings(kb, regra=None):
    reader = BundleReader(kb / "bundle")
    out = check_corpus(list(reader.iter_concepts()), reader)
    return [f for f in out if regra is None or f.rule == regra]


@pytest.fixture
def conflito(settings, kb):
    """Duas páginas do MESMO DOI que discordam do mesmo número: 12 km
    contra 20 km (67% de dispersão relativa, muito acima de 1%)."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "Versão A",
                  f"# Versão A\n\nO trajeto tem 12 km. Ver doi:{DOI}."),
             _doc("concepts/b.md", "Versão B",
                  f"# Versão B\n\nO trajeto tem 20 km. Ver doi:{DOI}."))
    return settings


# ======================================= o teste que reprova ANTES (§8.5)
def test_paginas_do_mesmo_doi_que_discordam_do_numero_viram_finding(
        conflito, kb):
    """O caso que o `docs/14` §P-5 pediu e que nada detectava.

    Medido ANTES do enxerto: `check_corpus` devolvia UM finding
    (`contradiction_candidate`) — a coexistência era acusada, a divergência
    numérica não.

    Falsificável de duas formas, ambas executadas antes do commit:
    revertendo o achatamento do `si` em `_medidas` (o dict aninhado de
    `quantities.py:69` passando cru faz `isinstance(si,(int,float))`
    reprovar tudo em `factual.py:85`), e removendo o laço de
    `divergencias`. Nos dois casos a lista volta a ter um finding só."""
    regras = [f.rule for f in _findings(kb)]
    assert regras == ["policy.contradiction_candidate",
                      "policy.factual_conflict"], (
        "o conflito factual precisa vir DEPOIS do candidato (há testes que "
        "indexam findings[0]) e ambos precisam existir")

    f = _findings(kb, "policy.factual_conflict")[0]
    assert f.severity == "warn"          # check_corpus NUNCA é error
    assert f.meta["dim"] == "len"
    assert f.meta["spread"] > f.meta["tolerance"] == 0.01
    assert f.meta["pages"] == ["concepts/a.md", "concepts/b.md"]
    assert f.meta["identifier"] == DOI
    # a mensagem mostra a SUPERFÍCIE, não o SI: quem confere procura no
    # texto o que está escrito, não o convertido
    assert "12 km" in f.message and "20 km" in f.message
    assert "12000" not in f.message


def test_o_alvo_e_a_pagina_que_sobrevive_a_resolucao(settings, kb):
    """O alvo sai do SUBCONJUNTO divergente, não do grupo — e é a mais
    entrincheirada (humana > máquina). Escolher a de máquina faria a oferta
    de fusão propor absorver a prosa humana dentro do rascunho.

    Falsificável: usando `group` em vez de `envolvidas`, o alvo vira
    `concepts/humana.md` (que não diverge) e a asserção reprova."""
    _escreve(settings, kb,
             _doc("concepts/humana.md", "Humana",
                  f"# Humana\n\nSem número aqui. Ver doi:{DOI}."),
             _doc("concepts/maquina1.md", "M1",
                  f"# M1\n\nVer doi:{DOI} — o trajeto tem 12 km\n",
                  generated_via="local:promote"),
             _doc("concepts/maquina2.md", "M2",
                  f"# M2\n\nVer doi:{DOI} — o trajeto tem 20 km\n",
                  generated_via="local:promote"))
    f = _findings(kb, "policy.factual_conflict")[0]
    assert f.meta["pages"] == ["concepts/maquina1.md", "concepts/maquina2.md"]
    assert f.path == "concepts/maquina1.md", \
        "o alvo tem de estar entre as páginas que divergem"


# ================================================= precisão por construção
def test_sem_identificador_comum_nao_ha_conflito(settings, kb):
    """A decisão central do RFC-005 §3. Duas páginas que dizem números
    diferentes SEM identificador forte compartilhado não são comparáveis —
    `250 ms` numa e `900 ms` noutra podem ser de coisas diferentes.

    Falsificável: um detector que varresse o corpus atrás de quantidades
    iguais devolveria finding aqui, e inundaria a fila no item de maior
    VoI — o modo de falha que RFC-005 §2 mede."""
    _escreve(settings, kb,
             _doc("concepts/x.md", "X", "# X\n\nA latência é 250 ms."),
             _doc("concepts/y.md", "Y", "# Y\n\nA latência é 900 ms."))
    assert _findings(kb) == []


def test_divergencia_dentro_da_tolerancia_nao_e_conflito(settings, kb):
    """`12.5 km` vs `12.51 km` é digitação, não divergência (0,08% < 1%).

    Falsificável: com a tolerância em 0, o finding aparece e a asserção
    de comprimento reprova."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "A", f"# A\n\nSão 12.5 km. doi:{DOI}."),
             _doc("concepts/b.md", "B", f"# B\n\nSão 12.51 km. doi:{DOI}."))
    assert _findings(kb, "policy.factual_conflict") == []
    assert len(_findings(kb, "policy.contradiction_candidate")) == 1


def test_unidades_diferentes_no_mesmo_valor_nao_sao_conflito(settings, kb):
    """`12 km` e `12000 m` são O MESMO valor. RFC-005 §4 derrubou a cláusula
    "unidade idêntica" do `docs/14` §P-5 exatamente por isto: exigir unidade
    igual descartaria o caso que a normalização SI existe para pegar.

    Falsificável: filtrando por `m.data["unit"]` em qualquer ponto, este
    par vira conflito e a asserção reprova."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "A", f"# A\n\nSão 12 km. doi:{DOI}."),
             _doc("concepts/b.md", "B", f"# B\n\nSão 12000 m. doi:{DOI}."))
    assert _findings(kb, "policy.factual_conflict") == []


def test_pagina_que_afirma_faixa_tira_a_dimensao_inteira(settings, kb):
    """A guarda de precisão de `kernel/factual.py` que o plano não previa:
    uma página que menciona `12 km` E `20 km` descreve faixa ou comparação,
    não afirma um valor. Comparar o extremo dela com outra página seria ler
    mal o texto. Precisão > recall, e o custo é declarado no contrato.

    Falsificável: sem a guarda de faixa no kernel, o finding aparece."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "A",
                  f"# A\n\nEntre 12 km e 20 km. doi:{DOI}."),
             _doc("concepts/b.md", "B", f"# B\n\nSão 90 km. doi:{DOI}."))
    assert _findings(kb, "policy.factual_conflict") == []


def test_sucessao_declarada_resolve_antes_de_medir_numero(settings, kb):
    """Se as páginas já estão ligadas por sucessão, o grupo nem chega ao
    exame factual — o refinamento herda TODAS as guardas do candidato.

    Falsificável: emitindo o conflito fora do laço de grupos (detector
    paralelo, o desenho que RFC-005 recusou), o finding aparece."""
    _escreve(settings, kb,
             _doc("concepts/velha.md", "Velha",
                  f"# Velha\n\nSão 12 km. doi:{DOI}.",
                  superseded_by="concepts/nova.md"),
             _doc("concepts/nova.md", "Nova",
                  f"# Nova\n\nSão 20 km. doi:{DOI}."))
    assert _findings(kb) == []


# ================================================== a fila distingue os dois
def test_fila_distingue_conflito_factual_de_coexistencia(conflito, kb):
    """A entrega #2 da RFC-005 §6. Antes do despacho por regra, o conflito
    factual entraria na fila DISFARÇADO: `kind:"contradiction"`, mesmo
    rótulo, mesmo custo, mesma chave de supressão.

    Falsificável: sem `_KIND_POR_REGRA`, o item volta a `contradiction` e
    as duas primeiras asserções reprovam."""
    from corpusmith.usecases.next_actions import contradiction_items
    itens = contradiction_items(conflito)
    assert [i["kind"] for i in itens] == ["factual_conflict"], (
        "mesmas páginas: o factual é estritamente mais informativo e "
        "absorve o candidato genérico — dois itens seriam o mesmo trabalho "
        "duas vezes no topo da fila")
    item = itens[0]
    assert item["origin"] == "conflito factual"
    assert "12 km" in item["reason"] and "20 km" in item["reason"]
    # a densidade sobe pelo CUSTO, não pelo valor: o detector não mede
    # importância, e subir o valor poria um limiar não calibrado a governar
    # o item de maior VoI do produto
    assert item["value"] == 0.85
    assert item["cost_min"] < 8.0


def test_veredito_no_generico_nao_cala_o_conflito_factual(settings, kb):
    """Namespace de supressão PRÓPRIO, sem herança.

    Rejeitar "estas páginas coexistem" é juízo sobre a convivência; não diz
    nada sobre o número divergente. Herdar o silêncio repetiria a dívida do
    ADR-41.5 que o F3-PR2 pagou — um veredito sobre UMA relação apagando
    outra que ninguém julgou.

    Falsificável: com um namespace só (`suppressed_keys(settings,
    "contradiction")` para os dois), o item factual some e a asserção
    reprova."""
    from corpusmith.runtime.verdicts import record
    from corpusmith.usecases.next_actions import contradiction_items
    _escreve(settings, kb,
             _doc("concepts/a.md", "A", f"# A\n\nSão 12 km. doi:{DOI}."),
             _doc("concepts/b.md", "B", f"# B\n\nSão 20 km. doi:{DOI}."))
    record(settings, "contradiction",
           ["concepts/a.md", "concepts/b.md"], "rejected")
    kinds = [i["kind"] for i in contradiction_items(settings)]
    assert kinds == ["factual_conflict"], (
        "o veredito era sobre a coexistência; o número divergente não foi "
        "julgado por ninguém")


def test_conflito_factual_oferece_edit_antes_de_merge(conflito):
    """RFC-005 / parecer de produto: para um NÚMERO divergente, fundir é a
    saída errada — e `merge` era o clique principal.

    Falsificável: removendo o bloco `if kind == "factual_conflict"` de
    `acts_for`, a primeira oferta volta a ser `merge`."""
    from corpusmith.usecases.next_actions import acts_for, contradiction_items
    item = contradiction_items(conflito)[0]
    atos = [o["act"] for o in acts_for(item)]
    assert atos[0] == "edit", "corrigir o número vem antes de fundir"
    assert "merge" in atos, ("fundir continua disponível — duas versões da "
                             "mesma fonte às vezes são isso mesmo")
    assert atos.index("edit") < atos.index("merge")


def test_preview_da_fusao_declara_que_fundir_silencia_o_conflito(
        conflito, settings):
    """A descoberta mais séria do parecer de produto, e a razão de o
    preview existir: fundir põe `12 km` e `20 km` na MESMA página, a guarda
    de faixa descarta a dimensão inteira, e o finding some **sem que o
    número tenha sido corrigido**. O preview declararia resolvido o que só
    foi silenciado — dentro do ato cuja única razão de existir é declarar a
    verdade antes do efeito.

    Mesma disciplina de `ratificacao_perdida`: o ato pode destruir, mas
    nunca em silêncio.

    Falsificável: sem `_conflitos_factuais` na `_nota`, a nota não menciona
    o conflito e as asserções reprovam."""
    from corpusmith.usecases.curate import MergePages
    nota = MergePages(settings, page="concepts/b.md",
                      into="concepts/a.md").execute(
                          dry_run=True)["preview"]["note"]
    assert "CONFLITO FACTUAL" in nota
    assert "fundir NÃO resolve" in nota
    assert "`edit`" in nota


def test_temperatura_fica_fora_e_o_contrato_declara(settings, kb):
    """`quantities.py:65` suprime o payload SI de `dim=temp` porque não há
    conversão afim °C↔°F. Sem SI não há comparação — e comparar valores
    brutos de escalas diferentes seria pior que não comparar. Falso
    negativo DECLARADO no contrato, não defeito escondido."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "A", f"# A\n\nFerve a 100 °C. doi:{DOI}."),
             _doc("concepts/b.md", "B", f"# B\n\nFerve a 50 °C. doi:{DOI}."))
    assert _findings(kb, "policy.factual_conflict") == []
