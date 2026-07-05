# 01 · Conceitos abstratos

> O QUE o sistema acredita. Cada conceito aqui tem um mecanismo concreto
> (documento 05) e um fundamento teórico (documento 03). Este documento é
> o vocabulário compartilhado — quando dois módulos discordarem sobre um
> termo, este texto arbitra.

## 1. A tese central: memória como compilação

O LLM Wiki trata conhecimento pessoal como um **alvo de compilação**:
fontes brutas (`raw/`) são *código-fonte*; páginas OKF versionadas em Git
são o *binário auditável*; o índice SQLite é um *artefato derivado*
sempre reconstruível. As consequências dessa metáfora são normativas:

- **Determinismo antes de modelo**: tudo que regex/checksum/grafo resolve
  não passa por LLM. O LLM é um estágio da pipeline cercado por passadas
  determinísticas (o "sanduíche", doc 02 §1) — nunca a autoridade final.
- **O índice nunca é a verdade**: `index.db` pode ser apagado e
  reconstruído (`llmwiki okf index`) sem perda. A verdade está no bundle
  + Git. Corolário: qualquer melhoria de retrieval é segura para
  experimentar — o pior caso é reindexar.
- **Git é o juiz**: toda escrita no bundle é um commit com trilha em
  `log.md`. Arquivar ≠ apagar; depreciar ≠ deletar; errar ≠ perder
  (reverter é `git revert`).

## 2. OKF — o formato de conhecimento aberto

Compatibilidade estrita com o **OKF v0.1** (GoogleCloudPlatform/
knowledge-catalog). O contrato mínimo:

- Página = Markdown com frontmatter YAML; **apenas `type` é obrigatório**;
  chaves desconhecidas são toleradas (`extra="allow"` no pydantic).
- `index.md` e `log.md` são **reservados** — não são conceitos; `index.md`
  de subdiretório não tem frontmatter; o da raiz pode ter apenas
  `okf_version`. Ausência de reservados **nunca** invalida o bundle;
  presença é validada.
- Identidade de página = caminho relativo sem `.md` (`concepts/grafo`).
- Links internos emitidos pelo writer são **Markdown bundle-absolutos**
  (`[t](/concepts/x.md)`); wikilinks `[[...]]` são aceitos na leitura e
  reescritos na compilação.

**Separação de camadas de validação** (invariante desde a v0.6):

| Camada | Escopo | Exemplo | Severidade típica |
|---|---|---|---|
| Conformidade OKF | Só o SPEC | link quebrado, frontmatter ausente | nunca inventa exigência: `# Citations` é SHOULD ⇒ zero findings |
| Política local | Nossas regras | privacy obrigatório, checksum inválido | pode ser `error` e bloquear escrita |

Um consumidor OKF externo lê nosso bundle sem saber que a política local
existe. **Toda extensão vive em chaves extras toleradas + tipos locais.**

## 3. As quatro camadas de memória

Mapeamento direto da taxonomia cognitiva para artefatos do sistema
(exposto em `GET /cockpit/memory`):

| Camada | Artefato | Mutação | Quem escreve |
|---|---|---|---|
| **Working** | tabela `events` (últimos N) | efêmera | runtime (jobs, daemon) |
| **Episódica** | `log.md` + histórico Git | append-only | writer (nunca reescrita) |
| **Semântica** | páginas `concept`, `decision`, `academic_paper`, `*_specification`, `field_profile`, `learning_note` | compilada, reconciliada, normalizada | sanduíche + humano |
| **Procedural** | páginas `runbook`, `skill` + adapter LoRA ativo | compilada; opcionalmente destilada em pesos | sanduíche + job `lora_train` |

Regra transversal: **a normalização (v0.8) só toca memória compilada**
(semântica + procedural). A episódica é verbatim por definição — o
mecanismo correto para ela é staleness, não reescrita.

## 4. Bi-temporalidade: tempo de mundo × tempo de código

Dois eixos temporais independentes que **coexistem** no frontmatter
(modelo do Graphiti/zep):

- `valid_at` / `invalid_at` — **tempo de MUNDO**: quando o fato passou a
  valer / deixou de valer na realidade. Alimenta o filtro `as_of` do
  `/ask` (perguntas com data despriorizam evidência fora da validade).
