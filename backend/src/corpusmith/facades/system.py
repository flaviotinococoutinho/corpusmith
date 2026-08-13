"""SystemFacade (F0, v1.8.1) — os invariantes do produto ganham porta.

`DiagnoseSystem` é o único verificador de INV-* do produto e vivia
alcançável APENAS por `corpusmith doctor` (cli.py): nenhuma facade, nenhum
endpoint, nada no Cockpit. Consequência prática: quem usa o app não tem
como saber que o índice está órfão, nem como reparar — e um invariante
novo (como o carimbo da camada de padrões, F2-PR1) nasceria invisível.

Sobre `known_jobs`: a checagem de `pipeline_runs` só roda quando recebe o
conjunto de tipos de job válidos (`diagnose.py`: sem ele a checagem é
silenciosamente desligada). O REGISTRY mora em `jobs/`, que importa
`facades/` — então a facade NÃO pode importá-lo de volta (seria ciclo, e
inverteria o gradiente de mutabilidade). Quem injeta é o adapter que já
conhece os dois lados: o daemon, via `build_app(known_jobs=...)`.
"""
from __future__ import annotations
from ..settings import Settings


class SystemFacade:
    def __init__(self, settings: Settings,
                 known_jobs: set[str] | None = None):
        self._settings = settings
        self._known_jobs = known_jobs or set()

    def doctor(self, *, repair: bool = False, notify=None) -> dict:
        """Invariantes INV-* + estado da camada nativa. `repair=True` só
        age nos invariantes declarados reparáveis (rebuild do índice) —
        nunca toca o canônico, que é a autoridade."""
        from ..usecases.diagnose import DiagnoseSystem
        return DiagnoseSystem(self._settings, repair=repair,
                              known_jobs=self._known_jobs,
                              notify=notify).execute()
