from __future__ import annotations
from datetime import datetime
import frontmatter
from pydantic import BaseModel, ConfigDict, field_validator

RESERVED = {"index.md", "log.md"}

def is_reserved(name_or_rel: str) -> bool:
    return name_or_rel.split("/")[-1] in RESERVED

class MissingFrontmatter(ValueError):
    """Arquivo não-reservado sem bloco YAML inicial — erro CONTROLADO,
    convertido em Finding de conformidade pelo lint (nunca stacktrace)."""

class OKFFrontMatter(BaseModel):
    """SPEC §9: apenas `type` é obrigatório; chaves desconhecidas toleradas.
    Extensões privadas válidas: privacy, source_sha256, generated_via,
    confidence, supersedes, stale_as_of..."""
    model_config = ConfigDict(extra="allow")

    type: str
    title: str | None = None
    description: str | None = None
    resource: str | None = None            # URI canônica OPCIONAL
    tags: list[str] = []
    timestamp: datetime | None = None      # datetime real; pydantic coage ISO-8601
    # bi-temporalidade (v0.8 §6.3): TEMPO DE MUNDO do fato compilado
    # (stale_as_of continua sendo tempo de CÓDIGO, ancorado em commit)
    valid_at: datetime | None = None       # quando o fato passou a valer no mundo
    invalid_at: datetime | None = None     # quando deixou de valer (nunca deletar)
    superseded_by: str | None = None       # rel_path da página substituta
    sensitive_data: bool | None = None     # setado pelo detector de PII (§4.3)
    entities: list[str] | None = None      # lista curta legível (anexo: index.db)

    @field_validator("type")
    @classmethod
    def _type_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("type não pode ser vazio")
        return v.strip()

class OKFDocument(BaseModel):
    rel_path: str                          # relativo à raiz do bundle, com .md
    meta: OKFFrontMatter
    body: str

    @property
    def concept_id(self) -> str:           # SPEC: id = caminho sem extensão
        return self.rel_path[:-3]

    def dumps(self) -> str:
        post = frontmatter.Post(
            self.body.strip() + "\n",
            **self.meta.model_dump(exclude_none=True, mode="json"))
        return frontmatter.dumps(post) + "\n"

    @classmethod
    def loads(cls, rel_path: str, text: str) -> "OKFDocument":
        if is_reserved(rel_path):
            raise ValueError(f"{rel_path}: arquivo reservado não é conceito OKF")
        text = text.lstrip("\ufeff")
        if not text.startswith("---\n"):
            raise MissingFrontmatter(f"{rel_path}: sem YAML frontmatter")
        post = frontmatter.loads(text)
        if not post.metadata:
            raise MissingFrontmatter(f"{rel_path}: frontmatter vazio")
        return cls(rel_path=rel_path,
                   meta=OKFFrontMatter(**post.metadata),
                   body=post.content)
