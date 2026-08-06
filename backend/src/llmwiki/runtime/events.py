"""Barramento de eventos: persiste em runtime.db e propaga para assinantes
SSE em memória (Parte V §5.5).

**F-UI: o tipo de evento vira vocabulário declarado.** O `EventSource` do
navegador só entrega um evento nomeado a quem tenha feito `addEventListener`
com aquele nome exato — `onmessage` recebe apenas os SEM nome. O cliente
registrava **cinco** nomes fixos, e o servidor emite quarenta e oito: todo o
"filme ao vivo" de compilação, consolidação e pipeline saía do backend e
morria antes da tela. O Stepper do Inbox e a barra de progresso por job eram
código morto — escrito, tipado, e nunca alimentado.

A correção poderia ser o cliente registrar uma lista fixa maior, e seria a
mesma armadilha um ano depois. Em vez disso o produto **declara** o
vocabulário aqui, `/events/types` o serve, e o cliente registra o que o
servidor disser que emite. Para a declaração não poder mentir, `emit` RECUSA
tipo não declarado — a mesma disciplina de `kernel/checkpoints.py:DERIVATIONS`
(ADR-46): registro dinâmico é registro que ninguém garante.
"""
from __future__ import annotations
import json
import queue as _queue
import threading
import time
from sqlite3 import Connection

# Ordem alfabética, agrupada por origem. Acrescentar `emit`/`notify` com tipo
# novo EXIGE acrescentar aqui — e `test_eventos.py` prova isso estaticamente,
# varrendo o código por literais, para que o esquecimento não dependa de
# aquele caminho estar coberto por teste de runtime.
EVENT_TYPES: frozenset[str] = frozenset({
    # ciclo de vida do daemon e da fila
    "daemon.started", "orphans.recovered",
    "job.started", "job.done", "job.failed", "job.cancelled", "job.timeout",
    "job.retry_scheduled", "job.dead_lettered",
    "worker.started", "worker.completed", "worker.failed", "worker.killed",
    # escrita e compilação
    "page.stage", "page.noop", "page.recycled", "supersede.dependents",
    "compile.extracting", "compile.done", "source.ingested",
    "consolidate.done", "curation.applied",
    "pipeline.stage", "pipeline.done", "pipeline.cancelled",
    "stage.progress", "embed.progress",
    # memória, reflexão e cognição
    "memory.promoted", "memory.frozen", "memory.recycled",
    "reflect.done", "feedback.recorded",
    # família dinâmica: `f"retrieval.{...}"` em cognitive_journey.py:372.
    # Invisível para a varredura estática (f-string), como `job.{state}` em
    # worker.py — as duas famílias têm teste próprio, que lê o CÓDIGO que as
    # gera em vez de repetir a lista à mão.
    "retrieval.attempted", "retrieval.succeeded", "retrieval.failed",
    "cognitive.state_declared", "metacog.observed", "metacog.reviewed",
    "analogy.registered", "analogy.promoted",
    # operação e manutenção
    "doctor.repaired", "backup.created", "backup.restored",
    "config.tuned", "config.rolled_back", "behavior.streams_reset",
    "reference.imported", "eval.done", "lora.dataset",
    "review.scheduled", "review.done", "review.completed",
    "themes.adopt_refused",
    # jornada cognitiva — TRÊS segmentos, e é por isso que a varredura
    # estática sozinha não bastava: a primeira versão dela só casava
    # `canal.evento` e deu verde com estes nove de fora. Quem os pegou foi a
    # recusa em runtime, ao rodar a suíte. As duas guardas cobrem buracos
    # diferentes, e nenhuma das duas cobre o do outro.
    "focus.goal.created", "focus.node.promoted", "focus.node.suppressed",
    "focus.projection.generated", "metacognitive.experience.reported",
    "cognitive.session.started", "cognitive.session.suspended",
    "cognitive.session.resumed", "cognitive.session.completed",
})


class EventTypeNaoDeclarado(ValueError):
    """Tipo de evento fora de `EVENT_TYPES` — a UI nunca o receberia."""


class EventBus:
    def __init__(self, db: Connection):
        self.db = db
        self._lock = threading.Lock()
        self._subscribers: list[_queue.Queue] = []

    def emit(self, channel: str, type: str, data: dict | None = None) -> int:
        if type not in EVENT_TYPES:
            raise EventTypeNaoDeclarado(
                f"tipo de evento não declarado: {type!r} — acrescente em "
                f"runtime/events.py:EVENT_TYPES, senão `/events/types` não o "
                f"lista e a UI nunca o recebe (o EventSource só entrega "
                f"evento nomeado a quem registrou aquele nome)")
        payload = json.dumps(data or {}, default=str)
        with self._lock:
            cur = self.db.execute(
                "INSERT INTO events(channel,type,data,created_at) VALUES (?,?,?,?)",
                (channel, type, payload, time.time()))
            self.db.commit()
            seq = cur.lastrowid
            event = {"seq": seq, "channel": channel, "type": type,
                     "data": data or {}}
            for q in list(self._subscribers):
                try:
                    q.put_nowait(event)
                except _queue.Full:
                    pass
        return seq

    def subscribe(self) -> _queue.Queue:
        q: _queue.Queue = _queue.Queue(maxsize=500)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: _queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def tail(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT seq,channel,type,data,created_at FROM events "
            "ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
