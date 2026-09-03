# pyinstaller build.spec  → dist/corpusmith-server/ (onedir: startup rápido)
#
# Duas correções do PR-0.1, ambas com a falha REPRODUZIDA antes:
#
# 1. `exclude_binaries=True` no EXE. Sem ele o onedir quebra com
#    `ValueError: Resource '.../corpusmith-server' is not a valid file!` — o EXE
#    tenta ser um onefile e o COLLECT seguinte não tem o que coletar. Medido:
#    `pyinstaller build.spec` falhava assim, então `just sidecar` NÃO
#    construía, e por isso o binário que o `sidecar.ts` procura no app
#    empacotado nunca existiu para terceiro nenhum;
#
# 2. `search_patterns` explícito no `collect_dynamic_libs`. O default do
#    PyInstaller é `['*.dll', '*.dylib', 'lib*.so']` — e a extensão do
#    sqlite-vec se chama `vec0.so`, que NÃO casa com `lib*.so`. Medido: com o
#    default a chamada devolve `[]`, com `*.so` devolve o `vec0.so`. O binário
#    sairia sem a extensão vetorial **em silêncio**, e a busca semântica
#    degradaria sem ninguém saber. A causa não é o extra `[ml]` estar ausente
#    (o pacote estava instalado): é o padrão de nome.
from PyInstaller.utils.hooks import collect_dynamic_libs

_vec = collect_dynamic_libs("sqlite_vec",
                            search_patterns=["*.so", "*.dylib", "*.dll"])
if not _vec:
    # Falhar ALTO em vez de embarcar um binário mudo: um pacote sem busca
    # vetorial parece funcionar e responde pior, que é o pior modo de falha.
    raise SystemExit(
        "build.spec: sqlite-vec não encontrado — instale o extra [ml] "
        "(`pip install -e '.[dev,ml]'`) antes de empacotar. Embarcar sem a "
        "extensão vec0 degradaria a busca em silêncio.")

a = Analysis(
    ["packaging_entry.py"],
    pathex=["src"],
    # `epistemics.toml` e `ontology.toml` moram na raiz do repo e são lidos em
    # RUNTIME (o painel Qualidade e `/cockpit/epistemics` chamam `lint()`).
    # Fora dos `datas`, o app empacotado responderia `epistemic.registry_missing`
    # e o painel mostraria "lint com erros" — o produto acusando a si mesmo de
    # não saber o que afirma saber. Reproduzido no binário antes de acrescentar
    # aqui; `ontology.toml` entrou junto por ser o mesmo modo de falha (RFC-004).
    datas=[("config/default.yaml", "config"), ("db", "db"),
           ("../epistemics.toml", "."), ("../ontology.toml", ".")],
    binaries=_vec,                                 # extensão vec0 nativa
    hiddenimports=["sqlite_vec", "sse_starlette", "uvicorn.logging",
                   "uvicorn.protocols.http.auto", "uvicorn.lifespan.on"],
    excludes=["fitz", "pymupdf4llm", "ebooklib"],  # AGPL fora do binário (§8 v0.6)
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="corpusmith-server",
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="corpusmith-server")
