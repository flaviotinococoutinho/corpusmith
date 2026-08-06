"""Pontas soltas e código morto — os instrumentos, não a lista (docs/17).

A auditoria descreveu qualitativamente ("use case completo, endpoint completo,
nenhuma tela"). Estes testes MEDEM, e é a diferença entre um achado e um gate:
a lista de defeitos envelhece, o instrumento não.

Dois instrumentos, os dois derivados de achados confirmados por execução:

1. **rota sem consumidor** — 12 de 92 rotas do backend não são chamadas por
   nenhum arquivo do desktop. Duas delas (`/curation/acts` e
   `/curation/history`) são exatamente o que torna o `undo` inalcançável pelo
   app: sem listar os atos, não há `act_id` para desfazer;
2. **evento sem escutador** — 45 tipos de evento são emitidos pelo backend e
   **5** chegam à UI, logo **44 são mudos** (`compile.done` é o único repassado
   que o backend também emite). O `Stepper` do Inbox e a barra de progresso de
   Processos são código já escrito que nunca recebe `page.stage` nem
   `stage.progress`.

Os testes fixam o número ATUAL como teto, não como meta. Piorar quebra; melhorar
exige baixar o teto no mesmo commit — que é o gesto que faz o número descer em
vez de virar decoração.
"""
from __future__ import annotations
import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CLIENTE = RAIZ / "desktop/src/lib/daemonClient.ts"

# Tetos MEDIDOS em 2026-07-27. Baixar junto com a correção; nunca subir.
MAX_ROTAS_ORFAS = 12
MAX_EVENTOS_MUDOS = 44


def _rotas() -> list[tuple[str, str, str]]:
    achadas = []
    for py in (RAIZ / "backend/src/llmwiki/api").rglob("*.py"):
        for no in ast.walk(ast.parse(py.read_text())):
            if not isinstance(no, ast.FunctionDef):
                continue
            for dec in no.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                metodo = getattr(dec.func, "attr", None)
                if metodo not in ("get", "post", "put", "delete", "patch"):
                    continue
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    achadas.append((metodo.upper(), dec.args[0].value,
                                    f"{py.relative_to(RAIZ)}:{no.lineno}"))
    return achadas


def _consumidas() -> set[str]:
    fontes = CLIENTE.read_text() + "\n".join(
        p.read_text() for p in (RAIZ / "desktop/src").rglob("*.tsx"))
    # QUALQUER caminho absoluto citado no cliente ou num painel conta como
    # consumo. Restringir a prefixos conhecidos produzia falso positivo:
    # `/ask`, `/status` e `/health` SÃO chamados e apareciam como órfãos.
    return {m.split("?")[0].rstrip("/") for m in
            re.findall(r'["`\'](/[a-z][^"`\'?\s]*)', fontes)}


def _orfas() -> list[tuple[str, str, str]]:
    consumidas = _consumidas()
    fora = []
    for metodo, rota, onde in _rotas():
        base = rota.split("{")[0].rstrip("/")
        if not base or not any(c == rota or c.startswith(base)
                               for c in consumidas):
            fora.append((metodo, rota, onde))
    return fora


def test_rotas_sem_consumidor_nao_aumentam():
    """Rota que nenhuma superfície chama é capacidade que o produto anuncia e
    o usuário não alcança. O teto é o número medido — corrigir exige baixá-lo
    no mesmo commit, senão a melhoria não fica registrada."""
    orfas = _orfas()
    assert len(orfas) <= MAX_ROTAS_ORFAS, (
        f"{len(orfas)} rotas sem consumidor (teto {MAX_ROTAS_ORFAS}):\n"
        + "\n".join(f"  {m} {r}  {o}" for m, r, o in sorted(orfas,
                                                            key=lambda x: x[1])))


def test_o_undo_segue_inalcancavel_pelo_app_e_isso_esta_declarado():
    """Achado confirmado por execução: o ato existe, o endpoint existe, e
    nenhuma superfície lista os atos para obter o `act_id`. Este teste NÃO
    conserta — declara, e quebra no dia em que alguém religar, forçando a
    atualização do teto e da documentação."""
    orfas = {r for _, r, _ in _orfas()}
    assert "/curation/history" in orfas, (
        "o histórico de atos ganhou consumidor — baixe MAX_ROTAS_ORFAS e "
        "atualize docs/17, porque o undo deixou de ser inalcançável")


