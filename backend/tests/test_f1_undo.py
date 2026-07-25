"""F1-PR2 (ADR-41) — desfazer sem sair do produto, e sem apagar nada.

O rito é o INVERSO do óbvio, por uma razão estrutural: `BundleWriter.write`
roda o gate e SÓ ENTÃO escreve, então um `git revert` no worktree colocaria
bytes antes do Harness e recuperar de uma rejeição exigiria
`checkout`/`reset` — as operações que "invalidar-nunca-apagar" proíbe.
O undo lê o conteúdo do commit PAI e reescreve pelo caminho normal:
escrita PARA A FRENTE, gateada, com commit novo, e o commit desfeito
seguindo alcançável.

O que estes testes cravam: restauração byte a byte, undo registrado como
ATO NOVO (nunca apagando a linha do original), o rito não usando `revert`
nem `reset`, e o limite DECLARADO da criação (recusa nomeada em vez de
escolher em silêncio qual invariante cede).
"""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.facades.curation_acts import CurationActsFacade
from llmwiki.kernel.curation import UndoNotExpressible
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.git_store import GitStore
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue
from llmwiki.usecases.curate import SupersedePage, UndoCurationAct

TOKEN = "t2"


def _doc(rel: str, title: str, body: str) -> OKFDocument:
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only",
                                           generated_via="human:promote"))


@pytest.fixture
def base(settings, kb):
    BundleWriter(kb).write(
        [_doc("concepts/a.md", "A antiga", "# A\n\nversão antiga do fato."),
         _doc("concepts/b.md", "B nova", "# B\n\nversão nova do fato.")],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    return settings


@pytest.fixture
def client(base):
    rt = connect(base.app_support / "runtime.db")
    app = build_app(base, JobQueue(rt), Governor(base, rt), EventBus(rt),
                    token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": TOKEN})
        yield c


# ===================================== o coração: nada se perde
def test_undo_restaura_bytes_e_cria_novo_ato(base, kb):
    antes = (kb / "bundle/concepts/a.md").read_bytes()
    sha_antes = GitStore(kb).repo.head.commit.hexsha

    aplicado = SupersedePage(base, page="concepts/a.md",
                             successor="concepts/b.md").execute()
    sha_do_ato = aplicado["commit"]
    assert (kb / "bundle/concepts/a.md").read_bytes() != antes

    desfeito = UndoCurationAct(base, act_id=aplicado["id"]).execute()

    # (a) bytes idênticos, byte a byte
    assert (kb / "bundle/concepts/a.md").read_bytes() == antes
    # (b) HEAD AVANÇOU e o commit desfeito segue alcançável (nada reescrito)
    repo = GitStore(kb).repo
    assert repo.head.commit.hexsha not in (sha_antes, sha_do_ato)
    assert GitStore(kb).has_commit(sha_do_ato)
    # (c) o undo é um ATO NOVO; a linha do original permanece, marcada
    rt = connect(base.app_support / "runtime.db")
    linhas = {r["id"]: dict(r) for r in rt.execute(
        "SELECT id, act, undoes, undone_by FROM curation_acts")}
    rt.close()
    assert len(linhas) == 2
    assert linhas[aplicado["id"]]["act"] == "supersede"
    assert linhas[aplicado["id"]]["undone_by"] == desfeito["id"]
    assert linhas[desfeito["id"]]["act"] == "undo"
    assert linhas[desfeito["id"]]["undoes"] == aplicado["id"]
    # (d) o log registra o desfazer
    assert "desfeito o ato" in (kb / "bundle/log.md").read_text()


def test_undo_preview_e_puro(base, kb):
    aplicado = SupersedePage(base, page="concepts/a.md",
                             successor="concepts/b.md").execute()
    sha = GitStore(kb).repo.head.commit.hexsha
    texto = (kb / "bundle/concepts/a.md").read_text()
    out = UndoCurationAct(base, act_id=aplicado["id"]).execute(dry_run=True)
    assert out["applied"] is False
    assert "superseded_by" in out["preview"]["diffs"]["concepts/a.md"]
    assert "escrita para a frente" in out["preview"]["note"]
    # nenhum efeito
    assert GitStore(kb).repo.head.commit.hexsha == sha
    assert (kb / "bundle/concepts/a.md").read_text() == texto
    rt = connect(base.app_support / "runtime.db")
    assert rt.execute("SELECT COUNT(*) c FROM curation_acts"
                      ).fetchone()["c"] == 1
    rt.close()


def test_undo_duas_vezes_recusa(base):
    aplicado = SupersedePage(base, page="concepts/a.md",
                             successor="concepts/b.md").execute()
    UndoCurationAct(base, act_id=aplicado["id"]).execute()
    with pytest.raises(ValueError, match="já foi desfeito"):
        UndoCurationAct(base, act_id=aplicado["id"]).execute()


def test_undo_do_undo_refaz(base, kb):
    """O undo é um ato como qualquer outro — desfazê-lo restaura o efeito
    original. Sem caso especial: cai no MESMO rito."""
    original = (kb / "bundle/concepts/a.md").read_bytes()
    aplicado = SupersedePage(base, page="concepts/a.md",
                             successor="concepts/b.md").execute()
    com_supersede = (kb / "bundle/concepts/a.md").read_bytes()
    desfeito = UndoCurationAct(base, act_id=aplicado["id"]).execute()
    assert (kb / "bundle/concepts/a.md").read_bytes() == original
    UndoCurationAct(base, act_id=desfeito["id"]).execute()
    assert (kb / "bundle/concepts/a.md").read_bytes() == com_supersede


def test_undo_avisa_quando_sobrescreve_trabalho_posterior(base, kb):
    """Desfazer um ato ANTIGO sobrescreve o que veio depois. O diff mostra;
    a nota NOMEIA o risco — propõe, não decide."""
    aplicado = SupersedePage(base, page="concepts/a.md",
                             successor="concepts/b.md").execute()
    # uma edição posterior na mesma página, por fora do ato
    atual = BundleWriter(kb).reader.load("concepts/a.md")
    meta = atual.meta.model_dump(exclude_none=True)
    meta["description"] = "anotação posterior"
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/a.md", body=atual.body,
                     meta=OKFFrontMatter(**meta))],
        log_kind="Update", log_message="posterior",
        commit_message="posterior")
    out = UndoCurationAct(base, act_id=aplicado["id"]).execute(dry_run=True)
    assert "ATENÇÃO" in out["preview"]["note"]
    assert "concepts/a.md" in out["preview"]["note"]


