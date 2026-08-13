"""Colisão de caminho — F3-PR1 / RFC-003.

O defeito de origem, reproduzido por execução antes de qualquer correção:
dois promotes do mesmo título e o segundo APAGAVA a página do primeiro —
40 linhas de anotação humana viravam um rascunho de duas, com o log
registrando "Creation". O único vestígio era o histórico Git, que nenhuma
superfície mostra como "você acabou de perder trabalho".

Estes testes fixam as três camadas da correção: o gate que confere a
intenção declarada contra o estado do mundo (`policy.path_collision`), o
promote que devolve a decisão ao humano (`op="COLLISION"`) e o fluxo de
máquina que funde frontmatter em vez de reconstruí-lo do zero.
"""
from __future__ import annotations
import pytest
from corpusmith.harness.runner import HarnessRejection
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.usecases.base import DraftPage, MachinePageUseCase
from corpusmith.usecases.promote_memory import PromoteToMemory

from conftest import write_page


def _promote(settings, title="Docker", content="conteúdo", **kw):
    return PromoteToMemory(settings, kind="semantic", title=title,
                           content=content, **kw).execute()


# ------------------------------------------------------------- o defeito
def test_promover_o_mesmo_titulo_nao_destroi_mais(settings, kb):
    """A reprodução exata do caminho destrutivo, agora com o desfecho novo:
    o segundo promote NÃO escreve e devolve a decisão ao humano."""
    _promote(settings, content="Anotações CUIDADOSAS: 40 linhas de volumes.")
    r2 = _promote(settings, content="rascunho de duas linhas")
    assert r2["op"] == "COLLISION"
    assert r2["target"] == "concepts/docker.md"
    assert sorted(r2["options"]) == ["new_slug", "update"]
    assert "commit" not in r2, "COLLISION não pode ter escrito nada"
    corpo = (kb / "bundle" / "concepts" / "docker.md").read_text()
    assert "CUIDADOSAS" in corpo, "a página residente foi destruída"


def test_colisao_nao_aparece_no_log_como_creation(settings, kb):
    """A mentira específica que o RFC nomeia: o log registrava 'Creation'
    para uma sobrescrita. Colisão sem resolução não toca o log."""
    _promote(settings)
    antes = (kb / "bundle" / "log.md").read_text()
    _promote(settings, content="outro texto")
    assert (kb / "bundle" / "log.md").read_text() == antes


# ------------------------------------------------------ as saídas humanas
def test_resolution_update_escreve_sobre_o_alvo_com_log_honesto(settings, kb):
    """Saída 1: substituir É substituir — mas explícito, com log Update."""
    _promote(settings, content="original")
    r = _promote(settings, content="texto novo escolhido pelo humano",
                 resolution="update", target="concepts/docker.md")
    assert r["op"] == "UPDATE"
    corpo = (kb / "bundle" / "concepts" / "docker.md").read_text()
    assert "texto novo" in corpo and "original" not in corpo
    log = (kb / "bundle" / "log.md").read_text()
    assert "[Update] promovido SOBRE concepts/docker.md" in log


def test_resolution_update_funde_o_frontmatter_curado(settings, kb):
    """O que o humano curou na residente não evapora junto com o corpo.

    Falsificável: sem `merge_meta` no caminho, as tags da residente somem
    (o promote novo veio sem tags) e a description é sobrescrita."""
    _promote(settings, content="original",
             tags=["infra", "curada-a-mão"], description="descrição antiga")
    r = _promote(settings, content="novo", resolution="update",
                 target="concepts/docker.md")
    reader = BundleWriter(settings.path("knowledge")).reader
    meta = reader.load("concepts/docker.md").meta
    assert set(meta.tags or []) >= {"infra", "curada-a-mão"}
    assert meta.description == "descrição antiga"   # novo não trouxe — fica
    assert r["op"] == "UPDATE"


def test_resolution_new_slug_cria_com_sufixo_deterministico(settings, kb):
    """Saída 2: o humano declarou que são conceitos distintos. Duas páginas
    vivas são um item de consolidação futura — reversível; fusão errada não."""
    _promote(settings, content="a primeira")
    r = _promote(settings, content="a segunda", resolution="new_slug")
    assert r["op"] == "ADD"
    assert r["pages"] == ["concepts/docker-2.md"]
    assert (kb / "bundle" / "concepts" / "docker.md").exists()
    r3 = _promote(settings, content="a terceira", resolution="new_slug")
    assert r3["pages"] == ["concepts/docker-3.md"]


