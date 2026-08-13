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
                cw.set_value("user", "name", "corpusmith")
                cw.set_value("user", "email", "corpusmith@localhost")

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

    # ------------------------------------------------ leitura histórica (F1-PR2)
    # O undo NÃO usa `git revert`: reverter no worktree colocaria bytes no
    # disco ANTES do gate do Harness, e recuperar de uma rejeição exigiria
    # `checkout`/`reset` — as operações que "invalidar-nunca-apagar" proíbe.
    # Em vez disso lemos o conteúdo ANTERIOR e o reescrevemos pelo caminho
    # normal: o desfazer vira escrita PARA A FRENTE, gateada como qualquer
    # outra. Estes dois métodos são só leitura — nada aqui toca o worktree.
    def parent_of(self, sha: str) -> str | None:
        """Sha do primeiro pai (None para o commit raiz)."""
        pais = self.repo.commit(sha).parents
        return pais[0].hexsha if pais else None

    def read_at(self, sha: str, rel_path: str) -> str | None:
        """Conteúdo do arquivo NAQUELE commit; None se não existia ainda."""
        try:
            blob = self.repo.commit(sha).tree / rel_path
        except KeyError:
            return None
        return blob.data_stream.read().decode("utf-8")

    def changed_since(self, sha: str, rel_path: str) -> bool:
        """O arquivo mudou entre `sha` e o HEAD? Usado para AVISAR que um
        undo antigo vai sobrescrever trabalho posterior — o preview mostra
        o diff, mas o aviso nomeia o risco."""
        atual = self.head()
        if atual is None or atual == sha:
            return False
        return self.read_at(sha, rel_path) != self.read_at(atual, rel_path)

    def _has_head(self) -> bool:
        try:
            self.repo.head.commit
            return True
        except ValueError:
            return False
