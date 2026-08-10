"""F1-PR1 (ADR-41) — o ATO DE CURADORIA humano existe.

Antes daqui havia UM caminho de escrita (`okf/writer.py`) e ele só era
dirigido por use cases de MÁQUINA: `_supersede` era método protegido de
`MachinePageUseCase`, e o finding `policy.contradiction_candidate` mandava
"resolva com supersede/invalid_at ou funda as páginas" sem que existisse
como fazer isso de dentro do produto.

O que estes testes cravam: preview é PURO (HEAD imóvel, nada registrado),
aplicar faz UM commit e deixa trilha, rejeição de política vira 422 legível
em TODA superfície de escrita (não só na nova), e o esqueleto do ato é
fechado como o de máquina.
"""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.facades.curation_acts import CurationActsFacade
from llmwiki.harness.runner import HarnessRejection
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.git_store import GitStore
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue
from llmwiki.usecases.curate import ACTS, CurationAct, SupersedePage

TOKEN = "t1"


def _doc(rel: str, title: str, body: str, **meta) -> OKFDocument:
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


@pytest.fixture
def base(settings, kb):
    """Duas páginas e um link de C para A — o dependente TMS."""
    BundleWriter(kb).write(
        [_doc("concepts/a.md", "A antiga", "# A\n\nversão antiga do fato."),
         _doc("concepts/b.md", "B nova", "# B\n\nversão nova do fato."),
         _doc("concepts/c.md", "C depende",
              "# C\n\nver [A antiga](/concepts/a.md).")],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    return settings


@pytest.fixture
def client(base, kb):
    rt = connect(base.app_support / "runtime.db")
    app = build_app(base, JobQueue(rt), Governor(base, rt), EventBus(rt),
                    token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": TOKEN})
        yield c


# ===================================== preview é PURO (o coração do modelo)
def test_supersede_preview_nao_move_head_e_nao_registra_ato(base, kb):
    head_antes = GitStore(kb).repo.head.commit.hexsha
    out = SupersedePage(base, page="concepts/a.md",
                        successor="concepts/b.md").execute(dry_run=True)
    p = out["preview"]
    assert out["applied"] is False and out["dry_run"] is True
    assert p["pages"] == ["concepts/a.md"]
    assert "superseded_by" in p["diffs"]["concepts/a.md"]
    assert p["blocked"] is False
    # TMS: quem depende da página entra no preview para revisão humana
    assert p["dependents"] == ["concepts/c.md"]
    # nenhum efeito: HEAD imóvel e trilha vazia
    assert GitStore(kb).repo.head.commit.hexsha == head_antes
    rt = connect(base.app_support / "runtime.db")
    assert rt.execute("SELECT COUNT(*) c FROM curation_acts"
                      ).fetchone()["c"] == 0
    rt.close()
    # e o corpo no disco continua sem a marca
    assert "superseded_by" not in (kb / "bundle/concepts/a.md").read_text()


def test_supersede_aplica_um_commit_e_registra_o_ato(base, kb):
    head_antes = GitStore(kb).repo.head.commit.hexsha
    out = SupersedePage(base, page="concepts/a.md",
                        successor="concepts/b.md",
                        reason="medição refeita").execute()
    assert out["applied"] is True and out["commit"]
    texto = (kb / "bundle/concepts/a.md").read_text()
    assert "superseded_by: concepts/b.md" in texto
    assert "invalid_at:" in texto
    # invalidar-nunca-apagar: a página CONTINUA existindo e legível
    assert "versão antiga do fato" in texto
    # exatamente UM commit novo
    repo = GitStore(kb).repo
    assert repo.head.commit.hexsha != head_antes
    assert len(list(repo.iter_commits(f"{head_antes}..HEAD"))) == 1
    # trilha: o ato registrado com o sha do commit (Git segue a autoridade)
    rt = connect(base.app_support / "runtime.db")
    linha = rt.execute("SELECT act, commit_sha, pages FROM curation_acts"
                       ).fetchone()
    rt.close()
    assert linha["act"] == "supersede" and linha["commit_sha"]
    assert "concepts/a.md" in linha["pages"]
    # e o log.md registra a natureza do ato
    assert "[Deprecation]" in (kb / "bundle/log.md").read_text()


def test_invalidate_declara_tempo_de_mundo(base, kb):
    out = CurationActsFacade(base).act(
        "invalidate", {"page": "concepts/a.md", "invalid_at": "2024-03-01",
                       "reason": "contrato encerrado"})
    assert out["applied"] is True
    texto = (kb / "bundle/concepts/a.md").read_text()
    assert "invalid_at: '2024-03-01" in texto   # ISO com tempo de MUNDO
    assert "superseded_by" not in texto     # invalidar ≠ suceder
    assert "versão antiga do fato" in texto


def test_supersede_recusa_alvo_inexistente_e_autossucessao(base):
    with pytest.raises(ValueError):
        SupersedePage(base, page="concepts/a.md",
                      successor="concepts/a.md").execute(dry_run=True)
    with pytest.raises(FileNotFoundError):
        SupersedePage(base, page="concepts/a.md",
                      successor="concepts/nao-existe.md").execute(dry_run=True)


# ===================================== o esqueleto é FECHADO
def test_esqueleto_do_ato_e_fechado_para_modificacao():
    """Irmão do INV-ARCH-006: nenhum ato pode sobrescrever `execute` — o
    rito (preview → gate → writer → trilha → reindex) é estrutural."""
    for nome, cls in ACTS.items():
        assert "execute" not in vars(cls), (
            f"{nome}: sobrescreveu execute — o rito deixaria de ser garantido")
        assert issubclass(cls, CurationAct)


def _nomes_do_modulo(modulo) -> tuple[set[str], set[str]]:
    """(nomes importados, nomes chamados) via AST — asserção ESTRUTURAL.

    Comentário e docstring não contam: casar string em fonte passaria a
    verde com um comentário e falharia com um rename (é a crítica que o
    docs/15 §5 faz ao teste-por-grep)."""
    import ast
    import inspect
    arvore = ast.parse(inspect.getsource(modulo))
    importados, chamados, origens = set(), set(), set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom):
            origens.add(no.module or "")
            importados |= {a.name for a in no.names}
        elif isinstance(no, ast.Import):
            importados |= {a.name for a in no.names}
        elif isinstance(no, ast.Call):
            alvo = no.func
            nome = getattr(alvo, "id", None) or getattr(alvo, "attr", None)
            if nome:
                chamados.add(nome)
    return importados | origens, chamados


def test_ato_nao_normaliza_prosa_humana():
    """v0.8 §1.2: o sanduíche de normalização de corpo é do eixo MÁQUINA.
    Um ato humano que o chamasse reescreveria a prosa do usuário."""
    import llmwiki.usecases.curate.base as ato_base
    import llmwiki.usecases.curate.invalidate as invalidar
    import llmwiki.usecases.curate.supersede as suceder
    for modulo in (ato_base, invalidar, suceder):
        importados, chamados = _nomes_do_modulo(modulo)
        assert "normalize_machine_body" not in importados | chamados, (
            f"{modulo.__name__}: prosa humana não passa pelo sanduíche")


def test_os_dois_eixos_usam_a_mesma_definicao_de_sucessao():
    """A transformação mora no kernel PURO: o eixo máquina não conhece o
    eixo humano (seria ciclo e inverteria o gradiente de mutabilidade)."""
    from llmwiki.usecases import base as maquina
    importados, chamados = _nomes_do_modulo(maquina)
    assert "superseded_meta" in importados and "superseded_meta" in chamados
    assert not any(origem.endswith("curate") or ".curate." in origem
                   for origem in importados), \
        "o eixo máquina importou o eixo humano"


# ===================================== 422 vale para TODA escrita (G-7)
def test_rejeicao_de_politica_vira_422_legivel_no_ato(client, kb):
    """Uma página sem `privacy` é rejeitada pela política. O preview já
    prevê o erro, então o ato recusa ANTES de começar o rito."""
    # grava uma página crua inválida direto no bundle (simula edição externa)
    ruim = kb / "bundle/concepts/ruim.md"
    ruim.write_text('---\ntype: concept\ntitle: Ruim\n---\n\n# Ruim\n\ncorpo.\n')
    GitStore(kb).commit("página crua sem privacy")
    r = client.post("/curation/act", json={
        "act": "invalidate", "params": {"page": "concepts/ruim.md"},
        "dry_run": False})
    assert r.status_code == 422, r.text
    corpo = r.json()
    assert corpo["error"] == "harness_rejection"
    assert corpo["findings"] and any(f["severity"] == "error"
                                     for f in corpo["findings"])


def test_422_vale_tambem_para_as_superficies_antigas(client):
    """G-7 transversal: o handler é único, então /cockpit/promote — que
    ANTES devolvia 500 — passa a devolver 422 com a regra nomeada."""
    r = client.post("/cockpit/promote", json={
        "kind": "decision", "title": "X", "content": "y",
        "source": "chat", "privacy": "valor-invalido"})
    assert r.status_code in (400, 422), r.text
    assert r.status_code != 500


# ===================================== fiação: API e CLI
def test_endpoint_lista_atos_e_faz_preview_sem_efeito(client, base, kb):
    assert set(client.get("/curation/acts").json()["acts"]) == set(ACTS)
    head_antes = GitStore(kb).repo.head.commit.hexsha
    r = client.post("/curation/act", json={
        "act": "supersede",
        "params": {"page": "concepts/a.md", "successor": "concepts/b.md"},
        "dry_run": True})
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is False
    assert GitStore(kb).repo.head.commit.hexsha == head_antes


def test_endpoint_aplica_e_aparece_no_historico(client):
    r = client.post("/curation/act", json={
        "act": "supersede",
        "params": {"page": "concepts/a.md", "successor": "concepts/b.md"},
        "dry_run": False})
    assert r.status_code == 200, r.text
    historico = client.get("/curation/history").json()["acts"]
    assert historico and historico[0]["act"] == "supersede"
    assert historico[0]["params"]["successor"] == "concepts/b.md"


def test_ato_desconhecido_e_404_nao_500(client):
    r = client.post("/curation/act", json={"act": "explodir", "params": {},
                                           "dry_run": True})
    assert r.status_code == 404


def test_dry_run_e_obrigatorio_no_corpo(client):
    """Sem default silencioso: esquecer o campo não pode escrever."""
    r = client.post("/curation/act", json={
        "act": "supersede",
        "params": {"page": "concepts/a.md", "successor": "concepts/b.md"}})
    assert r.status_code == 422       # validação da borda tipada


def test_cli_curate_dry_run_nao_escreve(base, kb, capsys):
    from llmwiki.cli import cmd_curate
    import argparse
    args = argparse.Namespace(
        act="supersede",
        params=["page=concepts/a.md", "successor=concepts/b.md"],
        dry_run=True)
    head_antes = GitStore(kb).repo.head.commit.hexsha
    assert cmd_curate(base, args) == 0
    assert "superseded_by" in capsys.readouterr().out
    assert GitStore(kb).repo.head.commit.hexsha == head_antes


# ===================================== D-H: o rito inteiro é serializado
def test_dois_atos_concorrentes_nao_entrelacam_o_rito(base, kb):
    """D-H (docs/15 §5): o flock do writer serializa só a ESCRITA — o
    plano podia ser computado sobre estado que outro ato mudou entre o
    plan e o apply, e o rebuild corria fora de qualquer lock. O esqueleto
    agora segura um mutex do processo do plan ao rebuild: numa corrida,
    o segundo ato PLANEJA depois de o primeiro reindexar."""
    import threading
    from llmwiki.usecases.curate.invalidate import InvalidatePage
    trace: list[str] = []
    original_plan = InvalidatePage._plan
    original_apply = InvalidatePage._apply
    barreira = threading.Event()

    def plan_instrumentado(self):
        trace.append(f"plan:{self._page}")
        return original_plan(self)

    def apply_lento(self, preview):
        if self._page == "concepts/a.md":
            barreira.set()               # B pode tentar começar AGORA
            import time
            time.sleep(0.3)              # janela generosa para B invadir
        out = original_apply(self, preview)
        trace.append(f"applied:{self._page}")
        return out

    InvalidatePage._plan = plan_instrumentado
    InvalidatePage._apply = apply_lento
    try:
        t = threading.Thread(target=lambda: InvalidatePage(
            base, page="concepts/a.md", reason="corrida").execute())
        t.start()
        barreira.wait(5.0)               # A está DENTRO do apply
        InvalidatePage(base, page="concepts/b.md",
                       reason="corrida").execute()
        t.join(10.0)
    finally:
        InvalidatePage._plan = original_plan
        InvalidatePage._apply = original_apply
    # sem o mutex, o plan de B invade a janela entre o plan de A e a
    # conclusão do apply de A — B teria planejado sobre estado que A mudou
    assert trace == ["plan:concepts/a.md", "applied:concepts/a.md",
                     "plan:concepts/b.md", "applied:concepts/b.md"], trace
