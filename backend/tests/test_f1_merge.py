"""F1-PR5 (ADR-41.5) — MergePages: fundir duas versões da mesma verdade.

Último ato da Fase 1, e o que o Harness pede por escrito: o finding
`policy.contradiction_candidate` diz "resolva com supersede/invalid_at **ou
funda as páginas**", e só a primeira metade existia.

Três coisas que estes testes fixam e que nenhum ato anterior precisou:

1. **o corpo da perdedora entra INTEGRAL** — a fusão não reescreve, não
   entrelaça e não renumera. A região sentinelada declara a origem, e o
   `undo` devolve os dois arquivos byte a byte;
2. **a união de frontmatter não herda ciclo de vida** — `invalid_at` da
   origem faria a VENCEDORA nascer expirada; `source_sha256` da origem
   seria um checksum de outra fonte no campo escalar da vencedora;
3. **o preview mostra o finding que MOTIVA o ato** (D-D do `docs/15`), e
   declara o limite: `check_corpus` silencia o grupo inteiro quando uma
   sucessão aparece nele, então fundir A em B faz o alerta do par (B, C)
   desaparecer sem ter sido tratado.
"""
from __future__ import annotations
import pytest
from llmwiki.harness.local_policy import check_corpus
from llmwiki.kernel.curation import merge_meta, mergeable_source_meta
from llmwiki.okf.absorbed import sources_of, with_absorbed
from llmwiki.okf.bundle import BundleReader
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.git_store import GitStore
from llmwiki.okf.regions import RegiaoInconsistente
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.usecases.curate import ACTS, MergePages, UndoCurationAct
from llmwiki.usecases.next_actions import acts_for

DOI = "10.1145/3292500.3330648"


def _doc(rel, title, body, **extra):
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only",
                                           generated_via="human:promote",
                                           **extra))