def test_undo_recusa_desfazer_criacao_com_motivo_nomeado(base, kb):
    """LIMITE DECLARADO: 'estado anterior = ausente' só seria expressável
    removendo, e `remove` não roda o Harness. Recusar nomeando o motivo é
    mais honesto que escolher em silêncio qual invariante cede."""
    # simula um ato que CRIOU uma página (nenhum ato da Fase 1 faz isso)
    BundleWriter(kb).write(
        [_doc("concepts/nova.md", "Nova", "# Nova\n\ncriada agora.")],
        log_kind="Creation", log_message="cria", commit_message="cria")
    sha = GitStore(kb).repo.head.commit.hexsha
    rt = connect(base.app_support / "runtime.db")
    rt.execute("INSERT INTO curation_acts(act, params, commit_sha, pages) "
               "VALUES ('supersede','{}',?,?)",
               (sha, '["concepts/nova.md"]'))
    rt.commit()
    act_id = rt.execute("SELECT MAX(id) m FROM curation_acts").fetchone()["m"]
    rt.close()
    with pytest.raises(UndoNotExpressible, match="CRIAÇÃO"):
        UndoCurationAct(base, act_id=act_id).execute(dry_run=True)
    # e a página criada continua lá — recusar não destrói nada
    assert (kb / "bundle/concepts/nova.md").exists()


def test_trilha_do_undo_e_atomica(base, monkeypatch):
    """A linha do undo e os vínculos `undoes`/`undone_by` entram na MESMA
    transação: se a gravação falhar no meio, a trilha não pode ficar
    afirmando um undo sem o vínculo que o explica. Simulo a falha DEPOIS
    do INSERT e exijo que nada tenha sobrado."""
    aplicado = SupersedePage(base, page="concepts/a.md",
                             successor="concepts/b.md").execute()

    def explode(self, conn, act_id):
        raise RuntimeError("falha simulada após o INSERT")

    # patch na SUBCLASSE: ela sobrescreve o hook, então patchar a base não
    # teria efeito (o teste falhou assim primeiro, e é o comportamento certo)
    monkeypatch.setattr(UndoCurationAct, "_record_extra", explode)
    with pytest.raises(RuntimeError, match="falha simulada"):
        UndoCurationAct(base, act_id=aplicado["id"]).execute()
    rt = connect(base.app_support / "runtime.db")
    linhas = rt.execute("SELECT id, act, undoes, undone_by "
                        "FROM curation_acts").fetchall()
    rt.close()
    # só o supersede original; nenhuma linha de undo meio-gravada
    assert [r["act"] for r in linhas] == ["supersede"]
    assert linhas[0]["undone_by"] is None


def test_undo_de_ato_inexistente_e_keyerror(base):
    with pytest.raises(KeyError):
        UndoCurationAct(base, act_id=999).execute(dry_run=True)


