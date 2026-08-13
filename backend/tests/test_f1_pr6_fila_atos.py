"""F1-PR6 — o item da fila declara os ATOS que o clique pode abrir.

Não existe runner de teste de UI no desktop (nem vitest, nem jest, nem
@testing-library — só `tsc --noEmit` no gate), e o docs/15 rejeitou
explicitamente teste-por-grep em `.tsx` ("passa a verde com um comentário
e falha com um rename"). A garantia honesta tem duas pernas:

1. **tipagem** no cliente — só vira gate depois que `nextActions()` deixa
   de devolver `any`; feito neste PR;
2. **contrato no backend** — estes testes. O mais forte prova por
   `inspect.signature` que `params + needs` CONSTROEM o ato: sem ele, o
   conhecimento das assinaturas migra para o `.tsx`, onde nenhum teste de
   backend o alcança.

O que estes testes NÃO provam, e é honesto dizer: que o `onClick` foi
religado. O `.tsx` segue sem cobertura executável — a diferença é que o
payload, os parâmetros e os tipos deixam de ser suposição.
"""
from __future__ import annotations
import inspect
import pytest
from fastapi.testclient import TestClient
from corpusmith.api.system import build_app
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.git_store import GitStore
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.runtime.events import EventBus
from corpusmith.runtime.governor import Governor
from corpusmith.runtime.queue import JobQueue
from corpusmith.usecases.curate import ACTS
from corpusmith.usecases.next_actions import NextActions, acts_for

TOKEN = "t6"
KINDS = ["review", "question", "low_yield", "stale", "inbox", "bridge",
         "contradiction"]


def _doc(rel, title, body):
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only",
                                           generated_via="human:promote"))


@pytest.fixture
def base(settings, kb):
    BundleWriter(kb).write(
        [_doc("concepts/a.md", "Página A", "# A\n\nprosa."),
         _doc("concepts/b.md", "Página B", "# B\n\noutra.")],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT OR REPLACE INTO graph_bridges VALUES (?,?,?,?,?)",
                ("concepts/a.md", "concepts/b.md", 0.15, 3, 7))
    idx.commit()
    idx.close()
    return settings


