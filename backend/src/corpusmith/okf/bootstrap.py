"""Bootstrap OKF-conformante do knowledge base (v0.6 §5.6).

Cria kb/{bundle,raw}, `index.md` da raiz com frontmatter contendo APENAS
`okf_version`, `log.md` e o commit inicial. Idempotente: nunca sobrescreve
um bundle existente.
"""
from __future__ import annotations
from pathlib import Path
from .git_store import GitStore
from .index_file import OKF_VERSION
from .log_file import LogWriter


def ensure_bundle(kb_root: Path) -> bool:
    """Retorna True se o bundle foi criado agora."""
    bundle = kb_root / "bundle"
    created = not (bundle / "index.md").exists()
    (kb_root / "raw").mkdir(parents=True, exist_ok=True)
    bundle.mkdir(parents=True, exist_ok=True)
    git = GitStore(kb_root)
    if created:
        (bundle / "index.md").write_text(
            f"---\nokf_version: \"{OKF_VERSION}\"\n---\n\n# Bundle\n")
        LogWriter(bundle).append("Creation", "bundle inicializado")
        gitignore = kb_root / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(".write.lock\n")
        git.commit("bootstrap: bundle OKF inicial")
    return created