@pytest.fixture
def base(settings, kb):
    """Duas páginas citando o MESMO doi — a contradição candidata real."""
    BundleWriter(kb).write(
        [_doc("concepts/a.md", "Versão A",
              f"# Versão A\n\nprosa do autor A. Ver doi:{DOI}.",
              tags=["grafo"]),
         _doc("concepts/b.md", "Versão B",
              f"# Versão B\n\nprosa  do autor B, com espaçamento proprio. "
              f"Ver doi:{DOI}.", tags=["memoria"])],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    return settings


# ============================================ a fixture prova o cenário
def test_o_cenario_e_uma_contradicao_candidata_de_verdade(base, kb):
    """Sem isto, os testes de resolução poderiam passar por vacuidade."""
    reader = BundleReader(kb / "bundle")
    findings = check_corpus(list(reader.iter_concepts()), reader)
    assert [f.rule for f in findings] == ["policy.contradiction_candidate"]
    assert findings[0].meta["pages"] == ["concepts/a.md", "concepts/b.md"]


# ============================================ o ato
def test_funde_absorvendo_o_corpo_integral_e_supersedendo_a_origem(base, kb):
    out = MergePages(base, page="concepts/b.md", into="concepts/a.md").execute()
    assert out["applied"]
    vencedora = (kb / "bundle/concepts/a.md").read_text()
    # a prosa da perdedora entra COMO ESTAVA — inclusive o espaçamento
    assert "prosa  do autor B, com espaçamento proprio" in vencedora
    assert "prosa do autor A" in vencedora
    assert "## Incorporado de" in vencedora
    perdedora = (kb / "bundle/concepts/b.md").read_text()
    assert "superseded_by: concepts/a.md" in perdedora
    assert "prosa  do autor B" in perdedora      # perdedora segue legível
    assert sources_of(BundleReader(kb / "bundle").load("concepts/a.md").body) \
        == ["concepts/b.md"]


def test_fusao_resolve_a_contradicao(base, kb):
    MergePages(base, page="concepts/b.md", into="concepts/a.md").execute()
    reader = BundleReader(kb / "bundle")
    assert check_corpus(list(reader.iter_concepts()), reader) == []


def test_um_commit_para_as_duas_paginas(base, kb):
    antes = GitStore(kb).head()
    out = MergePages(base, page="concepts/b.md", into="concepts/a.md").execute()
    depois = GitStore(kb).head()
    assert depois != antes and out["commit"] == depois
    rt = connect(base.app_support / "runtime.db")
    linhas = rt.execute("SELECT act, pages FROM curation_acts").fetchall()
    rt.close()
    assert len(linhas) == 1 and linhas[0]["act"] == "merge"
    assert "concepts/a.md" in linhas[0]["pages"]
    assert "concepts/b.md" in linhas[0]["pages"]


def test_preview_e_puro(base, kb):
    sha = GitStore(kb).head()
    out = MergePages(base, page="concepts/b.md",
                     into="concepts/a.md").execute(dry_run=True)
    assert out["applied"] is False
    assert set(out["preview"]["diffs"]) == {"concepts/a.md", "concepts/b.md"}
    assert GitStore(kb).head() == sha
    rt = connect(base.app_support / "runtime.db")
    assert rt.execute("SELECT COUNT(*) c FROM curation_acts"
                      ).fetchone()["c"] == 0
    rt.close()


def test_undo_da_fusao_devolve_os_dois_arquivos_byte_a_byte(base, kb):
    antes = {p: (kb / f"bundle/concepts/{p}").read_bytes()
             for p in ("a.md", "b.md")}
    ato = MergePages(base, page="concepts/b.md", into="concepts/a.md").execute()
    assert (kb / "bundle/concepts/a.md").read_bytes() != antes["a.md"]
    UndoCurationAct(base, act_id=ato["id"]).execute()
    for p, bytes_ in antes.items():
        assert (kb / f"bundle/concepts/{p}").read_bytes() == bytes_, p


# ============================================ o que o ato RECUSA
def test_recusa_fundir_em_si_mesma(base):
    with pytest.raises(ValueError, match="si mesma"):
        MergePages(base, page="concepts/a.md",
                   into="concepts/a.md").execute(dry_run=True)


def test_recusa_fundir_pagina_ja_supersedida(base, kb):
    """Duas sucessoras para a mesma página seria uma cadeia bifurcada que
    nem o lint detecta hoje."""
    from llmwiki.usecases.curate import SupersedePage
    SupersedePage(base, page="concepts/b.md",
                  successor="concepts/a.md").execute()
    with pytest.raises(ValueError, match="já foi supersedida"):
        MergePages(base, page="concepts/b.md",
                   into="concepts/a.md").execute(dry_run=True)


def test_recusa_absorver_duas_vezes(base, kb):
    MergePages(base, page="concepts/b.md", into="concepts/a.md").execute()
    corpo = BundleReader(kb / "bundle").load("concepts/a.md").body
    with pytest.raises(ValueError, match="já foi absorvida"):
        with_absorbed(corpo, "concepts/b.md", "Versão B", "outro texto")


def test_recusa_corpo_com_sentinela_ambigua(base, kb):
    """Mesma guarda do F1-PR4, agora compartilhada: sentinela de
    fechamento apagada à mão não pode fazer a fusão engolir prosa."""
    corpo = ("# A\n\n<!-- llmwiki:absorvido de concepts/x.md -->\n"
             "texto\n\nPROSA HUMANA NO MEIO\n\n"
             "<!-- llmwiki:absorvido de concepts/y.md -->\ntexto\n"
             "<!-- /llmwiki:absorvido -->\n")
    with pytest.raises(RegiaoInconsistente, match="inconsistente"):
        with_absorbed(corpo, "concepts/z.md", "Z", "z")


def test_sentinela_em_cerca_de_codigo_e_ignorada():
    """A primeira vítima seria a página que documenta esta feature."""
    corpo = ("# Doc\n\n```md\n<!-- llmwiki:absorvido de concepts/x.md -->\n"
             "<!-- /llmwiki:absorvido -->\n```\n")
    assert sources_of(corpo) == []
    assert "concepts/z.md" in with_absorbed(corpo, "concepts/z.md", "Z", "z")


# ============================ a união de frontmatter não herda ciclo de vida
def test_uniao_junta_tags_e_nao_herda_invalid_at(base, kb):
    """`invalid_at` da origem faria a VENCEDORA nascer expirada — e a
    origem pode estar stale sem estar supersedida."""
    from datetime import datetime, timezone
    doc = _doc("concepts/velha.md", "Velha", f"# Velha\n\nx. doi:{DOI}",
               tags=["antiga"],
               invalid_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    BundleWriter(kb).write([doc], log_kind="Update", log_message="m",
                           commit_message="c")
    MergePages(base, page="concepts/velha.md",
               into="concepts/a.md").execute()
    vencedora = BundleReader(kb / "bundle").load("concepts/a.md")
    meta = vencedora.meta.model_dump(exclude_none=True)
    assert meta.get("invalid_at") is None, "a vencedora nasceu expirada"
    assert set(meta["tags"]) == {"grafo", "antiga"}


def test_uniao_nao_herda_proveniencia_da_origem(base):
    """Checksum e URI canônica descrevem a FONTE da origem. A proveniência
    do texto absorvido fica na página de origem, que segue no bundle e é
    linkada da região — por referência, não por cópia."""
    limpo = mergeable_source_meta(
        {"tags": ["x"], "source_sha256": "deadbeef", "resource": "urn:a",
         "generated_via": "api:openalex", "superseded_by": "concepts/z.md"})
    assert limpo == {"tags": ["x"]}
    unido = merge_meta({"type": "concept"}, limpo)
    assert "source_sha256" not in unido and "superseded_by" not in unido


# ============================ D-D: o preview vê o finding que motiva o ato
def test_preview_declara_que_a_fusao_resolve_a_contradicao(base):
    nota = MergePages(base, page="concepts/b.md", into="concepts/a.md"
                      ).execute(dry_run=True)["preview"]["note"]
    assert "RESOLVE a contradição" in nota and DOI in nota


def test_preview_declara_a_terceira_pagina_que_a_fusao_nao_trata(base, kb):
    """O achado deste PR: `check_corpus` marca o grupo INTEIRO como
    resolvido quando uma sucessão aparece nele. Fundir A em B silencia o
    alerta também para o par (B, C) — sem tratá-lo. O preview declara."""
    BundleWriter(kb).write(
        [_doc("concepts/c.md", "Versão C", f"# C\n\noutra. Ver doi:{DOI}.")],
        log_kind="Update", log_message="m", commit_message="c")
    rebuild_index(base)
    nota = MergePages(base, page="concepts/b.md", into="concepts/a.md"
                      ).execute(dry_run=True)["preview"]["note"]
    assert "concepts/c.md" in nota
    assert "silencia o grupo" in nota
    # e a consequência declarada é REAL: depois da fusão o alerta some
    MergePages(base, page="concepts/b.md", into="concepts/a.md").execute()
    reader = BundleReader(kb / "bundle")
    assert check_corpus(list(reader.iter_concepts()), reader) == []


def test_preview_sem_contradicao_nao_inventa_declaracao(base, kb):
    """Fundir duas páginas que NÃO compartilham identificador é legítimo —
    o ato não passa a afirmar que resolveu algo."""
    BundleWriter(kb).write(
        [_doc("concepts/solta.md", "Solta", "# Solta\n\nsem identificador.")],
        log_kind="Update", log_message="m", commit_message="c")
    nota = MergePages(base, page="concepts/solta.md", into="concepts/a.md"
                      ).execute(dry_run=True)["preview"]["note"]
    assert "RESOLVE" not in nota
    assert "INTEGRAL" in nota


def test_preview_do_merge_nao_varre_o_bundle(base, kb):
    """A D-D previa preview O(bundle). O custo é O(páginas do ato) mais uma
    consulta indexada — provado contando quantos documentos o detector
    recebe."""
    vistos = []
    import llmwiki.usecases.curate.merge as mod
    original = mod.check_corpus
    mod.check_corpus = lambda docs, reader: vistos.append(len(docs)) or \
        original(docs, reader)
    try:
        MergePages(base, page="concepts/b.md",
                   into="concepts/a.md").execute(dry_run=True)
    finally:
        mod.check_corpus = original
    assert vistos and all(n == 2 for n in vistos), vistos


# ================= as três interações que só apareceram na revisão adversarial
def test_regiao_entra_antes_de_citations_e_nao_desarma_o_detector(base, kb):
    """O ACHADO mais sério do PR, medido com o mesmo corpo e a mesma página:
    `local_policy` monta `listed` com tudo depois do primeiro `# Citations`,
    então região no FIM ⇒ nenhum finding (a citação `[42]` fabricada no
    texto absorvido fica legitimada); região ANTES ⇒ `citation_invalid`.
    Um ato de curadoria desarmando o detector de citação fabricada é pior
    que não ter o ato."""
    from llmwiki.harness.local_policy import check
    from llmwiki.okf.absorbed import with_absorbed
    corpo = "# V\n\nafirma [1].\n\n# Citations\n\n[1] fonte real\n"
    fundido = with_absorbed(corpo, "concepts/b.md", "B",
                            "afirma [42] que ninguém definiu.")
    # a região está ANTES da seção de citações
    assert fundido.index("absorvido") < fundido.index("# Citations")
    doc = OKFDocument(rel_path="concepts/api.md", body=fundido,
                      meta=OKFFrontMatter(type="concept", title="V",
                                          privacy="local_only",
                                          generated_via="api:openalex",
                                          source_sha256="a" * 64))
    reader = BundleReader(kb / "bundle")
    regras = [f.rule for f in check([doc], reader, GitStore(kb))]
    assert "policy.citation_invalid" in regras, (
        "a região absorvida desarmou o detector de citação fabricada")


def test_bloco_de_relacoes_da_origem_nao_entra_na_vencedora(base, kb):
    """Se entrasse, a vencedora ficaria com DOIS pares de sentinela de
    relações e `find_block` passaria a recusar — a página nunca mais
    receberia um link. As relações seguem na página de origem."""
    from llmwiki.okf.relations import find_block
    from llmwiki.usecases.curate import LinkPages
    LinkPages(base, src="concepts/b.md", dst="concepts/a.md").execute()
    MergePages(base, page="concepts/b.md", into="concepts/a.md").execute()
    reader = BundleReader(kb / "bundle")
    vencedora = reader.load("concepts/a.md").body
    assert "llmwiki:relacionados" not in vencedora
    assert find_block(vencedora) is None       # não recusa: corpo sem ambiguidade
    # e a vencedora continua podendo receber relação
    LinkPages(base, src="concepts/a.md", dst="concepts/b.md").execute()
    assert "llmwiki:relacionados" in reader.load("concepts/a.md").body


def test_recusa_fundir_pagina_que_ja_e_resultado_de_fusao(base, kb):
    """Aninhar regiões deixaria as sentinelas em ordem ambígua e
    `regions.blocks` recusaria QUALQUER operação no corpo da vencedora.
    Limite declarado com a saída legítima na mensagem — remover a região
    interna apagaria a prosa de uma terceira página."""
    BundleWriter(kb).write(
        [_doc("concepts/c.md", "Versão C", "# C\n\nprosa do autor C.")],
        log_kind="Update", log_message="m", commit_message="c")
    MergePages(base, page="concepts/c.md", into="concepts/b.md").execute()
    with pytest.raises(ValueError, match="já absorveu"):
        MergePages(base, page="concepts/b.md",
                   into="concepts/a.md").execute(dry_run=True)
    # a saída legítima nomeada na mensagem FUNCIONA
    out = MergePages(base, page="concepts/a.md", into="concepts/b.md").execute()
    assert out["applied"]


# ============================================ a fila passa a oferecer merge
def test_contradicao_oferece_merge_primeiro():
    ofertas = acts_for({"kind": "contradiction", "target": "concepts/a.md",
                        "action": {"pages": ["concepts/a.md",
                                             "concepts/b.md"]}})
    assert [o["act"] for o in ofertas] == ["merge", "supersede", "invalidate"]
    assert ofertas[0]["params"] == {"into": "concepts/a.md"}
    assert ofertas[0]["needs"] == ["page"]
    assert ofertas[0]["options"] == {"page": ["concepts/b.md"]}
    assert "merge" in ACTS


def test_contradicao_com_uma_pagina_nao_oferece_merge():
    """Com uma página só, `page == into` levantaria ValueError no plano."""
    ofertas = acts_for({"kind": "contradiction", "target": "concepts/a.md",
                        "action": {"pages": ["concepts/a.md"]}})
    assert [o["act"] for o in ofertas] == ["invalidate"]