- `stale_as_of` — **tempo de CÓDIGO**: commit do repositório-alvo a
  partir do qual a página ficou suspeita. Para memória episódica de
  codebase.
- `superseded_by` — sucessão explícita: a página antiga ganha
  `invalid_at` + ponteiro para a nova. **Invalidar, nunca apagar** — a
  página continua respondível para `as_of` passado e presente no Git.

Coerência é política: `invalid_at ≤ valid_at` é `policy.temporal_order`
(error).

## 5. A escala única de confiança

Um único enum de três níveis (`extracted` / `inferred` / `ambiguous`)
qualifica **qualquer** artefato derivado — a mesma coluna, o mesmo
vocabulário, os mesmos pesos em todo o sistema:

| Onde | extracted | inferred | ambiguous |
|---|---|---|---|
| Data numérica | `25/12/2024` (dia>12 desambigua) | `05/07/2026` via locale | `13/13/2024` — descartada |
| Quantidade | separadores claros | milhar/decimal decidido por locale, unidade de 1 letra | — |
| Aresta do grafo | link Markdown escrito | co-menção de entidade | wikilink não resolvido |
| Reconciliação | identificador forte (DOI/ISBN/sha) | similaridade acima do corte | decisão do árbitro LLM |
| CEP | com hífen | — | sem hífen |

Consequências operacionais:
- **Reescrita** de superfície: só matches `extracted` (doc 02 §3).
- **Pesos do grafo** (Leiden): 1.0 / 0.5 / 0.15.
- **Anexo de entidades**: `ambiguous` nunca é indexado.

Filosofia: *um grafo que confessa incerteza vale mais que um grafo
confiantemente errado* — e isso vale para valores, não só arestas.

## 6. Controle de autoridade (biblioteconomia aplicada)

A curadoria de grafias canônicas não é código — é **memória**. Cada nome
canônico (stack, editora, publicação, organização, país, regulador,
unidade) é uma página `type: authority_record` no próprio bundle:

```yaml
type: authority_record
canonical: PostgreSQL
authority: stack          # stack|publisher|publication|org|country|regulator|unit
aliases: [postgres, pgsql, postgre]
qid: Q192490              # Wikidata — resolução externa de entidade
```

O normalizador compila (seeds embutidos ∪ authority_records) num único
autômato regex no load. Efeitos: curadoria versionada no Git, lintável
pelo Harness, editável no Explorer — **corrigir uma grafia é um commit,
não um deploy**. Termos com alto risco de falso positivo (`Go`, `R`,
`C`, `Rust`, `Nature`) estão em `UNSAFE_BARE`: nunca casam sozinhos.

## 7. Proveniência e a divisão máquina/humano

`generated_via` divide o mundo em dois regimes com deveres distintos:

| | Página de máquina (`api:*`, `local:*`) | Página humana (`human:*`) |
|---|---|---|
| `source_sha256` | **obrigatório** (o binário aponta para o fonte) | dispensado (campo `source` livre) |
| `# Citations` | obrigatório se `api:*` (política) | SHOULD (nunca finding) |
| Reescrita de grafia | aplicada; residual é `error` | nunca; sugestão é `info` |
| Identificador com DV inválido | `error` (alucinação) | `warn` |

Isso protege o gesto humano de promover conhecimento (fricção mínima)
enquanto mantém a máquina sob prova (fricção máxima).

## 8. Epistemologia operacional

Três mecanismos transformam "qualidade da memória" de impressão em
métrica:

1. **Abstenção** (LongMemEval, arXiv:2410.10813): sem evidência
   suficiente o `/ask` devolve `abstained: true` + `gaps` — nunca
   resposta fabricada. Toda resposta carrega `uncertainty` ∈ [0,1]
   (entropia normalizada da fusão): o sistema pode responder E confessar
   dúvida.
2. **Desfecho** (`useful` / `dead_end` / `corrected`): o julgamento do
   usuário é dado de primeira classe (`ask_outcomes`) e realimenta DOIS
   laços — o overlay de páginas (`preferred`/`tentative`/`contested`) e
   o crédito de streams (Hedge). Correção com nota vira memória nova no
   inbox: o erro é matéria-prima.
3. **Eval de 5 categorias** contra golden set versionado no bundle
   (`harness/golden_eval.jsonl`): extract · multi_session · temporal ·
   update · **abstain**. Mede o SISTEMA (retrieval+temporal+abstenção),
   não o modelo. A categoria abstain só passa com abstenção real —
   responder "não sei" quando não sabe é comportamento correto testável.

