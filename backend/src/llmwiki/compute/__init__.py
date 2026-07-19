"""ComputeKernel — a PORTA do compute plane (ADR-39, v1.7).

Princípio: **Rust calcula sinais e projeções; Python decide seu
significado.** Nenhum backend daqui decide ADD/UPDATE/SUPERSEDE,
prioridade cognitiva final, abstenção, confiança epistemológica,
privacidade, escrita no bundle ou commits — isso é domínio Python.

- `PythonComputeKernel` é a implementação de REFERÊNCIA (sempre
  presente; o produto funciona sem Rust);
- `RustComputeKernel` acelera via extensão PyO3 (llmwiki_native),
  quando instalada e compatível;
- `get_kernel(settings)` seleciona por `compute.backend`
  (auto|python|rust) com fallback observável (motivo registrado).
"""
from .types import BackendInfo, GraphHandle
from .select import get_kernel, selection_report
from .graph_cache import graph_cache_stats

__all__ = ["BackendInfo", "GraphHandle", "get_kernel",
           "selection_report", "graph_cache_stats"]
