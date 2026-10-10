"""Ontologia dos blocos do projeto (ontology.toml §4, INV-ONT-002).

O repositório tinha registro para o que o software pode depender, para o
que um mecanismo pode alegar e para o que cada palavra significa — e
nenhum para as PARTES do próprio repositório. Medido antes deste arquivo:
oito unidades de código Python fora da lista de camadas, `compute` no
mapa do AGENTS §3 e fora do TOML, e arestas de import para fora do
gradiente que nada registrava.

Três famílias de teste, no padrão do resto da suíte:

1. **o registro real descreve o repositório de hoje** — cada asserção
   recomputa o fato com uma TESTEMUNHA independente (prefixo, AST e `git
   ls-files` próprios), em vez de reler a saída da implementação que
   está sendo verificada;
2. **o lint acusa cada modo de falha** — sobre uma árvore sintética com
   Git próprio, plantando o defeito e exigindo o finding (falsificável
   por construção);
3. **o índice semântico responde** — `overview()["blocks"]`, `where()` e
   a CLI leem a MESMA fonte.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import textwrap
import tomllib
from pathlib import Path

import pytest

from corpusmith.harness import ontology as onto_lint
from corpusmith.kernel import blocks as blk
from corpusmith.kernel import ontology as onto

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "backend/src/corpusmith"


def _toml(nome: str) -> dict:
    return tomllib.loads((_ROOT / nome).read_text())


def _blocos() -> dict:
    return _toml("ontology.toml")["blocks"]


def _versionados(raiz: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(raiz), "ls-files", "-z"],
                         capture_output=True, check=True).stdout.decode()
    return [p for p in out.split("\0") if p and (raiz / p).is_file()]


def _codigos(findings, prefixos=("ontology.block", "ontology.tier",
                                 "ontology.package", "ontology.blocks")):
    return sorted({(f.code, f.mechanism_id) for f in findings
                   if f.code.startswith(prefixos)})


# ============================== 1. o registro real descreve o repositório
def test_lint_dos_blocos_esta_verde_no_repositorio():
    _, findings = onto_lint.lint()
    erros = [f.to_dict() for f in findings
             if f.severity == "error" and f.code.startswith(
                 ("ontology.block", "ontology.tier", "ontology.package"))]
    assert erros == []


def test_todo_arquivo_versionado_pertence_a_exatamente_um_bloco():
    """INV-ONT-002, metade da PARTIÇÃO — a propriedade que define um eixo
    (nenhum termo em dois eixos) transposta para arquivos. Testemunha
    própria: prefixo escrito aqui, lista do Git lida aqui."""
    blocos = _blocos()

    def cobre(p: str, arquivo: str) -> bool:
        return arquivo.startswith(p) if p.endswith("/") else arquivo == p

    sem, dois = [], []
    for arquivo in _versionados(_ROOT):
        donos = [b for b, c in blocos.items()
                 if any(cobre(p, arquivo) for p in c["paths"])]
        if not donos:
            sem.append(arquivo)
        elif len(donos) > 1:
            dois.append((arquivo, donos))
    assert sem == [], f"arquivos fora do índice: {sem[:10]}"
    assert dois == [], f"arquivos em dois blocos: {dois[:10]}"


def test_toda_unidade_da_arvore_tem_camada_e_toda_camada_existe():
    """Q-19 (camadas × árvore). Antes desta regra, `[project].layers`
    omitia `bench`, `compute`, `context_pack`, `ingestion`, `jobs_proc`,
    `paths`, `runtime` e `settings` — e regra que cita pacote pelo nome
    não vale para o pacote que ela não cita."""
    tiers = _toml("architecture.toml")["tier"]
    declaradas = [u for t in tiers for u in t["units"]]
    assert len(declaradas) == len(set(declaradas)), "unidade em duas camadas"
    arvore = ({p.name for p in _SRC.iterdir()
               if p.is_dir() and (p / "__init__.py").is_file()}
              | {p.stem for p in _SRC.glob("*.py") if p.name != "__init__.py"}
              | {"desktop", "native"})
    assert set(declaradas) == arvore, (
        f"sem camada: {sorted(arvore - set(declaradas))}; "
        f"camada fantasma: {sorted(set(declaradas) - arvore)}")


def test_pure_e_domain_do_architecture_toml_sao_unidades_com_camada():
    arch = _toml("architecture.toml")
    unidades = {u for t in arch["tier"] for u in t["units"]}
    assert set(arch["pure"]["packages"]) <= unidades
    assert set(arch["domain"]["packages"]) <= unidades
    assert "layers" not in arch["project"], (
        "a lista plana de camadas voltou ao lado de [[tier]] — duas fontes "
        "para a posição de uma unidade no gradiente")
    # o núcleo puro é a camada MAIS interna, inteira
    assert set(arch["tier"][0]["units"]) == set(arch["pure"]["packages"])


def _testemunha_de_imports(arquivo: Path, unidades: set[str]) -> set[str]:
    """Leitura própria do AST (não a de harness/ontology.py): resolve o
    pacote do arquivo e sobe `level` níveis."""
    rel = arquivo.relative_to(_SRC).parts
    pacote = list(rel[:-1])
    achou: set[str] = set()
    for node in ast.walk(ast.parse(arquivo.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = pacote[:len(pacote) - (node.level - 1)]
                nomes = base + (node.module.split(".") if node.module else [])
            else:
                partes = (node.module or "").split(".")
                if partes[0] != "corpusmith":
                    continue
                nomes = partes[1:]
            candidatos = nomes[:1] or [a.name for a in node.names]
            achou |= set(candidatos) & unidades
        elif isinstance(node, ast.Import):
            for a in node.names:
                p = a.name.split(".")
                if p[0] == "corpusmith" and len(p) > 1 and p[1] in unidades:
                    achou.add(p[1])
    return achou


def test_dependencias_declaradas_sao_exatamente_os_imports_reais():
    """INV-ONT-002, metade da DEPENDÊNCIA: `depends_on` é allowlist — o
    acoplamento novo entre blocos tem de aparecer no diff do registro."""
    unidades = ({p.name for p in _SRC.iterdir()
                 if p.is_dir() and (p / "__init__.py").is_file()}
                | {p.stem for p in _SRC.glob("*.py")
                   if p.name != "__init__.py"})
    blocos = _blocos()
    divergentes = {}
    for u in sorted(unidades):
        alvo = _SRC / u if (_SRC / u).is_dir() else _SRC / f"{u}.py"
        arquivos = sorted(alvo.rglob("*.py")) if alvo.is_dir() else [alvo]
        real: set[str] = set()
        for py in arquivos:
            real |= _testemunha_de_imports(py, unidades)
        real.discard(u)
        declarado = set(blocos[u].get("depends_on", ()))
        if real != declarado:
            divergentes[u] = {"sem_declaracao": sorted(real - declarado),
                              "sem_import": sorted(declarado - real)}
    assert divergentes == {}


def test_aresta_contra_o_gradiente_so_existe_como_divida_com_motivo():
    """O gradiente de `architecture.toml [[tier]]` vale para o código, e a
    exceção é dívida registrada — nunca silêncio. Recomputado aqui."""
    tiers = _toml("architecture.toml")["tier"]
    nivel = {u: i for i, t in enumerate(tiers) for u in t["units"]}
    blocos = _blocos()
    for bid, corpo in blocos.items():
        dividas = corpo.get("debts", {})
        for alvo in corpo.get("depends_on", ()):
            if nivel.get(bid, -1) < nivel.get(alvo, -1) and bid in nivel:
                assert alvo in dividas, f"{bid} → {alvo} contra o gradiente"
        for alvo, motivo in dividas.items():
            assert alvo in corpo.get("depends_on", ()), (bid, alvo)
            assert len(motivo.split()) >= 8, (
                f"dívida {bid} → {alvo} sem motivo que se possa conferir")


def test_api_fora_da_allowlist_de_facades_e_divida_declarada():
    """`[dependency_rule].api_allowed_internal = ["facades"]` é allowlist;
    a suíte só proibia usecases/jobs (docs/17 mediu o vão). O registro
    passa a dizer, aresta por aresta, onde `api` pula a facade."""
    regra = _toml("architecture.toml")["dependency_rule"]
    api = _blocos()["api"]
    fora = set(api["depends_on"]) - set(regra["api_allowed_internal"])
    assert fora <= set(api.get("debts", {})), sorted(
        fora - set(api.get("debts", {})))
    assert not set(api["depends_on"]) & {"usecases", "jobs"}


def test_raiz_do_pacote_so_carrega_a_versao():
    """É o que justifica não contar `from .. import __version__` como
    acoplamento: se a raiz ganhar lógica, a aresta passa a importar."""
    corpo = ast.parse((_SRC / "__init__.py").read_text()).body
    atribuicoes = [n for n in corpo if isinstance(n, ast.Assign)]
    assert [t.id for n in atribuicoes for t in n.targets] == ["__version__"]
    assert all(isinstance(n, (ast.Assign, ast.Expr, ast.ImportFrom))
               for n in corpo)


def test_todo_bloco_declara_pergunta_e_fronteira():
    for bid, corpo in _blocos().items():
        assert corpo["kind"] in blk.KINDS, bid
        assert corpo["question"].strip().endswith("?"), (
            f"{bid}: `question` precisa ser PERGUNTA — é o teste de que o "
            "bloco responde a uma só")
        assert corpo["not_means"].strip(), bid


def test_block_kind_e_vocabulario_fechado_espelhado_no_kernel():
    valores, objeto, mora = onto.VOCABULARIES["block_kind"]
    assert valores == blk.KINDS and objeto == "project_block"
    assert mora == "backend/src/corpusmith/kernel/blocks.py"
    verbete = _toml("ontology.toml")["vocabularies"]["block_kind"]
    assert tuple(verbete["values"]) == blk.KINDS


def test_bloco_do_projeto_nasce_qualificado_e_a_deriva_de_bloco_e_registrada():
    """"Bloco" já tinha quatro sentidos no código (corpo, grafo, sucessão,
    estudo). O quinto nasce qualificado — e a polissemia que já existia
    ganha entrada viva em [drift.block], com marcadores conferidos."""
    data = _toml("ontology.toml")
    assert "project_block" in data["terms"]
    assert "block" not in data["terms"], "termo sem qualificador"
    deriva = data["drift"]["block"]
    assert deriva["status"] == "open"
    assert len(deriva["senses"]) >= 5
    assert any("kernel/blocks.py" in ref for ref, _ in deriva["markers"])


# =================================== 2. o lint acusa cada modo de falha
_ARCH = """\
schema_version = 1
[[tier]]
name = "núcleo"
units = ["kernel"]
[[tier]]
name = "aplicação"
units = ["usecases"]
[[tier]]
name = "borda"
units = ["api"]
[dependency_rule]
usecases_forbidden = ["api"]
api_allowed_internal = ["usecases"]
"""

_BLOCOS = """\
schema_version = 1

