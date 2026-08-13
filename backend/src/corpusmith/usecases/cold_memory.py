"""Base fria (v0.12) — esquecer é COMPACTAR, nunca destruir.

Política de camadas por tempo de memória:

    T0 working (events)   · efêmera
    T1 episódica (log.md) · append-only, barata para sempre
    T2 QUENTE  (bundle)   · P(recall) ACT-R acima do limiar
    T3 FRIA    (cold.db)  · digest indexável + corpo zlib (MDL)
    T4 Git                · backstop imutável de tudo

Demoção T2→T3 (`FreezeMemory`) só passa pela CADEIA DE GATES:
  1. tipo não-protegido (authority_record/collection_specification ficam);
  2. sem dependentes (TMS: quem cita a página vetaria o freeze);
  3. overlay ≠ preferred (páginas que o uso consagrou não congelam);
  4. P(recall) = 1/(1+e^((τ−B)/s)) abaixo do corte — o CRITÉRIO VALIDADO:
     o próprio modelo cognitivo (ACT-R) prevê que a memória não seria
     recuperada;
  5. ociosidade mínima (min_idle_days sem uso).
`force=True` (gesto humano explícito) dispensa 3–5, nunca 1–2.

Compactação MDL (Rissanen 1978): o DIGEST (título, headings, entidades,
ids fortes — o "modelo") fica descomprimido e indexável em FTS; o corpo
integral (o "resíduo dado o modelo") vai em zlib nível 9. O recall de
fallback busca no digest; a reidratação (`RecycleMemory`) restaura a
página byte a byte no bundle, pelo writer normal (lock+log+commit).
"""
from __future__ import annotations
import json
import re
import time
import zlib
from .base import UseCase
from .mark_stale import dependents_of
from ..kernel.activation import base_level_activation, retrieval_probability
from ..normalize import analyze
from ..okf.authorities import load_gazetteer
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..retrieval.fts import fts_terms, rebuild_index
from ..runtime.db import connect
from ..settings import Settings

PROTECTED_TYPES = {"authority_record", "collection_specification"}
STRONG_IDS = ("doi", "isbn", "issn", "arxiv")


class FreezeVeto(ValueError):
    """Gate reprovou o esquecimento — a razão explica qual."""


