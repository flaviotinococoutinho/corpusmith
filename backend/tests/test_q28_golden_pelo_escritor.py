"""Q-28 (P0) — o golden eval entra no bundle pelo escritor, ou não entra.

`usecases/seed_eval.py` escrevia `bundle/harness/golden_eval.jsonl` com
`write_text` e commitava por `GitStore.commit` — fora do `BundleWriter`, a
única escrita no bundle fora do escritor que a varredura abaixo encontrou:

- sem LOCK: corria contra um escritor concorrente (daemon × CLI);
- sem `log.md`: o diário do bundle não registrava que o instrumento mudou;
- sem VALIDAÇÃO: golden malformado só explodia na hora do eval
  (`KeyError` em `case["q"]`), depois de entrar no histórico;
- com `git add -A`: o commit do seed levava junto qualquer sujeira do kb —
  capturas de `raw/`, edição manual —, sob a mensagem "seed: golden".

O golden é o INSTRUMENTO que mede os mecanismos (viés, ruído, limite de
conhecimento). O envelope de avaliação já carimba `dataset_sha256`; faltava
saber QUANDO e POR QUAL ato aquele hash passou a valer — sem isso a série
de medições não é reproduzível no tempo.
"""
from __future__ import annotations

import ast
import json
import os
import threading
import time
from pathlib import Path

import pytest
from git import Repo
from git.exc import CommandError

from corpusmith.harness.runner import HarnessRejection
from corpusmith.okf.git_store import GitStore
from corpusmith.okf.writer import BundleWriter
from corpusmith.usecases.seed_eval import seed_golden_eval

GOLDEN = "harness/golden_eval.jsonl"
_SRC = Path(__file__).resolve().parents[1] / "src" / "corpusmith"


def _golden(kb: Path) -> Path:
    return kb / "bundle" / GOLDEN


def _seed_so_casos(tmp_path: Path) -> Path:
    """Seed sem páginas: o único commit do seed é o do golden — isola o
    ato que este arquivo examina."""
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"pages": [], "cases": [
        {"q": "qual porta o daemon usa?", "category": "extract",
         "expect_pages": ["runbooks/daemon.md"], "expect_regex": r"\b8377\b"},
        {"q": "resultado com Neo4j?", "category": "abstain",
         "expect_abstain": True}]}))
    return seed


def _artefato(kb: Path, rel: str, texto: str, **kw) -> dict:
    return BundleWriter(kb).write_artifact(
        rel, texto, log_kind="Creation", log_message="teste",
        commit_message="teste: artefato", **kw)


# ======================================== o seed passa pelo rito do escritor
def test_golden_espera_o_lock_do_escritor(settings, kb, tmp_path):
    """Sem o lock, o arquivo aparece em milissegundos com outro escritor
    no meio de um ato; com ele, o seed espera a vez."""
    seed = _seed_so_casos(tmp_path)
    terminou = threading.Event()
    erro: list[BaseException] = []

    def _seed() -> None:
        try:
            seed_golden_eval(settings, seed)
        except BaseException as e:            # noqa: BLE001 — reportado abaixo
            erro.append(e)
        finally:
            terminou.set()

    with BundleWriter(kb).locked():
        t = threading.Thread(target=_seed)
        t.start()
        time.sleep(0.5)
        assert not _golden(kb).exists(), (
            "o seed escreveu no bundle com o lock de outro escritor em mãos")
    t.join(timeout=60)
    assert terminou.is_set() and not erro, erro
    assert _golden(kb).exists()


def test_commit_do_golden_leva_so_o_que_o_ato_escreveu(settings, kb, tmp_path):
    """A sujeira alheia — uma captura não confiável em `raw/` e uma edição
    manual num arquivo versionado — fica onde estava, fora do commit."""
    (kb / "raw" / "captura.md").write_text("captura não confiável\n")
    gitignore = kb / ".gitignore"
    gitignore.write_text(gitignore.read_text() + "editado-a-mao\n")
    seed_golden_eval(settings, _seed_so_casos(tmp_path))
    repo = GitStore(kb).repo
    assert set(repo.head.commit.stats.files) == {
        f"bundle/{GOLDEN}", "bundle/log.md"}
    assert "raw/captura.md" in repo.untracked_files
    assert ".gitignore" in {d.a_path for d in repo.index.diff(None)}


def test_golden_entra_no_diario_do_bundle(settings, kb, tmp_path):
    seed_golden_eval(settings, _seed_so_casos(tmp_path))
    log = (kb / "bundle" / "log.md").read_text()
    assert f"golden eval (QA-1): {GOLDEN}" in log


