"""Versionamento do knowledge base (v0.6 §2.5).

Interfaces consumidas pelo restante do sistema (preservadas na v0.7):
`GitStore.commit`, `GitStore.has_commit`, `GitStore.repo`.
"""
from __future__ import annotations
from pathlib import Path
from git import Repo
from git.exc import BadName, InvalidGitRepositoryError, NoSuchPathError


class GitStore:
    def __init__(self, root: Path):
        self.root = root
        try:
            self.repo = Repo(root)
        except (InvalidGitRepositoryError, NoSuchPathError):
            root.mkdir(parents=True, exist_ok=True)
            self.repo = Repo.init(root)
            with self.repo.config_writer() as cw:
                cw.set_value("user", "name", "llmwiki")
                cw.set_value("user", "email", "llmwiki@localhost")

    def commit(self, message: str) -> str | None:
        """Stage tudo sob a raiz e commita; retorna o sha (ou None se limpo)."""
        self.repo.git.add(A=True)
        if not self.repo.is_dirty(untracked_files=True) and self._has_head():
            return None
        return self.repo.index.commit(message).hexsha

    def has_commit(self, sha: str) -> bool:
        try:
            self.repo.commit(sha)
            return True
        except (BadName, ValueError):
            return False

    def head(self) -> str | None:
        return self.repo.head.commit.hexsha if self._has_head() else None

    def _has_head(self) -> bool:
        try:
            self.repo.head.commit
            return True
        except ValueError:
            return False
