"""Loader do registro ontológico (shell) — a ÚNICA implementação de
carga/lint, compartilhada por CLI, facade, API e testes (RFC-004).

Mesmo desenho de `harness/epistemics.py`: lê `ontology.toml` da raiz,
delega ao domínio PURO (`kernel/ontology.py`, `kernel/blocks.py`) tudo que
é regra, e acrescenta só o que exige filesystem — existência dos
`lives_in`, presença dos `markers` de deriva, a lista de arquivos
versionados e os imports de cada bloco do projeto. Somente leitura.

**O que um `marker` afirma.** Sempre a mesma coisa: *este sentido existe
no código, aqui*. O que muda com o `status` é o que a AUSÊNCIA significa.
Numa deriva `open` os sentidos dividem um nome só, e um marcador que some
sugere que a dívida foi paga — warn, para que o registro seja atualizado
em vez de continuar cobrando o que já não existe. Numa deriva `resolved`
os sentidos já têm nomes distintos, e um marcador que some é a separação
REGREDINDO — erro, porque foi exatamente para impedir isso que a entrada
continuou no arquivo depois de resolvida.

Um registro de dívida que só sabe cobrar apodrece de um jeito silencioso:
alguém conserta a conflação, ninguém volta ao arquivo, e o documento passa
a acusar defeito inexistente — o que treina o leitor a ignorar o documento
inteiro. O registro só fica verde quando descreve o código de hoje.

**Blocos do projeto (§4 do `ontology.toml`).** A mesma disciplina, aplicada
às partes do repositório: todo arquivo versionado pertence a UM bloco, todo
bloco responde a UMA pergunta, a dependência entre blocos de código Python
é DECLARADA e conferida contra os imports reais (nas duas direções), e a
aresta que contraria o gradiente de `architecture.toml [[tier]]` — ou a
allowlist de `[dependency_rule]` — só existe como dívida registrada, com
motivo. O índice que sai daqui (`overview()["blocks"]`, `where()`) junta
cada bloco aos termos, mecanismos e testes que moram nele: é o mapa
SEMÂNTICO do repositório, derivado das fontes e nunca copiado à mão.
"""
from __future__ import annotations
import ast
import subprocess
import tomllib
from pathlib import Path
from ..epistemic import Finding
from ..kernel import blocks as blk
from ..kernel import ontology as onto
from ..paths import frozen, resource as _resource

# harness/ → corpusmith → src → backend → raiz do repo
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATH = _resource("ontology.toml", source_root=_REPO_ROOT)

SCHEMA_VERSION = 1

#: Unidades de código do gradiente que NÃO são Python — onde cada uma mora
#: na árvore. O resto das unidades sai de `kernel/blocks.PYTHON_SRC`.
_UNIDADES_FORA_DO_PYTHON = {"desktop": "desktop/", "native": "native/crates/"}

_TESTES = "backend/tests/"


class OntologyError(RuntimeError):
    """Registro inparseável ou de versão incompatível."""


def load(path: Path | str | None = None) -> dict:
    """O registro cru, validado só quanto a schema — as regras vêm depois."""
    toml_path = Path(path) if path else DEFAULT_PATH
    try:
        data = tomllib.loads(toml_path.read_text())
    except tomllib.TOMLDecodeError as e:            # pragma: no cover - I/O
        raise OntologyError(f"ontology.toml inparseável: {e}") from e
    if data.get("schema_version") != SCHEMA_VERSION:
        raise OntologyError(
            f"schema_version {data.get('schema_version')!r} != "
            f"{SCHEMA_VERSION} — o loader não adivinha formato")
    return data


def _refs(data: dict) -> set[str]:
    alvos: set[str] = set()
    for secao in ("axes", "terms", "vocabularies"):
        for corpo in data.get(secao, {}).values():
            alvos.update(corpo.get("lives_in", ()))
    return alvos


