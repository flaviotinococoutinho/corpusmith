"""Controle de autoridade (v0.8 §4): o gazetteer curado vive no bundle
como páginas `type: authority_record` — corrigir uma grafia é um commit,
não um deploy. Helper aqui para manter `normalize/` livre de dependências."""
from __future__ import annotations
from pathlib import Path
from .bundle import BundleReader
from ..normalize import Gazetteer, NormReport, analyze, rewrite


def normalize_machine_body(body: str, gaz: Gazetteer) -> tuple[str, NormReport]:
    """Sanduíche PÓS para qualquer página gerada por máquina: reescreve a
    grafia canônica e re-anota sobre o texto final (o report devolvido
    reflete o corpo definitivo — é ele que vai para o índice)."""
    body = rewrite(body, analyze(body, gaz=gaz))
    return body, analyze(body, gaz=gaz)


# ------------------------------------------------------------------- cache
# Derivados do bundle (gazetteer + schemas de tipo) são caros de construir
# (varrem todos os concepts) e consultados em TODO ask/lint/compile. Como
# TODA escrita no bundle passa pelo BundleWriter e commita, o HEAD do kb é
# uma chave de invalidação perfeita: cache de 1 entrada keyed por (kb, HEAD).
_CACHE: dict[tuple[str, str], dict] = {}


def _kb_head(bundle_root: Path) -> str | None:
    """Lê o HEAD do kb direto do .git (barato; sem GitPython). None quando
    ilegível/sem commit ⇒ chamador NÃO cacheia (comportamento correto)."""
    git_dir = bundle_root.parent / ".git"
    try:
        head = (git_dir / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = git_dir / head[5:]
            return ref.read_text().strip() if ref.is_file() else None
        return head or None
    except OSError:
        return None


def _derived(reader: BundleReader) -> dict:
    head = _kb_head(reader.root)
    if head is None:
        return _build_derived(reader)
    key = (str(reader.root), head)
    if key not in _CACHE:
        _CACHE.clear()                     # 1 entrada viva basta (local-first)
        _CACHE[key] = _build_derived(reader)
    return _CACHE[key]


def _build_derived(reader: BundleReader) -> dict:
    extra: list[dict] = []
    schemas: dict[str, dict] = {}
    for d in reader.iter_concepts():
        x = d.meta.model_dump(exclude_none=True)
        if d.meta.type == "authority_record" and x.get("canonical"):
            extra.append({"canonical": x["canonical"],
                          "aliases": x.get("aliases", []),
                          "authority": x.get("authority", "term"),
                          "qid": x.get("qid")})
        elif d.meta.type == "collection_specification" and x.get("applies_to"):
            schemas[str(x["applies_to"])] = {
                "required_fields": list(x.get("required_fields", [])),
                "page": d.rel_path}
    return {"gazetteer": Gazetteer.load(extra), "schemas": schemas}


def load_gazetteer(reader: BundleReader) -> Gazetteer:
    return _derived(reader)["gazetteer"]


def load_type_schemas(reader: BundleReader) -> dict[str, dict]:
    """Schemas por tipo (DTT lite, v0.10): páginas collection_specification
    com `applies_to` declaram campos obrigatórios para aquele type — a
    validação é curada NO bundle, como tudo mais."""
    return _derived(reader)["schemas"]
