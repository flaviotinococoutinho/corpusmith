"""F1-PR3 (ADR-41.4) — EditPage: a primeira escrita HUMANA de corpo.

Fecha a falha da "1ª correção" da tabela de viabilidade: o painel Wiki era
somente-leitura com um botão, não havia use case/endpoint/CLI de edição, e
a correção acontecia FORA do produto — onde o doctor nem detecta a
divergência (INV-002 compara `bundle_head` com o HEAD do Git, e edição não
commitada não move o HEAD).

Dois pontos que este PR trata e que os atos anteriores não precisavam:

1. **a prosa vai como escrita** — `normalize_machine_body` é o eixo de
   MÁQUINA (v0.8 §1.2); um ato humano que a chamasse reescreveria o texto
   do autor;
2. **o preview deixa de subdeclarar** — usava `reader.load().dumps()` como
   "antes", e a escrita reordena chaves do frontmatter, injeta campos com
   default e normaliza o fim do arquivo. Numa página editada à mão, o
   usuário via só a mudança que pediu e o disco mudava mais. Agora o diff
   é contra os bytes CRUS e a nota nomeia a reformatação.
"""
from __future__ import annotations
import pytest
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.git_store import GitStore
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.usecases.curate import ACTS, EditPage, UndoCurationAct
from llmwiki.usecases.next_actions import acts_for


