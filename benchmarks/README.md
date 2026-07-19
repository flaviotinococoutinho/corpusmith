# Benchmarks — harness reprodutível do compute plane (ADR-39)

Regra de ouro: **nenhum ganho é alegado sem medição registrada aqui.**
Números absolutos variam por máquina; as RAZÕES (speedups Python×Rust,
frio×quente, full×incremental) são o que os ADRs alegam.

## Comandos

```bash
cd backend
.venv/bin/python -m llmwiki.bench core                    # QA-2 (frio×quente, full×incremental)
.venv/bin/python -m llmwiki.bench ask --pages 150         # /ask por estágio
.venv/bin/python -m llmwiki.bench graph --nodes 5000      # PPR/Brandes python×rust
.venv/bin/python -m llmwiki.bench consolidate             # SimHash/candidatos python×rust
.venv/bin/python -m llmwiki.bench compare                 # tudo + speedups
.venv/bin/python -m llmwiki.bench generate-fixture small  # materializa fixture
# ou: .venv/bin/python -m llmwiki.cli bench <verbo> ...
```

Saída: JSON schema 1 (`--json arquivo`). Fixtures são determinísticas
por semente (`fixtures/<nome>/spec.json`); o bundle materializado
(`home/`) não é versionado — regenerável byte-a-byte.

## Baseline vigente

`baseline.json` — capturada nesta máquina em v1.7.0 (dev). Destaques
MEDIDOS (não estimados):

| Workload | Python | Rust | Speedup |
|---|---:|---:|---:|
| PPR (5000 nós, 20k arestas, p50) | 183.7 ms | 1.9 ms | **97.7×** |
| Brandes (idem, p50) | 88.1 s | 1.9 s | **45.3×** |
| SimHash lote (440 docs, p50) | 800.2 ms | 13.5 ms | **59.1×** |
| Pares candidatos LSH (p50) | 6.4 ms | 0.4 ms | 16.0× |
| Índice incremental 1 página (git delta) | 190 KB lidos → **130 bytes** | — | bytes 1460× |

Igualdade verificada junto com a velocidade: os pares candidatos são
IDÊNTICOS entre backends (asserção dentro do próprio bench) e
PPR/Brandes coincidem com |Δ| ≤ 1e-8 (test_compute_differential).

## METRICS.md

Toda métrica de estágio (ask.*, index.*, consolidate.*) é declarada em
[`METRICS.md`](METRICS.md): unidade, origem, janela, cardinalidade,
versão do algoritmo, backend e propósito decisório.
