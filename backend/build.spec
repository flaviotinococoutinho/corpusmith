# pyinstaller build.spec  → dist/llmwiki-server/ (onedir: startup rápido)
from PyInstaller.utils.hooks import collect_dynamic_libs
a = Analysis(
    ["src/llmwiki/daemon.py"],
    datas=[("config/default.yaml", "config"), ("db", "db")],
    binaries=collect_dynamic_libs("sqlite_vec"),   # extensão vec0 nativa
    hiddenimports=["sqlite_vec", "sse_starlette", "uvicorn.logging",
                   "uvicorn.protocols.http.auto", "uvicorn.lifespan.on"],
    excludes=["fitz", "pymupdf4llm", "ebooklib"],  # AGPL fora do binário (§8 v0.6)
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, name="llmwiki-server", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="llmwiki-server")