@pytest.fixture
def base(settings, kb):
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/a.md",
                     body="# A\n\ntexto original do autor.",
                     meta=OKFFrontMatter(type="concept", title="Página A",
                                         privacy="local_only",
                                         generated_via="human:promote"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    return settings


# ============================================ o ato
def test_edita_corpo_e_o_texto_vai_como_escrito(base, kb):
    """A prosa humana NÃO passa pelo sanduíche: grafia idiossincrática do
    autor tem de sobreviver byte a byte."""
    novo = "# A\n\ntexto  com   espaçamento   proprio e postgres minúsculo.\n"
    out = EditPage(base, page="concepts/a.md", body=novo).execute()
    assert out["applied"]
    corpo = (kb / "bundle/concepts/a.md").read_text()
    assert novo.strip() in corpo, "a prosa foi reescrita"
    assert "postgres minúsculo" in corpo   # gazetteer NÃO canonizou


def test_edita_frontmatter_por_patch(base, kb):
    EditPage(base, page="concepts/a.md",
             meta_patch={"description": "resumo novo"}).execute()
    texto = (kb / "bundle/concepts/a.md").read_text()
    assert "description: resumo novo" in texto
    assert "texto original do autor" in texto    # corpo intocado


def test_preview_e_puro(base, kb):
    sha = GitStore(kb).head()
    out = EditPage(base, page="concepts/a.md",
                   body="# A\n\noutro.").execute(dry_run=True)
    assert out["applied"] is False
    assert "+outro." in out["preview"]["diffs"]["concepts/a.md"]
    assert GitStore(kb).head() == sha
    rt = connect(base.app_support / "runtime.db")
    assert rt.execute("SELECT COUNT(*) c FROM curation_acts"
                      ).fetchone()["c"] == 0
    rt.close()


def test_undo_de_edicao_devolve_os_bytes(base, kb):
    antes = (kb / "bundle/concepts/a.md").read_bytes()
    ato = EditPage(base, page="concepts/a.md",
                   body="# A\n\ntexto trocado.").execute()
    assert (kb / "bundle/concepts/a.md").read_bytes() != antes
    UndoCurationAct(base, act_id=ato["id"]).execute()
    assert (kb / "bundle/concepts/a.md").read_bytes() == antes


# ============================================ o que o ato RECUSA
def test_recusa_edicao_vazia(base):
    with pytest.raises(ValueError, match="nada a editar"):
        EditPage(base, page="concepts/a.md").execute(dry_run=True)


def test_recusa_renomear_pela_edicao(base):
    """A identidade OKF É o caminho da página (SPEC). Renomear por patch
    criaria duas verdades sobre a mesma coisa."""
    with pytest.raises(ValueError, match="identidade OKF"):
        EditPage(base, page="concepts/a.md",
                 meta_patch={"rel_path": "concepts/b.md"}).execute(dry_run=True)


def test_recusa_remover_campo_de_frontmatter(base):
    """Apagar declaração é gesto diferente de corrigir — e o gate acusaria
    `policy.metadata_shrink` de qualquer modo."""
    with pytest.raises(ValueError, match="não REMOVE"):
        EditPage(base, page="concepts/a.md",
                 meta_patch={"title": ""}).execute(dry_run=True)


def test_edicao_invalida_e_rejeitada_pelo_gate(base, kb):
    """O Harness continua soberano sobre a escrita humana: privacidade
    inválida não entra."""
    from llmwiki.harness.runner import HarnessRejection
    with pytest.raises((HarnessRejection, ValueError)):
        EditPage(base, page="concepts/a.md",
                 meta_patch={"privacy": "publico-irrestrito"}).execute()


# ============================ o preview deixa de subdeclarar (o achado)
def test_preview_declara_a_reformatacao_de_pagina_editada_a_mao(base, kb):
    """Página com ordem própria de chave e sem `tags`: a escrita vai
    reordenar e injetar o default. Antes o diff usava `dumps()` como
    'antes' e isso ficava INVISÍVEL — o usuário via só o que pediu."""
    crua = ("---\ntitle: A mao\ntype: concept\nprivacy: local_only\n"
            "generated_via: human:promote\n---\n\n# A mao\n\ncorpo.")
    (kb / "bundle/concepts/mao.md").write_text(crua)
    GitStore(kb).commit("página editada à mão")
    out = EditPage(base, page="concepts/mao.md",
                   body="# A mao\n\ncorpo corrigido.").execute(dry_run=True)
    nota = out["preview"]["note"]
    assert "NORMALIZA o formato" in nota and "concepts/mao.md" in nota
    diff = out["preview"]["diffs"]["concepts/mao.md"]
    # a reordenação aparece no diff, junto com a mudança pedida
    assert "+tags: []" in diff and "+corpo corrigido." in diff


def test_pagina_ja_canonica_nao_recebe_aviso_de_reformatacao(base):
    out = EditPage(base, page="concepts/a.md",
                   body="# A\n\noutro.").execute(dry_run=True)
    assert "NORMALIZA o formato" not in out["preview"]["note"]


# ============================================ a fila passa a ter destino
@pytest.mark.parametrize("kind", ["contested", "stale"])
def test_contested_e_stale_agora_oferecem_edit(kind):
    """Eram os dois kinds sem ato: `invalidate` afirmaria expiração no
    mundo que nenhum dos dois declara. Corrigir o corpo não afirma nada."""
    ofertas = acts_for({"kind": kind, "target": "concepts/a.md",
                        "action": {"type": "resolve",
                                   "target": "concepts/a.md"}})
    assert [o["act"] for o in ofertas] == ["edit"]
    assert ofertas[0]["needs"] == ["body"]
    assert "edit" in ACTS


@pytest.mark.parametrize("kind", ["question", "inbox", "review"])
def test_kinds_sem_ato_continuam_sem_ato(kind):
    assert acts_for({"kind": kind, "target": "concepts/a.md",
                     "action": {}}) == []


# =================== a superfície de edição: campo longo, com valor inicial
def test_oferta_declara_campo_longo_e_de_onde_vem_o_valor_inicial():
    """`body` não é campo curto como `page`. Quem declara isso é a OFERTA:
    a alternativa era o `.tsx` saber o nome do ato, e é justamente o que os
    testes de contrato existem para evitar."""
    oferta = acts_for({"kind": "contested", "target": "concepts/a.md",
                       "action": {}})[0]
    assert oferta["multiline"] == ["body"]
    assert oferta["prefill"] == {"body": {"page": "concepts/a.md",
                                         "field": "body"}}
    # o que se declara longo/pré-preenchido TEM de ser algo que se pede
    assert set(oferta["multiline"]) <= set(oferta["needs"])
    assert set(oferta["prefill"]) <= set(oferta["needs"])


def test_o_campo_do_prefill_existe_na_resposta_da_pagina(base, kb):
    """A garantia que IMPORTA: sem ela o textarea abriria vazio e aplicar
    SUBSTITUIRIA a página que o usuário quis corrigir. Prova que o
    `field` declarado é servido pelo endpoint que a interface consulta —
    e que o valor é o corpo atual, não uma projeção."""
    from fastapi.testclient import TestClient
    from llmwiki.api.system import build_app
    from llmwiki.runtime.events import EventBus
    from llmwiki.runtime.governor import Governor
    from llmwiki.runtime.queue import JobQueue
    rt = connect(base.app_support / "runtime.db")
    app = build_app(base, JobQueue(rt), Governor(base, rt), EventBus(rt),
                    token="t3")
    oferta = acts_for({"kind": "contested", "target": "concepts/a.md",
                       "action": {}})[0]
    fonte = oferta["prefill"]["body"]
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": "t3"})
        r = c.get("/cockpit/page", params={"path": fonte["page"]})
        assert r.status_code == 200, r.text
        assert fonte["field"] in r.json(), "prefill aponta para campo inexistente"
        assert "texto original do autor" in r.json()[fonte["field"]]


def test_reenviar_o_corpo_pre_preenchido_nao_muda_nada(base, kb):
    """Consequência do prefill: abrir o dialog e aplicar sem digitar é
    NOOP no conteúdo — o usuário não perde a página por reflexo."""
    atual = base.path("knowledge") / "bundle/concepts/a.md"
    from llmwiki.okf.bundle import BundleReader
    corpo = BundleReader(base.path("knowledge") / "bundle").load(
        "concepts/a.md").body
    antes = atual.read_bytes()
    out = EditPage(base, page="concepts/a.md", body=corpo).execute(dry_run=True)
    assert out["preview"]["diffs"]["concepts/a.md"] == ""
    assert atual.read_bytes() == antes