def test_trilha_divergente_do_git_recusa_com_erro_estavel(base, kb):
    """A trilha é PROJEÇÃO (runtime.db, restaurável de backup); o Git é a
    AUTORIDADE. Quando discordam — cenário real, porque `RestoreBackup`
    restaura o runtime.db — o sha registrado pode não existir.

    Sem a guarda, o GitPython vazava `ValueError: SHA … could not be
    resolved` (mensagem interna, e 400 na API). O DoD do AGENTS.md §9 exige
    erro com código estável."""
    rt = connect(base.app_support / "runtime.db")
    rt.execute("INSERT INTO curation_acts(act, params, commit_sha, pages) "
               "VALUES ('supersede','{}',?,?)",
               ("deadbeef" * 5, '["concepts/a.md"]'))
    rt.commit()
    act_id = rt.execute("SELECT MAX(id) m FROM curation_acts").fetchone()["m"]
    rt.close()
    antes = (kb / "bundle/concepts/a.md").read_bytes()
    with pytest.raises(UndoNotExpressible, match="divergiram"):
        UndoCurationAct(base, act_id=act_id).execute(dry_run=True)
    # "nada será tocado" não é só promessa do texto
    assert (kb / "bundle/concepts/a.md").read_bytes() == antes


# ===================================== o rito NÃO usa revert/reset/checkout
def test_o_undo_nao_usa_revert_reset_nem_checkout():
    """D-C do docs/15: essas operações colocariam bytes antes do gate (ou
    apagariam histórico). Asserção ESTRUTURAL por AST — comentário e
    docstring não contam (o docstring do módulo cita `git revert` para
    explicar por que NÃO o usa)."""
    import ast
    import inspect
    import llmwiki.usecases.curate.undo as modulo
    arvore = ast.parse(inspect.getsource(modulo))
    chamados = {getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                for n in ast.walk(arvore) if isinstance(n, ast.Call)}
    assert not chamados & {"revert", "reset", "checkout"}, (
        f"o undo usou operação destrutiva de Git: "
        f"{chamados & {'revert', 'reset', 'checkout'}}")
    # e passa pelo gate único: a escrita é do writer, não do disco
    assert "write" in chamados


def test_gitstore_leitura_historica_nao_toca_o_worktree(base, kb):
    git = GitStore(kb)
    sha = git.head()
    sujo_antes = git.repo.is_dirty(untracked_files=True)
    conteudo = git.read_at(sha, "bundle/concepts/a.md")
    assert conteudo and "versão antiga do fato" in conteudo
    assert git.read_at(sha, "bundle/nao-existe.md") is None
    assert git.parent_of(sha)
    assert git.repo.is_dirty(untracked_files=True) == sujo_antes
    assert git.head() == sha


# ===================================== fiação
def test_undo_pela_api_e_pelo_historico(client, base):
    aplicado = CurationActsFacade(base).act(
        "supersede", {"page": "concepts/a.md", "successor": "concepts/b.md"})
    r = client.post("/curation/act", json={
        "act": "undo", "params": {"act_id": aplicado["id"]},
        "dry_run": False})
    assert r.status_code == 200, r.text
    assert r.json()["undone_act"] == aplicado["id"]
    historico = client.get("/curation/history").json()["acts"]
    assert historico[0]["act"] == "undo"
    assert historico[0]["undoes"] == aplicado["id"]


def test_undo_nao_expressivel_vira_409_nao_500(client, base, kb):
    BundleWriter(kb).write(
        [_doc("concepts/nova.md", "Nova", "# Nova\n\ncriada.")],
        log_kind="Creation", log_message="cria", commit_message="cria")
    sha = GitStore(kb).repo.head.commit.hexsha
    rt = connect(base.app_support / "runtime.db")
    rt.execute("INSERT INTO curation_acts(act, params, commit_sha, pages) "
               "VALUES ('supersede','{}',?,?)",
               (sha, '["concepts/nova.md"]'))
    rt.commit()
    act_id = rt.execute("SELECT MAX(id) m FROM curation_acts").fetchone()["m"]
    rt.close()
    r = client.post("/curation/act", json={
        "act": "undo", "params": {"act_id": act_id}, "dry_run": True})
    assert r.status_code == 409, r.text
    assert "CRIAÇÃO" in r.json()["detail"]


def test_cli_recusa_com_mensagem_limpa_e_codigo_estavel(base, capsys):
    """AGENTS §9 exige erro com código estável: a recusa do undo não pode
    sair como traceback de ValueError (era o comportamento antes)."""
    import argparse
    from llmwiki.cli import cmd_curate
    aplicado = SupersedePage(base, page="concepts/a.md",
                             successor="concepts/b.md").execute()
    args = argparse.Namespace(act="undo",
                              params=[f"act_id={aplicado['id']}"],
                              dry_run=False)
    assert cmd_curate(base, args) == 0            # 1º undo passa
    assert cmd_curate(base, args) == 2            # 2º recusa, sem traceback
    saida = capsys.readouterr().out
    assert "já foi desfeito" in saida and "Traceback" not in saida
