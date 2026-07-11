from __future__ import annotations
import re
from .findings import Finding
from ..normalize import analyze, findings as norm_findings
from ..normalize.detectors.identifiers import RE_GIT_SHA_CTX as COMMIT_REF
from ..okf.authorities import load_gazetteer, load_type_schemas
from ..okf.document import OKFDocument
from ..okf.links import parse_links, is_internal, resolve

CITATION_REF = re.compile(r"\[(\d+)\]")
SCHEMA_FIELD = re.compile(r"^\|\s*`?(\w+)`?\s*\|", re.M)
MACHINE = ("api:", "local:")

RECOMMENDED_TYPES = {
    "concept", "academic_paper", "runbook", "decision", "learning_note",
    "skill", "review", "question", "architectural_alert", "breaking_change",
    "collection_specification", "schema_specification", "field_profile",
    "message_channel", "feature_flag", "infrastructure_specification",
    "personal_reflection", "reference",
    "authority_record", "community_summary",
    # tipagem epistemológica explícita (v0.21, EPIC-11): a NATUREZA do
    # conteúdo é tipo de primeira classe — hipótese não vira fato sem
    # transição registrada (SUPERSEDE), nunca por edição silenciosa
    "fact", "claim", "hypothesis", "observation", "opinion"}

def check(docs, reader, git, mode: str = "write") -> list[Finding]:
    out: list[Finding] = []
    gaz = load_gazetteer(reader) if docs else None
    schemas = load_type_schemas(reader) if docs else {}
    for d in docs:
        x = d.meta.model_dump()
        via = str(x.get("generated_via", ""))

        if x.get("privacy") not in ("local_only", "api_allowed"):
            out.append(Finding("error", "policy.privacy_required", d.rel_path,
                               "toda página escrita precisa de privacy: "
                               "local_only|api_allowed"))

        # ---- normalização (v0.8 §4.3): grafia, checksums, PII, temporal ----
        report = analyze(d.body, gaz=gaz)
        machine = via.startswith(MACHINE)
        for sev, rule, path, msg in norm_findings(d.rel_path, report,
                                                  machine=machine):
            out.append(Finding(sev, rule, path, msg))
        # PII detectada com checksum válido ⇒ privacidade obrigatoriamente local
        if report.sensitive and x.get("privacy") == "api_allowed":
            out.append(Finding("error", "policy.pii_requires_local", d.rel_path,
                               "documento pessoal (CPF/CNPJ/IBAN) detectado; "
                               "privacy deve ser local_only"))
        # bi-temporalidade coerente (§6)
        va, ia = x.get("valid_at"), x.get("invalid_at")
        if va and ia and str(ia) <= str(va):
            out.append(Finding("error", "policy.temporal_order", d.rel_path,
                               "invalid_at deve ser posterior a valid_at"))

        # proveniência: só páginas geradas por MÁQUINA exigem source_sha256
        # (promoções humanas usam generated_via: human:* e campo source)
        if via.startswith(MACHINE) and not x.get("source_sha256"):
            out.append(Finding("error", "policy.source_sha_required", d.rel_path,
                               "página gerada por máquina sem source_sha256"))

        # citações: POLÍTICA LOCAL (SPEC trata # Citations como SHOULD)
        if via.startswith("api:"):
            refs = {int(n) for n in CITATION_REF.findall(d.body)}
            m = re.search(r"^#{1,2}\s*Citations\s*$", d.body, re.M)
            listed = {int(n) for n in CITATION_REF.findall(
                d.body[m.end():])} if m else set()
            if not m or not listed:
                out.append(Finding("error", "policy.citation_required", d.rel_path,
                                   "conteúdo de API sem seção # Citations"))
            elif refs and not refs <= listed:
                out.append(Finding("error", "policy.citation_invalid", d.rel_path,
                                   f"refs {sorted(refs - listed)} sem entrada "
                                   "em Citations"))

        for sha in COMMIT_REF.findall(d.body + " " + str(x.get("stale_as_of", ""))):
            if not git.has_commit(sha):
                out.append(Finding("error", "policy.bad_commit_ref", d.rel_path,
                                   f"commit inexistente: {sha}"))

        if reader.exists(d.rel_path):
            old = reader.load(d.rel_path)
            lost = set(SCHEMA_FIELD.findall(_section(old.body, "Schema"))) \
                 - set(SCHEMA_FIELD.findall(_section(d.body, "Schema")))
            if lost and not x.get("supersedes"):
                out.append(Finding("error", "policy.schema_shrink", d.rel_path,
                                   f"campos removidos sem supersedes: {sorted(lost)}"))
            lost_keys = set(old.meta.model_dump(exclude_none=True)) \
                      - set(d.meta.model_dump(exclude_none=True)) - {"timestamp"}
            if lost_keys:
                out.append(Finding("warn", "policy.metadata_shrink", d.rel_path,
                                   f"frontmatter perdeu chaves: {sorted(lost_keys)}"))

        if d.meta.type not in RECOMMENDED_TYPES:
            out.append(Finding("info", "policy.unknown_type", d.rel_path,
                               f"type fora da taxonomia recomendada: {d.meta.type}"))

        # schemas por tipo (DTT lite, v0.10): collection_specification com
        # `applies_to` declara campos obrigatórios — contrato opt-in curado
        # no próprio bundle
        schema = schemas.get(d.meta.type)
        if schema:
            present = set(d.meta.model_dump(exclude_none=True))
            missing = [f for f in schema["required_fields"] if f not in present]
            if missing:
                out.append(Finding("error", "policy.schema_required_field",
                                   d.rel_path,
                                   f"type '{d.meta.type}' exige campos "
                                   f"{missing} (schema: {schema['page']})"))

        if mode == "release":
            for link in parse_links(d.body):
                if is_internal(link.target) and \
                   not reader.exists(resolve(link.target, d.rel_path)):
                    out.append(Finding("error", "policy.release_broken_link",
                                       d.rel_path,
                                       f"release com link quebrado: {link.target}"))
    return out