## 9. Privacidade topológica (LGPD estrutural)

`privacy: local_only | api_allowed` é obrigatório em toda página escrita.
O default do sistema é `local_only` — nada sai da máquina sem regra
explícita liberando. A cadeia é **detectada → marcada → podada**:

1. o detector de identificadores acha CPF/CNPJ/IBAN **com dígito
   verificador válido** (falso positivo não dispara);
2. a página é marcada `sensitive_data: true` e forçada `local_only`;
   se alguém tentar `api_allowed`, `policy.pii_requires_local` (error);
3. o roteador de modelos **nunca** envia conteúdo `local_only` para API.

A LGPD deixa de depender de tag manual: é aritmética (checksum) +
política (Harness) + roteamento (router).

## 10. Heat, uso e esquecimento reversível

`page_heat` acumula sinais de uso (leituras em evidência, citações
in-link, desfechos) num score baseado na **Base-Level Activation do
ACT-R** (lei de potência sobre a vida da memória — doc 03 §3.3), que
captura o efeito de espaçamento: uso distribuído no tempo vale mais que
rajada antiga. O job `reflect` deriva candidatos a **promoção** e
**arquivamento** — sempre sugestão para o humano, nunca ação automática.
Esquecer é reversível por construção: arquivar é mover página (commit),
e o Git guarda tudo.

## 10b. A pilha de camadas por tempo de memória (v0.12)

O esquecimento agora tem uma CAMADA própria, entre o bundle quente e o
histórico Git:

```
T0 working (events)   efêmera
T1 episódica (log.md) append-only, barata para sempre
T2 QUENTE  (bundle)   P(recall) ACT-R acima do limiar — respondível
T3 FRIA    (cold.db)  digest indexável + corpo zlib (MDL) — recuperável
T4 Git                imutável — o backstop de tudo
```

**Demoção T2→T3** (`FreezeMemory`): só passa pela cadeia de gates —
tipo não-protegido, sem dependentes (TMS), overlay ≠ preferred,
`P(recall) = σ((B−τ)/s)` abaixo do corte (o próprio modelo cognitivo
prevê que a memória não seria recuperada) e ociosidade mínima. `force`
humano dispensa os gates comportamentais, nunca os estruturais.

**Compactação MDL**: a entrada fria guarda o *digest* (título, headings,
entidades, ids fortes — o "modelo") descomprimido e indexável, e o corpo
integral comprimido (o "resíduo"). Esquecer reduz custo, não conteúdo.

**Promoção T3→T2 (reciclagem)** acontece por três portas: (1) fallback
do `/ask` — abstenção consulta a base fria e devolve `cold_matches`
(com `memory.auto_recycle`, reidrata e responde na mesma consulta);
(2) o reconciliador — fonte nova com o mesmo identificador forte de uma
memória congelada dispara `RECYCLE` (reidrata e atualiza, nunca
duplica); (3) gesto humano no Cockpit. Memória reciclada carrega o
contador `recycled:` no frontmatter — a própria história de idas e
vindas é dado.

## 11. Recorrência, dependência e contradição (v0.10)

Três conceitos fecham o governo epistêmico do bundle:

- **Consolidação por recorrência (CLS)**: o inbox é o hipocampo —
  captura barata, sem modelo; a síntese neocortical só dispara quando
  notas pendentes CONVERGEM (id forte compartilhado ou entidades em
  comum, detecção 100% determinística). Uma chamada de LLM por cluster.
- **Dependência (TMS)**: os in-links são justificativas registradas.
  Depreciar uma página lista seus `dependents` para revisão — a suspeita
  propaga; a invalidação, nunca.
- **Contradição candidata (AGM)**: o mesmo identificador forte em duas
  páginas sem relação de sucessão é sinal de duas versões da mesma
  verdade convivendo. O lint aponta (warn) e nomeia a mais entrincheirada
  (humana > máquina); resolver — supersede, fusão ou invalid_at — é
  decisão humana. **Schemas por tipo** completam o contrato: uma página
  `collection_specification` com `applies_to` declara campos obrigatórios
  para aquele `type`, e o Harness passa a exigi-los — validação curada no
  próprio bundle, como tudo mais.