[blocks.package_root]
kind = "code"
paths = ["backend/src/corpusmith/__init__.py"]
question = "qual é a versão?"
not_means = "lugar de lógica"

[blocks.kernel]
kind = "code"
paths = ["backend/src/corpusmith/kernel/"]
question = "que regra vale sem I/O?"
not_means = "lugar de efeito"
depends_on = []

[blocks.usecases]
kind = "code"
paths = ["backend/src/corpusmith/usecases/"]
question = "qual é a operação?"
not_means = "transporte"
depends_on = ["kernel"]

[blocks.api]
kind = "code"
paths = ["backend/src/corpusmith/api/"]
question = "como o mundo fala com o produto?"
not_means = "regra de domínio"
depends_on = ["usecases"]

[blocks.registries]
kind = "registry"
paths = ["architecture.toml", "ontology.toml"]
question = "o que os contratos dizem?"
not_means = "decoração"

[blocks.tests]
kind = "test"
paths = ["backend/tests/"]
question = "o que prova o código?"
not_means = "alegação"
"""


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True,
                   capture_output=True)


def _arvore(raiz: Path, extra: dict[str, str] | None = None,
            ontologia: str = _BLOCOS, arch: str = _ARCH,
            git: bool = True) -> Path:
    arquivos = {
        "architecture.toml": arch,
        "ontology.toml": ontologia,
        "backend/src/corpusmith/__init__.py": '__version__ = "0.0.0"\n',
        "backend/src/corpusmith/kernel/__init__.py": "",
        "backend/src/corpusmith/kernel/regra.py": "X = 1\n",
        "backend/src/corpusmith/usecases/__init__.py": "",
        "backend/src/corpusmith/usecases/op.py":
            "from ..kernel import regra\n",
        "backend/src/corpusmith/api/__init__.py": "",
        "backend/src/corpusmith/api/rota.py":
            "from .. import __version__\nfrom ..usecases import op\n",
        "backend/tests/test_k.py":
            "from corpusmith.kernel import regra\n"
            "from corpusmith.usecases import op\n"
            "import corpusmith.api.rota\n",
    }
    arquivos.update(extra or {})
    for rel, texto in arquivos.items():
        if texto is None:
            continue
        alvo = raiz / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(textwrap.dedent(texto))
    if git:
        _git(raiz, "init", "-q")
        _git(raiz, "add", "-A")
    return raiz


def _lint_sintetico(raiz: Path):
    return onto_lint.lint(raiz / "ontology.toml", root=raiz)[1]


def test_arvore_sintetica_sa_nao_tem_finding_de_bloco(tmp_path):
    """O controle negativo: sem ele, os testes de mutação abaixo poderiam
    estar acusando a própria fixture."""
    assert _codigos(_lint_sintetico(_arvore(tmp_path))) == []


def test_lint_acusa_arquivo_versionado_sem_bloco(tmp_path):
    raiz = _arvore(tmp_path, {"_estudo/index.html": "<p>x</p>\n"})
    assert ("ontology.block_orphan_file", "_estudo/") in _codigos(
        _lint_sintetico(raiz))


def test_lint_acusa_arquivo_em_dois_blocos(tmp_path):
    ontologia = _BLOCOS + textwrap.dedent("""
        [blocks.duplicado]
        kind = "registry"
        paths = ["ontology.toml"]
        question = "de novo?"
        not_means = "nada"
        """)
    codigos = _codigos(_lint_sintetico(_arvore(tmp_path, ontologia=ontologia)))
    assert any(c == "ontology.block_overlap" for c, _ in codigos)


def test_lint_acusa_import_entre_blocos_nao_declarado(tmp_path):
    ontologia = _BLOCOS.replace('depends_on = ["kernel"]', "depends_on = []")
    codigos = _codigos(_lint_sintetico(_arvore(tmp_path, ontologia=ontologia)))
    assert ("ontology.block_dependency_undeclared", "usecases") in codigos


def test_lint_avisa_dependencia_declarada_sem_import(tmp_path):
    raiz = _arvore(tmp_path, {"backend/src/corpusmith/usecases/op.py": "Y = 2\n"})
    achados = [f for f in _lint_sintetico(raiz)
               if f.code == "ontology.block_dependency_stale"]
    assert [(f.mechanism_id, f.severity) for f in achados] == [
        ("usecases", "warn")]


def test_import_tardio_contra_o_gradiente_e_divida_obrigatoria(tmp_path):
    """Import dentro de função é acoplamento do mesmo jeito — o
    `runtime/worker.py` → `jobs` real é exatamente esse caso."""
    tardio = {"backend/src/corpusmith/kernel/regra.py":
              "def f():\n    from ..usecases import op\n    return op\n"}
    ontologia = _BLOCOS.replace(
        'not_means = "lugar de efeito"\ndepends_on = []',
        'not_means = "lugar de efeito"\ndepends_on = ["usecases"]')
    codigos = _codigos(_lint_sintetico(
        _arvore(tmp_path / "a", tardio, ontologia=ontologia)))
    assert ("ontology.block_debt_undeclared", "kernel") in codigos

    com_divida = ontologia + textwrap.dedent("""
        [blocks.kernel.debts]
        usecases = "a regra lê a operação para despachar — injetar a operação paga a dívida"
        """)
    assert _codigos(_lint_sintetico(
        _arvore(tmp_path / "b", tardio, ontologia=com_divida))) == []

    # a dívida paga, e não descadastrada, vira aviso — não silêncio
    paga = _codigos(_lint_sintetico(_arvore(tmp_path / "c",
                                            ontologia=com_divida)))
    assert ("ontology.block_debt_paid", "kernel") in paga


def test_divida_nao_legitima_o_que_dependency_rule_proibe(tmp_path):
    proibido = {"backend/src/corpusmith/usecases/op.py":
                "from ..kernel import regra\nfrom ..api import rota\n"}
    ontologia = _BLOCOS.replace(
        'not_means = "transporte"\ndepends_on = ["kernel"]',
        'not_means = "transporte"\ndepends_on = ["kernel", "api"]') + \
        '\n[blocks.usecases.debts]\napi = "um motivo qualquer longo o bastante para parecer razoável aqui"\n'
    codigos = _codigos(_lint_sintetico(
        _arvore(tmp_path, proibido, ontologia=ontologia)))
    assert ("ontology.block_dependency_forbidden", "usecases") in codigos


def test_allowlist_de_api_exige_divida_para_o_que_pula_a_facade(tmp_path):
    pula = {"backend/src/corpusmith/api/rota.py":
            "from ..usecases import op\nfrom ..kernel import regra\n"}
    ontologia = _BLOCOS.replace(
        'not_means = "regra de domínio"\ndepends_on = ["usecases"]',
        'not_means = "regra de domínio"\ndepends_on = ["kernel", "usecases"]')
    codigos = _codigos(_lint_sintetico(
        _arvore(tmp_path, pula, ontologia=ontologia)))
    assert ("ontology.block_debt_undeclared", "api") in codigos


def test_lint_acusa_unidade_sem_camada_e_camada_fantasma(tmp_path):
    raiz = _arvore(tmp_path, {
        "backend/src/corpusmith/novo/__init__.py": "",
        "backend/src/corpusmith/novo/x.py": "Z = 3\n"},
        arch=_ARCH + '[[tier]]\nname = "fantasma"\nunits = ["fantasma"]\n')
    codigos = _codigos(_lint_sintetico(raiz))
    assert ("ontology.tier_mismatch", "novo") in codigos
    assert ("ontology.tier_mismatch", "fantasma") in codigos
    # e a unidade nova também não tem bloco: duas regras, dois findings
    assert ("ontology.block_unit_mismatch", "novo") in codigos


def test_bloco_de_codigo_python_tem_o_nome_da_unidade(tmp_path):
    ontologia = _BLOCOS.replace("[blocks.kernel]", "[blocks.nucleo]")
    codigos = _codigos(_lint_sintetico(_arvore(tmp_path, ontologia=ontologia)))
    assert ("ontology.block_unit_mismatch", "nucleo") in codigos


def test_raiz_do_pacote_com_logica_e_acusada(tmp_path):
    raiz = _arvore(tmp_path, {"backend/src/corpusmith/__init__.py":
                              '__version__ = "0"\nimport os\n'})
    assert ("ontology.package_root_not_bare", blk.PACKAGE_ROOT) in _codigos(
        _lint_sintetico(raiz))


def test_tipo_fora_do_vocabulario_e_caminho_inexistente(tmp_path):
    ontologia = _BLOCOS.replace('kind = "registry"', 'kind = "planilha"') \
        .replace('"architecture.toml", "ontology.toml"',
                 '"architecture.toml", "ontology.toml", "naoexiste.md"')
    codigos = _codigos(_lint_sintetico(_arvore(tmp_path, ontologia=ontologia)))
    assert ("ontology.block_shape", "registries") in codigos
    assert ("ontology.block_path_missing", "registries") in codigos


def test_sem_git_a_particao_fica_declarada_como_nao_verificada(tmp_path):
    achados = _lint_sintetico(_arvore(tmp_path, git=False))
    assert [(f.code, f.severity) for f in achados
            if f.code == "ontology.blocks_uncheckable"] == [
        ("ontology.blocks_uncheckable", "warn")]


def test_bloco_sem_teste_que_o_importe_e_aviso(tmp_path):
    raiz = _arvore(tmp_path, {"backend/tests/test_k.py":
                              "from corpusmith.kernel import regra\n"})
    sem_prova = sorted(f.mechanism_id for f in _lint_sintetico(raiz)
                       if f.code == "ontology.block_unproven")
    assert sem_prova == ["api", "usecases"]


# ============================ 3. o índice semântico responde (mesma fonte)
@pytest.fixture(scope="module")
def visao() -> dict:
    return onto_lint.overview()


def test_indice_tem_todo_bloco_com_camada_termos_mecanismos_e_testes(visao):
    indice = {b["block"]: b for b in visao["blocks"]}
    assert set(indice) == set(_blocos())
    kernel = indice["kernel"]
    assert kernel["tier"] == visao["tiers"][0]["name"]
    assert "canon" in kernel["terms"]            # lives_in kernel/checkpoints.py
    assert kernel["mechanisms"] and kernel["tests"]
    assert kernel["depends_on"] == [] and "usecases" in kernel["used_by"]
    assert indice["registries"]["kind"] == "registry"
    assert sum(b["files"] for b in visao["blocks"]) == len(
        _versionados(_ROOT))


def test_where_por_caminho_termo_mecanismo_e_bloco():
    por_caminho = onto_lint.where("backend/src/corpusmith/okf/writer.py")
    assert [(m["block"], m["via"]) for m in por_caminho["matches"]] == [
        ("okf", "caminho")]
    assert onto_lint.where("backend/src/corpusmith/kernel")["matches"][0][
        "block"] == "kernel"
    # a abreviação que os docs usam (`okf/writer.py`) resolve igual
    assert [m["block"] for m in onto_lint.where("okf/writer.py")[
        "matches"]] == ["okf"]
    assert onto_lint.where("docs/08-decisoes.md")["matches"][0][
        "block"] == "docs"
    por_termo = onto_lint.where("canon")
    assert ("kernel", "termo (lives_in "
            "backend/src/corpusmith/kernel/checkpoints.py)") in [
        (m["block"], m["via"]) for m in por_termo["matches"]]
    por_mecanismo = {m["block"] for m in
                     onto_lint.where("retrieval_rrf_hedge")["matches"]}
    assert {"retrieval", "usecases", "kernel"} <= por_mecanismo
    assert onto_lint.where("harness")["matches"][0]["via"] == "bloco"
    assert onto_lint.where("nada_com_esse_nome_xyz")["matches"] == []


def test_cli_ontology_blocks_e_where(capsys, settings):
    from corpusmith.cli import cmd_ontology
    s = settings
    assert cmd_ontology(s, argparse.Namespace(op="blocks", alvo=None)) == 0
    saida = capsys.readouterr().out
    for bid in ("kernel", "okf", "registries", "desktop"):
        assert f"[{bid}]" in saida
    assert cmd_ontology(s, argparse.Namespace(
        op="where", alvo="backend/src/corpusmith/okf/writer.py")) == 0
    assert "[okf]" in capsys.readouterr().out
    assert cmd_ontology(s, argparse.Namespace(op="where",
                                              alvo="nada_xyz")) == 1
    assert cmd_ontology(s, argparse.Namespace(op="where", alvo=None)) == 2