def test_seed_continua_sem_sobrescrever_golden_curado(settings, kb, tmp_path):
    """O contrato do `corpusmith seed` fica — agora checado DENTRO do lock,
    para não haver corrida entre a checagem e a escrita."""
    curado = '{"q": "minha pergunta", "category": "extract"}\n'
    _artefato(kb, GOLDEN, curado)
    out = seed_golden_eval(settings, _seed_so_casos(tmp_path))
    assert out["cases"] == 0 and _golden(kb).read_text() == curado


# ============================================== o gate dos artefatos
@pytest.mark.parametrize("texto", [
    "isto não é json\n",
    '{"category": "extract"}\n',                       # sem `q`
    '{"q": "pergunta"}\n',                             # sem `category`
    '{"q": "  ", "category": "extract"}\n',            # `q` em branco
    '["q", "category"]\n',                             # não é objeto
    '{"q": "a", "category": "b", "expect_pages": "x.md"}\n',
    '{"q": "a", "category": "b", "expect_abstain": "sim"}\n',
    '{"q": "a", "category": "b", "expect_regex": "("}\n',
    '{"q": "a", "category": "b", "as_of": 2026}\n',
    "\n\n",                                            # instrumento vazio
])
def test_golden_malformado_e_recusado_e_o_bundle_fica_intocado(kb, texto):
    head = GitStore(kb).head()
    log_antes = (kb / "bundle" / "log.md").read_text()
    with pytest.raises(HarnessRejection) as exc:
        _artefato(kb, GOLDEN, texto)
    assert "policy.artifact_invalid" in exc.value.findings.rules()
    assert not _golden(kb).exists()
    assert GitStore(kb).head() == head
    assert (kb / "bundle" / "log.md").read_text() == log_antes


@pytest.mark.parametrize("rel", ["harness/outro.jsonl", "concepts/x.md",
                                 "log.md", "index.md", "../fora.txt"])
def test_artefato_fora_da_allowlist_e_recusado(kb, rel):
    """Sem a allowlist, `write_artifact` viraria a porta dos fundos genérica
    que ele existe para fechar: página entra por `write`, com o Harness."""
    with pytest.raises(HarnessRejection) as exc:
        _artefato(kb, rel, '{"q": "a", "category": "b"}\n')
    assert "policy.artifact_unknown" in exc.value.findings.rules()


def test_escrita_interrompida_nao_deixa_temporario_no_bundle(kb, monkeypatch):
    """Falha entre o temporário e o `os.replace` (disco cheio, permissão)
    não deixa `.golden_eval.jsonl.tmp` no bundle — o próximo `add -A` de
    outro ato o varreria para o histórico — nem entrada no `log.md`."""
    real = os.replace

    def _falha(src, dst, *a, **kw):
        if str(dst).endswith(GOLDEN):
            raise OSError("disco cheio")
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(os, "replace", _falha)
    head = GitStore(kb).head()
    log_antes = (kb / "bundle" / "log.md").read_text()
    with pytest.raises(OSError):
        _artefato(kb, GOLDEN, '{"q": "a", "category": "b"}\n')
    assert list(_golden(kb).parent.glob(".*.tmp")) == []
    assert not _golden(kb).exists()
    assert GitStore(kb).head() == head
    assert (kb / "bundle" / "log.md").read_text() == log_antes


def test_create_only_e_decidido_dentro_do_lock(kb):
    primeiro = _artefato(kb, GOLDEN, '{"q": "a", "category": "b"}\n',
                         create_only=True)
    segundo = _artefato(kb, GOLDEN, '{"q": "c", "category": "d"}\n',
                        create_only=True)
    assert primeiro["commit"]
    assert segundo == {"artifact": GOLDEN, "commit": None, "skipped": "exists"}
    assert '"q": "a"' in _golden(kb).read_text()


# ===================================== o commit que leva só o que mandaram
def test_commit_escopado_nao_leva_o_resto_do_kb(kb):
    git = GitStore(kb)
    (kb / "a.txt").write_text("a\n")
    (kb / "b.txt").write_text("b\n")
    sha = git.commit("só a", paths=["a.txt"])
    assert set(git.repo.commit(sha).stats.files) == {"a.txt"}
    assert "b.txt" in git.repo.untracked_files
    assert git.commit("nada mudou em a", paths=["a.txt"]) is None


def test_commit_escopado_roda_os_hooks_do_kb_como_o_historico(kb):
    """Paridade de hooks: o `index.commit` do GitPython (modo histórico)
    roda o pre-commit do repo do kb; o modo escopado também precisa rodar —
    senão um hook do usuário (um detector de segredo, por exemplo) valeria
    para todo ato menos o do golden."""
    git = GitStore(kb)
    hook = Path(git.repo.git_dir) / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    (kb / "a.txt").write_text("a\n")
    with pytest.raises(CommandError):
        git.commit("escopado", paths=["a.txt"])
    with pytest.raises(CommandError):
        git.commit("histórico")


