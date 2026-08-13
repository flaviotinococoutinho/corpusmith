"""okf/links.py — o único parser de link do produto (F1-PR4).

Este arquivo não existia: `MD_LINK` alimenta as arestas de `graph_edges`,
a regra `okf.broken_link` e a `policy.release_broken_link`, e nada o
cobria diretamente.

O PR estende o parser para o atributo de título do Markdown
(`[texto](alvo "titulo")`), que a Fase 5 usará como relação tipada. Três
defeitos MEDIDOS motivaram o escopo:

1. o formato anotado não casava ⇒ a aresta desaparecia de `graph_edges`
   em silêncio (o achado D-A do docs/15);
2. `normalize/masking.py` tem a SEGUNDA cópia do padrão e também não o
   conhecia ⇒ `rewrite()` CORROMPIA o alvo no canônico
   (`/p.md#k8s` → `/p.md#Kubernetes`);
3. `md_link` com `]` no título emitia uma NÃO-LINK: bytes no canônico,
   Harness aprovando, aresta inexistente.
"""
from __future__ import annotations
import pathlib
import tempfile
import pytest
from corpusmith.normalize.engine import analyze, rewrite
from corpusmith.normalize.masking import is_protected, protected_spans
from corpusmith.okf.authorities import load_gazetteer
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.links import (MD_LINK, is_internal, md_link, parse_links,
                               resolve, safe_link_text)

# o regex ANTES deste PR — a referência de não-regressão
import re
MD_LINK_ANTIGO = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")

# tudo que já casava DEVE continuar casando exatamente igual
IDENTICOS = [
    "[t](/p.md)",
    "[](/p.md)",
    "[t](/p.md#sec)",
    "![alt](/img.png)",
    "[t](mailto:a@b.com)",
    "- [alfa 0](/concepts/alfa-0.md)\n- [beta 0](/concepts/beta-0.md)",
    "ver (parenteses) e [t](/p.md).",
    "[t](/a(b).md)",                     # truncamento atual PRESERVADO
    '[t]("aspas-como-alvo")',            # lixo atual PRESERVADO
    "[t]()",                             # alvo vazio: não casa, nos dois
    "[t]( /p.md )",                      # espaço após '(': não casa
    "[titulo [aninhado]](/p.md)",        # limitação atual PRESERVADA
]


@pytest.mark.parametrize("corpo", IDENTICOS)
def test_nao_regressao_o_que_ja_casava_casa_igual(corpo):
    """A mudança é ESTRITAMENTE ADITIVA: (texto, alvo) idênticos ao antigo."""
    antigo = MD_LINK_ANTIGO.findall(corpo)
    novo = [(m.group("text"), m.group("target"))
            for m in MD_LINK.finditer(corpo)]
    assert novo == antigo, f"comportamento mudou para {corpo!r}"


def test_groupindex_e_fixo():
    """Capturar o `!` da imagem acrescentou um grupo à ESQUERDA. Sem
    grupos nomeados, `parse_links` leria `!` como texto e o texto como
    alvo — em silêncio. Este teste impede uma renumeração futura."""
    assert MD_LINK.groupindex == {"bang": 1, "text": 2, "target": 3,
                                  "title": 4}


# ============================================ o formato anotado (o motivo)
def test_link_anotado_agora_vira_link_com_relacao():
    link, = parse_links('[t](/p.md "rel:refines")')
    assert (link.text, link.target) == ("t", "/p.md")
    assert link.title == "rel:refines" and link.rel == "refines"


@pytest.mark.parametrize("corpo,alvo,titulo", [
    ('[t](/p.md  "rel:x")', "/p.md", "rel:x"),          # espaços múltiplos
    ('[t](/p.md\t"rel:x")', "/p.md", "rel:x"),          # TAB
    ('[t](/p.md "rel:x" )', "/p.md", "rel:x"),          # espaço antes do ')'
    ('[t](/p.md#sec "rel:x")', "/p.md#sec", "rel:x"),   # âncora + título
    ('[t](/p.md "")', "/p.md", ""),                     # título vazio
    ('[t](/p.md "nota (importante)")', "/p.md",
     "nota (importante)"),                              # parênteses no título
    ('![a](/i.png "legenda")', "/i.png", "legenda"),    # imagem anotada
])
def test_variacoes_do_atributo_de_titulo(corpo, alvo, titulo):
    link, = parse_links(corpo)
    assert link.target == alvo and link.title == titulo


