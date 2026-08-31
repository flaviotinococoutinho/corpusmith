# 11 · Contratos Epistêmicos & Generalization Envelope (ADR-38)

> **Especialidade deste documento:** epistemologia OPERACIONAL dos
> mecanismos heurísticos/adaptativos — o que cada um pode legitimamente
> alegar, sob quais pressupostos, e onde foi (e não foi) avaliado.
> Engenharia geral: [`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md).
> Fundamentos científicos: [`03-teoria.md`](03-teoria.md).

Fonte normativa: [`../epistemics.toml`](../epistemics.toml) · domínio puro:
`backend/src/corpusmith/epistemic/` · loader único: `harness/epistemics.py` ·
presa à realidade por `test_epistemics.py` + `test_epistemics_toml.py`.

## 1. Problema

O Corpusmith acumula mecanismos que **decidem sob incerteza**: fusão
RRF+Hedge, entropia de retrieval, abstenção, reconciliação
ADD/UPDATE/SUPERSEDE, prioridade cognitiva, mineração metacognitiva.
Cada um embute vieses indutivos, aproximações e limites — mas essas
premissas estavam espalhadas por código, ADRs e docs. O risco prático:
um humano (ou uma IA) lê uma métrica e **generaliza além do regime
avaliado**; ou trata uma heurística como garantia; ou lê a incerteza de
retrieval como probabilidade de verdade.

## 2. Objetivo

Registrar formalmente, POR MECANISMO, de forma legível por máquina,
validável e auditável:

1. a decisão tomada; 2. os vieses indutivos que a tornam possível;
3. os pressupostos que precisam valer; 4. o regime em que foi avaliado;
5. a garantia RELATIVA alegável; 6. os failure modes conhecidos;
7. quando abster/degradar/pedir revisão humana; 8. as evidências
empíricas; 9. os contextos ainda NÃO avaliados.

Não é uma ontologia filosófica: é infraestrutura operacional pequena,
com lint, CLI, API e painel usando **uma única implementação**.

## 3. Fundamento (e o que ele NÃO autoriza)

- **No Free Lunch (Wolpert & Macready)** motiva a regra central daqui:
  nenhum mecanismo tem `universal_guarantee` (o lint REJEITA `true`).
  Todo desempenho é relativo a uma distribuição de problemas — por isso
  cada contrato declara `validity_scope` e cada avaliação declara seu
  envelope. NFL **não** autoriza "qualquer heurística serve": dentro de
  um escopo declarado, heurísticas são comparáveis e mensuráveis.
- **Statistical Learning Theory** lembra que generalização exige
  declarar classe de hipóteses, amostra, perda e regime. Nenhum contrato
  alega bound da SLT sem esses elementos — na prática, os mecanismos
  daqui alegam menos: garantia `heuristic`, `property_tested` ou
  `online_regret_relative` com o referencial explícito.
- **Independência de validação**: um sistema não se valida apenas por
  métricas que ele próprio produz. Isso MOTIVA a regra
  `epistemic.self_certification_only` (evidência composta só de
  `self_reported` é erro). Teoremas de incompletude **não** fornecem
  bounds de generalização para ML e não podem aparecer como
  justificativa em contrato (`epistemic.forbidden_justification`) — o
  que fica é a postura: exigir golden set, feedback humano, regra
  determinística ou validador independente.

## 4. Tipos de garantia (vocabulário fechado)

| `guarantee_kind` | Significa | Exemplo aqui |
|---|---|---|
| `deterministic` | mesma entrada ⇒ mesma saída, por construção | degrau de identificador forte |
| `property_tested` | propriedade formal verificada por teste | monotonicidade do score cognitivo |
| `empirical` / `calibrated_empirical` | medido em avaliação (exige envelope) | — (exigem `evaluated_by`) |
| `online_regret_relative` | competitivo com o melhor expert fixo OBSERVADO | Hedge sobre streams |
| `heuristic` | regra plausível com referencial declarado, sem bound | reconciliação, abstenção |
| `probabilistic` / `formal` / `none` | reservados | — |

Heurística ≠ propriedade testada ≠ garantia formal: a primeira pode
falhar silenciosamente dentro do escopo; a segunda garante UMA
propriedade (não otimalidade); a terceira não existe em nenhum mecanismo
atual — e o registro torna isso visível em vez de deixar subentendido.

## 5. Incerteza de retrieval ≠ confiança factual

A `uncertainty` do `/ask` é **entropia normalizada da distribuição de
scores fundidos** (top-12): mede DISPERSÃO de evidência. Frases
corretas: "a evidência está espalhada"; "o sistema não sabe onde está a
resposta". Frases ERRADAS: "há 30% de chance de ser verdade"; "confiança
factual de 70%". Pode haver evidência **concentrada e incorreta**
(entropia baixa, resposta errada). O eixo factual é outro: desfechos
observados (useful/dead_end) e calibração Brier — e o contrato
`retrieval_uncertainty` registra que `ask_context.confidence`
(= 1 − uncertainty) herda essa limitação.

## 6. Estrutura do `epistemics.toml`

```toml
schema_version = 1
[registry]
version = "1.0.0"

[mechanisms.<id>]
title / decision / implementation_refs
inductive_biases / assumptions / validity_scope / known_failure_modes
guarantee_kind / guarantee_relative_to / universal_guarantee (= false!)
fallback / adaptive / feedback_signal
composite / composite_components
evidence / evaluated_by / misinterpretations
high_impact / abstention_supported / human_review_available
[mechanisms.<id>.parameters]      # constantes CRUZADAS com o código
```

Regras do lint (códigos estáveis): `contract_missing_bias`,
`contract_missing_scope`, `guarantee_unbounded` (universal OU sem
referencial), `failure_modes_missing` (heurísticos),
`evaluation_missing` (empíricos), `fallback_missing` (alto impacto),
`feedback_signal_missing` (adaptativos), `components_missing`
(compostos), `implementation_ref_missing`, `invalid_vocabulary`,
`unknown_field`, `self_certification_only`, `forbidden_justification`.

## 7. Mecanismos registrados (v1.6)

| id | decide | garantia (relativa a) | fallback |
|---|---|---|---|
| `retrieval_rrf_hedge` | ordenar evidências | regret relativo ao melhor stream fixo observado (clamp troca bound por exploração) | degrade |
| `retrieval_uncertainty` | quantificar dispersão | heurística — dispersão, NÃO verdade | no_decision |
| `abstention` | responder ou confessar | limiar sobre top_score; graded no golden | abstain + base fria |
| `reconciliation` | ADD/UPDATE/SUPERSEDE/NOOP/RECYCLE | escada determinística → cortes HI/LO | duplicar na dúvida (reversível > destrutivo) |
| `cognitive_priority` | ordenar atenção | monotonicidade testada; NÃO otimalidade | revisão humana |
| `adaptive_strategy_selection` | como explicar | pesos multiplicativos SEM bound formal no regime bandit | estratégia declarada |
| `metacog_observation_mining` | propor hipóteses | cortes declarados + gate humano obrigatório | revisão humana / silêncio |

Dívida registrada: `expected_information_gain` no score cognitivo é
**proxy heurístico** (lacuna × conectividade), não ganho de informação
esperado formal. O nome externo é preservado por compatibilidade; o
contrato e este doc marcam a natureza de proxy (ADR-38).

## 8. Generalization Envelope

Toda execução do eval (`eval_memory`) grava, por mecanismo com
`evaluated_by = ["eval_memory"]`, um envelope em
`runtime.db:evaluation_envelopes` (schema v7): dataset + **sha256**,
amostra, categorias, faixa temporal, HEAD do bundle, versão do produto e
da política, métricas, exclusões conhecidas e contextos fora de escopo.
Regra pura (`envelope_status`): amostra < `epistemics.min_sample`
(default 20) ⇒ `partially_evaluated`; zero ⇒ `unevaluated`. **Uma
métrica sem envelope não autoriza generalização.**

## 9. Fluxo de avaliação

```
golden_eval.jsonl ──► eval_memory ──► eval_runs (como antes)
                          └────────► evaluation_envelopes (v1.6)
corpusmith epistemics lint|list|show|evaluations   ┐
GET /cockpit/epistemics[/{id}[/evaluations]]    ├─ MESMA fonte
painel Qualidade → seção "Contratos epistêmicos"┘  (harness/epistemics)
```

## 10. Limitações (desta entrega)

- só o `eval_memory` gera envelopes; benchmarks (QA-2) e sensibilidade
  de constantes (QA-4) ainda não alimentam o registro;
- `drifted`/`invalidated` existem no vocabulário mas nenhum detector os
  seta automaticamente (porta: comparar envelopes consecutivos);
- idiomas/domínios do golden não são extraídos por caso (campos vazios
  com exclusão declarada);
- ~~o golden set não é distribuído por default~~ — **pago pelo QA-1**:
  `seed_golden_eval` distribui 10+ casos out-of-the-box e o eval deixa de
  ser no-op (idempotente: nunca sobrescreve golden curado pelo usuário);
- contratos cobrem **24 mecanismos** (registry 1.14.0) — a fonte viva é
  `epistemics.toml` (`[registry].version` + `EXPECTED_MECHANISMS` no
  lint; este documento não acompanha o conjunto entrada a entrada; a
  consolidação e o freeze/recycle, listados aqui como devidos, ganharam
  contrato desde então). Candidatos ainda sem contrato: staleness e o
  lint de citações — declarados devidos no
  [`18`](18-backlog-consolidado.md) (F-EPIST).
