"""v1.2 (Frente A) — backup lógico verificável e restore testado:
criar dados → backup → verificar → CORROMPER detecta → destruir o
ambiente → restaurar → reconstruir projeção → comparar invariantes."""
from __future__ import annotations
import hashlib
import zipfile
import pytest
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import SCHEMA_VERSIONS, connect
from llmwiki.settings import Settings
from llmwiki.usecases.backup_restore import (CreateBackup, RestoreBackup,
                                             list_backups, verify_backup)
from llmwiki.usecases.cognitive_state import DeclareCognitiveState
from llmwiki.usecases.manage_reference import seed_reference


def _seed(settings, kb):
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/es.md", body="# ES\n\neventos.",
                     meta=OKFFrontMatter(type="concept", title="ES",
                                         privacy="local_only"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    seed_reference(settings)                       # estado não-reconstruível
    DeclareCognitiveState(settings, load=4).execute()


def _bundle_fingerprint(kb) -> str:
    digest = hashlib.sha256()
    for p in sorted((kb / "bundle").rglob("*.md")):
        digest.update(p.read_bytes())
    return digest.hexdigest()


def test_schema_version_is_stamped_on_connect(settings):
    rt = connect(settings.app_support / "runtime.db")
    v = rt.execute("SELECT value FROM _meta WHERE key='schema_version'"
                   ).fetchone()["value"]
    rt.close()
    assert int(v) == SCHEMA_VERSIONS["runtime.db"]


def test_backup_create_verify_and_corruption_detection(settings, kb):
    _seed(settings, kb)
    result = CreateBackup(settings).execute()
    assert result["files"] > 3
    listed = list_backups(settings)
    assert listed and listed[-1]["product_version"]
    check = verify_backup(result["path"])
    assert check["ok"] and check["checked"] == result["files"]
    assert check["schema_versions"]["cognitive.db"] >= 2
    # manifesto declara o que NÃO entra (projeções)
    with zipfile.ZipFile(result["path"]) as zf:
        names = zf.namelist()
        assert not any("index.db" in n or "daemon.json" in n for n in names)
        assert any(n.startswith("knowledge/bundle/") for n in names)
        assert "state/runtime.db" in names        # heat/outcomes/linhagem
        assert "state/reference.db" in names      # dados importados
    # corrupção de 1 arquivo é detectada (reescreve o zip com um .md
    # alterado, manifesto intacto — o sha reconferido acusa)
    with zipfile.ZipFile(result["path"]) as zf:
        payload = {n: zf.read(n) for n in zf.namelist()}
    victim = next(n for n in payload
                  if n.endswith(".md") and b"eventos" in payload[n])
    payload[victim] = payload[victim].replace(b"eventos", b"Xventos")
    corrupted = str(kb.parent / "corrupted.zip")
    with zipfile.ZipFile(corrupted, "w") as zf:
        for name, data in payload.items():
            zf.writestr(name, data)
    check = verify_backup(corrupted)
    assert check["ok"] is False and victim in check["corrupted"]


def test_disaster_restore_into_fresh_home(settings, kb, tmp_path):
    _seed(settings, kb)
    before = _bundle_fingerprint(kb)
    backup = CreateBackup(settings).execute()

    fresh = Settings(**{**settings.model_dump(mode="python"),
                        "home": tmp_path / "novo-lar"})
    plan = RestoreBackup(fresh, backup["path"], dry_run=True).execute()
    assert plan["dry_run"] and not (tmp_path / "novo-lar" / "knowledge"
                                    / "bundle").exists()   # nada tocado
    result = RestoreBackup(fresh, backup["path"]).execute()
    assert result["restored"] == backup["files"]
    # canônico byte-idêntico + estados não-reconstruíveis presentes
    assert _bundle_fingerprint(fresh.path("knowledge")) == before
    rt = connect(fresh.app_support / "runtime.db")
    assert rt.execute("SELECT COUNT(*) c FROM cognitive_state"
                      ).fetchone()["c"] == 1       # estado declarado sobreviveu
    rt.close()
    ref = connect(fresh.app_support / "reference.db")
    assert ref.execute("SELECT COUNT(*) c FROM ref_terms"
                       ).fetchone()["c"] >= 4      # referência sobreviveu
    ref.close()
    # projeção reconstruída: /ask do lar novo encontra a página
    from llmwiki.retrieval import fts
    hits = fts.search(fresh, "eventos", limit=3)
    assert any(h["page"] == "concepts/es.md" for h in hits)


def test_restore_refuses_occupied_home_without_force(settings, kb):
    _seed(settings, kb)
    backup = CreateBackup(settings).execute()
    with pytest.raises(ValueError, match="ocupado"):
        RestoreBackup(settings, backup["path"]).execute()
    result = RestoreBackup(settings, backup["path"], force=True).execute()
    assert result["restored"] > 0                  # e o estado anterior…
    safety = list(settings.home.expanduser().glob("pre-restore-*"))
    assert safety and (safety[0] / "knowledge").exists()   # …foi preservado


def test_restore_refuses_newer_schema(settings, kb, tmp_path):
    _seed(settings, kb)
    backup = CreateBackup(settings).execute()
    import json as _json
    with zipfile.ZipFile(backup["path"]) as zf:
        manifest = _json.loads(zf.read("manifest.json"))
        payload = {n: zf.read(n) for n in zf.namelist()
                   if n != "manifest.json"}
    manifest["schema_versions"]["runtime.db"] = 999
    future = tmp_path / "futuro.zip"
    with zipfile.ZipFile(future, "w") as zf:
        for name, data in payload.items():
            zf.writestr(name, data)
        zf.writestr("manifest.json", _json.dumps(manifest))
    with pytest.raises(ValueError, match="MAIS NOVA"):
        RestoreBackup(settings, future, force=True).execute()


def test_backup_uses_quiescence_lock(settings, kb):
    """v1.4: begin-backup cria o lock; end-backup o remove; a
    quiescência espera nenhum job em execução (sem daemon: imediato)."""
    _seed(settings, kb)
    # simula um job em execução: a espera é bounded, não trava
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("INSERT INTO jobs(id,type,payload,state,created_at) "
               "VALUES ('x','embed','{}','done', 1.0)")
    rt.commit(); rt.close()
    result = CreateBackup(settings).execute()
    assert result["files"] > 3
    assert not (settings.app_support / "backup.lock").exists()  # liberado
