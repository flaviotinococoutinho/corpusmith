# 08 · Registro de decisões arquiteturais (ADRs)

> Decisões deliberadas sobre conceitos avaliados — adotados, adaptados e
> **rejeitados com razão registrada**, para que a mesma discussão não se
> repita sem fatos novos. Formato: contexto → decisão → consequência.
> Origem: revisão de conceitos de neurociência computacional, lógica
> formal, teoria de categorias e sistemas distribuídos (2026-07).

## Adotados (v0.10)

### ADR-01 — Consolidação por recorrência (CLS)
**Contexto**: consolidação ávida (LLM a cada nota) desperdiça tokens; a
teoria CLS (McClelland et al. 1995) separa captura rápida de síntese
lenta. **Decisão**: `ConsolidateInbox` — recorrência detectada
DETERMINISTICAMENTE (id forte ∨ ≥2 entidades canônicas compartilhadas,
via anexo do normalize; sem embeddings); uma chamada de LLM por cluster;
"esquecimento como default" da proposta original **rejeitado** (conflita
com "invalidar, nunca apagar" — raw/ e Git são backstop).
**Consequência**: custo de modelo proporcional a clusters, não a notas.

### ADR-02 — Heat por Base-Level Activation (ACT-R)
**Contexto**: o decaimento exponencial sobre o último acesso ignora o
efeito de espaçamento. **Decisão**: BLA com aproximação de aprendizado
otimizado (`kernel/activation.py`, d=0.5), `first_seen` em `page_heat`,
score em [0,1]. **Rejeitado no mesmo pacote**: *activation steering
vectors* — exigem acesso white-box às ativações residuais do modelo, que
nem Ollama nem a API expõem; só viável trocando o stack de inferência.

### ADR-03 — Propagação de staleness (TMS)
**Contexto**: depreciar uma página deixava os citadores intactos na
aparência. **Decisão**: in-links do grafo = justificativas (Doyle 1979);
`mark_stale`/SUPERSEDE listam/notificam `dependents`. Propagação de
SUSPEITA para revisão humana — nunca invalidação em cascata.

### ADR-04 — AGM como especificação, não como motor
**Contexto**: AGM completo exige fecho lógico — indefinido sobre prosa
Markdown; NLI no gate seria probabilístico no único ponto 100%
determinístico do sistema. **Decisão**: expansão/contração/revisão já
mapeiam para ADD/stale/SUPERSEDE; adicionada a detecção determinística
`policy.contradiction_candidate` (mesmo id forte, sem sucessão) com
entrincheiramento (humana > máquina) no finding; Recovery substituído
pelo versionamento Git. **Rejeitado**: NLI no gate de escrita.

### ADR-05 — Schemas por tipo (DTT "lite")
**Contexto**: DTT/Curry-Howard plenos (provas como termos) matariam o
fluxo de captura. **Decisão**: `collection_specification` com
`applies_to`+`required_fields` vira contrato executável
(`policy.schema_required_field`) — "tipo dependente do valor de `type`"
curado no bundle. O "resíduo de Kan" da proposta categórica reduz-se ao
subproduto natural: mudou o schema, o lint lista quem não conforma.
**Rejeitado**: provador de teoremas (Lean/Coq) no caminho da wiki.

### ADR-06 — Cache de derivados por HEAD do kb
**Contexto**: gazetteer/schemas varriam o bundle inteiro a cada
ask/lint/compile. **Decisão**: cache de 1 entrada keyed por `(kb, HEAD)`
— toda escrita commita, logo o HEAD é chave de invalidação perfeita.
Medido: ~92× no hit já em bundle mínimo (frio cresce linear; quente é
constante). Sem HEAD legível ⇒ sem cache (correto por construção).

## Rejeitados (com porta de reentrada)

### ADR-07 — CRDTs como substrato de memória
**Rejeitado**: resolvem multi-master concorrente — problema que o
projeto não tem (single-writer + lock + escritas raras). Adotá-los
substituiria **Git como juiz de merge**, invariante central de
auditabilidade. Os contadores (heat/outcomes) já são comutativos/
idempotentes por construção. **Porta de reentrada**: se subagentes
paralelos escreverem no bundle, o caminho alinhado é worktree/branch Git
+ `ReconcileCandidate` como merge driver — o reconciliador JÁ é a função
de merge semântica.

### ADR-08 — WFSTs para coordenação de retrievers
**Rejeitado**: composição de transdutores exige pesos num semiring comum
entre retrievers heterogêneos — exatamente o problema que o RRF evita
usando só posições; Hedge já adiciona aprendizado de pesos. Sem ganho
mensurável no volume local. **Reentrada**: nenhuma prevista.

### ADR-09 — Verhoeff/Damm como validadores
**Rejeitado por má aplicação**: são algoritmos para PROJETAR dígitos
verificadores de identificadores novos; nenhum identificador ingerido
(CPF, CNPJ, ISBN, ISSN, ORCID, IBAN, EAN) os usa — cada um tem seu
algoritmo oficial, já implementado com vetores-golden.

### ADR-10 — Métricas sem procedência
**Rejeitado como base de decisão**: números como "retenção >73%",
"mitigação de 74,40%", "MHM-LRU" e "O(K×L)" não têm fonte verificável.
Pelo padrão do projeto (doc 03 §4), claims sem reprodutibilidade não
dirigem arquitetura. **Reentrada**: papers citáveis com metodologia.

### ADR-11 — Formalismo categórico (coprefeixes/Kan)
**Rejeitado o formalismo, extraída a métrica**: a "medida de resíduo na
mudança de regime representacional" é útil e virou, na prática, o
relatório de não-conformidade pós-mudança de schema (ADR-05). Functores
explícitos não pagam o custo de manutenção aqui. **Reentrada**: se o
bundle ganhar schemas migráveis versionados com transformações
automáticas.
