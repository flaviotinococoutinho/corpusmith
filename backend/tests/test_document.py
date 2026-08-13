"""OKFDocument: frontmatter controlado, timestamp datetime real (§0.1/§0.2)."""
from __future__ import annotations
from datetime import datetime, timezone
import pytest
from corpusmith.okf.document import MissingFrontmatter, OKFDocument, OKFFrontMatter


VALID = """---
type: concept
title: Grafo de conhecimento
timestamp: 2026-07-01T12:00:00+00:00
privacy: local_only
---

# Grafo de conhecimento

Corpo.
"""


def test_loads_coerces_timestamp_to_datetime():
    d = OKFDocument.loads("concepts/grafo.md", VALID)
    assert isinstance(d.meta.timestamp, datetime)
    assert d.meta.timestamp == datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    assert d.concept_id == "concepts/grafo"


def test_dumps_serializes_timestamp_as_iso_and_roundtrips():
    d = OKFDocument(
        rel_path="concepts/x.md",
        body="# X\n\ncorpo",
        meta=OKFFrontMatter(type="concept", title="X",
                            timestamp=datetime(2026, 7, 5, 8, 30,
                                               tzinfo=timezone.utc)))
    text = d.dumps()
    assert "2026-07-05T08:30:00" in text          # ISO no arquivo
    again = OKFDocument.loads("concepts/x.md", text)
    assert again.meta.timestamp == d.meta.timestamp


def test_missing_frontmatter_is_controlled_error():
    with pytest.raises(MissingFrontmatter):
        OKFDocument.loads("concepts/x.md", "# Sem frontmatter\n\ncorpo\n")


def test_empty_frontmatter_is_controlled_error():
    with pytest.raises(MissingFrontmatter):
        OKFDocument.loads("concepts/x.md", "---\n---\n\ncorpo\n")


def test_bom_is_tolerated():
    d = OKFDocument.loads("concepts/x.md", "﻿" + VALID)
    assert d.meta.type == "concept"


def test_reserved_files_are_not_concepts():
    with pytest.raises(ValueError):
        OKFDocument.loads("index.md", VALID)
    with pytest.raises(ValueError):
        OKFDocument.loads("sub/log.md", VALID)


def test_unknown_keys_tolerated_and_type_required():
    d = OKFDocument.loads("c/x.md", "---\ntype: concept\nfoo: bar\n---\ncorpo")
    assert d.meta.model_dump()["foo"] == "bar"
    with pytest.raises(Exception):
        OKFFrontMatter(title="sem type")  # type: ignore[call-arg]
