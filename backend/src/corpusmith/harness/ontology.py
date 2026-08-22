"""Loader do registro ontológico (shell) — a ÚNICA implementação de
carga/lint, compartilhada por CLI, facade, API e testes (RFC-004).

Mesmo desenho de `harness/epistemics.py`: lê `ontology.toml` da raiz,
delega ao domínio PURO (`kernel/ontology.py`) tudo que é regra, e
acrescenta só o que exige filesystem — existência dos `lives_in` e
presença dos `markers` de deriva. Somente leitura.

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
"""
from __future__ import annotations
import tomllib
from pathlib import Path
from ..epistemic import Finding
from ..kernel import ontology as onto
from ..paths import frozen, resource as _resource

# harness/ → corpusmith → src → backend → raiz do repo
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATH = _resource("ontology.toml", source_root=_REPO_ROOT)

SCHEMA_VERSION = 1


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
    for secao in ("axes", "terms"):
        for corpo in data.get(secao, {}).values():
            alvos.update(corpo.get("lives_in", ()))
    return alvos


def lint(path: Path | str | None = None) -> tuple[dict, tuple[Finding, ...]]:
    """Registro + findings ordenados deterministicamente.

    Códigos estáveis (contrato de erro, como em `epistemic/model.py`):

    - `ontology.axis_mismatch` — vocabulário declarado ≠ constante real;
    - `ontology.axis_undeclared` — eixo no código sem verbete aqui;
    - `ontology.term_off_axis` — valor que aparece em dois eixos;
    - `ontology.ref_missing` — `lives_in` que não existe no disco;
    - `ontology.drift_sense_gone` — deriva aberta cujo marcador sumiu;
    - `ontology.drift_regressed` — separação resolvida que perdeu um nome;
    - `ontology.refs_uncheckable` — binário empacotado, sem árvore de código.
    """
    data = load(path)
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

    # --- 3. refs e marcadores (única parte que precisa de filesystem) ---
    if frozen():
        # Binário empacotado não carrega a árvore de código: dizer "não
        # existe" para todo `lives_in` acusaria dezenas de erros que não
        # existem. Omitir a checagem é legítimo; omitir que ela foi
        # omitida, não (mesma disciplina de harness/epistemics.py).
        out.append(Finding(
            "ontology.refs_uncheckable", "warn", "",
            "binário empacotado: `lives_in` e marcadores de deriva não "
            "são verificáveis sem a árvore de código"))
    else:
        for ref in sorted(_refs(data)):
            if not (_REPO_ROOT / ref).is_file():
                out.append(Finding(
                    "ontology.ref_missing", "error", ref,
                    f"`lives_in` aponta para {ref}, que não existe"))
        out.extend(_lint_drift(data))

    return data, tuple(sorted(set(out),
                              key=lambda f: (f.code, f.mechanism_id,
                                             f.message)))


def _lint_drift(data: dict) -> list[Finding]:
    out: list[Finding] = []
    for nome, corpo in data.get("drift", {}).items():
        status = corpo.get("status")
        if status not in ("open", "resolved"):
            out.append(Finding(
                "ontology.drift_status_invalid", "error", nome,
                f"status {status!r} fora de open|resolved"))
            continue
        for ref, marker in corpo.get("markers", ()):
            alvo = _REPO_ROOT / ref
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


def overview(path: Path | str | None = None) -> dict:
    """Resumo estável para CLI, API e painel — sem reimplementar leitura."""
    data, findings = lint(path)
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
        "findings": [f.to_dict() for f in findings],
        "ok": not any(f.severity == "error" for f in findings),
    }