def test_titulo_nao_atravessa_linha():
    """Sem essa barreira, aspas soltas na prosa de linhas diferentes
    seriam engolidas como título — e o link sumiria junto."""
    assert parse_links('[t](/p.md "titulo\ncom quebra")') == []
    corpo = 'linha1 "aspas" e [t](/p.md)\noutra "aspas" linha'
    link, = parse_links(corpo)
    assert link.target == "/p.md" and link.title is None


def test_dois_links_anotados_na_mesma_linha():
    a, b = parse_links('[a](/x.md "t1") e [b](/y.md "t2")')
    assert (a.target, b.target) == ("/x.md", "/y.md")


def test_rel_so_reconhece_o_vocabulario_declarado():
    assert parse_links('[t](/p.md "rel:refines")')[0].rel == "refines"
    assert parse_links('[t](/p.md "uma legenda")')[0].rel is None
    assert parse_links("[t](/p.md)")[0].rel is None


# ================================= a máscara é a OUTRA metade (corrupção)
@pytest.fixture
def gaz():
    return load_gazetteer(BundleReader(pathlib.Path(tempfile.mkdtemp())))


def test_mascara_protege_alvo_e_titulo():
    """Falhava antes: `protected_spans` devolvia [] para o anotado."""
    corpo = 'ver [x](/p.md#k8s "rel:refines").'
    spans = protected_spans(corpo)
    assert spans, "o alvo do link anotado ficava DESPROTEGIDO"
    m = MD_LINK.search(corpo)
    assert is_protected(spans, m.start("target"), m.end("target"))


def test_mascara_ainda_protege_alvo_vazio():
    """O `*` (e não `+`) no padrão da máscara é deliberado: `[x]()` não é
    aresta, mas também não pode ser reescrito por detector."""
    assert protected_spans("ver [x]() fim") == [(8, 8)]


def test_rewrite_nao_corrompe_alvo_anotado(gaz):
    """O defeito mais grave que este PR fecha: sem a máscara ciente do
    formato, o gazetteer reescrevia DENTRO do alvo do link — corrupção de
    dado canônico, não perda de aresta."""
    corpo = 'ver [x](/p.md#k8s "rel:refines").'
    assert rewrite(corpo, analyze(corpo, gaz=gaz)) == corpo


def test_pin_mascara_x_parser():
    """PIN comportamental: todo alvo que o PARSER enxerga tem de estar
    protegido pela MÁSCARA. É o que impede as duas cópias do padrão de
    divergirem de novo — elas não podem compartilhar código (normalize/ é
    puro e não importa okf/), então a costura é este teste."""
    corpus = [
        "ver [a](/x.md) e [b](/y.md \"rel:r\").",
        '![i](/a.png "leg")',
        "[t](/a(b).md)",
        'linha1 "q" e [t](/p.md)\noutra "q"',
        "- [x](/c/d.md)\n- [y](/c/e.md \"rel:requires\")",
    ]
    for corpo in corpus:
        spans = protected_spans(corpo)
        for m in MD_LINK.finditer(corpo):
            assert is_protected(spans, m.start("target"), m.end("target")), \
                f"alvo desprotegido em {corpo!r}"


# ============================================ o emissor tem de ser relegível
@pytest.mark.parametrize("titulo", [
    "]", "[a]", "\n", '"', "()", "2024", "", "Array[] em Go",
    "com  espaços   demais", "Título — com traço",
])
def test_round_trip_titulos_adversariais(titulo):
    """Contrato: o que `md_link` emite, `parse_links` relê como UM link
    para o alvo certo. Falhava antes com `]` no título."""
    saida = md_link(titulo, "concepts/x.md")
    links = parse_links(saida)
    assert len(links) == 1, f"{saida!r} não é um link"
    assert links[0].target == "/concepts/x.md"


def test_md_link_sem_rel_e_byte_identico_ao_formato_antigo():
    assert md_link("t", "concepts/x.md") == "[t](/concepts/x.md)"


def test_md_link_com_rel_e_relegivel():
    saida = md_link("t", "concepts/x.md", rel="refines")
    assert saida == '[t](/concepts/x.md "rel:refines")'
    link, = parse_links(saida)
    assert link.rel == "refines" and link.target == "/concepts/x.md"


def test_safe_link_text_preserva_o_que_ja_e_seguro():
    assert safe_link_text("Kubernetes") == "Kubernetes"
    assert safe_link_text("") == "—"


# ============================================ o resto do módulo, sem cobertura
def test_is_internal_e_resolve():
    assert is_internal("/p.md") and not is_internal("https://x.com")
    assert not is_internal("#ancora")
    assert resolve("/p.md#sec", "concepts/x.md") == "p.md"
    assert resolve("outra", "concepts/x.md") == "concepts/outra.md"
