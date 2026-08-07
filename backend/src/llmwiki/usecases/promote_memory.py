"""PromoteToMemory — o botão diferenciado como use case (v0.9).

Página HUMANA: não passa pelo template de máquina de propósito — prosa
humana não é reescrita (v0.8 §1.2); o Harness aplica só a política de
página humana (privacy obrigatório, findings informativos de grafia).

F3-PR1 (RFC-003): o promote deixou de ser o caminho destrutivo dominante.
Medido antes: dois promotes do mesmo título e o segundo APAGAVA a página do
primeiro, com o log registrando "Creation". Agora o candidato passa pela
MESMA escada de reconciliação do fluxo de máquina (RFC-002) e qualquer
colisão — de caminho ou de similaridade — vira `op="COLLISION"` com três
saídas humanas legítimas, **sem escrever nada**. A heurística informa o
gesto; quem escreve continua sendo a pessoa.

`analyze()` aqui é DETECÇÃO, não reescrita: o que a v0.8 §1.2 proíbe é o
sanduíche que reescreve a grafia da prosa, não a leitura dela — sem o
report, a escada não teria entidades nem identificadores para comparar.
"""
from __future__ import annotations
import re
import unicodedata
from datetime import datetime, timezone
from .base import UseCase
from ..normalize import analyze
from ..okf.authorities import load_gazetteer
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..retrieval.fts import rebuild_index
from ..settings import Settings

KIND_MAP = {   # botão "Promover para memória" → destino OKF
    "semantic": ("concept",             "concepts"),
    "decision": ("decision",            "decisions"),
    "runbook":  ("runbook",             "runbooks"),
    "skill":    ("skill",               "career/skills"),
    "question": ("question",            "questions"),
    "alert":    ("architectural_alert", "alerts"),
}

RESOLUTIONS = ("update", "new_slug")   # "cancelar" é do cliente: nada a persistir


class UnknownPromotionKind(ValueError):
    pass