# ------------------------------------------------------------ consultas puras
def cold_search(settings: Settings, query: str, *, limit: int = 5) -> list[dict]:
    """Recall de fallback: FTS sobre os digests da base fria."""
    cold = connect(settings.app_support / "cold.db")
    try:
        rows = cold.execute(
            "SELECT c.page, c.frozen_at, c.recycles, bm25(cold_fts) score "
            "FROM cold_fts JOIN cold_memories c ON c.rowid = cold_fts.rowid "
            "WHERE cold_fts MATCH ? ORDER BY score LIMIT ?",
            (fts_terms(query), limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        cold.close()


def cold_by_strong_id(settings: Settings, identifiers: set[str]) -> str | None:
    """Reconciliação com a base fria: id forte casado ⇒ página a reciclar."""
    if not identifiers:
        return None
    cold = connect(settings.app_support / "cold.db")
    try:
        for identifier in identifiers:
            row = cold.execute(
                "SELECT page FROM cold_memories WHERE strong_ids LIKE ?",
                (f"%{identifier}%",)).fetchone()
            if row:
                return row["page"]
        return None
    finally:
        cold.close()


def cold_stats(settings: Settings) -> dict:
    cold = connect(settings.app_support / "cold.db")
    row = cold.execute(
        "SELECT COUNT(*) n, COALESCE(SUM(body_bytes),0) raw, "
        "COALESCE(SUM(LENGTH(body_z)),0) packed, "
        "COALESCE(SUM(recycles),0) recycles FROM cold_memories").fetchone()
    entries = [dict(r) for r in cold.execute(
        "SELECT page, frozen_at, recall_p, recycles, body_bytes, "
        "LENGTH(body_z) packed FROM cold_memories "
        "ORDER BY frozen_at DESC LIMIT 50")]
    cold.close()
    ratio = (1 - row["packed"] / row["raw"]) if row["raw"] else 0.0
    return {"count": row["n"], "raw_bytes": row["raw"],
            "packed_bytes": row["packed"],
            "compression_saved": round(100 * ratio),
            "recycles": row["recycles"], "entries": entries}


# ------------------------------------------------------------------ freeze
class FreezeMemory(UseCase):
    def __init__(self, settings: Settings, page_path: str, *,
                 force: bool = False, reason: str = ""):
        self._settings = settings
        self._page_path = page_path
        self._force = force
        self._reason = reason

    def execute(self) -> dict:
        writer = BundleWriter(self._settings.path("knowledge"))
        document = writer.reader.load(self._page_path)
        activation, recall_p = self._validate(document)
        digest, strong_ids = self._digest(document)
        raw = document.dumps()

        cold = connect(self._settings.app_support / "cold.db")
        cold.execute(
            "INSERT OR REPLACE INTO cold_memories(page, digest, strong_ids, "
            "body_z, body_bytes, meta_json, frozen_at, activation, recall_p, "
            "reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (document.rel_path, digest, " ".join(sorted(strong_ids)),
             zlib.compress(raw.encode(), 9), len(raw.encode()),
             json.dumps(document.meta.model_dump(exclude_none=True,
                                                 mode="json")),
             time.time(), activation, recall_p,
             self._reason or ("forçado" if self._force
                              else "P(recall) abaixo do limiar")))
        cold.commit()
        cold.close()
        removed = writer.remove(
            document.rel_path, log_kind="Freeze",
            log_message=f"congelada na base fria: {document.rel_path}",
            commit_message=f"freeze: {document.rel_path}")
        # registrar o commit do freeze na entrada (auditoria completa)
        cold = connect(self._settings.app_support / "cold.db")
        cold.execute("UPDATE cold_memories SET frozen_commit=? WHERE page=?",
                     (removed["commit"], document.rel_path))
        cold.commit()
        cold.close()
        rebuild_index(self._settings)
        return {"page": document.rel_path, "frozen": True,
                "activation": activation, "recall_p": recall_p,
                "commit": removed["commit"]}

    # -------------------------------------------------- cadeia de gates
    def _validate(self, document: OKFDocument) -> tuple[float, float]:
        if document.meta.type in PROTECTED_TYPES:
            raise FreezeVeto(f"tipo protegido nunca congela: "
                             f"{document.meta.type}")
        dependents = dependents_of(self._settings, document.rel_path)
        if dependents:
            raise FreezeVeto(f"{len(dependents)} página(s) dependem dela "
                             f"(TMS): {dependents[:3]}")
        activation, recall_p, idle_days, overlay = self._signals(document)
        if self._force:
            return activation, recall_p
        if overlay == "preferred":
            raise FreezeVeto("overlay preferred: o uso consagrou esta página")
        limit = float(self._settings.get("memory.max_recall_probability", 0.05))
        if recall_p > limit:
            raise FreezeVeto(f"P(recall)={recall_p:.3f} > {limit} — o ACT-R "
                             "prevê que ela ainda seria recuperada")
        min_idle = float(self._settings.get("memory.min_idle_days", 90))
        if idle_days < min_idle:
            raise FreezeVeto(f"usada há {idle_days:.0f}d "
                             f"(mínimo de ócio: {min_idle:.0f}d)")
        return activation, recall_p

    def _signals(self, document) -> tuple[float, float, float, str | None]:
        now = time.time()
        rt = connect(self._settings.app_support / "runtime.db")
        heat = rt.execute("SELECT reads, last_seen, first_seen FROM page_heat "
                          "WHERE path=?", (document.rel_path,)).fetchone()
        rt.close()
        idx = connect(self._settings.app_support / "index.db")
        overlay_row = idx.execute("SELECT status FROM page_overlay "
                                  "WHERE page=?", (document.rel_path,)).fetchone()
        idx.close()
        if heat and heat["last_seen"]:
            idle_days = (now - heat["last_seen"]) / 86_400
            age_days = (now - (heat["first_seen"] or heat["last_seen"])) / 86_400
            activation = base_level_activation(heat["reads"] or 0, age_days)
        else:                                   # nunca usada ⇒ B = −inf
            idle_days = float("inf")
            activation = float("-inf")
        recall_p = retrieval_probability(
            activation,
            tau=float(self._settings.get("memory.freeze_tau", 0.0)),
            noise=float(self._settings.get("memory.activation_noise", 0.4)))
        return activation, recall_p, idle_days, \
            overlay_row["status"] if overlay_row else None

    def _digest(self, document: OKFDocument) -> tuple[str, set[str]]:
        gaz = load_gazetteer(
            BundleWriter(self._settings.path("knowledge")).reader)
        report = analyze(document.body, gaz=gaz)
        strong = {m.canonical for m in report.matches
                  if m.kind == "identifier" and m.subkind in STRONG_IDS
                  and m.valid is not False}
        headings = " · ".join(
            re.findall(r"^#{1,3}\s+(.+)$", document.body, re.M)[:12])
        parts = [document.meta.title or "", document.meta.description or "",
                 headings, " ".join(report.entities_frontmatter(limit=24)),
                 " ".join(sorted(strong))]
        return "\n".join(p for p in parts if p), strong


# ----------------------------------------------------------------- recycle
class RecycleMemory(UseCase):
    """T3→T2: reidrata uma memória fria de volta ao bundle, byte a byte,
    pelo writer normal (Harness + log `Recall` + commit). A entrada fria
    sai da base; o contador de reciclagens fica no frontmatter
    (`recycled: n`) — memória reciclada carrega a própria história."""

    def __init__(self, settings: Settings, page_path: str):
        self._settings = settings
        self._page_path = page_path

    def execute(self) -> dict:
        cold = connect(self._settings.app_support / "cold.db")
        row = cold.execute("SELECT * FROM cold_memories WHERE page=?",
                           (self._page_path,)).fetchone()
        if row is None:
            cold.close()
            raise KeyError(f"não está na base fria: {self._page_path}")
        # guarda quente×frio (v0.14): se a página voltou ao bundle por outra
        # via (re-promoção no mesmo slug), reidratar SOBRESCREVERIA conteúdo
        # mais novo com o antigo — purga a entrada obsoleta e recusa
        live = self._settings.path("knowledge") / "bundle" / self._page_path
        if live.is_file():
            cold.execute("DELETE FROM cold_memories WHERE page=?",
                         (self._page_path,))
            cold.commit()
            cold.close()
            raise KeyError(f"{self._page_path} já está quente no bundle — "
                           "entrada fria obsoleta foi removida")
        raw = zlib.decompress(row["body_z"]).decode()
        document = OKFDocument.loads(self._page_path, raw)
        meta = document.meta.model_dump(exclude_none=True)
        meta["recycled"] = int(row["recycles"]) + 1
        thawed = OKFDocument(rel_path=self._page_path, body=document.body,
                             meta=OKFFrontMatter(**meta))
        result = BundleWriter(self._settings.path("knowledge")).write(
            [thawed], log_kind="Recall",
            log_message=f"reciclada da base fria: {self._page_path}",
            commit_message=f"recycle: {self._page_path}")
        cold.execute("DELETE FROM cold_memories WHERE page=?",
                     (self._page_path,))
        cold.commit()
        cold.close()
        # a memória volta com a chama baixa, mas viva (heat de recall)
        rt = connect(self._settings.app_support / "runtime.db")
        now = time.time()
        rt.execute("INSERT INTO page_heat(path, reads, last_seen, first_seen) "
                   "VALUES (?,1,?,?) ON CONFLICT(path) DO UPDATE SET "
                   "reads = reads + 1, last_seen = ?",
                   (self._page_path, now, now, now))
        rt.commit()
        rt.close()
        rebuild_index(self._settings)
        return {"page": self._page_path, "recycled": True,
                "times": meta["recycled"], "commit": result["commit"]}
