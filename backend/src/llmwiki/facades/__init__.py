"""facades/ — orquestração dos use cases (v0.9).

Uma facade por área de negócio; os adapters (jobs/, api/, cli) só falam com
elas — nunca com use cases diretamente (regra garantida por teste de
arquitetura). A facade é o único lugar que sabe COMPOR casos de uso; cada
caso de uso continua sabendo fazer UMA coisa.
"""
from .compiler import CompilerFacade
from .curation import CurationFacade
from .memory import MemoryFacade

__all__ = ["CompilerFacade", "CurationFacade", "MemoryFacade"]