@pytest.fixture
def client(base):
    rt = connect(base.app_support / "runtime.db")
    app = build_app(base, JobQueue(rt), Governor(base, rt), EventBus(rt),
                    token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-corpusmith-auth": TOKEN})
        yield c


# ================================= o registro fechado manda na interface
@pytest.mark.parametrize("kind", KINDS)
def test_acts_for_so_oferece_atos_do_registro(kind):
    """Impede a UI oferecer um ato que não existe — é o que fará o
    F1-PR5 (merge) acender a opção só quando o ato existir de verdade."""
    item = {"kind": kind, "target": "concepts/x.md",
            "action": {"type": "x", "src": "concepts/a.md",
                       "dst": "concepts/b.md",
                       "pages": ["concepts/x.md", "concepts/y.md"]}}
    for oferta in acts_for(item):
        assert oferta["act"] in ACTS, f"{kind} ofereceu ato inexistente"


def test_params_ofertados_constroem_o_ato_de_verdade():
    """O teste FORTE: os obrigatórios de cada ato têm de estar em
    params ∪ needs. Sem ele, as assinaturas migram para o .tsx."""
    itens = [
        {"kind": "bridge", "target": "concepts/a.md",
         "action": {"src": "concepts/a.md", "dst": "concepts/b.md"}},
        {"kind": "contradiction", "target": "concepts/x.md",
         "action": {"pages": ["concepts/x.md", "concepts/y.md"]}},
    ]
    vistos = 0
    for item in itens:
        for oferta in acts_for(item):
            assinatura = inspect.signature(ACTS[oferta["act"]].__init__)
            obrigatorios = {
                nome for nome, p in assinatura.parameters.items()
                if p.default is inspect.Parameter.empty
                and nome not in ("self", "settings", "notify", "args",
                                 "kwargs")}
            disponiveis = set(oferta["params"]) | set(oferta["needs"])
            assert obrigatorios <= disponiveis, (
                f"{oferta['act']}: falta {obrigatorios - disponiveis}")
            vistos += 1
    assert vistos >= 3


# ================================= o que NÃO se oferece, e por quê
@pytest.mark.parametrize("kind", ["review", "question", "inbox"])
def test_kinds_sem_ato_declaram_lista_vazia(kind):
    """Declarado, não escondido: estes continuam navegando por aba."""
    assert acts_for({"kind": kind, "target": "concepts/x.md",
                     "action": {"type": "read",
                                "target": "concepts/x.md"}}) == []


@pytest.mark.parametrize("kind", ["low_yield", "stale"])
def test_stale_e_contested_oferecem_edit_e_nunca_invalidate(kind):
    """A recusa que IMPORTA aqui é semântica e permanece: `invalidate`
    afirma que o fato EXPIROU NO MUNDO, e nem "precisa de revisão" (stale)
    nem "deu beco" (contested) afirmaram isso — os parâmetros fechariam.
    Desde o F1-PR3 estes kinds oferecem `edit`: corrigir o corpo não
    afirma nada sobre o mundo."""
    ofertas = acts_for({"kind": kind, "target": "concepts/x.md",
                        "action": {"type": "resolve",
                                   "target": "concepts/x.md"}})
    atos = {o["act"] for o in ofertas}
    assert atos == {"edit"}
    assert "invalidate" not in atos


def test_ponte_nao_oferece_unlink():
    """O item pede REFORÇAR o fio fraco; `unlink` destruiria exatamente o
    que ele pede. Os params fechariam — a recusa é semântica."""
    ofertas = acts_for({"kind": "bridge", "target": "concepts/a.md",
                        "action": {"src": "concepts/a.md",
                                   "dst": "concepts/b.md"}})
    assert {o["act"] for o in ofertas} == {"link"}
    # os dois sentidos, porque a direção do par é lexicográfica no leiden
    assert {(o["params"]["src"], o["params"]["dst"]) for o in ofertas} == {
        ("concepts/a.md", "concepts/b.md"),
        ("concepts/b.md", "concepts/a.md")}


def test_contradicao_com_uma_pagina_nao_oferece_supersede():
    """Com uma página só, `page == successor` levantaria ValueError já no
    plano — a guarda evita oferecer um botão que sempre falha."""
    ofertas = acts_for({"kind": "contradiction", "target": "concepts/x.md",
                        "action": {"pages": ["concepts/x.md"]}})
    assert {o["act"] for o in ofertas} == {"invalidate"}


# ================================= o payload chega pela API
def test_todo_item_da_fila_traz_acts(client):
    corpo = client.get("/cockpit/next-actions").json()
    assert corpo["actions"], "a fila precisa ter item para o teste valer"
    for item in corpo["actions"]:
        assert isinstance(item["acts"], list)
        for oferta in item["acts"]:
            assert set(oferta) >= {"act", "params", "needs", "label"}
            assert oferta["act"] in ACTS


def test_item_de_ponte_traz_a_oferta_de_link_pronta(client):
    ponte = next(i for i in client.get("/cockpit/next-actions").json()["actions"]
                 if i["kind"] == "bridge")
    assert ponte["acts"][0] == {
        "act": "link",
        "params": {"src": "concepts/a.md", "dst": "concepts/b.md"},
        "needs": [], "label": "Linkar a → b"}


def test_round_trip_item_da_fila_abre_preview(client, base, kb):
    """'O clique abre um ato com preview', provado sem tocar em .tsx: pega
    a oferta que a fila emitiu e POSTa exatamente ela."""
    ponte = next(i for i in client.get("/cockpit/next-actions").json()["actions"]
                 if i["kind"] == "bridge")
    oferta = ponte["acts"][0]
    sha = GitStore(kb).head()
    r = client.post("/curation/act", json={"act": oferta["act"],
                                           "params": oferta["params"],
                                           "dry_run": True})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["applied"] is False and corpo["preview"]["pages"]
    assert GitStore(kb).head() == sha        # preview não move o HEAD


def test_preview_bloqueado_e_200_com_blocked_nao_422(client, kb):
    """Contrato de que o dialog depende para DESABILITAR o botão: no
    dry-run o `return` precede o `raise`, então preview bloqueado é 200."""
    (kb / "bundle/concepts/ruim.md").write_text(
        "---\ntype: concept\ntitle: Ruim\n---\n\n# Ruim\n\ncorpo.\n")
    GitStore(kb).commit("página crua sem privacy")
    r = client.post("/curation/act", json={
        "act": "invalidate", "params": {"page": "concepts/ruim.md"},
        "dry_run": True})
    assert r.status_code == 200, r.text
    assert r.json()["preview"]["blocked"] is True
    # o MESMO corpo com dry_run=false vira 422 nomeado
    r2 = client.post("/curation/act", json={
        "act": "invalidate", "params": {"page": "concepts/ruim.md"},
        "dry_run": False})
    assert r2.status_code == 422
    assert r2.json()["error"] == "harness_rejection"


def test_enriquecimento_nao_altera_a_ordem_da_fila(base):
    """Guarda da restrição do docs/15 §6: o PR6 não toca o ranking."""
    fila = NextActions(base).execute()["actions"]
    densidades = [i["value"] / i["cost_min"] for i in fila]
    assert densidades == sorted(densidades, reverse=True)
    assert all("acts" in i for i in fila)
