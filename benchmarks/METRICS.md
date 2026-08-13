# Declaração de métricas de estágio (ADR-39 §3)

Convenções GLOBAIS: unidade `_ms` = milissegundos (relógio MONOTÔNICO,
`time.monotonic`); `peak_rss_mb` = pico de RSS do processo em MiB
(`ru_maxrss`; Linux reporta KiB — convertido; macOS reportaria bytes);
janela = UMA execução da operação (o perfil viaja no RESULTADO — nada de
polling); `backend` ∈ python|rust (proveniência do ComputeKernel);
`algorithm_version` = versão declarada do algoritmo. Coleta:
`runtime/stages.py:StageProfile`. Propósito geral: decidir O QUE migrar
para Rust/subprocesso e detectar regressão — não SLA.

## ask.* (origem: usecases/ask_memory.py; cardinalidade: 1/consulta)

| Métrica | O que mede | Propósito decisório |
|---|---|---|
| ask.total_ms | consulta inteira | orçamento de latência do /ask |
| ask.normalize_ms | analyze() da pergunta | custo do gazetteer/detecção |
| ask.fts_ms | stream FTS5 | custo de busca lexical |
| ask.dense_ms | stream denso (só --deep) | custo de embeddings |
| ask.entity_lookup_ms | pesos por entidade + first_chunks | custo do stream de entidades |
| ask.graph_load_ms | obter snapshot do grafo (cache!) | eficácia do graph_cache |
| ask.ppr_ms | Personalized PageRank | ganho do backend nativo |
| ask.descend_ms | descida hierárquica (flag) | custo do stream descend |
| ask.fusion_ms | fusão RRF + overlay + temporal | custo da coordenação |
| ask.record_usage_ms | escrita de proveniência/heat | custo de I/O pós-fusão |
| ask.compose_ms | prompt + modelo/extrativo | custo de composição |
| ask.pages_considered | páginas únicas pré-fusão | cardinalidade da consulta |
| ask.chunks_considered | hits somados dos streams | idem |
| ask.graph_nodes / ask.graph_edges | tamanho do snapshot | escala do grafo |

## index.* (origem: retrieval/fts.py:rebuild_index; 1/execução)

| Métrica | O que mede | Propósito |
|---|---|---|
| index.total_ms | rebuild inteiro | orçamento de indexação |
| index.scan_ms | listagem de .md | custo do walk |
| index.git_delta_ms | delta prev HEAD→HEAD + sujos | custo do caminho git |
| index.hash_ms | sha256 (SÓ mudados no modo git) | bytes evitados |
| index.read_ms | reader.load das mudadas | custo de parse |
| index.page_process_ms | chunk+normalize+entidades+links (AGREGADO v1; split é porta da Fase 3) | custo de extração |
| index.sqlite_write_ms | commit | custo de escrita |
| index.pages_total / pages_changed | corpus × delta | eficácia do incremental |
| index.bytes_read | bytes lidos do bundle | gate "incremental não lê tudo" |
| index.chunks_created / entities_created / edges_created | Δ de linhas | cardinalidade produzida |
| (nota) delta | "git" \| "full" \| "full-hash (motivo)" | explicação full×incremental (§11) |

## consolidate.* (origem: usecases/consolidate_inbox.py; 1/execução)

| Métrica | O que mede | Propósito |
|---|---|---|
| consolidate.total_ms | consolidação inteira | orçamento do job |
| consolidate.sketch_ms | extract+analyze+SimHash do lote (AGREGADO; o SimHash isolado é medido no bench consolidate) | custo de assinatura |
| consolidate.band_index_ms | montagem dos baldes LSH | custo do índice invertido |
| consolidate.candidate_generation_ms | pares dos baldes | custo da geração |
| consolidate.cluster_ms | converges_with + union-find | custo da verificação |
| consolidate.documents / raw_pairs / candidate_pairs / clusters | n · n(n−1)/2 · candidatos · clusters | seletividade do LSH |
| (n/a nesta base) jaccard_ms / ncd_ms | Jaccard/NCD vivem no RECONCILE, não na consolidação — medidos lá quando instrumentado (porta) | — |

## topology.* (origem: bench graph; por execução de bench)

Brandes/PPR/components são medidos pelo `corpusmith bench graph`
(p50/p95/mean por backend + nodes/edges/iterations implícitos na
semente). O observatório (/cockpit/gaps) consome os mesmos kernels.

## graph_cache (origem: compute/graph_cache.py; contadores de processo)

hits · misses · builds · invalidations + geração/nós/arestas por
backend — expostos em `doctor` e no bench ask. Propósito: provar que o
/ask quente NÃO reconstrói o grafo (gate §18).