def test_commit_escopado_assina_como_o_historico_sem_identidade(
        tmp_path, monkeypatch):
    """Paridade de AUTORIA: kb que já era repo sem `user.*` (o `GitStore` só
    configura identidade no `init` que ele mesmo faz). O `index.commit` do
    GitPython assina com login@máquina; o `git commit` puro aborta ("Please
    tell me who you are") ou assina com outro nome — o histórico atribuiria
    o ato do golden a outra pessoa, ou nem o gravaria."""
    casa = tmp_path / "casa"
    casa.mkdir()
    for var in ("HOME", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(var, str(casa))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(var, raising=False)
    kb = tmp_path / "kb"
    Repo.init(kb)                                  # repo sem identidade
    git = GitStore(kb)
    (kb / "a.txt").write_text("a\n")
    historico = git.repo.commit(git.commit("histórico"))
    (kb / "b.txt").write_text("b\n")
    escopado = git.repo.commit(git.commit("escopado: só b", paths=["b.txt"]))
    for papel in ("author", "committer"):
        h, e = getattr(historico, papel), getattr(escopado, papel)
        assert (e.name, e.email) == (h.name, h.email), papel
    assert escopado.message.strip() == "escopado: só b"


# ============================ a CLASSE do defeito: nenhuma outra porta
_ESCRITA = {"write_text", "write_bytes", "unlink", "rename", "replace",
            "touch", "symlink_to", "rmdir"}
_ESCRITA_MODULO = {("os", "replace"), ("os", "rename"), ("os", "remove"),
                   ("os", "unlink"), ("shutil", "move"), ("shutil", "copy"),
                   ("shutil", "copy2"), ("shutil", "copyfile"),
                   ("shutil", "copytree"), ("shutil", "rmtree")}


def _literal_de_bundle(no: ast.AST) -> bool:
    """O literal que nomeia o bundle num caminho: `"bundle"` ou
    `"bundle/…"`, inclusive como pedaço de f-string."""
    return any(isinstance(s, ast.Constant) and isinstance(s.value, str)
               and (s.value == "bundle" or s.value.startswith("bundle/"))
               for s in ast.walk(no))


def _caminho_do_bundle(no: ast.AST, contaminados: set[str]) -> bool:
    """A expressão CONSTRÓI um caminho dentro do bundle? Só formas de
    caminho contam — `/`, `Path(…)`, `.joinpath`/`.parent`/`.with_*`, o
    atributo `.bundle` —, nunca "um valor lido do bundle": a data de uma
    página não é um caminho (medido: `ts.replace(tzinfo=…)` em
    weekly_review.py era falso positivo da primeira versão deste guarda)."""
    if isinstance(no, ast.Name):
        return no.id in contaminados
    if isinstance(no, ast.Constant):
        return _literal_de_bundle(no)
    if isinstance(no, ast.JoinedStr):
        return _literal_de_bundle(no)
    if isinstance(no, ast.Attribute):
        if no.attr == "bundle":
            return True
        return no.attr in ("parent",) and _caminho_do_bundle(no.value,
                                                             contaminados)
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div):
        return (_caminho_do_bundle(no.left, contaminados)
                or _caminho_do_bundle(no.right, contaminados))
    if isinstance(no, ast.Call):
        f = no.func
        if isinstance(f, ast.Name) and f.id in ("Path", "PurePath", "str"):
            return any(_caminho_do_bundle(a, contaminados) for a in no.args)
        if isinstance(f, ast.Attribute) and f.attr in (
                "joinpath", "with_name", "with_suffix", "resolve"):
            return _caminho_do_bundle(f.value, contaminados)
        if isinstance(f, ast.Attribute) and f.attr == "join" and isinstance(
                f.value, ast.Attribute) and f.value.attr == "path":
            return any(_caminho_do_bundle(a, contaminados) for a in no.args)
    return False


