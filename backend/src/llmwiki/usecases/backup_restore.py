"""Backup lógico portátil + restore verificável (v1.2, Frente A).

O que entra (fontes de verdade e estados NÃO reconstruíveis):
- knowledge/ inteiro: bundle canônico + .git (a história É canônica) +
  raw/ (fontes originais);
- state/runtime.db (heat, desfechos, linhagem de config, pipelines —
  operacional mas não-reconstruível), cognitive.db (acessibilidade,
  sessões, agenda — não-reconstruível), reference.db (dados importados
  pelo usuário), cold.db (memórias congeladas), overrides.yaml.

O que fica DE FORA (reconstruível ou efêmero): index.db (projeção —
`rebuild_index` refaz), daemon.json (token de sessão), WAL/SHM (o
backup faz checkpoint antes de copiar).

Manifesto: versão do produto, versões de schema por banco, sha256 de
CADA arquivo — `verify` reconfere byte a byte; `restore --dry-run`
lista as ações sem tocar nada; restore em versão mais nova é seguro
por construção (connect() reaplica migrações idempotentes ao abrir).
"""
from __future__ import annotations
import hashlib
import json
import shutil
import time
import zipfile
from pathlib import Path
from .base import UseCase
from .. import __version__
from ..runtime.db import SCHEMA_VERSIONS, connect
from ..settings import Settings

_STATE_FILES = ("runtime.db", "cognitive.db", "reference.db", "cold.db",
                "overrides.yaml")
_EXCLUDED = {"index.db", "daemon.json"}          # projeção · efêmero


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def _backup_dir(settings: Settings) -> Path:
    p = settings.home.expanduser() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_backups(settings: Settings) -> list[dict]:
    out = []
    for path in sorted(_backup_dir(settings).glob("llmwiki-backup-*.zip")):
        try:
            with zipfile.ZipFile(path) as zf:
                manifest = json.loads(zf.read("manifest.json"))
            out.append({"path": str(path), "bytes": path.stat().st_size,
                        "created_at": manifest["created_at"],
                        "product_version": manifest["product_version"],
                        "files": len(manifest["files"])})
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
            out.append({"path": str(path), "error": "manifesto ilegível"})
    return out


def verify_backup(archive: str | Path) -> dict:
    """Reconfere CADA sha256 do manifesto contra o conteúdo do zip."""
    archive = Path(archive)
    bad, checked = [], 0
    with zipfile.ZipFile(archive) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        for rel, expected in manifest["files"].items():
            digest = hashlib.sha256()
            with zf.open(rel) as fh:
                for block in iter(lambda: fh.read(1 << 16), b""):
                    digest.update(block)
            checked += 1
            if digest.hexdigest() != expected:
                bad.append(rel)
        missing = [rel for rel in manifest["files"]
                   if rel not in set(zf.namelist())]
    return {"ok": not bad and not missing, "checked": checked,
            "corrupted": bad, "missing": missing,
            "product_version": manifest["product_version"],
            "schema_versions": manifest["schema_versions"]}


