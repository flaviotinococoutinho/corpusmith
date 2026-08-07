"""O vocabulário de eventos — F-UI.

O achado que originou este arquivo: o cliente registrava CINCO nomes de evento
e o servidor emite quarenta e oito. Por spec do `EventSource`, um evento
nomeado só chega a quem fez `addEventListener` com aquele nome exato, então
`page.stage`, `pipeline.*`, `consolidate.done` e `source.ingested` saíam do
backend e morriam antes da tela — com o Stepper do Inbox e a barra de
progresso por job já escritos, tipados, e nunca alimentados.

Uma lista maior no cliente cairia na mesma armadilha na próxima adição. O que
estes testes protegem é o LAÇO: o produto declara o vocabulário, `/events/types`
o serve, e o registro não pode ficar para trás do código.
"""
from __future__ import annotations
import ast
import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.runtime.events import (EVENT_TYPES, EventBus,
                                    EventTypeNaoDeclarado)
from llmwiki.runtime.db import connect
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue

TOKEN = "tev"


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": TOKEN})
        yield c

SRC = Path(__file__).resolve().parents[1] / "src" / "llmwiki"
# `canal.evento` e também `canal.sub.evento`: a jornada cognitiva usa TRÊS
# segmentos (`focus.goal.created`), e a primeira versão desta regex, com dois
# fixos, deu verde com nove tipos de fora. Quem os pegou foi a recusa em
# runtime, ao rodar a suíte inteira — o que é o argumento para manter as duas
# guardas: a estática vê o código que ninguém executa, a dinâmica vê o que a
# estática não sabe reconhecer.
_TIPO = re.compile(r"^[a-z][a-z_]*(\.[a-z][a-z_]*)+$")
_EMISSORES = {"emit", "notify", "_notify", "ctx"}


def _literais_emitidos() -> dict[str, str]:
    """{tipo: arquivo:linha} de todo literal passado a um emissor.

    Varredura ESTÁTICA de propósito: um teste de runtime só pega os caminhos
    que a suíte exercita, e o modo de falha aqui é justamente o caminho que
    ninguém exercita — foi assim que cinco rótulos da StatusBar ficaram
    inalcançáveis sem que nada acusasse."""
    achados: dict[str, str] = {}
    for arquivo in SRC.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(), filename=str(arquivo))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            nome = (alvo.attr if isinstance(alvo, ast.Attribute)
                    else getattr(alvo, "id", ""))
            if nome not in _EMISSORES:
                continue
            for arg in no.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                        and _TIPO.match(arg.value):
                    achados.setdefault(
                        arg.value,
                        f"{arquivo.relative_to(SRC)}:{no.lineno}")
    return achados


def test_todo_evento_emitido_esta_declarado():
    """A varredura é o gate: `emit("x.y")` novo sem entrada em EVENT_TYPES
    reprova aqui, mesmo que nenhum teste chegue a executar aquela linha."""
    emitidos = _literais_emitidos()
    faltando = {t: onde for t, onde in emitidos.items() if t not in EVENT_TYPES}
    assert not faltando, (
        "eventos emitidos e não declarados — a UI nunca os receberia: "
        + ", ".join(f"{t} ({onde})" for t, onde in sorted(faltando.items())))


def test_a_varredura_acha_mesmo_os_emissores():
    """Guarda contra o pior desfecho: um scanner que não acha nada e por isso
    aprova tudo. Sem isto, quebrar o `_EMISSORES` deixaria o teste acima verde
    para sempre."""
    emitidos = _literais_emitidos()
    assert len(emitidos) >= 30, len(emitidos)
    assert {"page.stage", "pipeline.done", "compile.extracting"} <= set(emitidos)


def test_emitir_tipo_nao_declarado_e_erro(settings):
    """Registro dinâmico é registro que ninguém garante (mesma disciplina de
    `DERIVATIONS`, ADR-46). Sem esta recusa, `EVENT_TYPES` viraria documentação
    — verdadeira no dia em que foi escrita."""
    bus = EventBus(connect(settings.app_support / "runtime.db"))
    with pytest.raises(EventTypeNaoDeclarado, match="não declarado"):
        bus.emit("system", "invencao.nova", {})
    assert bus.emit("system", "daemon.started", {}) > 0


def test_familia_job_completa_esta_declarada():
    """`worker.py` emite `f"job.{state}"`, e `state` vem de `queue.fail()`.
    Um estado novo na fila sem entrada aqui só apareceria em produção, no dia
    do erro — que é o pior dia para descobrir."""
    fila = (SRC / "runtime" / "queue.py").read_text()
    estados = set(re.findall(r'"(failed|retry_scheduled|dead_lettered|'
                             r'cancelled)"', fila))
    assert estados, "fixture inútil: nenhum estado encontrado em queue.py"
    for estado in estados:
        assert f"job.{estado}" in EVENT_TYPES, estado


def _resultados(no: ast.expr) -> set[str]:
    """Valores que uma expressão pode PRODUZIR, ignorando os que ela testa.

    Um `ast.walk` ingênuo devolveria também `'success'` de
    `result == 'success'` — a string comparada, que nunca vira nome de evento.
    Aqui só descem os ramos do condicional."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return {no.value}
    if isinstance(no, ast.IfExp):
        return _resultados(no.body) | _resultados(no.orelse)
    return set()


def test_familias_por_f_string_estao_declaradas():
    """Um `_notify(f"...")` é invisível para a varredura estática.

    Só existe uma no produto (`retrieval.*`, cognitive_journey.py:372) e ela
    escapou das duas primeiras guardas — quem a pegou foi a recusa em runtime
    ao rodar a suíte. Este teste LÊ o código que gera a família em vez de
    repetir a lista, então acrescentar um ramo ao condicional reprova aqui."""
    fonte = (SRC / "usecases" / "cognitive_journey.py").read_text()
    for no in ast.walk(ast.parse(fonte)):
        if not (isinstance(no, ast.Call)
                and getattr(no.func, "attr", "") == "_notify"):
            continue
        if not (no.args and isinstance(no.args[0], ast.JoinedStr)):
            continue
        partes = no.args[0].values
        prefixo = partes[0].value if isinstance(partes[0], ast.Constant) else ""
        sufixos: set[str] = set()
        for p in partes[1:]:
            sufixos |= _resultados(p.value if isinstance(p, ast.FormattedValue)
                                   else p)
        assert sufixos, ast.dump(no.args[0])
        for sufixo in sufixos:
            assert prefixo + sufixo in EVENT_TYPES, prefixo + sufixo


def test_endpoint_serve_o_vocabulario(client):
    """O cliente não deve carregar cópia da lista: ele PERGUNTA."""
    r = client.get("/events/types")
    assert r.status_code == 200
    servidos = r.json()["types"]
    assert servidos == sorted(EVENT_TYPES)
    assert "page.stage" in servidos