def lint(path: Path | str | None = None, root: Path | str | None = None
         ) -> tuple[dict, tuple[Finding, ...]]:
    """Registro + findings ordenados deterministicamente.

    Códigos estáveis (contrato de erro, como em `epistemic/model.py`):

    - `ontology.axis_mismatch` — vocabulário declarado ≠ constante real;
    - `ontology.axis_undeclared` — eixo no código sem verbete aqui;
    - `ontology.term_off_axis` — valor que aparece em dois eixos;
    - `ontology.vocabulary_undeclared` — vocabulário fechado do código
      sem verbete (ou verbete sem constante);
    - `ontology.vocabulary_mismatch` — valores/objeto declarados ≠ código;
    - `ontology.ref_missing` — `lives_in` que não existe no disco;
    - `ontology.drift_sense_gone` — deriva aberta cujo marcador sumiu;
    - `ontology.drift_regressed` — separação resolvida que perdeu um nome;
    - `ontology.refs_uncheckable` — binário empacotado, sem árvore de código.

    Blocos do projeto (§4):

    - `ontology.block_shape` — bloco sem `kind`/`paths`/`question`/
      `not_means`, tipo fora de `block_kind` ou caminho malformado;
    - `ontology.block_path_missing` — caminho declarado que não existe;
    - `ontology.block_overlap` — um arquivo coberto por dois blocos;
    - `ontology.block_orphan_file` — arquivo versionado sem bloco;
    - `ontology.blocks_uncheckable` — sem git, a partição não é verificável;
    - `ontology.tier_mismatch` — unidade de código sem camada em
      `architecture.toml [[tier]]`, ou camada citando unidade inexistente;
    - `ontology.block_unit_mismatch` — unidade Python sem bloco homônimo,
      ou bloco de código Python que não é exatamente uma unidade;
    - `ontology.package_root_not_bare` — a raiz do pacote ganhou lógica;
    - `ontology.block_dependency_unknown` — `depends_on` citando o que não
      é bloco de código Python;
    - `ontology.block_dependency_undeclared` — import real sem declaração;
    - `ontology.block_dependency_stale` — declaração sem import (warn);
    - `ontology.block_dependency_forbidden` — dependência que
      `[dependency_rule]` proíbe (dívida não a legitima);
    - `ontology.block_debt_undeclared` — aresta contra o gradiente ou fora
      da allowlist de `api` sem dívida registrada;
    - `ontology.block_debt_paid` — dívida registrada que já não existe
      (warn: pare de cobrá-la);
    - `ontology.block_unproven` — bloco Python que nenhum teste importa (warn).
    """
    data, findings, _ = _lint_e_analise(path, root)
    return data, findings


