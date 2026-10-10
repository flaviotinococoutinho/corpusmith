"""Único caminho de ESCRITA no bundle (v0.6 §2.6).

Fluxo: Harness (gate) → arquivos → index.md regenerados → log.md → commit.
Nenhum job ou endpoint escreve no bundle fora daqui — páginas por `write`,
o artefato que não é página (o golden eval) por `write_artifact` (ADR-61);
`test_q28_golden_pelo_escritor.py` varre o código e reprova a porta lateral.
"""
from __future__ import annotations
import fcntl
import os
import posixpath
from contextlib import contextmanager
from pathlib import Path
from .bundle import BundleReader
from .document import OKFDocument
from .git_store import GitStore
from .index_file import regenerate_for
from .log_file import LogWriter
from ..harness import artifacts
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
        findings = self.harness.run(docs, mode=mode, intent=log_kind)
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

    def write_artifact(self, rel_path: str, text: str, *, log_kind: str,
                       log_message: str, commit_message: str,
                       create_only: bool = False) -> dict:
        """Escreve um ARTEFATO do bundle — arquivo que não é página OKF;
        hoje só o golden eval — pelo mesmo rito das páginas (Q-28, ADR-61).

        Gate próprio (`harness/artifacts.py`: allowlist fechada + formato),
        lock, escrita atômica (`os.replace`), entrada no `log.md` e um
        commit que leva SÓ o que este ato escreveu: o artefato e o log.
        `create_only` decide a existência DENTRO do lock — "nunca
        sobrescrever golden curado" deixa de ter janela de corrida."""
        findings = artifacts.check(rel_path, text)
        if findings.has_errors():
            raise HarnessRejection(findings)
        with self.locked():
            target = self.bundle / rel_path
            if create_only and target.exists():
                return {"artifact": rel_path, "commit": None,
                        "skipped": "exists"}
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.tmp")
            try:
                tmp.write_text(text)
                os.replace(tmp, target)
            finally:
                # depois do replace o temporário já não existe; se a escrita
                # falhou no meio, ele não fica para o `add -A` do próximo ato
                tmp.unlink(missing_ok=True)
            self.log.append(log_kind, log_message)
            commit = self.git.commit(
                commit_message,
                paths=[f"bundle/{rel_path}", f"bundle/{self.log.path.name}"])
        return {"artifact": rel_path, "commit": commit}

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
