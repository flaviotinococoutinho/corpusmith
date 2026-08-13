from __future__ import annotations
from .model import Match, NormReport, PRIORITY, REWRITE_KINDS, SENSITIVE_IDS
from .masking import protected_spans, is_protected
from .gazetteer import Gazetteer
from .grammar import fix_typography
from .detectors import dates, quantities, identifiers, standards, geo

def analyze(text: str, *, locale: str = "pt-BR",
            gaz: Gazetteer | None = None) -> NormReport:
    """Passada de anotação (não muta o texto). Ordem: detectar tudo →
    descartar o que cair em região protegida → resolver sobreposições
    (mais longo vence; empate → PRIORITY)."""
    gaz = gaz or Gazetteer.load()
    spans = protected_spans(text)
    raw: list[Match] = []
    for det in (identifiers.detect, standards.detect,
                lambda t: dates.detect(t, locale),
                lambda t: quantities.detect(t, locale), geo.detect, gaz.detect):
        raw.extend(det(text))
    raw = [m for m in raw if not is_protected(spans, m.start, m.end)]
    raw.sort(key=lambda m: (m.start, -(m.end - m.start), -PRIORITY[m.kind]))
    chosen: list[Match] = []
    last_end = -1
    for m in raw:
        if m.start >= last_end:
            chosen.append(m)
            last_end = m.end
    rep = NormReport(matches=chosen)
    rep.sensitive = any(m.subkind in SENSITIVE_IDS and m.valid
                        for m in chosen if m.kind == "identifier")
    return rep

def _rewritable(m: Match) -> bool:
    """Precisão > recall (§1.6): só matches 'extracted' com checksum não
    inválido entram na reescrita — 'inferred' (ex.: semver) fica como anexo,
    honrando a regra 'anota semântica, reescreve só grafia certa'."""
    return (m.kind in REWRITE_KINDS and m.confidence == "extracted"
            and m.valid is not False)

def rewrite(text: str, report: NormReport) -> str:
    """Passada de reescrita — SÓ páginas generated_via api:*|local:* (§1.2).
    Substitui de trás para a frente (offsets estáveis); depois tipografia.
    Idempotente por construção: canônico casa a si mesmo no gazetteer."""
    edits = [m for m in report.matches
             if _rewritable(m) and m.canonical != m.surface]
    for m in sorted(edits, key=lambda m: -m.start):
        text = text[:m.start] + m.canonical + text[m.end:]
    spans = protected_spans(text)               # tipografia também respeita máscara
    out, cur = [], 0
    for s, e in sorted(set(spans)):
        if s > cur:
            out.append(fix_typography(text[cur:s]))
        out.append(text[max(s, cur):e])
        cur = max(cur, e)
    out.append(fix_typography(text[cur:]))
    return "".join(out)

def findings(rel_path: str, report: NormReport, *, machine: bool) -> list[tuple]:
    """Sinais para o Harness (local_policy converte em Finding, §4.3).
    Formato: (severity, rule, path, message)."""
    out: list[tuple] = []
    for m in report.matches:
        if m.kind == "identifier" and m.valid is False:
            out.append(("error" if machine else "warn", "policy.identifier_invalid",
                        rel_path, f"{m.subkind} com dígito verificador inválido: "
                                  f"{m.surface} (possível alucinação)"))
        elif machine and _rewritable(m) and m.canonical != m.surface:
            out.append(("error", "policy.term_noncanonical", rel_path,
                        f"forma não-canônica residual: '{m.surface}' → "
                        f"'{m.canonical}' (rewrite não foi aplicado?)"))
        elif not machine and m.kind == "entity" and m.canonical != m.surface:
            out.append(("info", "policy.term_noncanonical", rel_path,
                        f"grafia curada disponível: '{m.surface}' → '{m.canonical}'"))
    return out
