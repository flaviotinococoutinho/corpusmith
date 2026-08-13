"""Gestão do reference.db (v0.22) — referência determinística do mundo.

Separação da avaliação funcional: "memória SUA → bundle (Git, OKF);
referência DO MUNDO → relacional (reference.db)". Nomes próprios, leis,
equações, axiomas e citações célebres não são conhecimento pessoal — são
dados de conferência que alimentam a normalização (precedência
authority_record > ref_* > seeds) e o verificador de citação
mal-atribuída (anti-alucinação, irmão dos check-digits da v0.8).
"""
from __future__ import annotations
import json
import re
from .base import UseCase
from ..okf.authorities import invalidate_cache
from ..runtime.db import connect
from ..settings import Settings

FACT_KINDS = ("law", "equation", "axiom", "logic_rule")

SEED_REFERENCE = {
    "terms": [
        {"canonical": "Edsger W. Dijkstra", "kind": "person",
         "aliases": ["dijkstra", "e. w. dijkstra"]},
        {"canonical": "Donald Knuth", "kind": "person",
         "aliases": ["knuth", "d. e. knuth"]},
        {"canonical": "Claude Shannon", "kind": "person",
         "aliases": ["shannon"]},
        {"canonical": "Alan Turing", "kind": "person",
         "aliases": ["turing"]},
    ],
    "quotations": [
        {"quote": "Program testing can be used to show the presence of "
                  "bugs, but never to show their absence!",
         "author": "Edsger W. Dijkstra",
         "source": "Notes on Structured Programming (1970)"},
        {"quote": "Premature optimization is the root of all evil.",
         "author": "Donald Knuth",
         "source": "Structured Programming with go to Statements (1974)"},
        {"quote": "Talk is cheap. Show me the code.",
         "author": "Linus Torvalds", "source": "LKML (2000)"},
    ],
    "facts": [
        {"kind": "law", "name": "Lei de Little",
         "statement": "L = λ·W", "domain": "teoria de filas"},
        {"kind": "law", "name": "Teorema CAP",
         "statement": "Consistência, disponibilidade e tolerância a "
                      "partição: escolha duas sob partição.",
         "domain": "sistemas distribuídos"},
        {"kind": "equation", "name": "Entropia de Shannon",
         "statement": "H(X) = −Σ p(x)·log₂ p(x)",
         "domain": "teoria da informação"},
        {"kind": "logic_rule", "name": "Modus ponens",
         "statement": "P; P→Q ⊢ Q", "domain": "lógica"},
    ],
}


def _norm(text: str) -> str:
    """Normalização de citação p/ matching: minúsculas, só alfanumérico."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _same_author(claimed: str, author: str) -> bool:
    """Comparação tolerante a iniciais: sobrenome tem de bater; os
    demais tokens do alegado devem ser prefixo de algum token do autor
    ("E. W. Dijkstra" ≡ "Edsger W. Dijkstra"; "Linus" ≢ "Dijkstra")."""
    c, a = _norm(claimed).split(), _norm(author).split()
    if not c or not a or c[-1] != a[-1]:
        return False
    return all(any(token.startswith(part) for token in a) for part in c[:-1])


def _ref(settings: Settings):
    return connect(settings.app_support / "reference.db")


def reference_stats(settings: Settings) -> dict:
    ref = _ref(settings)
    stats = {t: ref.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
             for t in ("ref_terms", "ref_quotations", "ref_facts")}
    facts = [dict(r) for r in ref.execute(
        "SELECT kind, name, statement, domain FROM ref_facts "
        "ORDER BY kind, name LIMIT 50")]
    ref.close()
    return {**stats, "facts": facts}


def seed_reference(settings: Settings) -> None:
    """Seeds idempotentes — nunca sobrescrevem dado importado."""
    ImportReferenceData(settings, SEED_REFERENCE, replace=False).execute()


def check_quotation(settings: Settings, text: str,
                    claimed_author: str | None = None) -> dict:
    """Cita alguém? Confere contra a base. Match por substring
    normalizada (determinístico); se o autor alegado divergir do
    registrado, aponta a má-atribuição com a fonte correta."""
    norm_text = _norm(text)
    ref = _ref(settings)
    matches = []
    for r in ref.execute("SELECT quote, author, source, norm "
                         "FROM ref_quotations"):
        if r["norm"] in norm_text:
            misattributed = bool(
                claimed_author
                and not _same_author(claimed_author, r["author"]))
            matches.append({"quote": r["quote"], "author": r["author"],
                            "source": r["source"],
                            "misattributed": misattributed})
    ref.close()
    return {"matches": matches,
            "misattributions": [m for m in matches if m["misattributed"]]}


class ImportReferenceData(UseCase):
    """Upsert de terms/quotations/facts. `replace=False` (seeds) nunca
    toca linha existente; `replace=True` (import do usuário) atualiza.
    Sempre invalida o cache do gazetteer (o import não passa pelo Git)."""

    def __init__(self, settings: Settings, payload: dict, *,
                 replace: bool = True, notify=None):
        self._settings = settings
        self._payload = payload or {}
        self._replace = replace
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        conflict = "DO UPDATE SET" if self._replace else "DO NOTHING --"
        ref = _ref(self._settings)
        counts = {"terms": 0, "quotations": 0, "facts": 0}
        for t in self._payload.get("terms", []):
            if not t.get("canonical"):
                raise ValueError("term sem canonical")
            ref.execute(
                f"INSERT INTO ref_terms(canonical, kind, aliases, source) "
                f"VALUES (?,?,?,?) ON CONFLICT(canonical) {conflict} "
                f"kind=excluded.kind, aliases=excluded.aliases",
                (t["canonical"], t.get("kind", "entity"),
                 json.dumps(t.get("aliases", [])), t.get("source")))
            counts["terms"] += 1
        for q in self._payload.get("quotations", []):
            if not q.get("quote") or not q.get("author"):
                raise ValueError("quotation exige quote e author")
            ref.execute(
                f"INSERT INTO ref_quotations(quote, author, source, norm) "
                f"VALUES (?,?,?,?) ON CONFLICT(norm) {conflict} "
                f"author=excluded.author, source=excluded.source",
                (q["quote"], q["author"], q.get("source"),
                 _norm(q["quote"])))
            counts["quotations"] += 1
        for f in self._payload.get("facts", []):
            if f.get("kind") not in FACT_KINDS:
                raise ValueError(f"fact.kind ∈ {FACT_KINDS}")
            ref.execute(
                f"INSERT INTO ref_facts(kind, name, statement, domain) "
                f"VALUES (?,?,?,?) ON CONFLICT(kind, name) {conflict} "
                f"statement=excluded.statement, domain=excluded.domain",
                (f["kind"], f["name"], f["statement"], f.get("domain")))
            counts["facts"] += 1
        ref.commit()
        ref.close()
        invalidate_cache()          # gazetteer relê a referência nova
        self._notify("reference.imported", counts)
        return counts
