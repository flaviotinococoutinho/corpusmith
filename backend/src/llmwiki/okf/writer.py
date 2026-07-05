"""Único caminho de ESCRITA no bundle (v0.6 §2.6).

Fluxo: Harness (gate) → arquivos → index.md regenerados → log.md → commit.
Nenhum job ou endpoint escreve páginas fora daqui.
"""
from __future__ import annotations
import fcntl
import posixpath
from contextlib import contextmanager
from pathlib import Path
from .bundle import BundleReader
from .document import OKFDocument
from .git_store import GitStore
from .index_file import regenerate_for
from .log_file import LogWriter
from ..harness.runner import HarnessRejection, HarnessRunner


class BundleWriter:
    def __init__(self, kb_root: Path):
        self.kb = kb_root
        self.bundle = kb_root / "bundle"
        self.bundle.mkdir(parents=True, exist_ok=True)
        self.reader = BundleReader(self.bundle)
        self.git = GitStore(kb_root)
        self.log = LogWriter(self.bundle)
        self.harness = HarnessRunner(self.reader, self.git)

    @contextmanager
    def locked(self):
        """Lock de escrita entre processos (daemon × CLI)."""
        lock_path = self.kb / ".write.lock"
        with open(lock_path, "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def write(self, docs: list[OKFDocument], *, log_kind: str,
              log_message: str, commit_message: str,
              mode: str = "write") -> dict:
        findings = self.harness.run(docs, mode=mode)
        if HarnessRunner.has_errors(findings):
            raise HarnessRejection(findings)
        with self.locked():
            pages: list[str] = []
            for d in docs:
                target = self.bundle / d.rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(d.dumps())
                pages.append(d.rel_path)
            regenerate_for(self.bundle,
                           {posixpath.dirname(p) for p in pages})
            self.log.append(log_kind, log_message)
            commit = self.git.commit(commit_message)
        return {"pages": pages, "commit": commit,
                "findings": [f.__dict__ for f in findings]}

    def remove(self, rel_path: str, *, log_kind: str, log_message: str,
               commit_message: str) -> dict:
        """Remove uma página do bundle (freeze → base fria, v0.12).
        Mesmo rito da escrita: lock → arquivo → index.md → log → commit.
        A página permanece no histórico Git — remoção é compactação."""
        with self.locked():
            target = self.bundle / rel_path
            if target.is_file():
                target.unlink()
            regenerate_for(self.bundle, {posixpath.dirname(rel_path)})
            self.log.append(log_kind, log_message)
            commit = self.git.commit(commit_message)
        return {"removed": rel_path, "commit": commit}
