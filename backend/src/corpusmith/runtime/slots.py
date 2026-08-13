"""Controle de concorrência por classe de job (Parte V §5.4).

Jobs pesados (compile, lora, leiden, ocr) disputam poucos slots para não
saturar a máquina; leves (embed, review, rerank) têm mais folga.
"""
from __future__ import annotations
import threading
from contextlib import contextmanager

HEAVY = {"compile_source", "lora_train", "leiden", "ocr",
         "pipeline"}   # pipeline pode conter estágios pesados (v0.17)


class Slots:
    def __init__(self, heavy: int = 1, light: int = 2):
        self._sem = {
            "heavy": threading.Semaphore(heavy),
            "light": threading.Semaphore(light),
        }

    def kind(self, job_type: str) -> str:
        return "heavy" if job_type in HEAVY else "light"

    @contextmanager
    def hold(self, job_type: str):
        sem = self._sem[self.kind(job_type)]
        sem.acquire()
        try:
            yield
        finally:
            sem.release()