class PromoteToMemory(UseCase):
    def __init__(self, settings: Settings, *, kind: str, title: str,
                 content: str, source: str = "chat",
                 privacy: str = "local_only", description: str | None = None,
                 tags: list[str] | None = None,
                 resolution: str | None = None, target: str | None = None):
        if kind not in KIND_MAP:
            raise UnknownPromotionKind(f"kind inválido: {kind}")
        if resolution is not None and resolution not in RESOLUTIONS:
            raise ValueError(f"resolution inválida: {resolution} — "
                             f"aceitas: {RESOLUTIONS}")
        if resolution == "update" and not target:
            raise ValueError("resolution=update exige target — o alvo veio "
                             "na resposta COLLISION anterior")
        self._settings = settings
        self._kind = kind
        self._title = title
        self._content = content.strip()
        self._source = source
        self._privacy = privacy
        self._description = description
        self._tags = tags or []
        self._resolution = resolution
        self._target = target

    def execute(self) -> dict:
        okf_type, folder = KIND_MAP[self._kind]
        rel_path = f"{folder}/{self._slug(self._title)}.md"
        writer = BundleWriter(self._settings.path("knowledge"))

        if self._resolution is None:
            colisao = self._detect_collision(writer, rel_path)
            if colisao:
                return colisao          # NADA foi escrito — decisão é humana
        elif self._resolution == "update":
            return self._resolve_update(writer)
        else:                           # new_slug
            rel_path = self._free_slug(writer, folder)

        result = writer.write(
            [self._document(rel_path, okf_type)], log_kind="Creation",
            log_message=f"promovido de {self._source}: {self._title}",
            commit_message=f"promote({self._kind}): {rel_path}")
        # incremental (v0.14): a memória promovida fica respondível JÁ —
        # antes ela só entrava no índice no próximo compile/okf index
        rebuild_index(self._settings)
        return {**result, "op": "ADD", "kind": self._kind}

    # ------------------------------------------------------------ colisão
    def _detect_collision(self, writer: BundleWriter,
                          rel_path: str) -> dict | None:
        """A escada do RFC-002, agora informando o gesto humano.

        Duas portas, porque a escada estruturalmente não vê uma delas: o
        caminho idêntico é checado no FILESYSTEM (`ReconcileCandidate`
        exclui a própria `rel_path` dos degraus), e a similaridade com
        OUTRO caminho vem dos degraus normais."""
        if writer.reader.exists(rel_path):
            return {"op": "COLLISION", "target": rel_path, "score": 1.0,
                    "reason": "já existe uma página neste caminho — o "
                              "título slugifica para um endereço ocupado",
                    "options": list(RESOLUTIONS), "kind": self._kind}
        from .reconcile_candidate import ReconcileCandidate
        report = analyze(self._content, gaz=load_gazetteer(writer.reader))
        decision = ReconcileCandidate(
            self._settings,
            self._document(rel_path, KIND_MAP[self._kind][0]),
            report).execute()
        if decision["op"] in ("UPDATE", "RECYCLE", "NOOP") \
                and decision.get("target"):
            return {"op": "COLLISION", "target": decision["target"],
                    "score": decision["score"], "reason": decision["reason"],
                    "options": list(RESOLUTIONS), "kind": self._kind}
        return None

    def _resolve_update(self, writer: BundleWriter) -> dict:
        """Saída humana 1: escrever SOBRE o alvo, nomeado e escolhido.

        Substituir o corpo continua sendo substituir — a diferença é que
        agora é um gesto explícito com a residente à vista. O frontmatter
        FUNDE (`merge_meta`, a mesma regra do MergePages): o que o humano
        curou na residente não evapora junto com o corpo."""
        from ..kernel.curation import merge_meta, mergeable_source_meta
        if not writer.reader.exists(self._target):
            # alvo congelado entre a COLLISION e a escolha? Reidrata — o
            # fluxo de máquina já faz o mesmo no op RECYCLE
            from .cold_memory import RecycleMemory
            RecycleMemory(self._settings, self._target).execute()
        residente = writer.reader.load(self._target)
        novo = self._document(self._target, residente.meta.type)
        fundido = merge_meta(
            novo.meta.model_dump(exclude_none=True),
            mergeable_source_meta(
                residente.meta.model_dump(exclude_none=True)))
        document = OKFDocument(rel_path=self._target, body=novo.body,
                               meta=OKFFrontMatter(**fundido))
        result = writer.write(
            [document], log_kind="Update",
            log_message=f"promovido SOBRE {self._target} "
                        f"(colisão resolvida): {self._title}",
            commit_message=f"promote-update({self._kind}): {self._target}")
        rebuild_index(self._settings)
        return {**result, "op": "UPDATE", "kind": self._kind}

    def _free_slug(self, writer: BundleWriter, folder: str) -> str:
        """Saída humana 2: sufixo determinístico, como o `raw/` já faz.

        Duas páginas vivas para conceitos que o humano DECLAROU distintos —
        e, se ele errou, consolidar depois é reversível; fusão errada não."""
        base = self._slug(self._title)
        n = 2
        while writer.reader.exists(f"{folder}/{base}-{n}.md"):
            n += 1
        return f"{folder}/{base}-{n}.md"

    # ----------------------------------------------------------- documento
    def _document(self, rel_path: str, okf_type: str) -> OKFDocument:
        return OKFDocument(
            rel_path=rel_path,
            body=f"# {self._title}\n\n{self._content}\n",
            meta=OKFFrontMatter(
                type=okf_type, title=self._title,
                description=self._description, tags=self._tags,
                timestamp=datetime.now(timezone.utc),
                **{"privacy": self._privacy,
                   "generated_via": "human:promote",
                   "confidence": "human_approved",
                   "source": self._source}))

    @staticmethod
    def _slug(title: str) -> str:
        folded = unicodedata.normalize("NFKD", title).encode(
            "ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:60]
