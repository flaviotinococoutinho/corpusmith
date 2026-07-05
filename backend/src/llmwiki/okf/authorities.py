"""Controle de autoridade (v0.8 §4): o gazetteer curado vive no bundle
como páginas `type: authority_record` — corrigir uma grafia é um commit,
não um deploy. Helper aqui para manter `normalize/` livre de dependências."""
from __future__ import annotations
from .bundle import BundleReader
from ..normalize import Gazetteer, NormReport, analyze, rewrite


def normalize_machine_body(body: str, gaz: Gazetteer) -> tuple[str, NormReport]:
    """Sanduíche PÓS para qualquer página gerada por máquina: reescreve a
    grafia canônica e re-anota sobre o texto final (o report devolvido
    reflete o corpo definitivo — é ele que vai para o índice)."""
    body = rewrite(body, analyze(body, gaz=gaz))
    return body, analyze(body, gaz=gaz)


def load_gazetteer(reader: BundleReader) -> Gazetteer:
    extra = []
    for d in reader.iter_concepts():
        if d.meta.type != "authority_record":
            continue
        x = d.meta.model_dump(exclude_none=True)
        if x.get("canonical"):
            extra.append({"canonical": x["canonical"],
                          "aliases": x.get("aliases", []),
                          "authority": x.get("authority", "term"),
                          "qid": x.get("qid")})
    return Gazetteer.load(extra)