def _eventos_emitidos() -> set[str]:
    tipos = set()
    padrao = re.compile(
        r'(?:_notify|emit|publish)\(\s*["\']([a-z_]+\.[a-z_.]+)["\']')
    for py in (RAIZ / "backend/src/llmwiki").rglob("*.py"):
        tipos |= set(padrao.findall(py.read_text()))
    return tipos


def _eventos_repassados() -> set[str]:
    bloco = re.search(r'for \(const t of \[(.*?)\]', CLIENTE.read_text(), re.S)
    return set(re.findall(r'["\']([a-z_]+\.[a-z_]+)["\']', bloco.group(1))) \
        if bloco else set()


def test_eventos_mudos_nao_aumentam():
    """O `EventSource` do cliente registra listener por TIPO. Tipo não
    registrado nunca chega — e há UI já escrita esperando por eles (`Stepper`
    do Inbox por `page.stage`, barra de progresso por `stage.progress`)."""
    mudos = _eventos_emitidos() - _eventos_repassados()
    assert len(mudos) <= MAX_EVENTOS_MUDOS, (
        f"{len(mudos)} tipos de evento nunca chegam à UI "
        f"(teto {MAX_EVENTOS_MUDOS}):\n  " + "\n  ".join(sorted(mudos)))


def test_o_evento_do_ato_de_curadoria_e_um_dos_mudos():
    """`curation.applied` é emitido pelo esqueleto de TODO ato (F1-PR1) e
    não chega à UI: o dialog descobre o resultado pela resposta HTTP, e
    nenhuma outra superfície sabe que o canônico mudou. Declarado aqui para
    não se perder entre 44."""
    assert "curation.applied" in _eventos_emitidos() - _eventos_repassados()


def test_o_evento_que_esta_sessao_criou_tambem_e_mudo():
    """Honestidade sobre o próprio trabalho: `themes.adopt_refused` foi
    emitido no F2-PR2 e ninguém escuta. Emitir evento sem escutador é
    exatamente a ponta solta que este arquivo mede — inclusive quando fui eu
    que a criei."""
    assert "themes.adopt_refused" in _eventos_emitidos() - _eventos_repassados()


# ================================ o degrau de similaridade morto
def test_a_falha_da_similaridade_deixou_de_ser_muda():
    """Achado de maior consequência da auditoria, verificado por execução:
    `MIN(bm25(chunks_fts))` levanta `OperationalError: unable to use function
    bm25 in the requested context` em SQLite 3.45.1 — SEMPRE. Com o `except
    Exception` cego original, o degrau de similaridade, os limiares HI/LO, o
    NCD e o árbitro LLM eram código morto indistinguível de "não achei
    candidato".

    Este teste NÃO conserta a SQL: corrigi-la ativa o árbitro LLM no caminho
    de escrita, e o `AGENTS.md` §8 exige RFC para isso. O que ele garante é
    que a falha ficou AUDÍVEL — que é o que impede o defeito de sobreviver
    outra vez por ser silencioso."""
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.executescript(
        "CREATE TABLE chunks(id INTEGER PRIMARY KEY, page TEXT, text TEXT);"
        "CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='chunks',"
        " content_rowid='id');"
        "INSERT INTO chunks(page,text) VALUES ('a.md','entropia de shannon');"
        "INSERT INTO chunks_fts(rowid,text) SELECT id,text FROM chunks;")
    sql = ("SELECT c.page, MIN(bm25(chunks_fts)) r FROM chunks_fts "
           "JOIN chunks c ON c.id = chunks_fts.rowid "
           "WHERE chunks_fts MATCH ? GROUP BY c.page ORDER BY r LIMIT 8")
    try:
        con.execute(sql, ('"entropia"',)).fetchall()
        con.close()
        raise AssertionError(
            "a consulta parou de estourar neste SQLite — o degrau de "
            "similaridade pode ter voltado à vida SEM o RFC que o AGENTS.md "
            "§8 exige (ela ativa o árbitro LLM no caminho de escrita). "
            "Leia docs/17 antes de mexer.")
    except sqlite3.OperationalError as e:
        assert "bm25" in str(e)
    finally:
        con.close()
    # e o use case agora tem onde registrar isso
    from llmwiki.usecases.reconcile_candidate import ReconcileCandidate
    assert hasattr(ReconcileCandidate, "similarity_error")