class CreateBackup(UseCase):
    def __init__(self, settings: Settings, out: str | None = None,
                 notify=None, exclude_job: str | None = None):
        self._settings = settings
        self._out = out
        self._notify = notify or (lambda *a, **k: None)
        # P-14: quando o backup RODA como job, ele mesmo está leased —
        # sem se excluir, esperaria o timeout inteiro de quiescência
        self._exclude_job = exclude_job

    def execute(self) -> dict:
        home = self._settings.home.expanduser()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        archive = Path(self._out) if self._out else \
            _backup_dir(self._settings) / f"llmwiki-backup-{stamp}.zip"
        lock = self._settings.app_support / "backup.lock"
        lock.write_text(stamp)               # begin-backup: worker pausa
        try:
            self._await_quiescence()
            return self._snapshot(home, archive)
        finally:
            lock.unlink(missing_ok=True)     # end-backup

    def _await_quiescence(self, timeout_s: float = 30.0) -> None:
        """Espera nenhum job em execução (o worker já parou de leasear
        pelo lock; o job em voo termina). Bounded — segue mesmo assim."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            rt = connect(self._settings.app_support / "runtime.db")
            busy = rt.execute(
                "SELECT COUNT(*) c FROM jobs WHERE state IN "
                "('leased','cancel_requested') AND id != ?",
                (self._exclude_job or "",)).fetchone()["c"]
            rt.close()
            if not busy:
                return
            time.sleep(0.2)

    def _snapshot(self, home: Path, archive: Path) -> dict:
        # checkpoint dos WAL: o arquivo .db fica completo p/ cópia fria
        for name in _STATE_FILES:
            path = home / "state" / name
            if path.suffix == ".db" and path.exists():
                conn = connect(path)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
        files: dict[str, str] = {}
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            knowledge = home / "knowledge"
            for path in sorted(knowledge.rglob("*")):
                if not path.is_file():
                    continue
                rel = f"knowledge/{path.relative_to(knowledge)}"
                zf.write(path, rel)
                files[rel] = _sha256(path)
            for name in _STATE_FILES:
                path = home / "state" / name
                if path.exists():
                    rel = f"state/{name}"
                    zf.write(path, rel)
                    files[rel] = _sha256(path)
            manifest = {"product_version": __version__,
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "schema_versions": dict(SCHEMA_VERSIONS),
                        "excluded_projections": sorted(_EXCLUDED),
                        "files": files}
            zf.writestr("manifest.json",
                        json.dumps(manifest, indent=1, sort_keys=True))
        self._notify("backup.created", {"path": str(archive),
                                        "files": len(files)})
        return {"path": str(archive), "files": len(files),
                "bytes": archive.stat().st_size}


class RestoreBackup(UseCase):
    """Restore com dry-run. Destino não-vazio exige `force` — e nesse
    caso o estado atual vai para <home>/pre-restore-<ts>/ ANTES de
    qualquer escrita (rollback manual sempre possível). Ao final,
    reconstrói a projeção (index.db) do canônico restaurado."""

    def __init__(self, settings: Settings, archive: str | Path, *,
                 dry_run: bool = False, force: bool = False, notify=None):
        self._settings = settings
        self._archive = Path(archive)
        self._dry_run = dry_run
        self._force = force
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        verification = verify_backup(self._archive)
        if not verification["ok"]:
            raise ValueError(f"backup falhou na verificação: "
                             f"{verification['corrupted'] or verification['missing']}")
        newer = {name: v for name, v in
                 verification["schema_versions"].items()
                 if v > SCHEMA_VERSIONS.get(name, 0)}
        if newer:
            raise ValueError(
                f"backup de versão de schema MAIS NOVA que este produto "
                f"({newer}) — atualize o llmwiki antes de restaurar")
        home = self._settings.home.expanduser()
        occupied = [p.name for p in (home / "knowledge").glob("*")] \
            if (home / "knowledge").exists() else []
        actions = [f"extrair {verification['checked']} arquivo(s) em {home}",
                   "reconstruir index.db (projeção) do canônico restaurado"]
        if occupied:
            actions.insert(0, f"mover estado atual para pre-restore-* "
                              f"(destino ocupado: {len(occupied)} item(ns))")
        if self._dry_run:
            return {"dry_run": True, "actions": actions,
                    "verification": verification}
        if occupied and not self._force:
            raise ValueError("destino ocupado — use force para restaurar "
                             "(o estado atual será preservado em "
                             "pre-restore-*)")
        if occupied:
            safety = home / f"pre-restore-{time.strftime('%Y%m%d-%H%M%S')}"
            safety.mkdir(parents=True)
            for name in ("knowledge", "state"):
                if (home / name).exists():
                    shutil.move(str(home / name), str(safety / name))
        with zipfile.ZipFile(self._archive) as zf:
            members = [m for m in zf.namelist() if m != "manifest.json"]
            zf.extractall(home, members)
        # ADR-39: bancos trocados por baixo ⇒ o fast-path de connect()
        # é invalidado — o próximo open repassa schema+migração inteiros
        from ..runtime.db import reset_initialized
        reset_initialized()
        from .rebuild_index import RebuildIndex
        rebuilt = RebuildIndex(self._settings).execute()
        self._notify("backup.restored",
                     {"archive": str(self._archive),
                      "files": verification["checked"]})
        return {"restored": verification["checked"],
                "rebuilt_index": rebuilt, "actions": actions,
                "product_version": verification["product_version"]}
