# 09 · Backlog — estado de fechamento (v1.0)

> Última auditoria: v1.0. Tudo que foi pedido nas 22 rodadas está
> ✅ entregue, ⏳ aguardando volume de uso (porta com condição de
> entrada em ADR), ou ❌ rejeitado com razão registrada.

## ✅ Entregue (com teste)
Núcleo OKF/Harness/daemon/Cockpit (v0.7–0.15) · qualidade epistêmica
(normalize, autoridade, reconcile, bi-temporal, eval, abstenção) ·
arquitetura como asserção (camadas, pureza, template fechado, domínio
sem transporte, memória⊬cognitivo) · base fria T3 + reciclagem ·
NFRs (config-linhagem+rollback, snowflake tracing, health profunda,
HATEOAS, seleção adaptativa LSH) · pipelines configuráveis · convívio
cognitivo (estado declarado, resposta adaptativa, calibração Brier,
metacognição com gate, economia de atenção) · Cognitive Experience
Domain (jornada FocusGoal→…→ResumeCapsule, canônico byte-idêntico) ·
profundidade validada, experiências Efklides, analogias com ruptura
obrigatória, CurationProjection, métricas §17 · VoI, fading,
intercalação, Toulmin, tipos epistemológicos, episódios ·
reference.db com precedência e má-atribuição · Docker Compose + seeds ·
leitura de rede de texto (intermediação de Brandes, lacunas estruturais
com pergunta-ponte, estrutura do discurso — InfraNodus próprio, v1.1) ·
grafo com articulação e arestas-fantasma clicáveis (v1.1.1) · lint de
atribuição de citação no corpus (`policy.quotation_attribution`, v1.2).

## ⏳ Portas abertas — dependem de VOLUME DE USO (dados já coletados)
| Porta | Condição de entrada | ADR |
|---|---|---|
| FSRS por item | histórico de tentativas por página | 27 |
| IRT/psicometria leve | dezenas de itens exercitados | 31 |
| Learning-to-rank | centenas de desfechos | 31 |
| Auto-rollback por eval | série histórica de eval_runs | 14 |
| Métricas de abandono/aderência | semanas de sessões reais | 30 |

## ⏳ Portas abertas — dependem de CASO DE USO NOVO
| Porta | Condição | ADR |
|---|---|---|
| Servidor MCP (memória p/ agentes) | cliente agêntico real conectado | 15 |
| Contextual integrity granular | export seletivo/2º consumidor | 31 |
| DAG em pipelines | fan-out real num run | 18 |
| Avaliação de resposta por LLM | critérios explícitos + marca inferido | 26 |

## ❌ Rejeitados (não reabrir sem evidência nova)
GraphQL (ADR-15) · CRDTs/WFST/Verhoeff-Damm/steering vectors
(ADR-04…09) · métricas sem procedência (ADR-10) · bancos externos
(ADR-13) · algoritmos genéticos sobre config (ADR-14) · VARK/
inferência emocional/diagnóstico/perfil auto-reescrito (ADR-19/31).


## Backlog executável pós-auditoria (v1.3) — priorizado
| ID | P | Problema (evidência da auditoria) | Aceite |
|---|---|---|---|
| REL-1 | P0 | compile_source cria ModelRouter SEM governor ⇒ fura orçamento e ledger | gov injetado; ledger reflete compile; teste |
| ~~DATA-1~~ (v1.4) | P0 | sem verificação/repair de invariantes em runtime | `llmwiki doctor`: INV-001/002/003 + config×history; repair=rebuild |
| REL-2 | P1 | ~~heartbeat/timeout/cancel cooperativo (v1.4)~~; resta hard-kill de thread síncrona (REL-2b: isolamento de processo) | isolamento de processo p/ hard-kill |
| ~~REL-3~~ (v1.4) | P1 | recuperação de órfãos só preguiçosa | sweep no boot do daemon; teste |
| QA-1 | P1 | golden_eval.jsonl não é distribuído; eval é no-op out-of-the-box; sem Recall@K/MRR | seed com ≥10 casos (temporal/update/abstain); métricas fracionárias |
| QA-3 | P1 | /ask não valida [n]→evidência (só header, só api:) | validação estrutural p/ local: e api:; teste |
| UX-1 | P1 | 8 superfícies concorrentes de "o que fazer agora" | UMA fila unificada com origem explicada |
| UX-2 | P1 | 12 abas planas; jargão (BLA/Hedge/gate/trace) exposto | 3 níveis (essencial/análise/avançado); glossário aplicado |
| UX-3 | P1 | onboarding inexistente; bundle vazio = becos | workspace de exemplo removível + tutorial |
| UX-4 | P1 | presets não existem | ≥3 presets versionados via linhagem de config |
| QA-2 | P2 | claims 92×/29× sem harness reprodutível | bench.py frio×quente e full×incremental versionado |
| QA-4 | P2 | ~20 constantes de decisão sem teste de sensibilidade | testes paramétricos nos limiares críticos |
| UX-5 | P2 | analogias/métricas/curation-projection sem UI | superfícies mínimas ou remoção do anúncio |