CONTRADICTION_IDS = ("doi", "isbn", "issn", "arxiv")


def check_corpus(docs, reader) -> list[Finding]:
    """Detecção AGM-inspirada de CONTRADIÇÃO candidata (v0.10, só no lint):
    o mesmo identificador forte em 2+ páginas sem relação de sucessão
    (superseded_by/supersedes dentro do grupo, ou invalid_at resolvendo o
    conflito no tempo) sugere duas versões da mesma verdade convivendo.
    A resolução NUNCA é automática — o finding nomeia a página mais
    ENTRINCHEIRADA (humana > máquina; mais desfechos úteis viriam depois)
    e o humano/SUPERSEDE decide. Warn, nunca error."""
    by_id: dict[str, list] = {}
    gaz = load_gazetteer(reader)
    for d in docs:
        x = d.meta.model_dump(exclude_none=True)
        for m in analyze(d.body, gaz=gaz).matches:
            if m.kind == "identifier" and m.subkind in CONTRADICTION_IDS \
                    and m.valid is not False:
                by_id.setdefault(m.canonical, []).append((d, x))
    out: list[Finding] = []
    for ident, group in by_id.items():
        pages = {d.rel_path for d, _ in group}
        if len(pages) < 2:
            continue
        resolved = any(x.get("superseded_by") in pages
                       or x.get("supersedes") in pages
                       or x.get("invalid_at")
                       for _, x in group)
        if resolved:
            continue
        entrenched = sorted(
            group, key=lambda item: (
                not str(item[1].get("generated_via", "")).startswith("human:"),
                item[0].rel_path))[0][0]
        out.append(Finding(
            "warn", "policy.contradiction_candidate", entrenched.rel_path,
            f"identificador {ident} em {len(pages)} páginas sem sucessão: "
            f"{sorted(pages)} — mais entrincheirada: {entrenched.rel_path}; "
            "resolva com supersede/invalid_at ou funda as páginas",
            meta={"identifier": ident, "pages": sorted(pages)}))
    return out


def _section(body: str, name: str) -> str:
    m = re.search(rf"^#{{1,3}}\s*{name}\s*$(.*?)(?=^#{{1,3}}\s|\Z)",
                  body, re.M | re.S)
    return m.group(1) if m else ""
