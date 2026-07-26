"""Agendador interno (Parte V §5.7): enfileira trabalhos recorrentes.

- revisão semanal (segunda-feira) — dedupe por semana ISO
- varredura de embeddings pendentes (diária)
- mapa de padrões (semanal) — F2-PR1

O `leiden` estava no REGISTRY de jobs e **nunca era enfileirado** (G-5 do
`docs/15`): quem quisesse o mapa atualizado tinha de saber que existe um
job e disparar à mão. Com o carimbo do F2-PR1, um mapa que ninguém recomputa
passa a ser um mapa que o doctor acusa de velho para sempre — o INV-004 sem
o agendamento seria um alarme sem saída.

**Semanal, não diário, e por medição.** O particionamento é a operação mais
cara fora do request, e o mapa de temas muda em escala de semanas, não de
horas: recomputar toda noite numa máquina pequena gasta a janela em que o
usuário poderia estar usando o produto. A urgência real é coberta por outro
caminho: quem quiser o mapa agora dispara o job (o INV-004 diz quando vale
a pena).
"""
from __future__ import annotations
import threading
import time
from .queue import JobQueue


class Scheduler(threading.Thread):
    def __init__(self, queue: JobQueue, interval: float = 300.0):
        super().__init__(daemon=True, name="llmwiki-scheduler")
        self.queue = queue
        self.interval = interval
        # `_halt`, não `_stop`: Thread usa `_stop()` como MÉTODO interno —
        # sombreá-lo com um Event quebra `join()` (TypeError)
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.is_set():
            now = time.localtime()
            if now.tm_wday == 0:                       # segunda-feira
                week = time.strftime("%Y-W%W")
                self.queue.enqueue("reflect", {}, priority=6,
                                   dedupe_key=f"reflect:{week}")
                self.queue.enqueue("review_weekly", {}, priority=6,
                                   dedupe_key=f"review:{week}")
                self.queue.enqueue("metacog", {}, priority=5,
                                   dedupe_key=f"metacog:{week}")
                # F2-PR1: prioridade BAIXA de propósito — o mapa de padrões
                # cede a vez para tudo que o usuário pediu
                self.queue.enqueue("leiden", {}, priority=7,
                                   dedupe_key=f"leiden:{week}")
            today = time.strftime("%Y-%m-%d")
            self.queue.enqueue("embed", {}, priority=3,
                               dedupe_key=f"embed:{today}")
            self.queue.enqueue("consolidate_inbox", {}, priority=4,
                               dedupe_key=f"consolidate:{today}")
            self._halt.wait(self.interval)
