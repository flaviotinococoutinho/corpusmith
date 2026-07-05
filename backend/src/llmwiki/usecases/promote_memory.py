"""PromoteToMemory — o botão diferenciado como use case (v0.9).

Página HUMANA: não passa pelo template de máquina de propósito — prosa
humana não é reescrita (v0.8 §1.2); o Harness aplica só a política de
página humana (privacy obrigatório, findings informativos de grafia).
"""
from __future__ import annotations
import re
import unicodedata
from datetime import datetime, timezone
from .base import UseCase
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..settings import Settings

KIND_MAP = {   # botão "Promover para memória" → destino OKF
    "semantic": ("concept",             "concepts"),
    "decision": ("decision",            "decisions"),
    "runbook":  ("runbook",             "runbooks"),
    "skill":    ("skill",               "career/skills"),
    "question": ("question",            "questions"),
    "alert":    ("architectural_alert", "alerts"),
}


class UnknownPromotionKind(ValueError):
    pass


class PromoteToMemory(UseCase):
    def __init__(self, settings: Settings, *, kind: str, title: str,
                 content: str, source: str = "chat",
                 privacy: str = "local_only", description: str | None = None,
                 tags: list[str] | None = None):
        if kind not in KIND_MAP:
            raise UnknownPromotionKind(f"kind inválido: {kind}")
        self._settings = settings
        self._kind = kind
        self._title = title
        self._content = content.strip()
        self._source = source
        self._privacy = privacy
        self._description = description
        self._tags = tags or []

    def execute(self) -> dict:
        okf_type, folder = KIND_MAP[self._kind]
        slug = self._slug(self._title)
        document = OKFDocument(
            rel_path=f"{folder}/{slug}.md",
            body=f"# {self._title}\n\n{self._content}\n",
            meta=OKFFrontMatter(
                type=okf_type, title=self._title,
                description=self._description, tags=self._tags,
                timestamp=datetime.now(timezone.utc),
                **{"privacy": self._privacy,
                   "generated_via": "human:promote",
                   "confidence": "human_approved",
                   "source": self._source}))
        result = BundleWriter(self._settings.path("knowledge")).write(
            [document], log_kind="Creation",
            log_message=f"promovido de {self._source}: {self._title}",
            commit_message=f"promote({self._kind}): {slug}")
        return {**result, "kind": self._kind}

    @staticmethod
    def _slug(title: str) -> str:
        folded = unicodedata.normalize("NFKD", title).encode(
            "ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:60]
