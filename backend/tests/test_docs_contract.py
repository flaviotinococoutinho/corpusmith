"""A documentação vira contrato — as guardas que faltavam (docs/10 §18).

Até aqui a única doc lida por teste era o `AGENTS.md` (uma linha em
`test_pr0_gate`). Índice, links, status e contagens de 30 documentos podiam
apodrecer sem quebrar a suíte — e apodreceram, medido em 2026-09-02:
`docs/README` dizia "17 verbetes" com 22 no registro; `docs/10` dizia
"1.5.0, 248 testes" com o produto em 2.0.0 e 900+ testes; cinco planos
congelados (09, 13, 14, 15, 17) não diziam a um leitor — humano ou agente —
que são fotografias, e um agente que os lesse como vivos proporia construir
o que já existe.

Cinco guardas, todas baratas e todas derivadas de um defeito real:

1. **todo doc declara altitude e status** na cabeça (uma linha, parseável):
   `histórico` aponta para a fonte viva, `vivo` é mantido no PR que muda o
   fato. É a diferença entre "fotografia" e "estado";
2. **o índice lista todo documento** — arquivo sem linha em `docs/README.md`
   é documento que ninguém roteia;
3. **todo link relativo resolve** — fora de crase e de bloco de código, onde
   os três "links quebrados" medidos eram exemplos de sintaxe;
4. **doc VIVO não crava contagem de registro nem de suíte** — o número
   deriva no primeiro PR que adiciona um mecanismo, termo ou teste. A fonte
   é o registro (`epistemics.toml`, `ontology.toml`) e o coletor; a doc
   linka ou cita o comando que conta (`corpusmith context`);
5. **a projeção à mão do registro epistêmico acompanha o registro** — a
   C13 rebaixou `retrieval_rrf_hedge` só no `epistemics.toml`, e o
   `docs/11` seguiu alegando o regret retirado na tabela da §7 e no exemplo
   da §4. O tipo de garantia de cada linha da §7 e o vocabulário da §4
   (reservado, exemplo) são cruzados com o registro.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"

ALTITUDES = ("produto", "ciência", "engenharia", "referência", "contrato",
             "fluxo", "governança", "índice")
_HEADER = re.compile(
    r"^> \*\*Altitude:\*\* (?P<alt>[^·]+?) · \*\*Status:\*\* "
    r"(?P<status>vivo|histórico)(?P<resto>.*)$")

# Docs que podem carregar número de teste/mecanismo/termo: são LEDGERS —
# registram o que foi verdade no commit em que fecharam algo (ADRs, o
# histórico de fechamento do backlog, RFCs com evidência da época) ou são
# fotografias congeladas. O resto é doc VIVO e a regra 4 vale.
LEDGERS = {"08-decisoes.md", "18-backlog-consolidado.md",
           "16-rfc-theme-id.md", "19-rfc-escada-reconciliacao.md",
           "20-rfc-colisao-de-caminho.md", "21-adr-categoria-corpusmith.md",
           "22-rfc-ontologia-da-assercao.md", "27-rfc-conflito-factual.md",
           "29-rfc-006-re-mira.md"}
_CONTAGEM = re.compile(
    r"\b\d+\s+(mecanismos?|termos|verbetes|testes|contratos|eixos)\b")


def _docs() -> list[Path]:
    return sorted(p for p in _DOCS.glob("*.md"))


def _header(path: Path) -> re.Match | None:
    for line in path.read_text().splitlines()[:8]:
        m = _HEADER.match(line)
        if m:
            return m
    return None


def _strip_code(text: str) -> str:
    """Remove blocos ``` e crases inline — exemplos de sintaxe não são
    links nem alegações (docs/01:58, docs/06:178, docs/15:193 medidos)."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


# ------------------------------------------------ 1. altitude e status
def test_todo_doc_declara_altitude_e_status():
    faltando = [p.name for p in _docs() if _header(p) is None]
    assert faltando == [], (
        "docs sem a linha `> **Altitude:** … · **Status:** vivo|histórico` "
        f"nas 8 primeiras linhas: {faltando}")


def test_altitude_e_vocabulario_fechado():
    fora = {p.name: _header(p)["alt"].strip() for p in _docs()
            if _header(p)["alt"].strip() not in ALTITUDES}
    assert fora == {}, f"altitude fora do vocabulário {ALTITUDES}: {fora}"


def test_doc_historico_aponta_para_a_fonte_viva():
    """Fotografia sem ponteiro é a armadilha: o leitor não sabe que há um
    estado mais novo. `histórico` obriga a dizer ONDE está o vivo."""
    for p in _docs():
        m = _header(p)
        if m["status"] == "histórico":
            assert "18-backlog-consolidado.md" in m["resto"], (
                f"{p.name} é histórico e não aponta para docs/18")


def test_agents_nao_roteia_doc_historico_como_destino_de_escrita():
    """AGENTS.md §10 mandava fechar backlog em docs/09 (congelado na v1.5)
    enquanto docs/README declarava docs/18 a fonte viva. Um agente que
    seguisse o roteamento escreveria numa fotografia."""
    agents = (_ROOT / "AGENTS.md").read_text()
    historicos = [p.name for p in _docs()
                  if _header(p)["status"] == "histórico"]
    citados = [h for h in historicos if h in agents]
    assert citados == [], (
        f"AGENTS.md cita documento histórico como se fosse vivo: {citados}")


# ------------------------------------------------ 2. índice completo
def test_readme_dos_docs_lista_todo_documento():
    indice = (_DOCS / "README.md").read_text()
    fora = [p.name for p in _docs()
            if p.name != "README.md" and p.name not in indice]
    assert fora == [], f"documentos sem linha em docs/README.md: {fora}"


# ------------------------------------------------ 3. links resolvem
_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def _paginas_com_links() -> list[Path]:
    return _docs() + [_ROOT / "README.md", _ROOT / "AGENTS.md",
                      _ROOT / "CLAUDE.md", _ROOT / "CONTRIBUTING.md"]


def test_todo_link_relativo_resolve():
    quebrados = []
    for p in _paginas_com_links():
        if not p.is_file():
            continue
        for alvo in _LINK.findall(_strip_code(p.read_text())):
            if alvo.startswith(("http://", "https://", "mailto:")):
                continue
            if not (p.parent / alvo).resolve().exists():
                quebrados.append(f"{p.relative_to(_ROOT)} -> {alvo}")
    assert quebrados == [], "links relativos sem alvo:\n  " + \
        "\n  ".join(quebrados)


def test_todo_adr_citado_existe_em_docs08():
    """`ADR-NN` é citado em docs, AGENTS e nos TOMLs; docs/08 tem 50+
    headings sem índice. Uma citação para o vazio não quebrava nada."""
    headings = set(re.findall(r"^#{2,4} ADR-(\d+)",
                              (_DOCS / "08-decisoes.md").read_text(), re.M))
    fontes = _paginas_com_links() + [_ROOT / "architecture.toml",
                                     _ROOT / "epistemics.toml",
                                     _ROOT / "ontology.toml",
                                     _ROOT / "nfr.toml"]
    fantasmas = sorted({f"{p.name}: ADR-{n}" for p in fontes if p.is_file()
                        for n in re.findall(r"ADR-(\d+)", p.read_text())
                        if n not in headings})
    assert fantasmas == [], f"ADR citado sem heading em docs/08: {fantasmas}"


# ------------------------------------------------ 4. contagem não crava
def _vivos() -> list[Path]:
    """Doc sem cabeçalho conta como VIVO aqui (a regra 4 vale para ele) —
    a ausência do cabeçalho é reprovada pelo teste próprio, não por erro
    de coleta desta parametrização (medido por mutação)."""
    def status(p: Path) -> str:
        m = _header(p)
        return m["status"] if m else "vivo"
    return [p for p in _docs()
            if p.name not in LEDGERS and status(p) == "vivo"] + \
        [_ROOT / "README.md", _ROOT / "AGENTS.md", _ROOT / "CLAUDE.md"]


@pytest.mark.parametrize("doc", _vivos(), ids=lambda p: p.name)
def test_doc_vivo_nao_crava_contagem_de_registro_nem_de_suite(doc: Path):
    """Generaliza `test_agents_md_nao_finge_contagem_de_testes` para todo
    doc vivo: "17 verbetes" com 22 no registro foi medido no índice."""
    achados = [(i + 1, m.group(0))
               for i, line in enumerate(_strip_code(doc.read_text())
                                        .splitlines())
               for m in [_CONTAGEM.search(line)] if m]
    assert achados == [], (
        f"{doc.name} crava contagem que deriva: {achados} — cite a fonte "
        "(`corpusmith context`, o registro) em vez do número")


# ------------------------------------------------ 5. docs/11 × registro
_DOC11 = _DOCS / "11-epistemic-contracts.md"


def _secao_do_doc11(n: str) -> str:
    m = re.search(rf"^## {n}\. .*?(?=^## )", _DOC11.read_text(), re.M | re.S)
    assert m, f"docs/11 perdeu a §{n}"
    return m.group(0)


def test_docs11_garantia_de_cada_mecanismo_abre_com_o_tipo_do_registro():
    """A tabela da §7 é projeção À MÃO do `epistemics.toml`: a C13 rebaixou
    `retrieval_rrf_hedge` a `heuristic` só no registro, e a linha seguiu
    alegando "regret relativo ao melhor stream fixo observado" — nada
    cruzava as duas. Cada célula de garantia abre com o literal do
    `guarantee_kind` do contrato; mudar o tipo no registro sem tocar a linha
    quebra a suíte no mesmo commit. Prende o TIPO; a prosa ao lado continua
    sob revisão."""
    from corpusmith.harness.epistemics import load_registry
    registry, _ = load_registry()
    linhas = re.findall(r"^\| `([a-z_]+)` \| [^|]+ \| ([^|]+) \|",
                        _secao_do_doc11("7"), re.M)
    assert linhas, "a tabela de mecanismos da §7 sumiu ou mudou de forma"
    divergentes = []
    for mecanismo, garantia in linhas:
        contrato = registry.get(mecanismo)
        if contrato is None:
            divergentes.append(f"{mecanismo}: fora do registro")
        elif not garantia.strip().startswith(
                f"`{contrato.guarantee.kind.value}` — "):
            divergentes.append(
                f"{mecanismo}: a garantia deve abrir com "
                f"`{contrato.guarantee.kind.value}` — (o tipo do contrato)")
    assert divergentes == [], "\n".join(divergentes)


def test_docs11_vocabulario_de_garantia_segue_o_uso_no_registro():
    """A §4 é o vocabulário FECHADO de `guarantee_kind`: lista exatamente os
    valores de `GuaranteeKind`, chama de reservado só tipo sem contrato e dá
    exemplo só a tipo em uso. Dois desses derivaram: depois da C13 o exemplo
    de `online_regret_relative` seguiu "Hedge sobre streams" sem contrato do
    tipo, e `none` seguiu "reservado" com dois contratos nativos usando-o."""
    from corpusmith.epistemic.model import GuaranteeKind
    from corpusmith.harness.epistemics import load_registry
    registry, _ = load_registry()
    em_uso = {c.guarantee.kind.value for c in registry.contracts}
    listados, erros = set(), []
    for celula, significa, exemplo in re.findall(
            r"^\| ((?:`[a-z_]+`(?: / )?)+) \| ([^|]+) \| ([^|]+) \|",
            _secao_do_doc11("4"), re.M):
        tipos = re.findall(r"`([a-z_]+)`", celula)
        if tipos == ["guarantee_kind"]:          # cabeçalho da tabela
            continue
        listados |= set(tipos)
        usados = sorted(set(tipos) & em_uso)
        if significa.strip().startswith("reservad") and usados:
            erros.append(f"{tipos}: 'reservados', mas o registro usa {usados}")
        if not usados and not exemplo.strip().startswith("—"):
            erros.append(f"{tipos}: nenhum contrato usa, e o exemplo é "
                         f"{exemplo.strip()!r}")
    divergencia = {k.value for k in GuaranteeKind} ^ listados
    assert divergencia == set(), f"§4 × GuaranteeKind divergem: {divergencia}"
    assert erros == [], "\n".join(erros)