def _lint_e_analise(path: Path | str | None, root: Path | str | None
                    ) -> tuple[dict, tuple[Finding, ...], dict]:
    data = load(path)
    raiz = Path(root) if root else _REPO_ROOT
    out: list[Finding] = []
    declarados = data.get("axes", {})

    # --- 1. o TOML não pode mentir sobre o vocabulário do kernel --------
    for eixo, vocab in onto.AXES.items():
        corpo = declarados.get(eixo)
        if corpo is None:
            out.append(Finding(
                "ontology.axis_undeclared", "error", eixo,
                f"o eixo `{eixo}` existe em kernel/ontology.py e não tem "
                "verbete em ontology.toml"))
            continue
        if tuple(corpo.get("values", ())) != vocab:
            out.append(Finding(
                "ontology.axis_mismatch", "error", eixo,
                f"vocabulário declarado {list(corpo.get('values', ()))} ≠ "
                f"{list(vocab)} em kernel/ontology.py"))
        if not corpo.get("question"):
            out.append(Finding(
                "ontology.axis_undeclared", "error", eixo,
                "eixo sem `question` — um eixo que não declara a pergunta "
                "não permite testar se um valor está nele por engano"))

    # --- 2. nenhum valor pode responder a duas perguntas ----------------
    for eixo, vocab in onto.AXES.items():
        for valor in vocab:
            outros = [e for e in onto.eixos_de(valor) if e != eixo]
            if outros:
                out.append(Finding(
                    "ontology.term_off_axis", "error", eixo,
                    f"`{valor}` também está em {outros} — um termo, duas "
                    "perguntas: é a conflação que RFC-004 combate"))

    # --- 2b. vocabulário fechado NOVO precisa de verbete ---------------
    # O buraco que esta regra fecha foi MEDIDO nesta trilha: a V5 criou
    # `RELACOES` e a C6 criou `SideEffect` — dois vocabulários fechados
    # que entram no canônico e no registro epistêmico — e o léxico não
    # cresceu um verbete, sem que nada acendesse. É o mesmo defeito que
    # `EXPECTED_MECHANISMS` fechou do lado epistêmico (G-10): o registro
    # verificava o que ESTÁ declarado e nada cobrava o que FALTA.
    declarados_vocab = data.get("vocabularies", {})
    for nome, (valores, objeto, mora_em) in onto.VOCABULARIES.items():
        corpo = declarados_vocab.get(nome)
        if corpo is None:
            out.append(Finding(
                "ontology.vocabulary_undeclared", "error", nome,
                f"o vocabulário fechado `{nome}` existe em {mora_em} e não "
                "tem verbete em ontology.toml — vocabulário sem fronteira "
                "declarada é a deriva que este registro existe para impedir"))
            continue
        if tuple(corpo.get("values", ())) != valores:
            out.append(Finding(
                "ontology.vocabulary_mismatch", "error", nome,
                f"vocabulário declarado {list(corpo.get('values', ()))} ≠ "
                f"{list(valores)} em {mora_em}"))
        if corpo.get("applies_to") != objeto:
            out.append(Finding(
                "ontology.vocabulary_mismatch", "error", nome,
                f"`applies_to` declarado {corpo.get('applies_to')!r} ≠ "
                f"{objeto!r} — o OBJETO de um vocabulário fechado é parte "
                "da sua identidade (relação ≠ afirmação ≠ mecanismo)"))
    for nome in sorted(set(declarados_vocab) - set(onto.VOCABULARIES)):
        out.append(Finding(
            "ontology.vocabulary_undeclared", "error", nome,
            "verbete de vocabulário sem constante correspondente no "
            "código — registro não pode apodrecer em nenhuma das duas "
            "direções"))

    # --- 3. refs e marcadores (única parte que precisa de filesystem) ---
    analise: dict = {}
    if frozen():
        # Binário empacotado não carrega a árvore de código: dizer "não
        # existe" para todo `lives_in` acusaria dezenas de erros que não
        # existem. Omitir a checagem é legítimo; omitir que ela foi
        # omitida, não (mesma disciplina de harness/epistemics.py).
        out.append(Finding(
            "ontology.refs_uncheckable", "warn", "",
            "binário empacotado: `lives_in`, marcadores de deriva e blocos "
            "do projeto não são verificáveis sem a árvore de código"))
    else:
        for ref in sorted(_refs(data)):
            if not (raiz / ref).is_file():
                out.append(Finding(
                    "ontology.ref_missing", "error", ref,
                    f"`lives_in` aponta para {ref}, que não existe"))
        out.extend(_lint_drift(data, raiz))
        # --- 4. blocos do projeto: partição, camadas e dependências -----
        blocos_findings, analise = _lint_blocos(data, raiz)
        out.extend(blocos_findings)

    return data, tuple(sorted(set(out),
                              key=lambda f: (f.code, f.mechanism_id,
                                             f.message))), analise


def _lint_drift(data: dict, raiz: Path) -> list[Finding]:
    out: list[Finding] = []
    for nome, corpo in data.get("drift", {}).items():
        status = corpo.get("status")
        if status not in ("open", "resolved"):
            out.append(Finding(
                "ontology.drift_status_invalid", "error", nome,
                f"status {status!r} fora de open|resolved"))
            continue
        for ref, marker in corpo.get("markers", ()):
            alvo = raiz / ref
            if not alvo.is_file():
                out.append(Finding(
                    "ontology.ref_missing", "error", nome,
                    f"marcador de deriva aponta para {ref}, que não existe"))
                continue
            if marker in alvo.read_text():
                continue
            if status == "open":
                out.append(Finding(
                    "ontology.drift_sense_gone", "warn", nome,
                    f"o sentido marcado por `{marker}` sumiu de {ref}: se a "
                    "deriva foi paga, o registro precisa parar de cobrá-la"))
            else:
                out.append(Finding(
                    "ontology.drift_regressed", "error", nome,
                    f"a separação declarada resolvida perdeu um nome: "
                    f"`{marker}` não está mais em {ref}"))
    return out