def _violacoes(arquivo: Path) -> list[str]:
    """Rastreio de contaminação POR FUNÇÃO, de propósito simples: um nome
    atribuído a partir de um CAMINHO dentro do bundle fica contaminado
    (`_caminho_do_bundle`); escrita de arquivo sobre ele é violação. E
    `.commit(` sobre `GitStore(...)`, sobre nome vindo dele ou sobre `.git`
    também."""
    achados: list[str] = []
    arvore = ast.parse(arquivo.read_text())
    for fn in [n for n in ast.walk(arvore)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        contaminados: set[str] = set()
        gits: set[str] = set()
        for no in ast.walk(fn):
            if isinstance(no, ast.Assign):
                for alvo in no.targets:
                    if not isinstance(alvo, ast.Name):
                        continue
                    if _caminho_do_bundle(no.value, contaminados):
                        contaminados.add(alvo.id)
                    if isinstance(no.value, ast.Call) and getattr(
                            no.value.func, "id", "") == "GitStore":
                        gits.add(alvo.id)
            elif isinstance(no, ast.For) and isinstance(no.target, ast.Name) \
                    and isinstance(no.iter, ast.Call) \
                    and isinstance(no.iter.func, ast.Attribute) \
                    and no.iter.func.attr in ("rglob", "glob", "iterdir") \
                    and _caminho_do_bundle(no.iter.func.value, contaminados):
                contaminados.add(no.target.id)
        for no in ast.walk(fn):
            if not isinstance(no, ast.Call):
                continue
            f = no.func
            if isinstance(f, ast.Attribute) and f.attr in _ESCRITA \
                    and _caminho_do_bundle(f.value, contaminados):
                achados.append(f"{arquivo.name}:{no.lineno} {f.attr} no bundle")
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and (f.value.id, f.attr) in _ESCRITA_MODULO \
                    and any(_caminho_do_bundle(a, contaminados) for a in no.args):
                achados.append(f"{arquivo.name}:{no.lineno} {f.value.id}."
                               f"{f.attr} no bundle")
            if isinstance(f, ast.Name) and f.id == "open" and no.args \
                    and _caminho_do_bundle(no.args[0], contaminados):
                modo = no.args[1] if len(no.args) > 1 else next(
                    (k.value for k in no.keywords if k.arg == "mode"), None)
                if isinstance(modo, ast.Constant) and set(str(modo.value)) \
                        & set("wax+"):
                    achados.append(f"{arquivo.name}:{no.lineno} open(w) no "
                                   "bundle")
            if isinstance(f, ast.Attribute) and f.attr == "commit":
                alvo = f.value
                if (isinstance(alvo, ast.Call)
                        and getattr(alvo.func, "id", "") == "GitStore") \
                        or (isinstance(alvo, ast.Name) and alvo.id in gits) \
                        or (isinstance(alvo, ast.Attribute)
                            and alvo.attr == "git"):
                    achados.append(f"{arquivo.name}:{no.lineno} commit do kb")
    return achados


def test_nada_fora_do_okf_escreve_no_bundle_nem_commita_o_kb():
    """INV-DATA-001 como CLASSE: o seed era a única porta lateral; esta
    varredura garante que não nasce a próxima. `okf/` é o escritor (e o
    bootstrap, que cria o bundle antes de existir escritor); fora dele,
    escrever no bundle ou commitar o kb é violação."""
    achados = [v for py in sorted(_SRC.rglob("*.py"))
               if "okf" not in py.relative_to(_SRC).parts[:1]
               for v in _violacoes(py)]
    assert achados == [], achados


def test_a_varredura_pega_o_padrao_que_o_seed_usava(tmp_path):
    """Teste do instrumento: o guarda acima precisa ACUSAR o código antigo
    do seed — senão verde é só cegueira."""
    antigo = tmp_path / "antigo.py"
    antigo.write_text(
        "def seed(kb):\n"
        "    bundle = kb / 'bundle'\n"
        "    golden = bundle / 'harness' / 'golden_eval.jsonl'\n"
        "    golden.write_text('x')\n"
        "    GitStore(kb).commit('seed: golden_eval.jsonl')\n"
        "    g = GitStore(kb)\n"
        "    g.commit('outra')\n"
        "    for p in bundle.rglob('*'):\n"
        "        p.unlink()\n"
        "    with open(golden, 'a') as fh:\n"
        "        fh.write('y')\n")
    achados = _violacoes(antigo)
    assert len(achados) == 5, achados


def test_a_varredura_nao_confunde_valor_lido_com_caminho(tmp_path):
    """O outro lado do instrumento: a data de uma página LIDA do bundle não
    é caminho dentro dele. A primeira versão do guarda acusou
    `ts.replace(tzinfo=…)` em weekly_review.py — falso positivo que
    treinaria a ignorar o guarda."""
    leitura = tmp_path / "leitura.py"
    leitura.write_text(
        "def semana(kb):\n"
        "    reader = BundleReader(kb / 'bundle')\n"
        "    for d in reader.iter_concepts():\n"
        "        ts = d.meta.timestamp\n"
        "        ts.replace(tzinfo=None)\n"
        "        nome = d.rel_path.replace('/', '-')\n")
    assert _violacoes(leitura) == []
