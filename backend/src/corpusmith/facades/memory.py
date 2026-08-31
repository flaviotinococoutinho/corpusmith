"""MemoryFacade — a memória em uso: perguntar, julgar, medir."""
from __future__ import annotations
from ..settings import Settings
from ..usecases.ask_memory import AskMemory
from ..usecases.evaluate_memory import EvaluateMemory
from ..usecases.record_outcome import RecordOutcome


class MemoryFacade:
    def __init__(self, settings: Settings, gov=None):
        self._settings = settings
        self._gov = gov

    def ask(self, query: str, *, deep: bool = False, local_only: bool = False,
            as_of: str | None = None) -> dict:
        return AskMemory(self._settings, query, deep=deep,
                         local_only=local_only, gov=self._gov,
                         as_of=as_of).execute()

    def record_outcome(self, *, verdict: str, ask_id: str | None = None,
                       note: str | None = None,
                       pages: list[str] | None = None) -> dict:
        return RecordOutcome(self._settings, verdict=verdict, ask_id=ask_id,
                             note=note, pages=pages).execute()

    def evaluate(self, notify=None) -> dict:
        return EvaluateMemory(self._settings, notify).execute()

    def stability(self, *, limit: int | None = None) -> dict:
        """O que menos muda (RFC-006 V3): recomputa a projeção de
        estabilidade editorial e devolve o ranking. Determinística para o
        mesmo HEAD; "estável" = quieto no eixo de EDIÇÃO, nunca "correto"."""
        from ..usecases.compute_stability import ComputeStability
        return ComputeStability(self._settings, limit=limit).execute()

    def difficulty(self, *, limit: int | None = None) -> dict:
        """Onde o estudo trava (RFC-006 V4): recomputa o índice composto
        de dificuldade de EXPLICAR e devolve o ranking. Página sem sinal
        sai com `medida=False` — silêncio não é facilidade."""
        from ..usecases.compute_difficulty import ComputeDifficulty
        return ComputeDifficulty(self._settings, limit=limit).execute()