# ===================================================== blocos do projeto
def _arquivos_versionados(raiz: Path) -> list[str] | None:
    """O que o projeto É: os arquivos que o Git versiona (índice do
    checkout), sem o lixo local do working tree. `None` quando não há
    Git — e quem chama DIZ que a partição ficou sem verificar."""
    try:
        r = subprocess.run(["git", "-C", str(raiz), "ls-files", "-z"],
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return sorted(p for p in r.stdout.decode("utf-8").split("\0")
                  if p and (raiz / p).is_file())


def _unidades_python(raiz: Path) -> set[str]:
    src = raiz / blk.PYTHON_SRC
    if not src.is_dir():
        return set()
    return ({p.name for p in src.iterdir()
             if p.is_dir() and (p / "__init__.py").is_file()}
            | {p.stem for p in src.glob("*.py") if p.name != "__init__.py"})


def _camadas(raiz: Path) -> tuple[list[dict], dict[str, int], dict]:
    if not (raiz / "architecture.toml").is_file():
        return [], {}, {}                  # toda unidade acusará tier_mismatch
    arch = tomllib.loads((raiz / "architecture.toml").read_text())
    tiers = list(arch.get("tier", []))
    nivel = {u: i for i, t in enumerate(tiers) for u in t.get("units", [])}
    return tiers, nivel, arch.get("dependency_rule", {})


def _alvos_de_import(arquivo: Path, rel: str, unidades: set[str]) -> set[str]:
    """Unidades de `corpusmith` alcançadas por QUALQUER import do arquivo —
    relativo ou absoluto, no topo ou dentro de função (import tardio é
    acoplamento do mesmo jeito; só adia o custo). A raiz do pacote
    (`from .. import __version__`) não conta: carrega só a versão."""
    pacote = (rel[len(blk.PYTHON_SRC):].split("/")[:-1]
              if rel.startswith(blk.PYTHON_SRC) else [])
    alvos: set[str] = set()

    def _nome_na_raiz(nomes) -> None:
        for alias in nomes:
            if alias.name in unidades:
                alvos.add(alias.name)

    for node in ast.walk(ast.parse(arquivo.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0:
                partes = (node.module or "").split(".")
                if partes[0] != "corpusmith":
                    continue
                cheio = partes[1:]
            else:
                subir = node.level - 1
                base = pacote[:len(pacote) - subir] if subir else pacote
                cheio = base + (node.module.split(".") if node.module else [])
            if cheio:
                if cheio[0] in unidades:
                    alvos.add(cheio[0])
            else:
                _nome_na_raiz(node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                partes = alias.name.split(".")
                if partes[0] == "corpusmith" and len(partes) > 1 \
                        and partes[1] in unidades:
                    alvos.add(partes[1])
    return alvos


def _raiz_do_pacote_nua(raiz: Path) -> bool:
    """A raiz do pacote só pode ter docstring e `__version__` — é o que
    justifica não contar a aresta para ela como acoplamento."""
    arquivo = raiz / blk.PACKAGE_ROOT
    if not arquivo.is_file():
        return True
    corpo = ast.parse(arquivo.read_text()).body
    for node in corpo:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue                                   # docstring
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, ast.Assign) and [getattr(t, "id", None)
                                             for t in node.targets] \
                == ["__version__"]:
            continue
        return False
    return True


def _caminho_ok(p: object) -> bool:
    return (isinstance(p, str) and bool(p) and not p.startswith("/")
            and "\\" not in p and ".." not in p.split("/"))


def _lint_blocos(data: dict, raiz: Path) -> tuple[list[Finding], dict]:
    out: list[Finding] = []
    blocos_raw: dict = data.get("blocks", {})
    if not blocos_raw:
        out.append(Finding(
            "ontology.block_shape", "error", "",
            "ontology.toml sem §4 `[blocks]` — sem o índice, nenhum arquivo "
            "do projeto tem fronteira declarada"))
        return out, {}

    # --- 4a. forma de cada bloco ---------------------------------------
    caminhos: dict[str, list[str]] = {}
    for bid, corpo in sorted(blocos_raw.items()):
        faltando = [c for c in ("kind", "paths", "question", "not_means")
                    if not corpo.get(c)]
        if faltando:
            out.append(Finding(
                "ontology.block_shape", "error", bid,
                f"bloco sem {faltando} — um bloco que não declara a pergunta "
                "que responde e o que NÃO é não tem fronteira testável"))
        if corpo.get("kind") and corpo["kind"] not in blk.KINDS:
            out.append(Finding(
                "ontology.block_shape", "error", bid,
                f"tipo {corpo['kind']!r} fora de {list(blk.KINDS)}"))
        ps = list(corpo.get("paths", ()))
        ruins = [p for p in ps if not _caminho_ok(p)]
        if ruins:
            out.append(Finding(
                "ontology.block_shape", "error", bid,
                f"caminhos malformados {ruins} — relativos à raiz, com `/` "
                "e sem `..`"))
        caminhos[bid] = [p for p in ps if _caminho_ok(p)]
        for p in caminhos[bid]:
            alvo = raiz / p.rstrip("/")
            existe = alvo.is_dir() if p.endswith("/") else alvo.is_file()
            if not existe:
                out.append(Finding(
                    "ontology.block_path_missing", "error", bid,
                    f"`{p}` não existe — o índice não pode declarar parte "
                    "que o repositório não tem"))

    # --- 4b. partição: nenhum arquivo em dois blocos, nenhum sem bloco --
    for ba, pa, bb, pb in blk.sobreposicoes(caminhos):
        out.append(Finding(
            "ontology.block_overlap", "error", ba,
            f"`{pa}` ({ba}) e `{pb}` ({bb}) cobrem os mesmos arquivos — "
            "um arquivo, dois blocos: a conflação que a partição proíbe"))
    arquivos = _arquivos_versionados(raiz)
    if arquivos is None:
        out.append(Finding(
            "ontology.blocks_uncheckable", "warn", "",
            "sem Git não há lista de arquivos versionados: a partição do "
            "projeto em blocos não foi verificada"))
        arquivos = []
    else:
        por_topo: dict[str, list[str]] = {}
        for orfao in blk.orfaos(arquivos, caminhos):
            topo = orfao.split("/", 1)[0] + ("/" if "/" in orfao else "")
            por_topo.setdefault(topo, []).append(orfao)
        for topo, lista in sorted(por_topo.items()):
            exemplos = ", ".join(lista[:3]) + (" …" if len(lista) > 3 else "")
            out.append(Finding(
                "ontology.block_orphan_file", "error", topo,
                f"{len(lista)} arquivo(s) versionado(s) sem bloco: {exemplos} "
                "— parte do projeto fora do índice fica fora de toda regra "
                "que o índice sustenta"))

    # --- 4c. camadas × árvore (architecture.toml [[tier]]) --------------
    tiers, nivel, regra = _camadas(raiz)
    unidades = _unidades_python(raiz)
    na_arvore = unidades | {u for u, onde in _UNIDADES_FORA_DO_PYTHON.items()
                            if (raiz / onde).is_dir()}
    for u in sorted(na_arvore - set(nivel)):
        out.append(Finding(
            "ontology.tier_mismatch", "error", u,
            f"a unidade `{u}` existe na árvore e não tem camada em "
            "architecture.toml [[tier]] — regra que cita pacote pelo nome "
            "não vale para o pacote que ela não cita"))
    for u in sorted(set(nivel) - na_arvore):
        out.append(Finding(
            "ontology.tier_mismatch", "error", u,
            f"architecture.toml [[tier]] cita `{u}`, que não existe na "
            "árvore — camada para unidade fantasma"))

    # --- 4d. bloco de código Python = UMA unidade, de mesmo nome --------
    python: dict[str, str] = {}          # bloco → unidade
    for bid, ps in sorted(caminhos.items()):
        if blocos_raw[bid].get("kind") != "code":
            continue
        dentro = [p for p in ps if p.startswith(blk.PYTHON_SRC)]
        if not dentro or ps == [blk.PACKAGE_ROOT]:
            continue
        units = {blk.unidade_python(p.rstrip("/") + ("/x.py" if p.endswith("/") else ""))
                 for p in dentro}
        if len(dentro) != len(ps) or len(units) != 1 or None in units:
            out.append(Finding(
                "ontology.block_unit_mismatch", "error", bid,
                f"bloco de código Python precisa ser exatamente UMA unidade "
                f"do gradiente; declara {ps}"))
            continue
        unidade = units.pop()
        if unidade != bid:
            out.append(Finding(
                "ontology.block_unit_mismatch", "error", bid,
                f"o bloco cobre a unidade `{unidade}` e se chama `{bid}` — o "
                "nome do bloco de código Python é o da unidade, para que "
                "`depends_on` leia como os imports"))
            continue
        python[bid] = unidade
    for u in sorted(unidades - set(python.values())):
        out.append(Finding(
            "ontology.block_unit_mismatch", "error", u,
            f"a unidade Python `{u}` não tem bloco `[blocks.{u}]` de código"))
    if not _raiz_do_pacote_nua(raiz):
        out.append(Finding(
            "ontology.package_root_not_bare", "error", blk.PACKAGE_ROOT,
            "a raiz do pacote ganhou lógica além de `__version__` — a aresta "
            "para ela deixa de ser inofensiva e o índice não a enxerga"))

    # --- 4e. dependências: declaradas × reais, e as que são dívida ------
    real: dict[str, set[str]] = {}
    for bid, unidade in python.items():
        alvos: set[str] = set()
        for p in caminhos[bid]:
            base = raiz / p.rstrip("/")
            for py in sorted(base.rglob("*.py") if base.is_dir() else [base]):
                rel = py.relative_to(raiz).as_posix()
                alvos |= _alvos_de_import(py, rel, unidades)
        alvos.discard(unidade)
        real[bid] = {a for a in alvos if a in python}
    proibidas = {"usecases": set(regra.get("usecases_forbidden", ()))}
    so_facades = set(regra.get("api_allowed_internal", ()))
    for bid in sorted(python):
        corpo = blocos_raw[bid]
        declarado = list(corpo.get("depends_on", ()))
        desconhecidos = sorted(set(declarado) - set(python))
        if desconhecidos:
            out.append(Finding(
                "ontology.block_dependency_unknown", "error", bid,
                f"`depends_on` cita {desconhecidos}, que não são blocos de "
                "código Python"))
        novos, mortos = blk.divergencias(declarado, real[bid])
        for alvo in novos:
            out.append(Finding(
                "ontology.block_dependency_undeclared", "error", bid,
                f"`{bid}` importa `{alvo}` e não declara — acoplamento novo "
                "entre blocos é decisão visível no registro, não efeito "
                "colateral de um import"))
        for alvo in mortos:
            out.append(Finding(
                "ontology.block_dependency_stale", "warn", bid,
                f"`{bid}` declara depender de `{alvo}` e não importa — se o "
                "acoplamento acabou, o registro precisa parar de declará-lo"))
        for alvo in sorted((set(declarado) | real[bid])
                           & proibidas.get(bid, set())):
            out.append(Finding(
                "ontology.block_dependency_forbidden", "error", bid,
                f"`{bid}` → `{alvo}` é proibido por architecture.toml "
                "[dependency_rule] — invariante não vira dívida"))
        # o que é dívida: contra o gradiente, ou fora da allowlist de api
        devidas = {b for _, b in blk.contra_o_gradiente(
            ((bid, b) for b in real[bid]), nivel)}
        if bid == "api" and so_facades:
            devidas |= real[bid] - so_facades
        registradas = dict(corpo.get("debts", {}))
        for alvo in sorted(devidas - set(registradas)):
            out.append(Finding(
                "ontology.block_debt_undeclared", "error", bid,
                f"`{bid}` → `{alvo}` contraria o gradiente ou "
                "[dependency_rule] e não está em `debts` — a aresta pode "
                "existir, mas só como dívida com motivo"))
        for alvo in sorted(set(registradas) - devidas):
            out.append(Finding(
                "ontology.block_debt_paid", "warn", bid,
                f"dívida `{bid}` → `{alvo}` registrada e a aresta já não "
                "contraria nada — se foi paga, pare de cobrá-la"))

    # --- 4f. prova: algum teste exercita cada bloco Python? -------------
    testes: dict[str, set[str]] = {b: set() for b in python}
    pasta = raiz / _TESTES
    if pasta.is_dir():
        for py in sorted(pasta.rglob("*.py")):
            rel = py.relative_to(raiz).as_posix()
            for alvo in _alvos_de_import(py, rel, unidades):
                if alvo in testes:
                    testes[alvo].add(rel)
    for bid in sorted(b for b, ts in testes.items() if not ts):
        out.append(Finding(
            "ontology.block_unproven", "warn", bid,
            f"nenhum arquivo de {_TESTES} importa `{bid}` — bloco sem "
            "teste que o exercite diretamente"))

    analise = {"caminhos": caminhos, "arquivos": arquivos, "tiers": tiers,
               "nivel": nivel, "python": python, "real": real,
               "testes": testes}
    return out, analise


# ============================================================ o índice
def _mecanismos(raiz: Path) -> dict[str, list[str]]:
    """mecanismo → implementation_refs, pelo loader ÚNICO do registro
    epistêmico (nenhuma releitura paralela do TOML)."""
    caminho = raiz / "epistemics.toml"
    if not caminho.is_file():
        return {}
    from .epistemics import load_registry
    registry, _ = load_registry(caminho)
    return {c.mechanism_id: list(c.implementation_refs)
            for c in registry.contracts}


def _indice(data: dict, analise: dict, raiz: Path) -> list[dict]:
    if not analise:
        return []
    caminhos: dict[str, list[str]] = analise["caminhos"]
    nome_da_camada = {u: t.get("name", "") for t in analise["tiers"]
                      for u in t.get("units", [])}
    termos: dict[str, set[str]] = {b: set() for b in caminhos}
    for secao in ("axes", "terms", "vocabularies"):
        for nome, corpo in data.get(secao, {}).items():
            for ref in corpo.get("lives_in", ()):
                dono = blk.bloco_de(ref, caminhos)
                if dono:
                    termos[dono].add(nome)
    mecanismos: dict[str, set[str]] = {b: set() for b in caminhos}
    for mid, refs in _mecanismos(raiz).items():
        for ref in refs:
            dono = blk.bloco_de(ref, caminhos)
            if dono:
                mecanismos[dono].add(mid)
    arquivos_por: dict[str, int] = {b: 0 for b in caminhos}
    for a in analise["arquivos"]:
        dono = blk.bloco_de(a, caminhos)
        if dono:
            arquivos_por[dono] += 1
    blocos_raw = data.get("blocks", {})
    usado_por: dict[str, set[str]] = {b: set() for b in caminhos}
    for bid, corpo in blocos_raw.items():
        for alvo in corpo.get("depends_on", ()):
            if alvo in usado_por:
                usado_por[alvo].add(bid)
    out = []
    for bid in sorted(caminhos):
        corpo = blocos_raw[bid]
        unidade = analise["python"].get(bid) or (
            bid if bid in _UNIDADES_FORA_DO_PYTHON else "")
        out.append({
            "block": bid,
            "kind": corpo.get("kind", ""),
            "paths": list(caminhos[bid]),
            "question": corpo.get("question", ""),
            "not_means": corpo.get("not_means", ""),
            "tier": nome_da_camada.get(unidade, ""),
            "files": arquivos_por[bid],
            "depends_on": sorted(corpo.get("depends_on", ())),
            "used_by": sorted(usado_por[bid]),
            "debts": dict(sorted(corpo.get("debts", {}).items())),
            "terms": sorted(termos[bid]),
            "mechanisms": sorted(mecanismos[bid]),
            "tests": sorted(analise["testes"].get(bid, ())),
        })
    return out


def overview(path: Path | str | None = None,
             root: Path | str | None = None) -> dict:
    """Resumo estável para CLI, API e painel — sem reimplementar leitura."""
    raiz = Path(root) if root else _REPO_ROOT
    data, findings, analise = _lint_e_analise(path, raiz)
    return {
        "version": data.get("ontology", {}).get("version", ""),
        "axes": [{"axis": eixo,
                  "question": corpo.get("question", ""),
                  "values": list(corpo.get("values", ())),
                  "applies_to": corpo.get("applies_to", "")}
                 for eixo, corpo in sorted(data.get("axes", {}).items())],
        "terms": [{"term": termo,
                   "roots": corpo.get("roots", ""),
                   "means": corpo.get("means", ""),
                   "not_means": corpo.get("not_means", ""),
                   "constrains": corpo.get("constrains", "")}
                  for termo, corpo in sorted(data.get("terms", {}).items())],
        "drift": [{"name": nome,
                   "field": corpo.get("field", ""),
                   "status": corpo.get("status", ""),
                   "senses": list(corpo.get("senses", ()))}
                  for nome, corpo in sorted(data.get("drift", {}).items())],
        "tiers": [{"name": t.get("name", ""), "units": list(t.get("units", []))}
                  for t in analise.get("tiers", [])],
        "blocks": _indice(data, analise, raiz),
        "findings": [f.to_dict() for f in findings],
        "ok": not any(f.severity == "error" for f in findings),
    }


def where(alvo: str, path: Path | str | None = None,
          root: Path | str | None = None) -> dict:
    """Busca SEMÂNTICA no índice: a que bloco pertence um caminho, onde
    mora um termo/eixo/vocabulário, onde é implementado um mecanismo — ou
    o cartão de um bloco pelo nome. Devolve TODOS os casamentos, cada um
    com o motivo (`via`), porque o mesmo nome pode ser bloco e termo."""
    raiz = Path(root) if root else _REPO_ROOT
    data, _, analise = _lint_e_analise(path, raiz)
    indice = {b["block"]: b for b in _indice(data, analise, raiz)}
    caminhos = analise.get("caminhos", {})
    achados: list[tuple[str, str]] = []
    limpo = alvo.strip().removeprefix("./")
    if limpo in indice:
        achados.append((limpo, "bloco"))
    # o caminho como veio, como diretório, e a abreviação que os docs usam
    # (`okf/writer.py` = `backend/src/corpusmith/okf/writer.py`)
    dono = None
    for forma in (limpo, limpo + "/", blk.PYTHON_SRC + limpo,
                  blk.PYTHON_SRC + limpo + "/"):
        if caminhos and limpo and not forma.endswith("//"):
            dono = blk.bloco_de(forma, caminhos)
            if dono:
                break
    if dono and (dono, "bloco") not in achados:
        achados.append((dono, "caminho"))
    for secao, via in (("terms", "termo"), ("axes", "eixo"),
                       ("vocabularies", "vocabulário")):
        corpo = data.get(secao, {}).get(limpo)
        if corpo:
            for ref in corpo.get("lives_in", ()):
                b = blk.bloco_de(ref, caminhos)
                if b:
                    achados.append((b, f"{via} (lives_in {ref})"))
    for mid, refs in _mecanismos(raiz).items():
        if mid == limpo:
            for ref in refs:
                b = blk.bloco_de(ref, caminhos)
                if b:
                    achados.append((b, f"mecanismo (implementation_refs {ref})"))
    vistos: set[tuple[str, str]] = set()
    matches = []
    for b, via in achados:
        if (b, via) in vistos:
            continue
        vistos.add((b, via))
        matches.append({"via": via, **indice[b]})
    return {"query": alvo, "matches": matches}