def test_resolution_update_sem_target_e_erro():
    with pytest.raises(ValueError, match="exige target"):
        PromoteToMemory(None, kind="semantic", title="t", content="c",
                        resolution="update")


# --------------------------------------- colisão por SIMILARIDADE (escada)
def test_slug_diferente_mesmo_conceito_vira_colisao(settings, kb):
    """Dois títulos que slugificam diferente mas são o mesmo objeto do
    mundo: a escada do RFC-002 (título+entidades+NCD) aponta a residente e
    o promote devolve COLLISION em vez de criar a duplicata.

    Falsificável — sem a consulta à escada, isto criaria
    `concepts/ncd-distancia-de-compressao.md` ao lado da residente."""
    write_page(kb / "bundle", "concepts/aut-ncd.md",
               "---\ntype: authority_record\ntitle: NCD\n"
               "canonical: Distância de compressão normalizada\n"
               "aliases: [NCD]\nprivacy: local_only\n---\n# NCD\n")
    corpo = ("A NCD de Cilibrasi e Vitányi mede quanto dois textos se "
             "explicam: se o compressor aproveita um para codificar o "
             "outro, eles falam do mesmo objeto do mundo.")
    _promote(settings, title="Distância de compressão normalizada",
             content=corpo)
    r = _promote(settings, title="NCD (distância de compressão)",
                 content=corpo)
    assert r["op"] == "COLLISION", r
    assert r["target"] == "concepts/distancia-de-compressao-normalizada.md"
    assert r["score"] > 0.5


# ------------------------------------------------------------------ o gate
def test_creation_sobre_pagina_existente_e_rejeitado_pelo_gate(settings, kb):
    """`policy.path_collision`: a última linha de defesa, abaixo de todos
    os fluxos. Lê o FILESYSTEM — vale mesmo com a projeção atrasada e para
    qualquer chamador futuro que minta a intenção."""
    writer = BundleWriter(settings.path("knowledge"))
    doc = OKFDocument(
        rel_path="concepts/x.md", body="# X\n\nprimeira.\n",
        meta=OKFFrontMatter(type="concept", title="X", privacy="local_only"))
    writer.write([doc], log_kind="Creation", log_message="m",
                 commit_message="c")
    segunda = OKFDocument(
        rel_path="concepts/x.md", body="# X\n\nsobrescrita.\n",
        meta=OKFFrontMatter(type="concept", title="X", privacy="local_only"))
    with pytest.raises(HarnessRejection) as exc:
        writer.write([segunda], log_kind="Creation", log_message="m",
                     commit_message="c")
    assert any(f.rule == "policy.path_collision"
               for f in exc.value.findings.errors())
    # a intenção honesta continua passando — a regra pega a MENTIRA,
    # não a atualização
    writer.write([segunda], log_kind="Update", log_message="m",
                 commit_message="c")
    assert "sobrescrita" in (kb / "bundle" / "concepts" / "x.md").read_text()


# ------------------------------------------- fluxo de MÁQUINA (RFC-003 §4.4)
class _CompiladorDeTeste(MachinePageUseCase):
    """Mínimo que exercita o esqueleto imutável com decisão UPDATE."""
    MODULE = "compile"

    def __init__(self, settings, target: str):
        super().__init__(settings)
        self._target = target

    def _produce(self) -> DraftPage:
        return DraftPage(
            rel_path="concepts/novo-rascunho.md", title="Docker",
            body="# Docker\n\nCorpo recompilado pela máquina.\n",
            meta={"generated_via": "local:test",
                  "source_sha256": "0" * 64})

    def _reconcile(self, document, report) -> dict:
        return {"op": "UPDATE", "target": self._target}


def test_update_de_maquina_preserva_o_frontmatter_curado(settings, kb):
    """O agravante 3 do RFC: UPDATE reconstruía o frontmatter do zero e as
    tags curadas por humano evaporavam a cada recompilação, com
    `policy.metadata_shrink` (warn) como único guarda.

    Falsificável — sem `_merged_with_resident`, as tags somem."""
    _promote(settings, content="anotação humana",
             tags=["curada-a-mão"], description="minha descrição")
    resultado = _CompiladorDeTeste(settings, "concepts/docker.md").execute()
    assert resultado["op"] == "UPDATE"
    reader = BundleWriter(settings.path("knowledge")).reader
    meta = reader.load("concepts/docker.md").meta
    assert "curada-a-mão" in (meta.tags or []), (
        "a recompilação de máquina apagou a curadoria humana")
    assert meta.description == "minha descrição"
    assert "recompilado pela máquina" in reader.load(
        "concepts/docker.md").body
