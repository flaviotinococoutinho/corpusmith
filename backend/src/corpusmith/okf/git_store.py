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

    def edit_history(self) -> dict[str, dict]:
        """{caminho: {"edicoes", "primeira_em", "ultima_em"}} para TODOS os
        arquivos já commitados, numa passada única de `git log --name-only`
        (RFC-006 V3 — a projeção de estabilidade lê daqui).

        Somente leitura, como toda esta seção. Duas escolhas declaradas:

        - `--no-renames`: renomear conta como página NOVA. Continuidade
          através de rename exigiria confiar na heurística de detecção do
          Git — e um rename é, de fato, um gesto editorial;
        - contagem por COMMIT que toca o arquivo: um commit que reescreve a
          página inteira e um que troca uma vírgula contam 1 cada. Edição
          mede frequência de gesto, não tamanho de diff — pesar por bytes
          seria um segundo sentido escondido no mesmo número.

        Os caminhos vêm relativos à RAIZ do repositório (`kb/`), com o
        prefixo `bundle/` — quem consome normaliza para o rel_path do
        bundle. O separador \\x01 evita colisão com nome de arquivo."""
        if not self._has_head():
            return {}
        bruto = self.repo.git.log("--name-only", "--no-renames",
                                  "--pretty=format:\x01%ct")
        out: dict[str, dict] = {}
        quando = 0.0
        for linha in bruto.splitlines():
            if linha.startswith("\x01"):
                quando = float(linha[1:])
                continue
            caminho = linha.strip()
            if not caminho:
                continue
            reg = out.setdefault(caminho, {"edicoes": 0, "primeira_em": quando,
                                           "ultima_em": quando})
            reg["edicoes"] += 1
            # o log anda do mais NOVO ao mais velho: o primeiro timestamp
            # visto é a última edição; o corrente empurra a primeira p/ trás
            reg["primeira_em"] = quando
        return out

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
