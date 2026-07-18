# 09 · Backlog — estado de fechamento (v1.5)

> Última auditoria: validação da spec **BC-ENG-001** sobre o baseline
> 1.4.0 (ver [`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md)
> §21); a rodada de consolidação de doc é a v1.5 (ADR-37). Tudo que foi
> pedido está ✅ entregue, ⏳ aguardando volume de uso
> (porta com condição de entrada em ADR), 🎯 alvo de engenharia proposto
> (rastreado em `10` §21, achados A-01…A-10), ou ❌ rejeitado com razão
> registrada.

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
| ~~REL-1~~ (v1.6.1) | P0 | compile_source criava ModelRouter SEM governor ⇒ furava orçamento e ledger (idem consolidate/leiden/ask enfileirado) | `JobContext.gov` → adapters → facades → usecases; `test_rel1_governor.py` (fiação worker→router + ledger) |
| ~~DATA-1~~ (v1.4) | P0 | sem verificação/repair de invariantes em runtime | `llmwiki doctor`: INV-001/002/003 + config×history; repair=rebuild |
| REL-2 | P1 | ~~heartbeat/timeout/cancel cooperativo (v1.4)~~; resta hard-kill de thread síncrona (REL-2b: isolamento de processo) | isolamento de processo p/ hard-kill |
| ~~REL-3~~ (v1.4) | P1 | recuperação de órfãos só preguiçosa | sweep no boot do daemon; teste |
| ~~QA-1~~ (v1.6.3) | P1 | golden_eval.jsonl não era distribuído; eval era no-op out-of-the-box; sem Recall@K/MRR | `llmwiki seed` → `seed_golden_eval` (7 páginas + 12 casos, 5 categorias, 12/12 local); recall@5 + MRR por caso e média no envelope; `test_qa1_eval_seed.py` |
| ~~QA-3~~ (v1.6.2) | P1 | /ask não validava [n]→evidência (só header, só api:) | `_invalid_citations` em ask_memory (local: E api:); citação fabricada degrada p/ extrativo; `test_qa3_citations.py` |
| UX-1 | P1 | 8 superfícies concorrentes de "o que fazer agora" | UMA fila unificada com origem explicada |
| UX-2 | P1 | 12 abas planas; jargão (BLA/Hedge/gate/trace) exposto | 3 níveis (essencial/análise/avançado); glossário aplicado |
| UX-3 | P1 | onboarding inexistente; bundle vazio = becos | workspace de exemplo removível + tutorial |
| ~~UX-4~~ (v1.6.5) | P1 | presets não existiam | 3 presets (fabrica·precisao·exploracao) aplicados PELA linhagem (`TuneConfig`, source=preset:<nome>, guard+rollback); `GET/POST /cockpit/config/preset*`; botões 🎚 no card Linhagem da Curadoria; `test_ux4_presets.py` (10 testes) |
| ~~QA-2~~ (v1.6.4) | P2 | claims 92×/29× sem harness reprodutível | `llmwiki.bench` (bundle sintético determinístico, JSON schema 1): gazetteer frio×quente 236×@150/636×@500 (claim 92× era conservador); índice incremental 4–5× (1 pág) e 11–13× (no-op) — **claim 29× não reproduzido**, ADRs corrigidos; `test_qa2_bench.py` |
| ~~QA-4~~ (suíte, v1.6.3) | P2 | constantes de decisão sem teste de sensibilidade | `test_qa4_sensitivity.py` (17 testes, dois lados de cada fronteira): clamp Hedge, overlay 1.15/0.8 na fusão, abstain_threshold, orçamento do Governor, hamming ≤ 8, dígitos de citação; LSH/backoff já cobertos |
| UX-5 | P2 | analogias/métricas/curation-projection sem UI | superfícies mínimas ou remoção do anúncio |
| ~~A-06~~ (v1.5) | P2 | jitter de retry usava `hash()` do Python (randomizado por processo) | `_stable_jitter` blake2b; teste `test_retry_jitter_is_process_stable` |

## Achados de engenharia da spec BC-ENG-001 (rastreados em `10` §21)
Os riscos A-01…A-10 da validação de arquitetura (atomicidade do
BundleWriter, SUPERSEDE atômico, `StoragePolicy`, lease transacional,
tipos do frontend, outbox, idempotência HTTP, hard-kill, OpenAPI→TS)
estão listados com prioridade, status e porta de reentrada em
[`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md) §21, para
não duplicar a tabela. A-06 já foi corrigido (acima).
