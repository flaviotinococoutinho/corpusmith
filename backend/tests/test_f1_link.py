"""F1-PR4 — LinkPages/UnlinkPages: a relação no canônico (ADR-41.2).

O ato de maior densidade valor/custo da fila (`bridge_items` já entrega
`action.type='link'`) e o único ato de corpo cujo valor não depende de UI.

A proveniência é da REGIÃO, não do link: tudo entre as sentinelas é do
ato; tudo fora é do autor. Por construção o ato nunca reescreve prosa — e
quando isso significa que a aresta SOBREVIVE ao unlink, o preview declara.

Os três testes que mais importam aqui vieram de armadilhas MEDIDAS na
revisão do design, não de imaginação: sentinela apagada à mão engolindo
prosa, sentinela dentro de cerca de código, e entrada numérica desarmando
`policy.citation_invalid`.
"""
from __future__ import annotations
import pytest
from llmwiki.harness import local_policy
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.git_store import GitStore
from llmwiki.okf.relations import (ABRE, FECHA, BlocoInconsistente,
                                   entries_of, find_block, with_link,
                                   without_link)
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.usecases.curate import LinkPages, UndoCurationAct, UnlinkPages


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


@pytest.fixture
def base(settings, kb):
    BundleWriter(kb).write(
        [_doc("concepts/a.md", "Página A", "# A\n\nprosa do autor."),
         _doc("concepts/b.md", "Página B", "# B\n\noutra prosa."),
         _doc("concepts/c.md", "Página C", "# C\n\nterceira.")],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    return settings


# ==================================== o núcleo puro do bloco (armadilhas)
def test_sentinela_apagada_a_mao_recusa_em_vez_de_engolir_prosa():
    """A armadilha mais séria do design: com um regex guloso, 2 aberturas
    e 1 fechamento casam da PRIMEIRA abertura ao ÚNICO fechamento, e a
    re-renderização APAGA a prosa do meio. Contar sentinelas pega; contar
    blocos casados, não."""
    corpo = (f"# A\n\n{ABRE}\n- [b](/concepts/b.md)\n\n"
             "PROSA HUMANA IMPORTANTE QUE ESTÁ ENTRE OS DOIS\n\n"
             f"{ABRE}\n- [c](/concepts/c.md)\n{FECHA}\n")
    with pytest.raises(BlocoInconsistente, match="inconsistente"):
        find_block(corpo)
    with pytest.raises(BlocoInconsistente):
        with_link(corpo, "concepts/a.md", "concepts/c.md", "C")


def test_sentinela_dentro_de_cerca_de_codigo_e_ignorada():
    """A primeira vítima seria a página que documenta esta feature."""
    corpo = f"# Doc\n\n```markdown\n{ABRE}\n- [x](/y.md)\n{FECHA}\n```\n"
    assert find_block(corpo) is None
    novo = with_link(corpo, "concepts/a.md", "concepts/b.md", "B")
    assert "```markdown\n" + ABRE in novo      # o exemplo ficou intacto
    assert novo.count(ABRE) == 2               # um no exemplo, um real


def test_entrada_numerica_nao_desarma_citation_invalid(base, kb):
    """O bloco fica DEPOIS de `# Citations`, e `listed` é montado com tudo
    que vem depois dela. Uma entrada `- [2024](…)` entraria em `listed` e
    legitimaria uma citação `[2024]` FABRICADA na prosa."""
    corpo = ("# P\n\nSegundo a fonte [2024], isso vale.\n\n"
             "## Citations\n\n- [1] fonte real\n")
    com_bloco = with_link(corpo, "concepts/p.md", "concepts/2024.md", "2024")
    doc = OKFDocument(rel_path="concepts/p.md", body=com_bloco,
                      meta=OKFFrontMatter(type="concept", title="P",
                                          privacy="local_only",
                                          generated_via="api:openai",
                                          source_sha256="x" * 64))

    from llmwiki.okf.bundle import BundleReader

    class _Git:
        def has_commit(self, _s): return True

    achados = local_policy.check([doc], BundleReader(kb / "bundle"), _Git())
    regras = {f.rule for f in achados}
    assert "policy.citation_invalid" in regras, (
        "a entrada do bloco legitimou a citação fabricada")


def test_bloco_e_idempotente_e_deterministico():
    corpo = "# A\n\nprosa.\n"
    um = with_link(corpo, "concepts/a.md", "concepts/b.md", "B")
    dois = with_link(um, "concepts/a.md", "concepts/c.md", "C")
    # ordem inversa produz os MESMOS bytes
    outro = with_link(with_link(corpo, "concepts/a.md", "concepts/c.md", "C"),
                      "concepts/a.md", "concepts/b.md", "B")
    assert dois == outro
    assert len(entries_of(dois)) == 2
    with pytest.raises(ValueError, match="já existe"):
        with_link(dois, "concepts/a.md", "concepts/b.md", "B")


def test_remover_tudo_devolve_o_corpo_original():
    corpo = "# A\n\nprosa do autor.\n"
    com = with_link(corpo, "concepts/a.md", "concepts/b.md", "B")
    assert without_link(com, "concepts/a.md", "concepts/b.md") == corpo


# ==================================== os atos, ponta a ponta
def test_link_escreve_no_bloco_sem_tocar_a_prosa(base, kb):
    antes = (kb / "bundle/concepts/a.md").read_text()
    out = LinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    assert out["applied"]
    texto = (kb / "bundle/concepts/a.md").read_text()
    assert "prosa do autor." in texto            # prosa intacta
    assert ABRE in texto and "Página B" in texto
    assert antes.split("---")[2].strip() in texto.replace("\n\n" + ABRE, "")


def test_link_vira_aresta_no_grafo(base, kb):
    LinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    rebuild_index(base, full=True)
    idx = connect(base.app_support / "index.db")
    arestas = idx.execute(
        "SELECT COUNT(*) c FROM graph_edges WHERE src=? AND dst=?",
        ("concepts/a.md", "concepts/b.md")).fetchone()["c"]
    idx.close()
    assert arestas == 1, "o reparo tem de sobreviver ao rebuild"


def test_link_com_relacao_tipada_preserva_o_rel(base, kb):
    LinkPages(base, src="concepts/a.md", dst="concepts/b.md",
              rel="refines").execute()
    from llmwiki.okf.links import parse_links
    corpo = (kb / "bundle/concepts/a.md").read_text()
    link = next(l for l in parse_links(corpo)
                if l.target == "/concepts/b.md")
    assert link.rel == "refines"


def test_preview_do_link_e_puro(base, kb):
    sha = GitStore(kb).head()
    out = LinkPages(base, src="concepts/a.md",
                    dst="concepts/b.md").execute(dry_run=True)
    assert out["applied"] is False and out["preview"]["diffs"]
    assert GitStore(kb).head() == sha
    rt = connect(base.app_support / "runtime.db")
    assert rt.execute("SELECT COUNT(*) c FROM curation_acts"
                      ).fetchone()["c"] == 0
    rt.close()


def test_autolink_e_alvo_inexistente_recusam(base):
    with pytest.raises(ValueError, match="consigo mesma"):
        LinkPages(base, src="concepts/a.md",
                  dst="concepts/a.md").execute(dry_run=True)
    with pytest.raises(FileNotFoundError):
        LinkPages(base, src="concepts/a.md",
                  dst="concepts/nao-existe.md").execute(dry_run=True)


def test_unlink_nao_toca_link_da_prosa_e_declara_o_residuo(base, kb):
    """A prosa cita B; o bloco também. O unlink remove só a entrada — e
    DECLARA que a aresta sobrevive, em vez de fingir que resolveu."""
    BundleWriter(kb).write(
        [_doc("concepts/a.md", "Página A",
              "# A\n\nprosa citando [B](/concepts/b.md) direto.")],
        log_kind="Update", log_message="m", commit_message="c")
    LinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    out = UnlinkPages(base, src="concepts/a.md",
                      dst="concepts/b.md").execute(dry_run=True)
    assert "ARESTA CONTINUA" in out["preview"]["note"]
    UnlinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    texto = (kb / "bundle/concepts/a.md").read_text()
    assert "[B](/concepts/b.md) direto" in texto     # prosa byte a byte
    assert ABRE not in texto                         # bloco foi embora


def test_unlink_sem_bloco_recusa(base):
    with pytest.raises(ValueError, match="não tem bloco"):
        UnlinkPages(base, src="concepts/a.md",
                    dst="concepts/b.md").execute(dry_run=True)


def test_ciclo_completo_devolve_os_bytes_originais(base, kb):
    """link → unlink devolve o arquivo byte a byte (irmão do teste de undo)."""
    antes = (kb / "bundle/concepts/a.md").read_bytes()
    LinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    UnlinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    assert (kb / "bundle/concepts/a.md").read_bytes() == antes


def test_undo_de_link_funciona_pelo_mesmo_rito(base, kb):
    antes = (kb / "bundle/concepts/a.md").read_bytes()
    ato = LinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    UndoCurationAct(base, act_id=ato["id"]).execute()
    assert (kb / "bundle/concepts/a.md").read_bytes() == antes
