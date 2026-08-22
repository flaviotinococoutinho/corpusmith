"""Controle de autoridade (v0.8 §4): o gazetteer curado vive no bundle
como páginas `type: authority_record` — corrigir uma grafia é um commit,
não um deploy. Helper aqui para manter `normalize/` livre de dependências."""
from __future__ import annotations
from pathlib import Path
from .bundle import BundleReader
from ..normalize import Gazetteer, NormReport, analyze, rewrite
from ..normalize.gazetteer import TIER_BUNDLE, TIER_REFERENCIA


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


def _reference_quotations(bundle_root: Path) -> list[dict]:
    """Citações do reference.db (v1.2) — norma pré-computada no banco;
    o lint só normaliza o CORPO e faz busca de substring."""
    path = bundle_root.parent.parent / "state" / "reference.db"
    if not path.is_file():
        return []
    from ..runtime.db import connect
    conn = connect(path)
    rows = [dict(r) for r in conn.execute(
        "SELECT quote, author, source, norm FROM ref_quotations")]
    conn.close()
    return rows


def load_quotations(reader: BundleReader) -> list[dict]:
    return _derived(reader)["quotations"]


def _reference_terms(bundle_root: Path) -> list[dict]:
    """Termos do reference.db (v0.22) — referência DO MUNDO, relacional,
    separada do bundle. Layout padrão: <home>/knowledge/bundle ⇒
    <home>/state/reference.db; ausente ⇒ lista vazia (opcional)."""
    path = bundle_root.parent.parent / "state" / "reference.db"
    if not path.is_file():
        return []
    import json
    from ..runtime.db import connect
    conn = connect(path)
    rows = conn.execute("SELECT canonical, kind, aliases FROM ref_terms")
    out = [{"canonical": r["canonical"],
            "aliases": json.loads(r["aliases"]),
            "authority": r["kind"], "qid": None,
            "tier": TIER_REFERENCIA} for r in rows]
    conn.close()
    return out


def _build_derived(reader: BundleReader) -> dict:
    extra: list[dict] = []
    schemas: dict[str, dict] = {}
    for d in reader.iter_concepts():
        x = d.meta.model_dump(exclude_none=True)
        if d.meta.type == "authority_record" and x.get("canonical"):
            # `page` e `tier` (RFC-006 V2): a camada decide a precedência, e
            # a página é o alvo editável quando dois registros curados
            # disputam o mesmo alias — sem ela o finding não teria onde
            # apontar e o conflito viraria aviso sem ato
            extra.append({"canonical": x["canonical"],
                          "aliases": x.get("aliases", []),
                          "authority": x.get("authority", "term"),
                          "qid": x.get("qid"),
                          "tier": TIER_BUNDLE, "page": d.rel_path})
        elif d.meta.type == "collection_specification" and x.get("applies_to"):
            schemas[str(x["applies_to"])] = {
                "required_fields": list(x.get("required_fields", [])),
                "page": d.rel_path}
    # precedência (v0.22): authority_record VENCE reference.db, que vence
    # os SEEDS — a curadoria humana no bundle é sempre a última palavra
    taken = {e["canonical"].lower() for e in extra} | {
        str(a).lower() for e in extra for a in e["aliases"]}
    for term in _reference_terms(reader.root):
        # colisão por canonical OU por QUALQUER alias: a autoridade
        # curada no bundle fica com o termo inteiro
        claimed = {term["canonical"].lower()} | {
            str(a).lower() for a in term["aliases"]}
        if claimed & taken:
            continue
        extra.append(term)
    return {"gazetteer": Gazetteer.load(extra), "schemas": schemas,
            "quotations": _reference_quotations(reader.root)}


def invalidate_cache() -> None:
    """Import de referência não passa pelo Git — invalida o cache HEAD."""
    _CACHE.clear()


def load_gazetteer(reader: BundleReader) -> Gazetteer:
    return _derived(reader)["gazetteer"]


def load_type_schemas(reader: BundleReader) -> dict[str, dict]:
    """Schemas por tipo (DTT lite, v0.10): páginas collection_specification
    com `applies_to` declaram campos obrigatórios para aquele type — a
    validação é curada NO bundle, como tudo mais."""
    return _derived(reader)["schemas"]
