# 08 · Registro de decisões arquiteturais (ADRs)

> **Altitude:** governança · **Status:** vivo

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
Medido (harness reprodutível `python -m corpusmith.bench`, QA-2/v1.6.4):
236× no hit a 150 páginas sintéticas e 636× a 500 — frio cresce linear,
quente é constante; o ~92× anterior (medição de sessão) era
CONSERVADOR. Sem HEAD legível ⇒ sem cache (correto por construção).

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

### ADR-12 — Base fria: esquecer = compactar com critério ACT-R (v0.12)
**Contexto**: candidatos a arquivamento acumulavam sem destino; apagar
viola "invalidar, nunca apagar"; manter tudo quente dilui o retrieval.
**Decisão**: camada T3 (`cold.db`) entre o bundle e o Git — digest
indexável (MDL) + corpo zlib; demoção validada pela equação de
recuperação do ACT-R (P(recall) < 0.05) mais gates estruturais (TMS,
overlay, tipos protegidos, ócio mínimo); promoção de volta por três
portas (fallback do ask, RECYCLE no reconciliador, gesto humano).
**Rejeitado no pacote**: expiração automática por TTL (tempo sozinho não
valida esquecimento — uso previsto valida) e apagamento definitivo (Git
continua sendo o backstop de tudo).

### ADR-13 — Garimpo de repositórios de memória (v0.13)
**Contexto**: triagem de ~60 repositórios + a paper list Agent-Memory
para reaproveitar mecanismos. Muitos já haviam sido minerados
(mem0→reconcile, MemoryOS/MemoryBear→heat, OpenViking→descend,
TencentDB→pipeline local, Zep→bi-temporal, LongMemEval→eval).
**Adotados**: HippoRAG/PPR (stream `graph` multi-hop), A-mem
(relacionadas determinísticas), índice incremental por sha+fingerprint
(o conceito de layout de Arrow/FlatBuffers/LSM reduzido ao nosso
invariante "índice derivado" — medido no harness reprodutível
(`corpusmith.bench`, QA-2/v1.6.4): 4–5× com 1 página alterada e 11–13× no
no-op, a 150–500 páginas sintéticas; o 29× anterior era medição de
sessão NÃO reproduzida — o custo fixo do caminho incremental
(gazetteer pós-commit + passada de grafo) domina nessa escala), SimHash
(Charikar) como sinal de near-duplicata na consolidação.
**Rejeitados**: trocar SQLite por LanceDB/memgraph/Milvus (viola
local-first + índice-derivado); Arrow/FlatBuffers/zerocopy como
DEPENDÊNCIAS (escala não justifica; o conceito foi absorvido);
compressão de KV-cache (H2O/SnapKV — internals de inferência sem
acesso); honcho/theory-of-mind (multiusuário fora do escopo); MemOS/
Letta scheduling (sobrepõe camadas existentes); ChromeKatz e openfold
(fora de escopo do projeto). **Reentrada**: vetores de verdade quando o
extra [ml] com sqlite-vec for ativado — o stream `dense` já existe.

### ADR-11 — Formalismo categórico (coprefeixes/Kan)
**Rejeitado o formalismo, extraída a métrica**: a "medida de resíduo na
mudança de regime representacional" é útil e virou, na prática, o
relatório de não-conformidade pós-mudança de schema (ADR-05). Functores
explícitos não pagam o custo de manutenção aqui. **Reentrada**: se o
bundle ganhar schemas migráveis versionados com transformações
automáticas.

### ADR-14 — Configuração como linhagem: ring de 30 + rollback (v0.16)
**Contexto**: pedido de config de negócio em banco com histórico dos
últimos 30 ajustes e retorno automático à anterior em caso de problema;
pesquisa de conceitos de sistemas evolutivos.
**Decisão**: `config_history` no runtime.db — cada ajuste é uma GERAÇÃO
(delta + snapshot completo + trace snowflake); o ring poda além de 30;
a vigente é a mais recente. Guard de fitness em três linhas: validação
de tipo/domínio antes de tocar o estado, probe pós-aplicação com
reversão automática, e `RollbackConfig` (endpoint/botão) reaplicando o
snapshot anterior em O(1). Do vocabulário evolutivo adotamos o que o
projeto JÁ pratica: variação (ajuste), seleção (guard + desfechos
Hedge), hereditariedade (snapshot completo por geração). **Rejeitados**:
algoritmos genéticos/neuroevolução sobre parâmetros (população de 1,
fitness caro e ruidoso — seleção dirigida por humano + guard basta) e
ler config do banco no boot (fonte de verdade continua Settings +
overrides.yaml; o banco é MEMÓRIA da linhagem, não autoridade).
**Reentrada**: auto-rollback dirigido por métricas (eval regredindo ⇒
voltar geração) quando houver série histórica de eval suficiente.

### ADR-15 — Contratos: HATEOAS sim; GraphQL não; MCP porta aberta (v0.16)
**Adotado**: REST com `_links` (raiz `/` como mapa navegável do serviço,
recursos apontando as transições prováveis) — custo zero de dependência
e o Cockpit/CLI navegam por relação. **Rejeitado GraphQL**: um único
consumidor local em localhost não tem problema de over/under-fetching
que justifique schema+runtime extras; o "resolver" real aqui é SQLite.
**MCP: porta explicitamente aberta** — expor a memória como servidor
MCP (tools: ask/promote/outcome) é a evolução natural de um cockpit de
memória AGÊNTICA, mas entra como adapter novo em `api/`, sem tocar
domínio; fica para quando houver um cliente agêntico real conectado.

### ADR-16 — Identidade snowflake de ponta a ponta (v0.16)
**Decisão**: ids de 63 bits (41b tempo · 6b módulo · 6b algoritmo ·
10b seq) em `kernel/identity.py` (puro), renderizados em Crockford
base32 que ordena como o tempo. `ask_id` agora É o trace (módulo=ask,
algoritmo=rrf — decodificável offline); todo `page.stage` carrega
`trace_id` da execução + `span` do passo; eventos de job herdam o
trace do worker; cada geração de config tem o seu; o daemon ganha
identidade de INSTÂNCIA por boot (aparece em `/`, `/health*`).
**Rejeitado**: UUID (não carrega tempo nem procedência; não ordena) e
OpenTelemetry como dependência (o barramento SSE + runtime.db já são o
coletor local; o formato não impede exportar depois).

### ADR-17 — Seleção adaptativa de algoritmo na consolidação (v0.16)
**Contexto**: `_cluster` comparava todos os pares — O(n²) era o
primeiro gargalo real apontado na avaliação funcional.
**Decisão**: a estrutura segue o tamanho do dado. n ≤
`consolidate.pairwise_max` (32) mantém pares (constante mínima); acima
disso, índice invertido por id forte e por entidade + 9 bandas LSH do
SimHash geram os candidatos. EXATO por construção: convergência exige
compartilhar id forte, entidade ou hamming ≤ 8 — e 9 bandas garantem
banda comum para hamming ≤ 8 (casa de pombos), então nenhum par
verdadeiro escapa; falsos positivos são re-verificados por
`converges_with`. **Rejeitado**: MinHash/LSH probabilístico (perderia
a garantia de zero falso negativo que o determinismo do projeto exige).

### ADR-18 — Pipelines configuráveis: orquestração como dado (v0.17)
**Contexto**: pedido de sistemas de pipelines configuráveis (espec. AI
Memory §11.4/EPIC-13: cadeia de estados, linhagem, transformações
plugáveis).
**Decisão**: um pipeline é um SPEC declarativo (`pipelines` no
runtime.db, JSON com estágios) — cada estágio referencia um job já
registrado, com `on_error: stop|continue` e passagem de resultado
(`"$prev.chave"` no payload). Executa como job `pipeline` (slot heavy)
pela MESMA fila; cada run tem trace snowflake, cada estágio um span, e
o filme fica em `pipeline_runs` (últimos 200) + eventos
`pipeline.stage`/`pipeline.done` no SSE. Builtin seedados idempotentes
(`absorver-inbox`, `manutencao-semanal`, `qualidade-total`), editáveis
e removíveis. **Invariantes preservados**: o pipeline orquestra ACIMA
do Template Method — estágios são os jobs de sempre (sanduíche,
reconciliação e gate DENTRO deles); configurar pipeline não abre
caminho de escrita fora do trilho. DIP: o use case recebe o registry
de handlers por injeção (`jobs/pipeline.py` injeta o REGISTRY real;
testes injetam fakes) — domínio segue sem conhecer a camada adapter.
**Rejeitados**: motor de workflow externo (Airflow/Temporal — um
processo local com fila SQLite não paga orquestrador distribuído),
DAG arbitrário com paralelismo (sequência cobre os casos reais; a
fila já paraleliza ENTRE jobs), e pipeline-dentro-de-pipeline
(recusado na validação — sem recursão). **Reentrada**: DAG quando
existir um caso real de fan-out dentro de um mesmo run.

### ADR-19 — Camada cognitiva: convívio com gate humano (v0.18)
**Contexto**: perfil cognitivo, estado contextual/carga, metacognição
assistida, resposta adaptativa e economia de atenção (EPICs 14/15/21/
22/23 da espec AI Memory), antes adiados por falta de formalismo.
**Adotados (cada um com forma fechada e teste):**
- *Cognitive Load Theory* (Sweller 1988): estado SEMPRE declarado
  (1..5, TTL 8h → neutro), nunca inferido; `delivery_budget` encolhe a
  entrega sob carga alta (evidências 8→5, tokens 1024→512, concisão).
- *Calibração* (Brier 1950; Lichtenstein 1982): confiança = 1−incerteza
  da fusão × desfecho `useful` ⇒ Brier + overconfidence + curva de
  confiabilidade (kernel/calibration.py, puro).
- *Resposta adaptativa* = Hedge sobre ESTRATÉGIAS de explicação
  (mesmo kernel dos streams; roleta ∝ peso à EXP3 para exploração);
  perfil DECLARADO vence o observado (`profile.preferred_strategy`).
- *Dificuldade desejável* (Bjork 1994; Roediger & Karpicke 2006):
  ganho de revisão = 4p(1−p) sobre o P(recall) ACT-R já existente —
  pico no esforço produtivo, trivial e perdido rendem pouco.
- *Economia de atenção* = mochila gulosa por densidade valor/custo
  (Dantzig 1957) sobre revisões + lacunas do Harness + inbox, com o
  porquê em cada item; carga alta poda blocos grandes.
- *Metacognição* (Flavell 1979; Nelson & Narens 1990): monitoramento =
  mineração DETERMINÍSTICA (SQL, suporte mínimo, dedupe, correlação
  jamais causalidade); controle = gate humano — aceitar aplica a
  suggestion PELA LINHAGEM de config (source=metacog, guard+rollback).
**Rejeitados**: "learning styles" VARK (Pashler et al. 2008 — sem
evidência; preferência aqui é peso Hedge treinado por desfecho, não
rótulo); inferência de emoção/saúde (restrição da própria espec);
incorporação automática de perfil (FR-14.3 — só com aceite); estado
inferido de comportamento (declarado ou nada). **Reentrada**: espaçamento
ótimo por item (FSRS) quando houver histórico de revisão por página.

## v0.19 — Cognitive Experience Domain (ADR-20 … ADR-29)

### ADR-20 — Confiança epistemológica ≠ acessibilidade cognitiva
**Contexto**: um único "confidence" mistura "isto é verdade?" com
"consigo lembrar disto?". **Decisão**: campos e BANCOS distintos —
confiança epistemológica mora no frontmatter canônico; acessibilidade é
a escada `none→recognition→recall→explanation→application→transfer→
critique` em cognitive.db, validada por prática. **Alternativa
rejeitada**: score único ponderado (irreversível e ilegível).
**Invariante (testado)**: falhar numa recuperação NUNCA altera
confiança/evidência/validade canônicas — bundle e index.db ficam
byte-idênticos após a jornada inteira. **Porta**: derivar "profundidade
validada por dimensão" quando houver volume de tentativas.

### ADR-21 — Cognitive Control Plane (domínios independentes)
**Contexto**: risco de a experiência "ajudar" editando a memória.
**Decisão**: `cognitive/` é núcleo PURO (stdlib; mesmo regime de
kernel/normalize, asserção de arquitetura) e a dependência é
unidirecional: adapters leem a memória governada e montam
`KnowledgeItemView`; o domínio projeta; a memória JAMAIS importa
cognitive/ (teste). O plano pode selecionar/ordenar/reduzir/ocultar/
recomendar; não pode alterar fatos, evidências, temporalidade ou grafo.
**Consequência**: testável sem SQLite/FastAPI/LLM/filesystem.
**Porta**: um port formal (Protocol) se surgir segundo consumidor.

### ADR-22 — Working set limitado e explícito (Baddeley como restrição)
**Decisão**: `CognitiveWorkingSet` com orçamento DECLARADO na política
(max_items/max_questions/max_cost_min/max_distance) — nada de "7±2"
como verdade psicológica: defaults configuráveis e versionados. Todo
corte é nomeado (`excluded_by_gate`, `trimmed_by_budget`).
**Invariante (testado)**: reduzir orçamento nunca AUMENTA a projeção
(subconjunto). **Porta**: orçamento por tokens quando a projeção
alimentar contexto de LLM diretamente.

### ADR-23 — Recuperação ≠ comprometimento (projection gate)
**Contexto**: `artifact recall != state commitment` (Agent Cognitive
Compressor). **Decisão**: o retrieval produz CANDIDATOS; o
`build_working_set` (gates duros → score → orçamento) decide o que
entra — e hard gate vence prioridade sempre (superseded/invalid/
privacy/escopo barram antes de qualquer número; testado: página
sensível com todos os sinais altos fica fora). **Porta**: gate
adicional por "custo de switching" quando houver medição real.

### ADR-24 — Score cognitivo configurável, decomposto, monotônico
**Decisão**: prioridade = Σ wᵢ·componenteᵢ − w_custo·custo, com QUATRO
famílias de peso separadas (cognitiva, estrutural, operacional,
agenda) — nunca um "weight" único; coeficientes na CognitivePolicy
versionada, snapshot persistido com a projeção (reproduzível).
Decomposição + razões saem com o número. **Invariante (testado)**:
subir user_focus não reduz o score. **Porta**: expected_information_
gain como componente quando houver eval por conceito.

### ADR-25 — ResumeCapsule (Leroy: attention residue)
**Decisão**: suspender uma sessão SEMPRE gera cápsula (objetivo, item
atual, última decisão, questões abertas, próximo passo, razão, versão
da política); retomar reconstrói dela. Máquina de estados explícita
active→suspended→active→completed com transições inválidas recusadas.
**Invariante (testado)**: suspensa e retomada mantém objetivo, questões
abertas e próxima ação. **Porta**: cápsula automática por inatividade.

### ADR-26 — Retrieval practice como cidadão de primeira classe
**Contexto**: apresentação não é aprendizagem (Roediger & Karpicke
2006). **Decisão**: `RetrievalAttempt` exige `confidence_before` ANTES
de conferir a fonte (matéria-prima de calibração — Brier já existe na
v0.18); exercícios tipados (recall/explain/apply/compare/critique/
transfer) mapeiam para a escada de acessibilidade; sucesso valida o
nível, falha zera a sequência sem rebaixar o nível. **Rejeitado**:
avaliação automática por LLM neste ciclo (auto-avaliação honesta +
gap de calibração explícito primeiro). **Porta**: LLM como avaliador
COM critérios explícitos e marca de inferido.

### ADR-27 — Agenda espaçada spaced-v1 (Cepeda)
**Decisão**: intervalo cresce ×2.2 no sucesso, reinicia na falha, e
falha CONFIANTE volta antes de todos (0.5d) — sobreconfiança é o erro
mais caro; teto = horizonte/3 (retenção desejada governa o
espaçamento). Parâmetros na política; decisão sai com `reason`.
**Rejeitado**: SM-2/FSRS completos agora (estado por item que ainda
não temos volume para calibrar). **Porta**: FSRS quando houver
histórico suficiente de tentativas por item (mesma tabela alimenta).

### ADR-28 — Metacognição declarada (Efklides) e nunca diagnóstico
**Decisão**: experiências metacognitivas são EVENTOS declarados e
revisáveis — o feedback tipado (§11: too_shallow/confusing/
missing_formalism/…) com escopo e imutabilidade cobre o vocabulário de
Efklides na prática; estado cognitivo é declarado (v0.18) e a mineração
de padrões continua com gate humano (ADR-19). **Rejeitado**: inferir
fluência/dificuldade de telemetria. **Porta**: tipos de experiência
dedicados (surpresa/conflito) se o feedback atual não bastar.

### ADR-29 — Política cognitiva versionada com a projeção
**Decisão**: toda projeção persiste o SNAPSHOT da política que a gerou
(policy_version dentro do working set; sessão herda a versão) — mesma
disciplina da linhagem de config (v0.16): reproduzir ontem usa a
política de ontem. Ajustes de coeficiente pelo usuário passam pela
validação estrutural (chave desconhecida/valor negativo ⇒ 400, nada
muda). **Porta**: guardar políticas nomeadas em tabela própria com
ring de gerações quando houver mais de um perfil de uso real.

### ADR-30 — Fechamento das portas da v0.19 (v0.20)
**Decisão** (quatro portas fechadas + uma nova entidade):
1. *Profundidade validada por dimensão* (porta do ADR-20): exercício →
   dimensão (mapa 1:1 honesto em `cognitive/progress.py`); nível
   validado = maior nível bem-sucedido; dimensões SEM instrumento
   (mathematical, historical) reportam `measurable=false` — nunca um
   número inventado. `GET /cognitive/goals/{id}/progress`.
2. *Experiências metacognitivas declaradas* (Efklides, porta do
   ADR-28): 11 tipos fechados (familiarity … formalism_no_intuition),
   intensidade 1..5, eventos revisáveis (declared|revised|retracted),
   chips na sessão do painel Foco.
3. *Analogias como entidade* (§10): contrato `new_analogy` RECUSA
   analogia sem pontos de ruptura declarados; vive em cognitive.db
   como draft/kept; promoção ao canônico SÓ por gesto humano via o
   PromoteToMemory de sempre (corpo carrega "Onde a analogia QUEBRA").
4. *CurationProjection* (§5.11): `GET /cognitive/curation` prioriza
   stale/contested/questions sob a ótica dos objetivos ativos —
   leitura pura, canônico intacto (testado).
5. *Métricas §17*: `GET /cognitive/metrics` — Brier das tentativas,
   delayed recall (≥1 dia), sucesso em apply/transfer, recorrência de
   erro, conclusão de revisões, latência de retomada. Computadas dos
   dados, nomeadas, sem rótulo psicológico.
**Também**: prompts de exercício DETERMINÍSTICOS (template por tipo —
LLM nenhum; a pergunta vem do template, a resposta da pessoa).
**Rejeitado de novo**: LLM avaliando respostas (continua na porta do
ADR-26); analogia gerada por LLM entra apenas como origin=llm marcada.

### ADR-31 — Triagem do mapa interdisciplinar (v0.21)
**Contexto**: mapa de 6 pilares/26 teorias proposto para validação.
**Já implementado e testado (não duplicar)**: Baddeley (working set),
Sweller (budgets/gates), Nelson-Narens (object/meta), Efklides (11
tipos declarados), Roediger-Karpicke (attempts), Cepeda (spaced-v1),
Bjork (4p(1−p)), Tulving/CLS (raw→consolidação, episódico=sessões+log),
ACT-R (acessibilidade≠verdade), Leroy (capsule), Dehaene (atenção→
ação→feedback→consolidação = fluxo da sessão), TMS, AGM-lite
(ADD/UPDATE/SUPERSEDE/CONTEST=overlay/REVIEW=stale), Brier/ECE, teoria
de controle (setpoint=profundidade desejada; damping=clamp Hedge +
min_support), IR híbrido (RRF/Hedge/PPR/FTS), DDD/hexagonal/FCIS/CQRS
(projeções derivadas)/event-sourcing seletivo (feedback/linhagem)/
policy-as-data/HITL/explainable ranking/privacy by design.
**Adotados nesta rodada (afinidade × custo)**:
1. Tipos epistemológicos de primeira classe (fact/claim/hypothesis/
   observation/opinion na taxonomia; conversão SÓ por SUPERSEDE);
2. Value of Information no score cognitivo (lacuna×unlock, peso
   próprio, SEPARADO de interesse pessoal);
3. Scaffolding com fading (worked_example→hint→none pela streak);
4. Intercalação na fila de revisão (round-robin estável por grupo);
5. Toulmin no exercício de crítica (claim/evidência/garantia/
   qualificador/réplica);
6. Memória episódica da experiência exposta (GET /cognitive/episodes —
   linha do tempo de sessões; nunca promovida automaticamente).
**Adiados com porta**: contextual integrity granular (scope/audience/
allowed_uses por memória — quando houver segundo consumidor/export
seletivo); IRT/psicometria (volume); learning-to-rank (volume);
A/B-replay determinístico (a infra de eventos já permite).
**Rejeitados (reafirmando §18)**: tipologias de personalidade, VARK,
neuromitos, inferência emocional, NLP-como-psicometria, diagnóstico
clínico, engajamento-como-aprendizagem, agente que reescreve perfil.

### ADR-32 — reference.db: referência do mundo em banco relacional (v0.22)
**Contexto**: a avaliação funcional (v0.15) apontou que dados
determinísticos DO MUNDO (nomes próprios, leis, equações, axiomas,
citações célebres) não são memória pessoal — pediam banco relacional
separado das outras estruturas.
**Decisão**: `reference.db` (4º banco: ref_terms, ref_quotations com
norma de matching, ref_facts law|equation|axiom|logic_rule) com seeds
idempotentes que NUNCA sobrescrevem dado importado pelo usuário.
Precedência no gazetteer: **authority_record (bundle) > ref_terms >
SEEDS** — colisão por canonical OU alias entrega o termo inteiro à
curadoria humana; import invalida o cache HEAD (não passa pelo Git).
Verificador de citação mal-atribuída (`/cockpit/reference/check`):
match determinístico por substring normalizada + comparação de autor
tolerante a iniciais — irmão dos check-digits (anti-alucinação).
**Rejeitado**: Wikidata/DBpedia como dependência online (viola
local-first; o import aceita qualquer dataset externo convertido) e
fuzzy matching de citação (falso positivo custa mais que falso
negativo — precision-first). **Porta fechada (v1.2)**: regra de lint corpus
`policy.quotation_attribution` — warn quando uma citação conhecida
aparece numa página sem o sobrenome do autor em lugar nenhum do texto
(sem atribuição OU mal-atribuída; a curadoria decide). Condição de
entrada satisfeita: as normas vêm pré-computadas do banco e o custo é
1 normalização de corpo + Q substrings por página — medido na suíte
(< 2s no lint completo com seeds). **Porta remanescente**: datasets
maiores via import (CSV→payload).

### ADR-33 — Fechamento v1.0: empacotamento, seeds e backlog auditado
**Decisão**: (1) Docker Compose com daemon empacotado (bootstrap+seed
no boot, healthcheck em /health, porta publicada só em 127.0.0.1 —
local-first vale no container; perfil `ml` opcional com Ollama em rede
interna); (2) migração de dados pré-definidos: `corpusmith seed`
idempotente (referência do mundo via db/seeds/reference_seed.json +
pipelines builtin — nunca sobrescreve dado do usuário); (3) backlog
auditado e FECHADO em docs/09-backlog.md — entregue × porta-por-volume
× porta-por-caso-de-uso × rejeitado; (4) limpeza auditada: jobs/
reconcile.py foi INVESTIGADO como artefato e MANTIDO (adapter de
compatibilidade v0.8 consumido por teste de contrato — remoção
quebraria a suíte; agora documentado no import). Versão da API: 1.0.0.
**Rejeitado**: empacotar o Electron no compose (desktop é nativo por
natureza; o daemon é o serviço) e seeds automáticos silenciosos fora
do boot explícito.

### ADR-34 — Leitura de rede de texto: InfraNodus como solução própria (v1.1)
**Contexto**: aplicar a ideia do InfraNodus (análise de rede de texto:
comunidades, intermediação, lacunas estruturais, pergunta geradora) à
experiência com a memória.
**Já tínhamos (~metade)**: comunidades (leiden), grafo visual
(GraphPanel estilo Obsidian), pontes frágeis (persistência 0-dim),
gaps epistêmicos (perguntas/órfãos/contestadas). **Novo e adotado**:
(1) intermediação de Brandes (`betweenness_centrality`, kernel puro) —
o articulador, não o mais citado; (2) LACUNAS ESTRUTURAIS
(`structural_gaps`) — o fio AUSENTE medido pelo déficit sob o modelo de
configuração de Newman (a MESMA hipótese nula da modularidade que o
Leiden já usa: sob fiação aleatória preservando graus, A e B
compartilhariam K_A·K_B/2m arestas; muito menos ⇒ lacuna); (3)
pergunta-ponte determinística que a lacuna gera, capturável como
`question` via o promote de sempre — fecha o laço de sensemaking
(Pirolli & Card); (4) estrutura do discurso (disperso/focado/diverso)
por entropia normalizada dos tamanhos de comunidade × conectividade
(reusa `shannon_entropy`). **Determinístico — LLM nenhum**: a
diferença do InfraNodus (que usa GPT para a ideação) é opcional aqui e
fica na porta do ADR-26. **Rejeitado**: dependência de grafo externo
(o kernel já faz union-find/persistência/Brandes sem libs) e o serviço
online do InfraNodus (viola local-first). **Porta fechada (v1.1.1)**: sizing dos nós do GraphPanel por
intermediação (raio = grau + articulação·16) e lacunas renderizadas
como ARESTAS-FANTASMA roxas pontilhadas entre os articuladores, com
"?" clicável no ponto médio que captura a pergunta-ponte como
`question` — o link ausente fica literalmente visível no grafo.
**Porta remanescente**: frase da pergunta-ponte por LLM local marcada
como inferida (continua na condição do ADR-26).

### ADR-35 — Auditoria multiagente e endurecimento P0 (v1.3)
**Contexto**: auditoria por 4 agentes independentes (dados, runtime,
recuperação, UX+crítico) com o CÓDIGO como fonte primária.
**Achados graves confirmados e CORRIGIDOS nesta rodada**:
(1) crash do scheduler por UNIQUE(dedupe_key) ao reenfileirar chave de
job concluído — enqueue agora libera a chave de jobs terminais;
(2) INV-003 violado: página supersedida era indexada, recuperada e
citada sem marca — agora filtro DURO na recuperação padrão, partição
bi-temporal decide sob as_of, evidência carrega `superseded`;
(3) divergência silenciosa do índice — index_meta agora carimba
`index_generation` (mudar chunking força full) e `bundle_head`;
(4) sem retry/cancel/DLQ — máquina de estados completa (retry_scheduled
com backoff+jitter, dead_lettered, cancel cooperativo, retry manual,
attempts coerente no lease);
(5) sem backup — backup lógico portátil com manifesto+sha256, verify,
restore --dry-run/force com pre-restore-* e rebuild da projeção,
recusa de schema mais novo; teste de desastre completo;
(6) 3 versões de produto divergentes — fonte única `__version__`;
schema_version carimbado em _meta por banco (check-first);
(7) compile sem idempotência — SKIP por sha do compile_cache;
(8) claims 92×/29× sem harness — marcadas como pendentes (QA-2).
**Registrado como backlog com evidência (não corrigido nesta rodada)**:
governor não injetado no router do compile (orçamento furado — REL-1);
timeout/heartbeat de job (REL-2); golden_eval.jsonl como seed real +
Recall@K/MRR (QA-1); harness dos multiplicadores (QA-2); verificação
de citação no /ask vivo (QA-3); consolidação das 8 superfícies de
"o que fazer agora" (UX-1); progressive disclosure em 3 níveis e
tradução de jargão (UX-2); onboarding com workspace de exemplo (UX-3);
presets de uso (UX-4); UI para analogias/métricas/curadoria projetada
(UX-5); constantes sem teste de sensibilidade (QA-4); sweep de startup
de órfãos (REL-3); doctor de invariantes com repair (DATA-1).

### ADR-36 — Integridade round 2: doctor, watchdog, quiescência, schema safety (v1.4)
**Contexto**: avaliação externa da v1.3 validou o rumo (fundações) e
apontou lacunas concretas na sequência recomendada. Esta rodada fecha
as fatíveis-e-testáveis aqui.
**Corrigido/adicionado (com teste)**:
- versão: fonte única `__version__` = 1.4.0 (README/pyproject alinhados
  — a v1.3 tinha pyproject=1.2.0, pego pela avaliação);
- `connect()` REJEITA banco de schema mais novo (`SchemaTooNewError`) —
  o acesso direto agora tem a proteção que só o restore tinha; ledger
  `schema_migrations(from→to, applied_at)` — trilha auditável;
- `corpusmith doctor [--repair]` (backlog DATA-1): INV-001 (índice órfão),
  INV-002 (geração/HEAD do índice), INV-003 (supersedida sem marca),
  PIPE (job inexistente), COG (acessibilidade órfã); repair reconstrói
  a projeção (FULL) — nunca toca o canônico; reverifica após reparar;
- watchdog de job (REL-2): HEARTBEAT renova o lease (job legítimo longo
  não é mais falso-órfão), TIMEOUT por classe marca cancel_requested;
- cancelamento COOPERATIVO real (não só "não publicar"): `JobContext`
  substitui o `emit`, expõe `.cancelled()`; `RunPipeline` consulta
  entre estágios e PARA no meio — testado (b não roda);
- sweep de órfãos no BOOT (REL-3): `recover_orphans` devolve leased/
  cancel_requested a queued na hora do restart, sem esperar o lease;
- backup por QUIESCÊNCIA (Frente A, consistência): `backup.lock` faz o
  worker parar de leasear; `_await_quiescence` espera nenhum job em voo
  antes do checkpoint+cópia — instante consistente, não cross-state.
**Limitação honesta registrada**: o timeout NÃO mata thread síncrona
CPU-bound do Python (sem isolamento de processo) — marca para não
publicar e evita re-execução por falso-órfão; hard-kill fica para
isolamento de processo (backlog REL-2b). CI verde no GitHub e default
branch continuam sendo ações de administração do repositório (fora do
alcance de `git push` nesta branch) — sinalizadas, não fingidas.

### ADR-37 — Validação da spec de engenharia (BC-ENG-001) e doc por especialidade (v1.5)
**Contexto**: a spec técnica **BC-ENG-001** (arquitetura AI-friendly) foi
submetida para validar solidez/alinhamento/escala/manutenibilidade e para
tornar a documentação legível por humano E por IA, separando as
especialidades (produto × ciência × engenharia/algoritmos/paradigmas ×
NFR) e removendo referências órfãs.
**Decisão e o que foi feito (com teste onde aplicável)**:
- a spec vira [`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md),
  a doc de **engenharia + NFR**, com **selo explícito por mecanismo**
  (✅ implementado / ⚠️ parcial / 🎯 proposto) — resolve a ambiguidade de
  "descrito ≠ implementado"; `BundleUnitOfWork`, `StoragePolicy`, outbox,
  lease `RETURNING`, Problem Details e value objects ficam marcados 🎯,
  não como se existissem;
- `architecture.toml` (contrato legível-por-máquina) + `AGENTS.md` (ponto
  de entrada normativo) materializam a §18.1 da spec; `test_architecture_
  toml.py` (5 testes) **prende o TOML à realidade** — se divergir das
  constantes de `test_architecture.py`, do `__version__` ou dos
  `SCHEMA_VERSIONS`, o CI quebra;
- `test_architecture.py` refatorado: constantes `TRANSPORT`/`PURE_PACKAGES`/
  `DOMAIN_PACKAGES` hoisted para nível de módulo (fonte única cruzada);
- `docs/README.md` reescrito como **índice roteado por especialidade**
  (produto/ciência/engenharia/NFR/referência/operacional/governança); o
  órfão `09-backlog.md` (antes fora do índice) e o novo `10` entram;
- **A-06 corrigido**: o jitter de retry usava `hash()` do Python
  (randomizado por PYTHONHASHSEED, quebra coordenação entre processos);
  agora `_stable_jitter` (blake2b), congelado por teste — pré-condição do
  lease multiprocesso futuro (S2).
**Não feito de propósito (evitar big-bang)**: os P0/P1 de atomicidade
(A-01/A-02 `BundleUnitOfWork`), durabilidade (A-03 `StoragePolicy`),
contratos (A-05/A-08/A-10) ficam documentados como 🎯 com porta de
reentrada — não implementados nesta rodada de consolidação de doc, para
não misturar mudança estrutural com trabalho de documentação.

### ADR-38 — Epistemic Contract Registry + Generalization Envelope (v1.6)
**Contexto**: os mecanismos heurísticos/adaptativos (RRF+Hedge, entropia
de retrieval, abstenção, reconciliação, prioridade cognitiva, mineração
metacognitiva) embutem vieses indutivos, pressupostos e limites que
estavam espalhados por código/ADRs/docs — risco de leitura além do
regime avaliado (por humano E por IA).
**Decisão**: infraestrutura operacional pequena, uma fonte única:
- `epistemics.toml` na raiz (fonte normativa, como architecture.toml é
  para estrutura) com 7 contratos; `[mechanisms.*.parameters]` carrega
  as constantes reais, CRUZADAS com o código por
  `test_epistemics_toml.py` (η/clamp do Hedge, RRF_K, HI/LO, janela de
  entropia, cortes do metacog, componentes do score) — contrato que
  mente sobre o código quebra a suíte;
- pacote PURO `epistemic/` (model: enums fechados GuaranteeKind/
  DecisionFallback/EvaluationStatus/EvidenceKind + dataclasses
  congeladas; parse: texto→tipos sem I/O; validate: regras→findings
  determinísticos com códigos estáveis) — 4º pacote puro, asserção de
  arquitetura atualizada (architecture.toml [pure]);
- loader ÚNICO em `harness/epistemics.py` (a única checagem com
  filesystem: existência dos implementation_refs); CLI
  (`corpusmith epistemics lint|list|show|evaluations`), API
  (3 GETs `/cockpit/epistemics*` via CurationFacade) e painel Qualidade
  consomem a mesma fonte;
- **Generalization Envelope**: `evaluation_envelopes` no runtime.db
  (schema 6→7, migração idempotente + ledger) — cada eval grava dataset
  +sha256, amostra, categorias, HEAD, versões; amostra <
  `epistemics.min_sample` (20) ⇒ `partially_evaluated`. Estende
  eval_runs (referência por eval_run_ids), não duplica plataforma.
**Regras normativas do lint**: `universal_guarantee=true` PROIBIDO;
garantia declara referencial; heurístico exige failure modes; empírico
exige envelope; alto impacto exige fallback; adaptativo exige loss
signal; composto exige componentes; evidência só-self_reported PROIBIDA
(não-autocertificação); Gödel/No-Free-Lunch PROIBIDOS como justificativa
em contrato (motivam postura, não fornecem bounds de ML).
**Alternativas rejeitadas**: ontologia filosófica desacoplada (sem
consumidor); knowledge graph epistemológico paralelo (duplicaria fonte);
campos dentro do frontmatter OKF (mistura conhecimento com meta-registro
de mecanismo); renomear `expected_information_gain` (quebraria clientes
— preservado o nome externo, natureza de PROXY declarada no contrato:
dívida registrada aqui).
**Invariantes**: pureza do novo pacote (AST); semântica de
`epistemic_confidence`/`confidence` INTOCADA (eixos separados por
construção); monotonicidade do score cognitivo preservada; byte-identidade
do canônico intacta; loader somente-leitura (testado).
**Migração**: runtime.db 6→7 aditiva (CREATE IF NOT EXISTS) — rollback =
ignorar a tabela; nenhum dado existente alterado.
**Consequências**: o Cockpit mostra por mecanismo garantia/avaliação/
fallback com badge "não avaliado" honesto; sem golden set distribuído
(QA-1) tudo aparece `unevaluated` — o que é o retrato correto.
36 testes novos; 284 no total.

### ADR-39 — Compute plane híbrido Python+Rust, medido antes de migrado (v1.7)
**Contexto**: os hot paths CPU-bound (PPR, Brandes, SimHash em lote) e o
ETL do índice escalam mal em Python puro; a auditoria pedia hard-kill
real (REL-2b) e o incremental lia TODOS os bytes do bundle a cada
execução. Princípio adotado: **Rust calcula sinais e projeções; Python
decide o significado** — nenhuma decisão de domínio (ADD/UPDATE/
SUPERSEDE, prioridade, abstenção, privacidade, escrita/commit) sai do
Python.
**Fase 0 — medir primeiro (tudo REAL, nada estimado)**:
- instrumentação por estágio (`runtime/stages.py`; declaração completa
  em `benchmarks/METRICS.md`) em /ask, rebuild_index e consolidação;
- harness estendido: `corpusmith bench ask|index|graph|consolidate|compare|
  generate-fixture` (fixtures determinísticas por semente; JSON schema 1;
  baseline versionada em `benchmarks/baseline.json`).
**Correções Python ANTES de culpar a linguagem (§19, medidas)**:
- `connect()` separa inicialização (1×/processo) de abertura comum —
  a checagem SchemaTooNew continua em TODA abertura (invariante);
  restore/arquivo recriado re-inicializam (`reset_initialized`);
- incremental do índice usa DELTA DO GIT (prev HEAD→HEAD + sujos):
  1 página alterada lê **130 bytes** (antes ~190 KB — tudo) e o modo
  full×incremental é EXPLICADO no relatório (`delta`);
- `_first_chunks` sem N+1 (IN + MIN(ord), ordem preservada); 1 conexão
  runtime.db por /ask (eram 3); top-k por heap.
**Porta ComputeKernel** (`compute/`, domínio sem transporte):
`PythonComputeKernel` é a REFERÊNCIA e fallback (sempre presente);
`RustComputeKernel` via PyO3 (`corpusmith_native`, abi3-py311, GIL liberado,
SoA — nunca list[dict] gigante); seleção `compute.backend`
auto|python|rust com fallback OBSERVÁVEL (motivo registrado; rust
exigido + allow_fallback=false ⇒ erro explícito). Cache de grafo por
geração (snapshot imutável, swap atômico, hit/miss/build expostos).
**Workspace `native/`** (Cargo): corpusmith-types (protocolo v1, erros
fechados) · corpusmith-graph (interning u32, CSR offsets/targets/weights,
PPR com nó virtual p/ seeds fora do grafo — equivalência provada,
union-find, Brandes) · corpusmith-sketch (SimHash 64 blake2b
digest_size=8, 9 bandas round(i·64/9), pares candidatos, paridade
BIT-A-BIT com kernel/sketch.py) · corpusmith-text/etl (Fases 3/4:
tipos+plano fechado, zero lógica canônica) · corpusmith-native-python
(bindings) · corpusmith-native-worker (manifesto v1 campos fechados,
eventos NDJSON, report.json, exit codes estáveis; NUNCA escreve bundle
nem troca index.db — swap é decisão do Python, Fase 4).
**Isolamento de processo (REL-2b, atrás de `compute.process_isolation`,
default false)**: jobs pesados rodam em `python -m corpusmith.jobs_proc`
com hard timeout REAL (kill no prazo), cancelamento REAL
(terminate→grace 2s→kill) e crash ⇒ `WorkerCrashed(OSError)` =
transitório na fila (lease/at-least-once). Governor herdado no filho
(REL-1 vale isolado). Thread continua o default documentado — porta de
entrada pequena.
**Resultados MEDIDOS (benchmarks/baseline.json; semente fixa)**:
PPR 5000 nós/20k arestas: 183.7ms→1.9ms (**97.7×**); Brandes:
88.1s→1.9s (**45.3×**); SimHash 440 docs: 800ms→13.5ms (**59.1×**);
pares candidatos idênticos entre backends (asserção no bench).
**Equivalência**: 11 testes diferenciais (exato: simhash/bandas/pares/
componentes/interning; |Δ|≤1e-8 + mesmo top-k: PPR/Brandes; fim-a-fim:
/ask devolve as MESMAS evidências nos dois backends) + property tests
Hypothesis (2 achados REAIS corrigidos: `\w` do crate regex não cobre
No ('²') e `is_alphabetic` cobre a mais Other_Alphabetic — resolvido com
categorias L*∪N*∪'_' exatas do CPython) + limite DECLARADO: pontos de
código de Unicode > runtime (Kawi U+11F02) ficam fora da garantia
(contrato native_sketch_kernel).
**Governança**: 6 contratos novos em epistemics.toml (registro 1.1.0) —
native_graph_kernel, native_sketch_kernel, graph_cache, worker_isolation
(implementados) e native_text_extraction, native_index_builder
(PLANEJADOS, guarantee none, sem overclaim); `doctor` valida a camada
nativa (extensão, protocolo, smoke PPR, worker presente, tmp, fallback);
CI ganha job `native` (cargo test + wheel + worker).
**Rejeitado**: broker externo, microserviço, thread como hard timeout,
FFI por item, Rust como segunda fonte de verdade, NCD em Rust nesta
rodada (zlib nível 6 do Python é o comparável exato; miniz divergiria —
fica no Python até benchmark justificar), rename de campos externos.
**Rollback**: desinstalar a wheel ⇒ fallback Python automático e
observável; `compute.process_isolation=false` (default) volta ao
comportamento em thread; tabela nenhuma foi adicionada (schema
inalterado nesta rodada).

### ADR-40 — Fase A do plano de experiência: sinal visível (v1.8)
**Contexto**: o núcleo já computa muito mais sinal do que a interface
mostra (VoI, Hedge, BLA, entropia, intermediação, pontes frágeis,
contradições candidatas), e a experiência expõe uma fração disso em 12
abas planas com chamadas-para-ação espalhadas (tensões C-1 e C-2 da
auditoria em `docs/13`; UX-1/UX-3 abertos). Início da **Fase A** do
plano — as receitas **R3** (fila única de próxima ação, de n8n + VoI
interno) e **R1** (grounding por span, de langextract). Regra da fase:
*expor o que já existe, sem cálculo novo e sem decidir pelo humano.*
**Decisão** — duas projeções PURAS e reconstruíveis, zero heurística
nova de guarantee própria:
- **R3 · fila única "Próxima ação"** (`usecases/next_actions.py`):
  unifica num só lugar, ranqueado por densidade **valor/custo** (o mesmo
  VoI por minuto da mochila de atenção, só que sem orçamento — a fila
  inteira ordenada), as fontes que já existiam dispersas: revisões
  espaçadas vencidas (ACT-R), lacunas do Harness (perguntas/contestadas/
  stale), inbox a consolidar, **pontes frágeis** do grafo (persistência
  0-dim já persistida em `graph_bridges`) e **contradições candidatas**
  (AGM, a MESMA `check_corpus` do painel Qualidade — fonte única). Cada
  item traz origem, valor, custo e a ação de um clique. As três fontes
  de atenção viraram funções de módulo em `plan_attention.py`
  (`review_items`/`gap_items`/`inbox_items`) para reuso sem duplicar
  cálculo; `PlanAttention` continua montando a mochila com orçamento. A
  fila **substitui** (não soma) o texto livre "Ações recomendadas" do
  Dashboard — requisito do UX-1, não um 13º lugar.
- **R1 · grounding por span** (`kernel/grounding.py`, 4º-nível puro):
  `ground_spans(body, surfaces)` localiza no trecho as superfícies das
  entidades da pergunta e devolve offsets `[start,end)` — proveniência
  *verificável a olho*, determinística, à la langextract mas **sem LLM
  como autoridade** (fold sem acento preservando comprimento 1:1;
  fronteira de palavra; sem sobreposição; teto). A evidência do `/ask`
  ganha `spans`; o anexo `page_entities` ganha `span_start/span_end`
  (offset da 1ª ocorrência gravado em `index_entities`).
**Migração**: index.db 5→6 **aditiva** (`ALTER TABLE page_entities ADD
COLUMN span_start/span_end`, idempotente) + bump de `INDEX_GENERATION`
(g2→g3) que força um rebuild completo pela convergência do INV-002 — o
índice é projeção reconstruível, nenhum dado canônico muda. Rollback =
ignorar as colunas.
**Contrato epistêmico**: **nenhum novo** (DoD da fase). R3 é
composição/projeção do VoI já contratado (`cognitive_priority`,
ADR-38) — não introduz garantia; os pesos de ponte (0.7, cresce com o
bloco menor) e contradição (0.85) são priores transparentes com
justificativa no módulo, não um mecanismo com bound a declarar. R1
reforça a proveniência do sanduíche determinístico. Um contrato formal
`next_action_ranking` fica registrado como porta para quando/se a fila
ganhar aprendizado de feedback.
**Navegação**: a fila roteia por evento (`window` `bc:navigate`) para a
aba onde a ação se realiza — o Dashboard não acopla ao switch de abas; o
deep-link à página específica fica para uma fase seguinte.
**Alternativas rejeitadas**: extração-por-LLM como fonte de schema do
langextract (o produto usa gazetteer determinístico — grounding sim,
autoridade-por-LLM não); reprojetar spans a cada mudança de bundle (o
offset é ancorado no índice, que o INV-002 já reconstrói); a fila como
mais uma aba concorrente (ela substitui a chamada-para-ação, não soma);
memórias frias como fonte cega da fila (a reidratação já é automática na
compilação — listá-las todas seria ruído contra o objetivo de reduzir
superfícies).
**Invariantes preservados**: canônico ≠ projeção (fila e spans são
PROJEÇÕES reconstruíveis); LLM/heurística cercada (fila e grounding vêm
de sinal determinístico; a decisão de curadoria continua humana);
byte-identidade do canônico intacta; garantia relativa (nenhuma
universal introduzida); pureza do novo `kernel/grounding.py` (só re +
unicodedata). DoD verde: pytest+tsc+compose+epistemics lint; Recall@K do
golden inalterado (retrieval intocado). 13 testes novos; 389 no total.

### ADR-41 — O ato de curadoria humana sobre o canônico (v1.8.1, F1)
**Contexto**: a auditoria de viabilidade (`docs/14`) achou que o produto
**detecta** quase tudo e **materializa** quase nada: existia UM caminho de
escrita (`okf/writer.py:40-58`) e ele só era dirigido por use cases de
MÁQUINA. `_supersede()` — o único lugar que grava `superseded_by` — era
método PROTEGIDO de `MachinePageUseCase`, alcançável só quando a compilação
decidia SUPERSEDE. Nenhuma operação humana de suceder, invalidar, fundir,
editar, linkar ou desfazer existia; `GitStore` expunha só commit/head (sem
undo). Consequência medida: a fila da v1.8 punha no topo itens
**irresolvíveis dentro do app** — e o próprio finding
`policy.contradiction_candidate` instrui "resolva com supersede/invalid_at
ou funda as páginas".
**Decisão**: criar o eixo HUMANO de escrita como Template Method irmão —
`CurationAct` (`usecases/curate/base.py`), deliberadamente **não** subclasse
de `MachinePageUseCase`, porque o esqueleto de máquina passa o corpo por
`normalize_machine_body` e prosa humana não é reescrita (v0.8 §1.2). O
esqueleto é FECHADO (asserção irmã do INV-ARCH-006):
`_plan()` → preview PURO (diff unificado, findings PREVISTOS rodando o
MESMO `HarnessRunner.run(mode='write')` sem escrever, páginas tocadas,
dependentes TMS) → `_apply()` → UMA chamada ao `BundleWriter` com
`log_kind` explícito → registro em `curation_acts` → `rebuild_index`.
`execute(dry_run)` segue como único método público.
- **Atos**: `SupersedePage` e `InvalidatePage` (os demais — Edit, Link,
  Merge, Undo — herdam o esqueleto nos PRs seguintes: cada um é um arquivo
  em `usecases/curate/` mais uma entrada no registro fechado `ACTS`);
- **Compartilhamento sem acoplamento**: as transformações
  (`superseded_meta`, `invalidated_meta`, `merge_meta`, `unified_diff`)
  moram em `kernel/curation.py` — PURO — e os DOIS eixos importam de lá;
  `usecases/base.py` passou a usá-las. O eixo máquina **não** conhece o
  eixo humano (seria ciclo e inverteria o gradiente de mutabilidade);
- **Superfícies**: `CurationActsFacade` em arquivo próprio (a
  `CurationFacade` já tem ~20 métodos e a fase acrescenta sete atos);
  `api/curation.py` montado à parte (`api/cockpit.py` já tem 640 linhas e é
  tocado por quase todo pacote da fase); `corpusmith curate <ato>
  chave=valor [--dry-run]`. `dry_run` é OBRIGATÓRIO no corpo — sem default
  silencioso;
- **G-7 (transversal)**: handler único de `HarnessRejection` → **422** com
  os findings nomeados. Antes a exceção subia crua também de
  `/cockpit/promote` e `/cockpit/tags` e virava 500 — o produto parecia
  quebrado quando estava protegendo o canônico.
**Migração**: runtime.db 7→8 aditiva (`curation_acts`, CREATE IF NOT
EXISTS). Nasce já com `undoes`/`undone_by` (para o undo do F1-PR2 não pedir
segunda migração) e `origin_kind`/`origin_key` (para F3/F6 amarrarem
veredito e miss ao ato) — dívida antecipada de propósito, D-G do `docs/15`.
**Pré-condição paga**: `test_architecture.py` varria `usecases/*.py` com
`glob` e `pkgutil.iter_modules` — nenhum dos dois desce em subpacote, então
`curate/` nasceria FORA de INV-ARCH-003 e INV-ARCH-005. Trocado por `rglob`
e `walk_packages` ANTES de escrever qualquer ato (D-F).
**Alternativas rejeitadas**: `CurationAct` herdando de `MachinePageUseCase`
(traria a normalização de corpo para a prosa humana); `_supersede`
continuar em `base.py` e o eixo humano importá-lo (inverteria o gradiente);
atos empilhados em `CurationFacade`/`api/cockpit.py` (seis PRs disputando
dois arquivos); `dry_run` com default; escrever o ato só em `index.db` (é
projeção — o próximo rebuild apagaria o julgamento humano).
**Invariantes**: gate de escrita inescapável (todo ato passa pelo
`BundleWriter`); invalidar-nunca-apagar (a página segue legível, com corpo
intacto — testado byte a byte); canônico ≠ projeção (`curation_acts` é
ÍNDICE, cada linha guarda o `commit`; a autoridade é Git + `log.md`); CQS
(preview não tem efeito: HEAD imóvel e trilha vazia, asserção explícita);
1 método público por use case.
**Dívida declarada**: `superseded_meta` carimba `invalid_at` com o tempo de
ESCRITA — comportamento PRESERVADO do `_supersede` original, não
introduzido aqui. É o P-9 do `docs/14`, e o parâmetro `when` já está aberto
para a Fase 4 corrigir sem tocar nos atos.
**Consequências**: o item de maior valor da fila (contradição, VoI 0.85)
deixa de ser beco sem saída por CLI e HTTP; a interface do ato chega no
F1-PR6. 14 testes novos; 423 no total.

#### ADR-41.1 — O undo é escrita PARA A FRENTE (F1-PR2)
**Contexto**: sem desfazer, experimentar curadoria é irreversível — e os
atos que tocam corpo (edit, link, merge) seriam apostas. O rito óbvio
(`git revert` no worktree, depois o gate) está ERRADO aqui:
`BundleWriter.write` roda o Harness e **só então** escreve, então reverter
antes colocaria bytes no disco fora do gate, e recuperar de uma rejeição
exigiria `checkout`/`reset` — as operações que invalidar-nunca-apagar
proíbe. Agrava que `GitStore.commit` faz `add(A=True)` sobre o kb inteiro:
um revert rejeitado e não limpo entraria no PRÓXIMO commit de qualquer ato.
**Decisão**: o undo **não reverte**. Lê o conteúdo no commit PAI do ato
(`GitStore.read_at`/`parent_of`, somente leitura — nada toca o worktree),
monta `OKFDocument`s e passa pelo `write()` normal. O desfazer vira
**escrita para a frente**: gateada como qualquer outra, com commit novo, e
o commit desfeito seguindo alcançável. O undo é ele mesmo um ATO NOVO
(`undoes`), e o original é MARCADO (`undone_by`), nunca apagado.
**Limite DECLARADO**: desfazer uma CRIAÇÃO não é expressável — "estado
anterior = ausente" só seria alcançável removendo, e `BundleWriter.remove`
não roda o Harness. Em vez de escolher em silêncio qual invariante cede, o
ato **recusa** com motivo nomeado (409) e aponta a saída legítima (suceder
ou invalidar a página criada). Nenhum ato da Fase 1 cria página; o PR que
criar o primeiro é que decide.
**Achados da revisão adversarial** (feita antes do commit, porque undo é a
operação que pode destruir dado):
1. `commit_sha` inexistente — cenário REAL, porque `RestoreBackup` restaura
   o `runtime.db` e a trilha é projeção enquanto o Git é autoridade —
   vazava `ValueError: SHA … could not be resolved` do GitPython e virava
   400 com mensagem interna. Corrigido: guarda `has_commit` ⇒
   `UndoNotExpressible` (409) dizendo que trilha e histórico divergiram e
   que **nada será tocado**;
2. a trilha gravava em DUAS transações (INSERT no esqueleto, os dois
   UPDATEs no undo): havia janela em que a trilha afirmava um undo sem os
   vínculos que o explicam. Corrigido com o hook `_record_extra(conn,
   act_id)`, que roda na MESMA transação — com teste que injeta falha após
   o INSERT e exige que nada sobre;
3. recusa saindo como traceback no CLI (mesma classe do `TypeError` de
   `backup verify` corrigido no PR-0). Corrigido: mensagem limpa e código
   de saída estável (§9).
**Verificado num HOME real**: sha256 do arquivo IDÊNTICO antes do supersede
e depois do undo; histórico com os 4 commits, nada reescrito; segundo undo
recusado; `doctor` verde.
**Consequência declarada**: o commit acontece antes do registro na trilha.
Se o processo morrer entre os dois, o canônico mudou e a trilha não sabe —
recuperável, porque o Git é a autoridade e o commit carrega a mensagem do
ato; e um segundo undo restauraria o mesmo conteúdo (idempotente, sem perda).
14 testes novos; 437 no total.

#### ADR-41.2 — A relação vai ao canônico por REGIÃO, não por link (F1-PR4)
**Contexto**: `bridge_items` já entregava `action.type='link'` com `src` e
`dst`, e esse item — o de maior densidade valor/custo da fila — levava ao
painel Grafo, que não tem afordância de aresta. Faltava o ato. O problema
difícil não é escrever o link: é o `unlink` distinguir o link que o ATO pôs
do que o HUMANO escreveu na prosa. Remover o do humano seria reescrever
prosa (v0.8 §1.2).
**Decisão**: proveniência por **região sentinelada**
(`<!-- corpusmith:relacionados -->` … `<!-- /corpusmith:relacionados -->`, em
`okf/relations.py`). Tudo entre as sentinelas é território do ato; tudo
fora é do autor, e o ato **não olha**. Quando isso significa que a aresta
SOBREVIVE ao unlink (porque a prosa também cita o alvo), o preview
**declara** — contrato explícito em vez de um "não funcionou" silencioso.
A gramática da entrada é `- ` + `MD_LINK.fullmatch`: **nenhum regex novo**
de link nasce aqui.
**Três armadilhas medidas no design, cada uma virou teste**:
1. **sentinela apagada à mão engole prosa** — com regex guloso, 2 aberturas
   e 1 fechamento casam da primeira abertura ao único fechamento e a
   re-renderização APAGA a prosa do meio; cenário banal num produto que
   convida a editar o `.md`. A guarda é sobre a **contagem de sentinelas**,
   não sobre blocos casados: qualquer estado que não seja 0 ou 1 par
   completo recusa com motivo nomeado;
2. **sentinela dentro de cerca de código** — a primeira vítima seria a
   página que documenta esta feature. Descartadas via `protected_spans`;
3. **entrada puramente numérica** desarmaria `policy.citation_invalid`, o
   que legitimaria citação fabricada. `entry_text` nunca é só número.
**D-A resolvida (a decisão do `MD_LINK`)**: o parser passou a ler o
atributo de título (`[t](/p.md "rel:refines")`) com **grupos nomeados
obrigatórios** — capturar o `!` de imagem renumera posicionais. A análise
inicial concluiu "aditivo, seguro" e estava **cega para a segunda cópia do
padrão** em `normalize/masking.py`, que protege o alvo do link dos
detectores. Corrigir só `links.py` teria HABILITADO corrupção do canônico:
verificado por execução que `rewrite()` transformava `/p.md#k8s` em
`/p.md#Kubernetes` — e o Harness **não** pegaria, porque valida o corpo já
montado. As duas cópias não podem compartilhar código (`normalize/` é puro
e não importa `okf/`), então um teste PIN **comportamental** costura as
duas. `safe_link_text()` nasceu porque `md_link` com `]` no título emitia
um NÃO-link.
**Invariantes**: prosa humana nunca reescrita · gate inescapável ·
canônico ≠ projeção (a relação vai ao canônico; a aresta é projeção do
`rebuild`) · CQS · 1 método público. link→unlink devolve o arquivo byte a
byte, e o undo de um link funciona pelo mesmo rito, sem caso especial.
56 testes novos (42 de link + 14 do ato); 493 no total.

#### ADR-41.3 — O clique da fila abre o ATO, com preview (F1-PR6)
**Contexto**: o clique era uma **projeção destrutiva** — lia
`a.action.type`, jogava fora `src`/`dst`/`pages`/`identifier` e virava nome
de aba. Para o item `bridge` o payload já trazia `{src, dst}`, que **é** a
assinatura de `LinkPages`: o PR não precisou inventar dado, só parar de
descartar.
**Decisão**: `acts_for(item)` como **função de módulo separada** em
`next_actions.py` (a Fase 3 reescreve ranking e fontes deste arquivo, então
substitui uma função em vez do módulo — colisão mapeada em `docs/15` §6). O
enriquecimento entra em **uma linha antes do sort**, com teste de guarda de
que a ordenação não muda. `params` é o que já se sabe; `needs` é o que o
humano ainda escolhe. `CurationDialog` genérico: preview → diff colorido →
aplicar; botão DESABILITADO quando `blocked`, e o dialog **não fecha
sozinho**, porque a resposta traz o sha do commit — única prova visível de
que o ato virou história no Git.
**O que NÃO se oferece, e por quê** (em todos os casos os parâmetros
fechariam — a recusa é **semântica**): `unlink` para ponte destruiria
justamente o fio que o item pede para reforçar; `invalidate` para
stale/contested afirmaria que o fato EXPIROU NO MUNDO, coisa que "precisa
de revisão" e "deu beco" nunca declararam — poria uma mentira datada a um
clique do gate; `supersede` com uma página só levantaria `ValueError` já no
plano (`page == successor`), então a guarda `len(pages) >= 2` evita um botão
que sempre falha. Kinds sem ato saem com lista **vazia**, declarada.
**Contrato de que o dialog depende**: preview bloqueado é **200 com
`blocked: true`** (no dry-run o `return` precede o `raise`); o mesmo corpo
com `dry_run: false` é **422** nomeado.
**Garantia honesta, declarada por escrito**: não existe runner de teste de
UI no desktop (só `tsc --noEmit` no gate) e o `docs/15` rejeitou
teste-por-grep em `.tsx` ("passa a verde com um comentário e falha com um
rename"). A garantia tem duas pernas: **tipagem** no `daemonClient` (virou
gate — renomear `acts` quebra o `tsc` em 4 lugares) e **contrato no
backend** (20 testes, o mais forte provando por `inspect.signature` que
`params ∪ needs` constroem o ato, para as assinaturas não migrarem para o
`.tsx`). O que isso **não** prova: que o `onClick` foi religado.
20 testes novos; 513 no total.

#### ADR-41.4 — `EditPage`: a primeira escrita HUMANA de corpo (F1-PR3)
**Contexto**: é o mais consequente dos dois atos que faltavam. Fecha a
falha da **"1ª correção"** da tabela de viabilidade do `docs/14`: o painel
Wiki era somente-leitura com um botão ("marcar stale"), não existia use
case, endpoint nem CLI de edição, e corrigir uma página exigia **sair do
produto** — onde o `doctor` nem detecta a divergência, porque INV-002
compara `bundle_head` com o HEAD do Git e edição não commitada não move o
HEAD. É também o ato que resolve `contested`: uma página que "deu beco" não
expirou no mundo (não é `invalidate`) nem tem sucessora (não é
`supersede`) — o que ela precisa é ter o corpo corrigido.
**Decisão**: `EditPage(page, body=None, meta_patch=None)` herdando o
esqueleto — mais um arquivo em `usecases/curate/` e uma entrada em `ACTS`,
sem schema, sem endpoint e sem CLI novos. **A prosa vai COMO ESCRITA**:
`normalize_machine_body` é o eixo de MÁQUINA (v0.8 §1.2) e um ato humano
que a chamasse reescreveria o texto do autor — testado com grafia
idiossincrática que o gazetteer canonizaria (`postgres` minúsculo
sobrevive). O `meta_patch` **mescla**.
**Três recusas, com motivo nomeado**: edição vazia (`nada a editar`);
renomear por patch (`rel_path`/`path` — a identidade OKF **é** o caminho da
página, e renomear criaria duas verdades sobre a mesma coisa); **remover**
campo de frontmatter (apagar declaração é gesto diferente de corrigir, e o
gate acusaria `policy.metadata_shrink` de qualquer modo).
**O achado deste PR — o preview SUBDECLARAVA**. `_preview_write` usava
`reader.load().dumps()` como "antes". Medido: numa página editada à mão
(ordem própria de chave, sem `tags`), `dumps()` reordena o frontmatter,
injeta o campo com default e normaliza o fim do arquivo — então o usuário
via **só a mudança que pediu** e o disco mudava mais. Nos atos anteriores
isso passava porque suceder/invalidar só carimbam frontmatter de página já
canônica; com edição de corpo humano, é a página editada à mão que é o caso
típico. Corrigido: o diff é contra os **bytes CRUS do disco**, e quando a
forma canônica difere deles a nota **nomeia a reformatação**. Vale para
todos os atos, não só para este.
**Mudança de comportamento declarada**: `contested` e `stale` deixam de sair
com lista vazia e passam a oferecer `edit` — dois testes do F1-PR6 foram
**atualizados** (não contornados), preservando o ponto semântico de que
`invalidate` continua recusado para os dois. Corrigir o corpo não afirma
nada sobre o mundo.
**A superfície entrou no escopo** — a nota do `docs/15` dava duas saídas
(entrar depois do PR6 levando a superfície, ou reescrever o valor para
"editável por CLI/HTTP") e esta é a primeira. O `CurationDialog` já roteava
qualquer ato de `ACTS`, mas renderizava um `<input>` de UMA LINHA por
`needs`, e o `needs` do `edit` é o texto inteiro da página: aplicar teria
SUBSTITUÍDO a página que o usuário quis corrigir. A oferta passou a
**declarar** `multiline` e `prefill` (de qual página e qual campo vem o
valor inicial), e o dialog renderiza `textarea` pré-preenchido com o corpo
ATUAL, lido do `GET /cockpit/page` que a oferta aponta. Quem declara é o
backend, não um `if (act === "edit")` no `.tsx` — mesma razão dos testes de
contrato do ADR-41.3. O preview ficou com **debounce** de 350 ms: sem ele,
cada tecla num campo longo dispararia um `HarnessRunner` sobre a página
inteira. `PageDetail` deixou de ser `any` no cliente, então o `prefill`
indexando `body` é verificado pelo `tsc` (provado: renomear o campo quebra
o typecheck; renomear `multiline` quebra em outro ponto).
**Verificado num HOME real**: página com erro de digitação, dry-run
mostrando **as duas** coisas (a correção pedida e a reformatação), apply
produzindo o canônico corrigido, `curate undo` trazendo o erro de volta
pelo mesmo rito, `doctor` verde. E a cadeia que o dialog percorre provada
ponta a ponta pelos endpoints reais: oferta → `GET /cockpit/page` →
reenvio do corpo intocado dando **diff vazio** (aplicar sem digitar é NOOP)
→ preview da correção → apply → undo.
18 testes novos; 531 no total.

#### ADR-41.5 — `MergePages`: a fusão como absorção declarada (F1-PR5)
**Contexto**: último ato da Fase 1, e o que o Harness pede **por escrito** —
`policy.contradiction_candidate` diz "resolva com supersede/invalid_at **ou
funda as páginas**", e só a primeira metade existia desde o F1-PR1. É também
a única das três resoluções do item de maior valor epistêmico da fila (VoI
0.85) que não pede a ninguém para abandonar texto.
**Decisão**: um ato, duas escritas, um commit. A **vencedora** recebe a
união declarada de frontmatter (`merge_meta`) e o corpo da perdedora
**integral**, numa região sentinelada; a **perdedora** mantém o corpo
intocado e ganha `superseded_by`/`invalid_at` pelo MESMO `superseded_meta` do
supersede. Nenhum byte se perde: as duas seguem no HEAD, e o texto da
perdedora passa a ser legível de dentro da vencedora — que é o que "as duas
versões param de conviver" precisa significar para quem lê.
**Alternativas rejeitadas**: entrelaçar as duas prosas (é o eixo de MÁQUINA
operando sobre texto humano, v0.8 §1.2); só suceder sem absorver (a
perdedora ficaria legível apenas no caminho dela — "sem perder informação"
viraria "uma delas ficou invisível"); fundir renumerando notas de rodapé
(renumerar citação é forjar proveniência).
**A guarda de sentinela virou primitiva** (`okf/regions.py`). Relações são
UM bloco por página; absorções são N, cada uma declarando a origem. Escrever
a contagem de sentinelas de novo repetiria, no ato de reusá-la, o defeito
das duas cópias do `MD_LINK` (ADR-41.2). `relations.py` passou a ser o
primeiro cliente da primitiva, e os 56 testes do PR4 são o PIN dessa
extração — um deles falhou na hora e apontou uma mudança de mensagem, que é
contrato com o usuário.
**Três interações que o suíte verde não cobria** (revisão adversarial antes
do commit, cada uma virou teste que falha contra a implementação óbvia):
1. **a região no fim do corpo DESARMA `policy.citation_invalid`** — o achado
   mais sério. `local_policy` monta o conjunto `listed` com tudo que vem
   depois do primeiro `# Citations`, então uma região no
   fim cai **inteira** dentro de `listed` e legitima qualquer `[n]` que o
   texto absorvido cite sem definir. **Medido**, com o mesmo corpo e a mesma
   página: região depois de `# Citations` ⇒ **nenhum finding**; região antes
   ⇒ `policy.citation_invalid` (error). A região entra **antes** da seção, e
   a busca copia deliberadamente o regex do detector, sem "melhorar" o
   parsing — o que importa é cair do lado certo da fronteira que **ele** usa;
2. **o bloco de relações da origem entrando na vencedora** deixaria DOIS
   pares de sentinela lá, `find_block` passaria a recusar, e a vencedora
   **nunca mais receberia um link**. O bloco sai da cópia absorvida (é
   território de ato, não prosa) e as relações seguem na página de origem,
   que é linkada do cabeçalho da região;
3. **fundir uma página que já é resultado de fusão** aninharia as regiões
   (abre, abre, fecha, fecha) e `regions.blocks` recusaria qualquer operação
   no corpo da vencedora. **Recusa** com a saída legítima na mensagem, em vez
   de remover a região interna — remover apagaria a prosa que a origem havia
   absorvido de uma TERCEIRA página. Mesma postura do `UndoNotExpressible`.
**A união não herda ciclo de vida nem proveniência** (`NOT_MERGEABLE` em
`kernel/curation.py`). `invalid_at` da origem faria a vencedora nascer
**expirada** — verificado por execução: sem a guarda, a vencedora sai com
`invalid_at: 2020-01-01`. E `source_sha256`/`source`/`resource` descrevem a
FONTE da origem: dois checksums de fontes diferentes num campo escalar seria
escolher um em silêncio. A proveniência do texto absorvido fica na página de
origem, que segue no bundle e é linkada da região — **por referência, não
por cópia**.
**D-D RESOLVIDA, e por uma terceira saída.** O `docs/15` dava duas ("preview
lento por design" ou "antecipar a memoização da F7"), partindo de que ver a
contradição custaria os 16-40 s do P-11. **Medido**: aquele custo é do
`lint_bundle` (que roda TODOS os checks), não do `check_corpus`, que sai por
**~1,2 ms/doc + ~45 ms de gazetteer** (300 docs em 357 ms). E a pergunta que
o preview precisa responder é sobre AS DUAS PÁGINAS do ato, não sobre o
bundle. Então o preview roda `check_corpus` nos dois documentos **antes** (o
finding que o ato resolve) e nos dois **depois** (a prova de que sumiu), e
consulta `page_entities` — projeção já construída, com índice por entidade —
para saber se o identificador aparece em mais alguma página. **Sem varredura
e sem memoização**, com teste contando quantos documentos o detector recebe
(sempre 2).
**O limite que o preview DECLARA em vez de esconder**: `check_corpus` marca
o grupo INTEIRO como resolvido quando uma sucessão aparece nele. Fundir A em
B silencia o alerta também para o par (B, C) — sem que aquela convivência
tenha sido tratada. É comportamento pré-existente do detector, mas a fusão é
o gesto que mais facilmente o dispara, então a nota nomeia a terceira página
e diz que o alerta vai desaparecer para o grupo.
**A fila oferece `merge` PRIMEIRO** (antes de `supersede` e `invalidate`):
é a única resolução que preserva todo o texto, então é ela que o clique
principal do item abre. `merge` exige duas páginas distintas, então a guarda
`len(pages) >= 2` do ADR-41.3 passou a cobrir os dois atos.
**Invariantes**: prosa humana nunca reescrita (a região é a única coisa que
o ato escreve de próprio) · gate de escrita inescapável · invalidar-nunca-
apagar (undo devolve os DOIS arquivos byte a byte) · canônico ≠ projeção ·
CQS · 1 método público por use case.
**Verificado num HOME real**: fila → oferta `merge` com as escolhas prontas
→ preview declarando a resolução → apply com as duas prosas na vencedora,
tags unidas (`rag`, `memoria`, `grafo`), perdedora supersedida → a
contradição sai da fila → undo devolvendo os bytes → `doctor` verde.
22 testes novos; 553 no total. **Fase 1 completa.**

### ADR-42 — O modelo local é uma ESCADA resolvida contra a máquina (v1.9)
**Contexto**: `models.local.chat` era um nome fixo (`qwen2.5:7b-instruct`) e
`local_available()` significava apenas "o Ollama respondeu no socket". A
combinação produziu um estado que a instalação não previa e que foi
**medido numa máquina real** (Mac14,3, 8 GB de RAM, Ollama 0.32.1 com
`qwen3-vl:4b` instalado e `qwen2.5:7b-instruct` ausente):

- `local_available()` devolvia `True` (o `/api/tags` respondia);
- `_local()` pedia o modelo ausente e o Ollama devolvia **404**
  `{"error": "model ... not found"}`;
- `raise_for_status()` levantava `HTTPStatusError`, e `ask_memory._compose`
  só capturava `ModelUnavailable` — a exceção de transporte **vazava** e
  derrubava o `/ask`. `compile_source`, `consolidate_inbox` e
  `detect_communities` capturavam amplamente e degradavam; o `/ask`, não;
- consequência em produção: **203 jobs `embed` falhados em série** desde
  2026-07-24, um a cada 5 minutos, com o mesmo 404 em `/api/embeddings`;
- consequência no CI local: **25 testes vermelhos**, todos com esse 404. A
  suíte não era hermética — dependia de quais modelos o dev tinha
  instalado. Ela passava numa máquina SEM Ollama (o ambiente registrado no
  `docs/12`) e falhava numa máquina com Ollama e outro conjunto de modelos.

O `docs/12` §6 afirmava "sem Ollama o `/ask` não quebra" — verdade quando
ele está **ausente**, falso no estado intermediário "de pé com o modelo
errado", que é o mais provável na prática.

**Decisão**: `models.local.chat` passa a ser uma **escada de preferência**
(lista ordenada; string continua aceita para config anterior). O roteador
resolve em tempo de execução a primeira entrada que esteja **instalada** E
cujos pesos **caibam** em `memory_fraction` (default `0.6`) da RAM total.

- **não baixa nada sozinho**: resolução só LÊ `/api/tags`. Uma consulta
  jamais dispara download de gigabytes; aquisição é ato explícito
  (`pull_models.sh`, que escolhe pela RAM). Coberto por teste que proíbe
  qualquer POST durante a resolução;
- **orçamento de memória veta**: pedir 6,14 GB de pesos numa máquina de
  8 GB não é otimismo, é paginação até a inutilidade. Numa máquina de
  8,59 GB o orçamento é 5,15 GB e o `8b-instruct` é recusado **mesmo se
  baixado**; resolve para o `4b` (3,30 GB). Em 16 GB+ o preferido ganha;
- **`local_available()` passa a significar "existe modelo utilizável"**,
  não "o socket respondeu" — era essa a lacuna que fazia o estado
  intermediário passar por sadio;
- **falha de modelo é sempre `ModelUnavailable`**, nunca `HTTPStatusError`:
  `_local()` e `embed()` embrulham o transporte. O `ask_memory` não mudou —
  o `except ModelUnavailable` que já existia passou a ser alcançado. Foi a
  MENOR mudança possível (§8.6) em vez de alargar o `except` do use case;
- **resposta vazia não é resposta**: medido no `qwen3-vl:4b` (variante
  *thinking*), com `num_predict` curto o modelo gasta todo o orçamento no
  campo `thinking` e devolve `response` vazio com `done_reason: "length"`.
  Como `reconcile_candidate` pede 32 tokens e `detect_communities` 160,
  isso é alcançável de verdade. Vazio virou `ModelUnavailable` — degrada
  para o extrativo em vez de propagar vazio como se fosse síntese. A
  escada prefere as variantes `-instruct`, que não gastam orçamento
  raciocinando;
- **a decisão é inspecionável**: `corpusmith models` mostra o resolvido, o
  orçamento e por que cada candidato foi recusado (`ausente` × `nao_cabe`);
  exit 1 quando nada é utilizável. `--recommend` alimenta o instalador.

**Suíte hermética**: fixture autouse em `tests/conftest.py` aponta o
roteador para uma porta morta. A suíte deixa de consultar o Ollama da
máquina e exercita de forma determinística o caminho de degradação
documentado. Testes que exercitam o roteador substituem `httpx` e ficam
imunes ao redirecionamento.

**Migração**: nenhuma de dados. Config antiga com `chat` string continua
válida (coberto por teste). Instalações que dependiam de
`qwen2.5:7b-instruct` seguem funcionando — ele é a última entrada da
escada.

**Verificado nesta máquina**: `corpusmith models` resolvendo `qwen3-vl:4b`
com o `8b-instruct` marcado `ausente`; `complete()` real devolvendo
`via: local:qwen3-vl:4b`; o 404 de modelo ausente virando
`ModelUnavailable` e o `/ask` respondendo extrativo em vez de 500; jobs
`embed` passando a concluir depois do `nomic-embed-text` baixado
(`embeddings` de 0 → 7 linhas). 14 testes novos, sem skips — **545 no
total na base deste PR** (o F1-PR5 entrou em paralelo; no merge das duas
linhas a suíte fecha em **567**, medido: 553 + 14. O delta de 14 é a
medição deste PR; o total é propriedade da árvore, não da mudança).

### ADR-43 — O mapa de padrões passa a ser repetível e datado (v1.9.1, F2-PR1)
**Nota de numeração**: esta ADR é a **43** e não a 42 que o `docs/15` §4
reservava para a Fase 2 — o número 42 foi publicado pelo PR da escada de
modelo local, que saiu em paralelo. Renumerar ADR já publicada seria pior
que aceitar um buraco na sequência reservada.
**Contexto**: `DetectCommunities` produzia um mapa que ninguém sabia de
quando era, que não era repetível, e cujo produtor era invisível. O `docs/15`
listava a Fase 2 como "não é uma feature em quatro pedaços — é um objeto que
nasce de baixo para cima", e a base é esta: sem repetibilidade, o casamento
de partições da F2-PR2 compara ruído com ruído.
**A repetibilidade tem duas pernas, e qual perna faz o quê foi estabelecido
por EXECUÇÃO.** A primeira versão dos testes usava quatro blocos densos e
passava **com e sem** a canonicalização — blocos densos são inequívocos, o
Leiden os acha em qualquer ordem de vértice, e o teste era teatro. Num ANEL
de 24 nós (muitos cortes quase-empatados), 8 execuções:

| ordem de inserção das arestas | seed | partições distintas |
|---|---|---|
| variável | não | 8 |
| variável | sim | **6** |
| canônica | não | 1 |
| canônica | sim | 1 |

- **ordem canônica** (`sorted()` no `_partition` e no
  `_leiden_or_components`) é o que mata a variação: a numeração de vértice do
  `igraph` vem da ordem de inserção. **`seed` sozinho não resolve**;
- **`seed`** é o que sobrevive a `PYTHONHASHSEED=random`, que é a condição
  real (o daemon não fixa hash): medido em 4 processos, sem seed o de hash
  aleatório divergiu dos outros três; com seed, os quatro idênticos.

A **numeração da comunidade** virou derivada do menor membro: medido, em três
execuções sobre o mesmo bundle o agrupamento se manteve e o rótulo inteiro
trocou nas três — `communities` mudava sem o conhecimento ter mudado. O
rótulo não ganha semântica com isso (D-K: a semântica é do `theme_id`), ele
ganha **estabilidade**.
**Um ORDER BY que entrou e SAIU.** Acrescentei `ORDER BY` nas duas queries do
grafo achando que era o que canonizava a ordem, e removi depois de provar que
não: a PK de `graph_edges` é `(src, dst, kind)` com dois `kind` possíveis,
então um par recebe no máximo duas contribuições daquele laço e soma de dois
floats é comutativa; as do laço de co-menção são todas iguais (0.25). O teste
continuava verde com e sem o `ORDER BY`, ou seja era código infalsificável —
custo sem ganho medido, que o `AGENTS.md` proíbe. O raciocínio ficou no
comentário para ninguém repetir o caminho.
**Outra medição que NÃO virou mudança**: o laço de co-menção parecia um N+1
(uma query por entidade) e num banco sintético levou **76 s** para 10 000
entidades. Com o índice `idx_pe_entity`, que o schema real tem, o N+1
**empata** com uma varredura única (1,0×) — os 76 s eram artefato da minha
tabela sintética sem índice. Registrado porque a tentação de "otimizar" isso
vai voltar.
**Datação** (`graph_snapshot`, index 6→7 aditiva, uma linha sobrescrita):
`bundle_head`, `computed_at`, `backend`, `seed`, contagens. **O carimbo vem
DEPOIS dos sumários**, e essa ordem é a correção de um defeito medido:
`_write_summaries` escreve páginas `communities/` pelo writer e cada escrita
é um COMMIT, então carimbar antes gravava o HEAD anterior aos próprios
sumários — o mapa nascia "velho" e o INV-004 disparava para sempre, um alarme
sem saída porque recomputar reproduzia a divergência.
**O campo `backend` é o que muda a experiência numa máquina pequena.** Sem o
extra `[ml]` compilado, o particionamento cai em **componentes conexos** e o
produto continua chamando o resultado de "comunidade". Isso era invisível: o
`doctor` agora expõe `graph.backend`, e quem abre um Mac de 8 GB onde o
`igraph` não compilou passa a saber que seus "temas" são componentes conexos.
**INV-004, e por que é WARN e não ERROR**: mapa velho não é corrupção — é
mapa velho, e o produto tem de poder **servi-lo com aviso** em vez de
recomputar. Essa distinção é o que torna o mapa usável onde recomputar a cada
abertura não é opção. Duas divergências: `bundle_head` ≠ HEAD, e ponte com
endpoint aposentado. Mapa **ausente** não é finding — instalação nova não tem
mapa velho, tem mapa nenhum, e acusar isso viraria ruído em todo `doctor`.
**Poda de ponte órfã**: supersedida continua no índice
(invalidar-nunca-apagar), então não cai pela construção do grafo. E a fila do
cockpit põe ponte frágil entre os itens de maior densidade valor/custo:
oferecer "reforce este fio" apontando para página aposentada gasta a atenção
que a fila existe para economizar.
**D-E e D-I pagas**: `communities/` fora da construção do grafo (senão cada
rodada altera o grafo da seguinte, e o DoD da F2-PR2 diz que passará a
reindexar); `INSERT` de ponte com colunas **nomeadas** (provado por execução:
com uma coluna nova na tabela, a gravação continua funcionando). **G-2 já
estava paga** pelo PR-0 — a perna `backend-ml` existe e `test_ml_leiden.py`
prova que o ramo de produção é tomado; este PR usa esse instrumento em vez de
recriá-lo.
**G-5 paga**: o job `leiden` estava no REGISTRY e **nunca era enfileirado**.
Semanal (não diário) e prioridade 7 (baixa): o mapa cede a vez para tudo que
o usuário pediu, e o INV-004 diz quando vale a pena disparar antes da hora.
Sem o agendamento, o INV-004 seria alarme sem saída.
**Registro epistêmico**: `[mechanisms.pattern_layer_snapshot]` nasce aqui
(registro 1.1.0 → 1.2.0) e **cresce** nos PRs seguintes, em vez de um segundo
mecanismo mentindo sobre o primeiro. A garantia é RELATIVA e declarada:
mesmo `index.db` e mesmo backend ⇒ mesma partição rótulo a rótulo; nenhuma
garantia de que a partição seja a "certa", nem de estabilidade entre
backends. O lint recusou três termos fora do vocabulário fechado
(`deterministic_repeatability`, `components`, `synthetic_topology`) — é para
isso que ele existe.
**Invariantes**: canônico ≠ projeção (`graph_snapshot` é projeção, some no
`rebuild`) · INV-002 intocado · o doctor nunca muta o bundle · nenhum
comportamento novo no caminho de escrita (logo ADR, não RFC).
**Verificado num HOME real**: 4 comunidades e 3 pontes por `leiden`; mapa
idêntico em 4 execuções; um commit novo faz o INV-004 acusar `warn` com os
dois shas; supersedir endpoint de ponte faz o doctor acusar ponte órfã;
recomputar limpa os dois.
15 testes novos; **582 no total** na árvore com o ADR-42 mergeado (4 na
perna `ml`, 1 deles novo). Medido também com `igraph`/`leidenalg` bloqueados
no import — a condição do job `backend` e da máquina onde o extra `[ml]` não
compilou: 578 passed, 2 skipped, zero falhas, com o carimbo, o rótulo
canônico e a repetibilidade valendo no backend `components`.

### ADR-44 — Brandes fora do request, pelo kernel que já existia (v1.9.2, F2-PR3+4)
**Contexto**: o `docs/14` dizia que o produto tem "data de morte", e o número
está no `benchmarks/baseline.json`: Brandes em Python custa **88 058 ms** a
5000 nós contra **1 944 ms** em Rust (45×). Duas coisas somavam nisso, as duas
**medidas antes de escrever**:

| páginas | arestas | `graph_data` | quanto era Brandes | `gaps` |
|---|---|---|---|---|
| 100 | 909 | 25 ms | 52 % | 25 ms |
| 300 | 2 729 | 157 ms | 76 % | 152 ms |
| 600 | 5 459 | 610 ms | 82 % | 589 ms |
| 1 200 | 10 919 | **2 571 ms** | **95 %** | 2 610 ms |

E o achado que reposicionou o diagnóstico: **o caminho quente ignorava o
`ComputeKernel`**. O kernel selecionava `rust` e o `observatory` chamava o
`betweenness_centrality` PURO em Python direto — a camada nativa estava paga
(ADR-39) e não estava sendo usada onde mais doía.
**Decisão**: a intermediação vira **projeção persistida** (`graph_centrality`,
index 7→8 aditiva), computada pelo job `leiden` **através do kernel**. Quem
constrói o grafo é quem mede quem articula. O request lê uma tabela.
**Resultado medido**: `graph_data` a 1200 páginas passa de **2571 ms para
139 ms** (18,5×); `gaps`, de 2610 ms para 164 ms. O job leva 18,5 s, uma vez,
semanal e com prioridade 7.
**A garantia que sustenta o ganho** não é o tempo — é que os valores
persistidos são **idênticos** aos que o request calculava, com teste que
compara todos contra o kernel puro. "18× mais rápido" sem isso poderia ser só
"passou a responder outra coisa". Para tanto, o kernel lê `graph_edges` da
MESMA conexão e aplica o MESMO `EDGE_WEIGHT`. Alimentá-lo com o `adjacency` do
leiden era o caminho tentador e estava errado por duas razões: ele carrega
arestas de co-menção que a centralidade nunca teve, e `load_edges` mapeia o
terceiro campo por `EDGE_WEIGHT`, então **peso já acumulado viraria 0.5 para
tudo**, em silêncio.
**Degradação declarada**: centralidade não medida ⇒ `betweenness` 0.0 e
`centrality.computed: false`. A chave nunca sai do payload (D-J: há teste de
shape que depende dela), a interface serve **grau** em vez de inventar
influência, e o badge de frescor **oferece o job**. Falha do kernel não
derruba o job: a centralidade é enfeite do mapa, não o mapa (ADR-39 §22 —
ausência de camada nativa é comportamento suportado), então sai `none` e o
mapa sai inteiro.
**Migração com armadilha paga**: `graph_snapshot` nasceu na v7 sem
`centrality_backend`, e `CREATE TABLE IF NOT EXISTS` **não** acrescenta coluna
a tabela existente — sem o `ALTER` no `_migrate`, o carimbo falharia na
PRIMEIRA escrita de qualquer `index.db` v7. Há teste que recria a tabela no
formato v7 e prova o upgrade.
**O que o `docs/15` pedia e NÃO entrou, por medição**: "um snapshot
compartilhado por `graph`/`insights`/`gaps`". A premissa era o Brandes de
84,3 s; com ele fora, a montagem inteira custa 139 ms, e os três são requests
HTTP **separados** — compartilhar exigiria cache por geração, que compraria
~100 ms ao preço de servir `page_heat` velho. Cheguei a escrever o parâmetro
`graph=` em `structural_gaps` (medido: 164 → 42 ms) e o **removi por não ter
chamador**: mesma disciplina que tirou o `ORDER BY` do ADR-43. Quando um
endpoint precisar dos dois, ele volta junto com o caso de uso.
**Também não entrou**: "história do tema", que depende do `theme_id` do
F2-PR2 — e o PR2 exige **RFC** (`AGENTS.md` §8: heurística no caminho de
escrita). Entregar história de tema sem identidade de tema seria série
temporal de um rótulo que muda de significado.
**`limit` é do TRANSPORTE, não do cálculo**: `total_nodes`/`total_edges`/
`truncated` continuam falando do grafo inteiro, senão o recorte viraria
mentira sobre o tamanho da rede. Ordenação por heat, grau e `page` — o
terceiro critério existe para o recorte não "piscar" entre execuções.
**A tipagem do badge virou gate**, e não era: `GraphPanel` guardava o payload
em `useState<any>`, então renomear `centrality.computed` no backend não
quebrava nada. Com o estado tipado, quebra em dois pontos — verificado por
execução.
**Invariantes**: canônico ≠ projeção (`graph_centrality` sai no rebuild) ·
INV-002 e INV-004 intocados · nenhuma escrita no bundle · CQS.
11 testes novos; **593 no total** (4 na perna `ml`), e 589+2 skip com
`igraph`/`leidenalg` bloqueados no import.

### ADR-45 — Identidade de tema por casamento de partições (v1.9.3, F2-PR2)
**Implementa o [RFC-001](16-rfc-theme-id.md)** — o primeiro RFC do projeto
(o `docs/10` §19 definia o template e o marcava "🎯 a instanciar"). Foi RFC e
não só ADR porque o `AGENTS.md` §8 exige RFC para **heurística no caminho de
escrita**, e o casamento decide `UPDATE` vs `SUPERSEDE` de página canônica.
**O problema é MEDIDO, não previsto.** Um tema de 5 páginas cuja página mais
conectada troca de `ana` para `elo`, **sem nenhuma página entrar ou sair**:

```
1. tema nomeado pela mais conectada:   ['ana.md', 'index.md']
2. `elo` vira a mais conectada:        ['ana.md', 'elo.md', 'index.md']
```

**Duas páginas canônicas afirmando o mesmo tema, nenhuma supersedida** — o
produto fabricando a contradição que `policy.contradiction_candidate` existe
para acusar, uma por rodada do job.
**Decisão**: `theme_id` opaco atribuído no NASCIMENTO, `rel_path` derivado
dele (`communities/thm_<id>.md`), e o rótulo legível no frontmatter — onde
mudar não cria arquivo. É isso que fecha o defeito.
**A calibração mudou o desenho duas vezes**, e as duas viraram teste:

| perturbação | Jaccard | forma |
|---|---:|---|
| 1 página nova (6→7) | 0,86 | 1↔1 |
| +50 % / −33 % | 0,67 | 1↔1 |
| **tema dobra (6→12)** | **0,50** | 1↔1 |
| **tema parte em dois trios** | **0,50** | **1→2** |
| tema dissolve | 0,17 | 1→0 |

1. **τ = 0,5 seria o pior valor possível** — é exatamente o Jaccard de um
   crescimento legítimo E de um split. `TAU = 1/3` é o ponto médio da banda
   vazia medida entre 0,17 e 0,50, a única região em que o limiar não decide
   por acidente;
2. **o valor do Jaccard não distingue `split` de `grew`** (0,50 nos dois). Quem
   distingue é a **forma do casamento bipartido**. Por isso `match()` devolve a
   forma, e não um número com limiar.

**`merged` foi declarado e NÃO observado**, e isso está no contrato epistêmico
em vez de escondido. Não consegui produzir uma fusão nem com alfa e beta
densamente interligados: o Leiden manteve 3 comunidades e Jaccard 1,0 —
modularidade resiste a fundir cliques densos. E a fusão **assimétrica** (8 e 3
páginas) lê como `grew` + `died`, porque o menor tem Jaccard 3/11 = 0,27,
abaixo de τ. Com 27 % de sobreposição, dizer "estes temas se fundiram"
afirmaria continuidade que o dado não sustenta. O ramo existe porque a forma
2→1 é bem definida e barata, mas **nenhuma interface o pressupõe**.
**O LLM volta a só rotular** (RFC §4.4): com o roteador devolvendo rótulo
absurdo e diferente a cada chamada, `theme_id` e `rel_path` saem idênticos —
há teste que prova isso, e é a garantia de que a repetibilidade paga pelo
ADR-43 não é desfeita pelo modelo.
**Partição idêntica NÃO gera época.** Sem isso, cada execução do job semanal
registraria uma época por tema e a trilha viraria ruído — a mesma armadilha do
rótulo que trocava a cada execução (ADR-43).
**As páginas antigas são ADOTADAS, não abandonadas** (RFC §4.5). Verificado
que sem isso o PR **entregaria o INV-005 violado no primeiro upgrade**: a
página no caminho antigo continuava viva ao lado da nova. Agora ela é
supersedida apontando para o caminho novo, casada pelos membros que ela mesma
lista; sem tema correspondente, é aposentada com `invalid_at` — nunca removida.
**Uma escrita por página, e não uma com todas**: uma página antiga malformada
(editada à mão, sem `source_sha256`) faz o Harness recusar — corretamente. Numa
escrita única essa recusa bloquearia a adoção de **todas**, e o INV-005
seguiria violado no bundle inteiro por causa de um arquivo. O gate não é
enfraquecido: a recusa é isolada e a página segue visível ao `okf lint`.
**INV-005 nasce com verificador** — invariante sem verificador é promessa. É
ERROR e não warn: ao contrário de mapa velho (INV-004, servível com aviso),
duas verdades vivas sobre o mesmo tema não têm leitura correta. E é reparável
pelo próprio job.
**Comportamento pré-existente declarado, não corrigido aqui**: o
`_CommunitySummaryPage` reescreve o sumário a cada execução mesmo com conteúdo
idêntico, então o HEAD move a cada job. Não foi introduzido neste PR e a
asserção de idempotência mede a **contagem de adoções**, não o HEAD — dizer o
contrário seria testar outra coisa.
**Migração**: index 8→9 aditiva (`themes`, `theme_epochs`); nenhuma coluna nova
em tabela existente, então nenhum `ALTER` é necessário (a armadilha do ADR-44
não reaparece).
**Invariantes**: canônico ≠ projeção (as duas tabelas somem no rebuild) · gate
inescapável · invalidar-nunca-apagar · repetibilidade do ADR-43 preservada ·
INV-005 novo.
24 testes novos; **617 no total** (4 na perna `ml`), e 613+2 skip com
`igraph`/`leidenalg` bloqueados no import. Registro epistêmico 1.3.0 → 1.4.0
com `theme_identity_matching` — heurística no caminho de escrita **precisa** de
contrato declarado, e este é `high_impact = true`.

### ADR-46 — Checkpoints normalizados: o estado entre as fontes (v1.9.4)
**Contexto medido, e o custo não é estético.** Cada derivação inventava o
próprio carimbo de frescor e o próprio invariante: `bundle_head` aparecia em
**quatro** lugares (`index_meta` chave/valor, `graph_snapshot.bundle_head`,
`theme_epochs.bundle_head`, schema de runtime), e cada um exigiu um INV
separado no doctor — INV-002 (índice), INV-004 (mapa), INV-005 (temas). Cada
derivação nova custava um carimbo **mais** um invariante.
Foi essa dispersão que deixou passar o defeito confirmado por execução na
auditoria: o job `leiden` escrevia páginas, movendo o HEAD, e o índice ficava
atrás — **nada relacionava as duas coisas**. O carimbo do mapa se dizia fresco
enquanto o do índice apodrecia.
**Decisão**: uma tabela `checkpoints` (runtime 8→9 aditiva) com uma linha por
derivação — de qual ESTADO DA FONTE ela foi produzida e quando — e a **cadeia**
declarada em `kernel/checkpoints.py:DERIVATIONS`:

```
bundle (autoridade) → index → graph_map  → themes
                            → centrality
```

**A cadeia é o ponto, não a tabela.** Ela permite o veredito que carimbo
isolado não consegue dar por construção: `stale_upstream` — derivação coerente
com a fonte IMEDIATA e ainda assim servindo dado velho porque a fonte da fonte
mudou. O mapa comparando-se com o índice acha tudo bem; o índice comparando-se
com o bundle reclama de si; ninguém enxerga que o mapa está servindo dado de
duas gerações atrás. É a forma exata do defeito que a auditoria confirmou.
**Mora em `runtime.db`, não em `index.db`, e a escolha é a substância**: um
carimbo sobre o índice não pode morrer junto com o índice. `rebuild_index`
apaga e reconstrói, e um registro que some com aquilo que descreve não
consegue dizer "a derivação sumiu" — é o limite do `index_meta.bundle_head`
atual, e há teste que apaga o `index.db` e exige que o checkpoint sobreviva.
**Três vereditos, e a distinção entre eles é o ganho**: `absent` (nunca
computada — **não é defeito**: instalação nova não tem derivação velha, tem
derivação nenhuma), `stale` (a fonte imediata mudou) e `stale_upstream` (a
cadeia acima se moveu). WARN e nunca ERROR, pela mesma razão do INV-004:
derivação velha é **servível com aviso**, e é isso que a torna usável numa
máquina onde recomputar a cada abertura não é opção.
**INV-006 é UMA regra para toda a cadeia**, em vez de um invariante por
artefato — e é o que faz a próxima derivação nascer com frescor verificado de
graça, em vez de com mais um carimbo e mais um alarme. Registro dinâmico é
recusado: derivação que o produto não declara é derivação cujo frescor
ninguém garante.
**Dívida declarada, e é real**: os carimbos antigos **continuam**. Consolidar
`index_meta.bundle_head` no checkpoint exigiria mexer no INV-002, o invariante
mais exercitado da suíte, e fazê-lo no mesmo PR que introduz o mecanismo
juntaria duas mudanças cujos defeitos ficariam indistinguíveis. A duplicação é
temporária e está aqui por escrito para não virar permanente por esquecimento.
**Verificado num HOME real**, a cadeia inteira ao longo do ciclo: nada
derivado (5× `absent`) → rebuild (índice fresco, resto ausente) → job (tudo
fresco) → **usuário escreve sem reindexar** (índice `stale`, mapa e
centralidade `stale_upstream`, temas `stale_upstream` por dois saltos) →
reindexar (mapa e centralidade passam a `stale` direto, temas seguem
transitivos) → recomputar (tudo fresco).
`corpusmith checkpoints` lista a cadeia e sai com código 1 quando algo está
atrás — inspecionável, não só verificável.
16 testes novos; **635 no total**.

### ADR-47 — O caminho empacotado passa a ser executado, não só construído (v1.9.5, PR-0.1)
**Contexto medido, e o número importa: quatro defeitos, zero visíveis sem
rodar.** A auditoria (`docs/17`, G-1) verificou que `pyinstaller build.spec`
*construía* e parou aí. Construir o artefato e executá-lo são perguntas
diferentes, e a distância entre elas era o produto inteiro: nenhum terceiro
jamais teve um `corpusmith-server` que subisse. Reproduzidos, em ordem de morte:

1. `EXE(...)` sem `exclude_binaries=True` → `ValueError: Resource
   '.../corpusmith-server' is not a valid file!`. O `just sidecar` **não
   construía**; o binário que `sidecar.ts` procura no app empacotado nunca
   existiu;
2. `collect_dynamic_libs("sqlite_vec")` com o `search_patterns` default
   (`['*.dll', '*.dylib', 'lib*.so']`) devolve **`[]`**: a extensão se chama
   `vec0.so` e não casa com `lib*.so`. O diagnóstico da auditoria — "falta o
   extra `[ml]`" — estava errado, o pacote estava instalado. Este é o pior dos
   quatro porque é **silencioso**: um app sem busca vetorial sobe, responde, e
   responde pior;
3. ponto de entrada em `daemon.py`, que o PyInstaller roda como `__main__` →
   `ImportError: attempted relative import with no known parent package`. Um
   `packaging_entry.py` com import absoluto resolve, e diz por quê;
4. recursos resolvidos por `Path(__file__).parents[N]` →
   `FileNotFoundError: .../corpusmith-server/db/schema_runtime.sql`, com o arquivo
   em `.../_internal/db/`. O daemon morria antes de abrir a porta.

**Decisão em duas partes, e a segunda é a que dura.** `corpusmith/paths.py`
centraliza a resolução (`_MEIPASS` quando congelado, `source_root` explícito
na árvore) — quem chama declara de onde contar, em vez de esconder a contagem
num `parents[4]` que ninguém revalida quando o módulo muda de lugar. E o job
`package` do CI **sobe o binário** e bate em `/health`, `/system/doctor`
(`counts.error == 0`) e `/cockpit/epistemics`, além de exigir o `vec0.so` no
`_internal/`. `pyinstaller build.spec` entra em `[gate].ci_enforced` —
enquanto o token não existia, `test_ci_executa_todo_o_gate_declarado` era
estruturalmente incapaz de acusar a ausência.

**Um quinto defeito apareceu porque o binário passou a rodar.** `epistemics.toml`
mora na raiz do repo e é lido em **runtime** (`/cockpit/epistemics`, painel
Qualidade). Fora dos `datas`, o app instalado respondia
`epistemic.registry_missing` — o produto acusando a si mesmo de não saber o que
afirma saber. E, uma vez embarcado, a checagem de existência dos
`implementation_refs` passaria a acusar **~15 erros inexistentes**, porque a
árvore de código não vai no pacote. Em vez de omitir a checagem em silêncio, o
binário emite `epistemic.refs_uncheckable` (warn) dizendo que a pergunta não é
respondível ali e onde ela vale — repositório e CI. Ambos reproduzidos no
binário antes da correção.

**G-10 no mesmo PR, porque é o mesmo modo de falha em outro artefato.**
`validate_registry` iterava contrato a contrato e não tinha regra sobre o
CONJUNTO: apagar as 45 linhas de `[mechanisms.theme_identity_matching]` deixava
o lint responder *"14 mecanismo(s), 0 finding(s)"*, exit 0, suíte verde. Duas
listas, porque são dois erros distintos: `EXPECTED_MECHANISMS` (o registro de
hoje — sumiço é **error**, e remover passa a exigir remover o nome no mesmo
commit) e `PROMISED_MECHANISMS` (os cinco que `docs/14` §5 declara obrigatórios
e que ainda não existem — **warn**). Vermelho hoje só produziria contrato
escrito às pressas para calar o gate, ou o gate desligado; warn mantém a dívida
onde ela será paga. O painel Qualidade passa a listá-la: antes ele contava 15
mecanismos e o leitor não tinha como saber quantos faltavam.

A outra metade de G-10 — *"nada quebra se esquecerem o bump"* — vira regra de
parsing: `[registry].version` passa a exigir semver. `version = "banana"`
passava, e uma version que não ordena não consegue dizer que um registro é mais
novo que outro. Forçar o bump exigiria histórico e não é mecanizável barato; o
que é mecanizável, e está feito, é que **mexer no conjunto passe pela linha
onde a pergunta aparece**: um fingerprint do conjunto de mecanismos fica fixado
ao lado da version esperada, e mudar o registro sem tocar nesse par reprova.

**G-8 fecha com `release.yml`**: trigger em tag `v*`, runner arm64 (a máquina
declarada em `docs/15` é um M2; runner Intel mediria outra coisa), conferência
de que a tag bate com `desktop/package.json` **e** `backend/pyproject.toml`
antes de construir — a deriva de versão foi corrigida à mão uma vez e voltaria
na próxima release —, e `--draft`, nunca publicação direta: um `git push
--tags` acidental não deve produzir release visível, porque release não se
despublica. O `directories.output` do `electron-builder.yml` precisou ser
explicitado no mesmo movimento: o default é `dist/`, que aqui é a saída do
Vite listada em `files` — empacotar para dentro do diretório que se empacota.
Só apareceu quando algo passou a de fato executar o `electron-builder`.

**Falsificabilidade verificada por mutação, uma a uma**: desligar o ramo
`frozen` do lint, tirar o `epistemics.toml` dos `datas`, fazer `resource()`
ignorar o `_MEIPASS` e remover `_completude` — cada uma derruba exatamente o
teste que a cobre, e só ele. O primeiro teste de `frozen` **passava** com a
correção desfeita (rodava contra o repositório real, onde os refs existem);
simular `_REPO_ROOT` foi o que o tornou capaz de reprovar.
**Invariantes preservados**: local-first (nada no binário exige rede) · AGPL
fora do pacote (`excludes` de `fitz`/`pymupdf4llm`/`ebooklib`, v0.6 §8) ·
falhar alto em vez de degradar em silêncio (build.spec aborta sem `vec0`).
15 testes novos; **646 no total**.

### ADR-48 — A escada de reconciliação volta a ter três degraus (v1.9.6, F3-PR0)
**Decisão registrada por RFC-002 (`docs/19`)**, porque `AGENTS.md` §8 exige RFC
para heurística no caminho de escrita — e este conserto de uma linha ativa os
cortes HI/LO, o NCD e o árbitro LLM sobre a decisão ADD/UPDATE/SUPERSEDE da
página canônica. Este ADR registra o que ficou decidido; o RFC guarda as
opções, as medições e as condições de reentrada.
**O degrau 2 nunca executou.** `MIN(bm25(chunks_fts))` levanta
`OperationalError: unable to use function bm25 in the requested context` em
TODA execução desde a v0.9 — e a subquery também, porque a restrição do SQLite
é da consulta que carrega o `MATCH`, não do aninhamento. Um `except Exception`
cego engolia, e *"nenhum candidato acima do corte"* saía **idêntico** ao de uma
busca bem-sucedida e vazia. É a forma exata do defeito que a auditoria nomeou:
**construir bem e verificar mal aquilo que se construiu**.
**O ranking sai por chunk e a redução por página é feita em Python**, o que
corrige um segundo erro que o agregado escondia: sem deduplicar, uma página
longa ocuparia várias posições do top-N e inflaria o próprio termo
`1/(1+position)` do escore.
**A projeção deixa de decidir como se fosse autoridade.** `index.db` é
reconstruível e a escada o lia como fonte de verdade sobre o que existe:
índice atrasado esconde a página e o mesmo DOI vira duas páginas canônicas
vivas (medido). A escada passa a tornar o índice fresco antes de decidir —
incremental, delta de git — e, quando nem isso resolve, a decisão **declara**
`index_stale` e o `ADD` cai para `confidence = "ambiguous"`. *Ausência de
evidência num índice atrasado não é evidência de ausência.*
**Os cortes NÃO foram recalibrados**, e a medição diz por quê: com corpo
idêntico, o escore é **0.686** sem entidade curada e **0.976** com ela. O teto
sem acordo de entidades é ~0.7, abaixo de HI=0.82 — não é fraqueza do degrau, é
a exigência de que os três sinais concordem antes de sobrescrever canônico.
Recalibrar sem golden set seria adivinhar, e o contrato passaria a mentir.
**O `try/finally` do `rebuild_index`** deixa de ser higiene e vira
pré-requisito: a partir daqui a função roda dentro do caminho de escrita, onde
a conexão vazada travaria o próprio ato que a provocou (`database is locked`
após 30 s — medido nas duas direções).
**O registro epistêmico foi corrigido, não só acrescido** (1.4.0 → 1.5.0): a
suposição *"cortes calibráveis via bench"* virou *"NÃO calibrados — o degrau não
executou da v0.9 ao F3-PR0"*. Um contrato que descreve corretamente um caminho
que nunca rodou é pior que contrato nenhum, porque parece verificação.
**Falsificabilidade, uma mutação por correção**: repor `MIN(bm25)` derruba 4
testes; remover a pré-condição derruba 3; remover o `try/finally` derruba 1. A
primeira versão do teste do `finally` **passava com e sem** a correção —
conexão vazada sem transação aberta não tranca nada; foi preciso escrever antes
de estourar para o teste poder reprovar.
**`backend/tests/test_reconcile_candidate.py` não existia.** A decisão mais
consequente do produto não tinha teste próprio, e é por isso que um degrau
inteiro pôde morrer em silêncio por três versões.
12 testes novos; **657 no total**.

### ADR-49 — As superfícies órfãs, e o gate que não provava comportamento (v1.9.7, F-UI)
**O pré-requisito veio primeiro, e ele era uma dívida declarada sem dono.** O
ADR-41.3 nomeou a lacuna com precisão — *"não existe runner de teste de UI no
desktop (só `tsc --noEmit` no gate)… o que isso NÃO prova: que o onClick foi
religado"* — e ela não estava em G-1..G-10, portanto não entrou em fase nenhuma,
enquanto quatro entregas da vitrine passavam a depender dela. Medido nesta
árvore: **desligar o `onClick` do botão de reparo deixa `tsc --noEmit` sair 0**
e o smoke reprovar. `vitest` + `jsdom` entram com config **separada** do
`vite.config.mts`, que carrega o plugin de Electron e subiria um processo de
Electron dentro do runner. `npm test` entra em `[gate]`, na CI e no `justfile`.
**Cinco superfícies órfãs, todas com a mesma forma**: use case completo,
endpoint completo, método de cliente às vezes já declarado — e nenhuma tela.
- **doctor**: INV-001..006 eram o único verificador de integridade do produto e
  só existiam no terminal. A StatusBar pintava `🩺 stacks!` em vermelho **sem
  ato**, embora três dos seis se resolvam com um POST. Agora há aba, lista de
  findings, botão de reparo que só se oferece quando há finding reparável, e o
  badge navega para ela;
- **undo**: completo desde o F1-PR1, com 409 nomeado, e inalcançável porque
  `/curation/history` não tinha método no cliente — sem o `act_id` não havia
  como chamá-lo. Aplicar era irreversível pela interface;
- **cancel/retry**: o botão `↻` chamava `enqueue(type, payload)` e criava um
  job **novo**, deixando o antigo `failed` para sempre, zerando o rastro de
  tentativas e furando o dedupe, enquanto `/jobs/{id}/retry` existia. Cancelar
  não existia. A tabela conhecia **quatro** dos oito estados da fila — e os
  quatro que faltavam são os que dizem o que fazer.
**O SSE era o pior dos cinco, e o mais difícil de ver.** O `EventSource` só
entrega evento nomeado a quem registrou aquele nome; `onmessage` recebe só os
sem nome. O cliente registrava **cinco** e o daemon declara **sessenta e dois**.
Medido no fio, ingerindo uma nota: **10 frames, 6 tipos distintos — o cliente
antigo receberia 3**. `page.stage`, `compile.extracting` e `source.ingested`
saíam do backend e morriam ali, com o Stepper do Inbox e a barra de progresso
por job já escritos, tipados e nunca alimentados uma única vez.
**A correção não é uma lista maior.** Lista fixa maior cai na mesma armadilha
na próxima adição. O produto **declara** o vocabulário em
`runtime/events.py:EVENT_TYPES`, `/events/types` o serve (aditivo — nenhuma
mudança de fio, nenhum RFC), o cliente pergunta, e **`emit` recusa tipo não
declarado**: mesma disciplina de `DERIVATIONS` (ADR-46), registro dinâmico é
registro que ninguém garante.
**Três guardas, porque nenhuma cobre o buraco da outra**, e isso foi descoberto
falhando: a varredura estática por literais deu verde com **nove** tipos de
fora (`focus.goal.created` tem TRÊS segmentos e a regex tinha dois fixos); a
recusa em runtime pegou esses nove ao rodar a suíte — e deixaria passar
qualquer caminho não exercitado; a família por f-string (`f"retrieval.{…}"`)
escapou das duas e tem teste que lê o condicional que a gera, ignorando as
strings **comparadas** e olhando só as **produzidas**.
**`test_pontas_soltas` inverteu de sinal, que era o combinado.** Ele declarava
*"o undo segue inalcançável"* e quebraria *"no dia em que alguém religar":
religou e quebrou. Rotas órfãs 12 → **11**; eventos mudos 44 → **0** — e o teto
zero não é tautologia: a função que mede lê o `.ts` e, sem a ligação a
`/events/types`, volta a acusar 44.
**Falsificabilidade por mutação, uma por correção**: `onClick` do reparo
desligado (tsc verde, smoke vermelho) · ponte SSE de volta aos cinco nomes (3
testes) · `retryJob` de volta a `enqueue` (1) · 409 do undo engolido (1) ·
cliente sem a busca de tipos (o teto de mudos volta a 44).
17 testes de UI — **os primeiros do projeto** — e 6 de backend; **662** no
backend, 17 no desktop.

### ADR-50 — Colisão de caminho vira decisão humana (v1.9.8, F3-PR1)
**Decisão registrada por RFC-003 (`docs/20`)**, porque a escada de
reconciliação — com árbitro LLM opcional — passa a informar o `promote`, o
caminho de escrita **humano** mais usado do produto (`docs/15` §1.1 já exigia
RFC para a F3 por exatamente isso).
**O defeito, reproduzido antes de corrigir**: dois promotes do mesmo título e
o segundo APAGAVA a página do primeiro — 40 linhas de anotação humana viravam
um rascunho de duas, com o log registrando *"Creation"*. O caminho destrutivo
dominante não era UPDATE: era **ADD sobre `rel_path` existente**, que a escada
estruturalmente não vê (ela exclui a própria `rel_path` dos degraus) e que o
`promote` nem consultava.
**Três camadas, cada uma com mutação que a derruba**:
1. **`policy.path_collision`** — o `log_kind` que o writer já recebia vira
   `intent` no gate: *"Creation" sobre página existente é erro*. A regra lê o
   FILESYSTEM, não a projeção — vale com o índice irreparavelmente atrasado e
   para qualquer chamador futuro que minta a intenção;
2. **`op="COLLISION"`** — o promote roda `analyze()` (detecção pura, nenhuma
   reescrita de prosa) e a MESMA escada do RFC-002; colisão de caminho ou de
   similaridade devolve a decisão ao humano **sem escrever nada**, com três
   saídas: escrever sobre a residente (log `Update`, frontmatter **fundido**
   por `merge_meta`), criar com sufixo determinístico, ou cancelar. No caminho
   humano a heurística **informa**; quem escreve é a pessoa;
3. **fusão no fluxo de máquina** — UPDATE reconstruía o frontmatter do zero e
   tags curadas por humano evaporavam a cada recompilação, com
   `policy.metadata_shrink` (warn) como único guarda. `_merged_with_resident`
   usa a mesma `merge_meta` do MergePages: uma regra de fusão, não duas.
**A UI parou de mentir junto**: o `PromoteDialog` mostrava *"✅ criado: ok"*
para qualquer resposta — inclusive uma COLLISION que não escreveu nada. Agora
apresenta as três saídas, e o teste de mutação prova que reverter o dialog ao
comportamento antigo derruba exatamente os 3 testes de colisão.
**Verificado no fio**, daemon real: ADD → COLLISION (residente intacta, log
intocado) → `resolution=update` (log *"[Update] promovido SOBRE …"*) →
`resolution=new_slug` (`docker-2.md`). O evento `memory.promoted` não é
emitido em COLLISION — seria a mentira do log, no barramento.
**Registro epistêmico 1.5.0 → 1.6.0**: o contrato `reconciliation` declara o
caminho humano no `validity_scope` e ganha `promote_memory.py` nos
`implementation_refs`.
**Condições de reentrada** (RFC-003 §12): auto-fusão na zona alta só com
golden set; undo de criação continua dívida do ADR-41.1 (o `new_slug` cria
via promote, que não é ato de curadoria); colisão interativa na consolidação
em lote fica para F6.
9 testes de backend + 4 de UI; **671 no backend, 21 no desktop**.

### ADR-51 — Veredito e vitalidade: a fila para de mentir (v1.9.9, F3-PR2)
**"Nada fecha e nada aposenta"** é como `docs/14` nomeia o P-3, e cada palavra
era literal. Reproduzido antes de corrigir:
```
review_items -> ['concepts/apagada.md', 'concepts/morta.md', 'concepts/viva.md']
```
`morta.md` tinha `superseded_by` — aposentada por um ato humano explícito — e
`apagada.md` **nunca existiu no bundle**: `page_heat` guarda uso por caminho e
nenhuma fonte o confrontava com a autoridade. Uma pergunta respondida também
não tinha como sair: `type: question` valia 0.9 e voltava ao topo todo dia.
**Dois níveis, separados pelo invariante — e a separação é a decisão.**
Veredito sobre objeto **canônico** mora no canônico: `answered_by` e
`resolved_at` no frontmatter, escritos pelo ato `CloseQuestion`, versionados
em Git e revertíveis pelo `undo` como qualquer outro ato. Veredito sobre
padrão **computado** (ponte, contradição candidata) não pode morar lá — não é
página, é relação derivada que o job recria — e vai para `pattern_verdicts`
(runtime 9→10), pelo MESMO motivo dos checkpoints (ADR-46): guardado em
`index.db`, o juízo humano seria apagado pela recomputação que ele existe
para calar, e o item rejeitado voltaria na execução seguinte.
**A chave sai da evidência canônica, nunca da época.** O caminho óbvio seria
chavear pelo inteiro `community` do Leiden — e ele muda a cada execução, então
o veredito de hoje suprimiria um padrão diferente na semana que vem.
`pattern_key` hasheia os `rel_path` ordenados: A↔B é o mesmo padrão que B↔A,
para sempre. E rejeitar suprime com `until`, **jamais DELETE** — apagar a
linha seria desfeito pela próxima recomputação e não deixaria rastro do juízo.
**A primeira verificação do `CloseQuestion` era TEATRO, e a medição mostrou.**
A ideia óbvia — recusar se o `/ask` ainda abstém — não serve: com
`abstain_threshold = 0.0` (o default) a abstenção quase nunca dispara e,
pior, perguntar o título de uma pergunta **encontra a própria pergunta**, que
é uma página do bundle (`páginas na evidência: ['questions/q2.md']`). A guarda
passaria apontando para uma página de culinária. O que se verifica é o
**vínculo**: perguntado o título, o produto chega à página declarada como
resposta? A própria pergunta é descartada das evidências. E a verificação não
decide — `force=true` fecha contra a máquina, e a força fica no preview e no
log.
**`policy.dangling_successor` não existia nem para `superseded_by`**, que está
no produto desde a v0.8: dava para aposentar uma página apontando para o
vazio, tirando-a da fila sem sucessora real. A regra vale para o LOTE, porque
a fusão escreve sucessora e aposentada no mesmo `write`.
**A dívida do ADR-41.5 foi paga junto**, porque é o mesmo defeito: `resolved =
any(...)` silenciava o GRUPO INTEIRO assim que uma sucessão aparecesse — com
A, B e C no mesmo DOI, fundir A em B calava o par (B, C) sem tratá-lo, no item
de maior VoI da fila. A sucessão passa a **particionar** o grupo (union-find):
resolve o bloco que liga, não o grupo. O teste que fixava a dívida inverteu de
sinal, como o combinado.
**`[mechanisms.attention_queue]` finalmente existe** (registro 1.6.0 → 1.7.0):
a superfície que ORDENA o tempo do usuário não tinha contrato nenhum e era um
dos cinco `mechanism_promised` do lint. O nome saiu de `PROMISED_MECHANISMS` e
entrou em `EXPECTED_MECHANISMS` — o gesto de mover é o que registra a dívida
paga. Restam quatro.
**Verificado no fio**, daemon real: pergunta na fila → `close_question` sem
`force` (*"verificado: perguntado o título, o produto chega a …"*) → **fila
vazia**, com log `[Update] pergunta fechada por …`.
**Falsificabilidade, seis mutações**: `review_items` sem filtro · `gap_items`
sem o corte · `bridge_items` sem vitalidade nem veredito (3 testes) ·
`check_corpus` com o `any()` de volta · sem `dangling_successor` · verificação
do `close` desligada. Cada uma derruba exatamente os testes que a cobrem.
19 testes de backend + 4 de UI; **690 no backend, 25 no desktop**.

### ADR-52 — F4: os números epistêmicos param de mentir (v1.10)
**Contexto**: três promessas centrais do produto são traídas pelo número
que as representa, e as três moram no mesmo lugar (`epistemics.toml` +
`/ask`) — por isso o `docs/14` as agrupa na F4:

- **P-9**: `base._document` carimba `valid_at = now` junto com
  `timestamp = now`. O eixo de tempo de MUNDO colapsa no de escrita — o
  filtro `as_of` (que existe e é testado) filtra sobre um campo que não
  significa o que o `docs/01` §4 promete;
- **P-4**: a "confiança" do `/ask` é `1 − entropia da fusão`: mede
  DISPERSÃO e **zera quando a base é rasa** — certeza máxima exatamente
  quando a evidência é mais fraca. `evidence_sufficiency` é um dos
  contratos prometidos que o lint lista desde o G-10;
- **P-5**: `page_overlay.status = 'contested'` deriva de DESFECHO DE USO
  ("levou a beco") e cinco superfícies o exibem como disputa factual.

**Decisão** (três, uma por problema):

1. **`valid_at` deixa de ter default de escrita.** Página de máquina só
   carrega `valid_at` quando o conhecimento o fornece (extração, draft,
   ato humano com `when`). Ausente ⇒ válida em qualquer `as_of` (o
   comportamento do filtro já era esse: `not va ⇒ passa`). `timestamp`
   segue sendo o registro. NÃO é breaking: campo opcional no OKF desde
   sempre, e a partição bi-temporal do fuse não muda de forma.
2. **`support` nasce AO LADO de `uncertainty`** (aditivo — a razão de a
   F4 ser ADR e não RFC). `kernel/sufficiency.py` (puro) compõe quatro
   parcelas já disponíveis no request: páginas distintas (satura em 3),
   streams que corroboram (satura em 3; `fused.provenance` já existia
   para o Hedge), fração de evidência aterrada por span (v1.8) e fração
   fresca (nem stale nem superseded). `uncertainty` continua publicada e
   ROTULADA como dispersão. O contrato `evidence_sufficiency` sai de
   `PROMISED` para `EXPECTED` (registro 1.9.0) declarando o `support`
   como COMPOSTO heurístico: parcelas com saturação de projeto, não
   calibradas — mas a propriedade que importa é testada: base rasa ⇒
   support BAIXO mesmo com uncertainty 0.
3. **`contested` → `low_yield`** em valor, chave e rótulo — com a
   detecção de conflito REAL (`policy.factual_conflict`) entrando
   depois, separada, porque rename honesto e detector novo não se
   revisam juntos.

**Rollout em três PRs** (colisões de arquivo e revisabilidade):
**F4-PR1** = decisões 1 e 2 (este ADR, `base.py`, `sufficiency.py`,
`ask_memory`, contrato, painel); **F4-PR2** = decisão 3 (rename em ~19
arquivos + CHECK de `page_overlay` com migração index.db 9→10 +
superfícies); **F4-PR3** = `policy.factual_conflict` (quantity/date,
mesma dimensão, fora de tolerância, span nas DUAS — precisão > recall) +
limpeza do legado de `valid_at` como ATO em lote com preview.

**Invariantes**: INV-EPI-001 reforçado (o número central do produto
ganha contrato); INV-DATA-001..004 intocados. **Portas de reentrada**:
calibrar as saturações do `support` contra o golden quando houver
amostra; o legado de `valid_at` (~toda página de máquina existente) fica
INALTERADO até o ato em lote da F4-PR3 — reescrever frontmatter em massa
sem preview seria exatamente o que o produto proíbe.

### ADR-53 — Corpusmith: o nome, a categoria e o que o produto pode alegar (v2.0.0)
**Documento completo em [`docs/21`](21-adr-categoria-corpusmith.md).** Quatro
identidades concorrentes (Brain Compiler, LLM Wiki, `llmwiki`, `braincore-*`)
unificadas em **Corpusmith — o compilador local e governado de conhecimento**.
A categoria antes do nome: *outras memórias ajudam agentes a recordar;
Corpusmith governa o que humanos e agentes podem tratar como conhecimento.*
Rename mecânico completo (pacote, CLI, binário, header, env vars, preload,
appId, crates, módulo PyO3) com **compatibilidade deliberada**: `LLMWIKI_*`
aceito como fallback e `~/llmwiki` com dados vence `~/corpusmith` vazio —
verificado no binário empacotado. Versão **2.0.0** porque o rename é breaking.
A fronteira de honestidade fica fixada por escrito: a alegação atual é
*"máquinas escrevem sob políticas; humanos governam, revisam e podem
reverter"* — "Agents propose… Git remembers" é visão-alvo, e "source of
truth"/"zero hallucination"/"somente humanos escrevem" são alegações
proibidas no estado atual.

### ADR-54 — Ontologia: um campo, um eixo (RFC-004, v2.1)
**Documento completo em [`docs/22`](22-rfc-ontologia-da-assercao.md); léxico em
[`docs/23`](23-ontologia-e-etimologia.md).** `confidence` respondia a seis
perguntas, três delas dividindo literalmente o mesmo campo do frontmatter —
`extracted`/`inferred` (como derivou), `ambiguous` (foi assentada?) e
`human_approved` (quem autorizou) — e o Harness, que valida `privacy`, checksum,
PII e sucessão, **não validava `confidence`**: sem vocabulário fechado, qualquer
string passava.

A conflação tinha consequência executável, não teórica: `merge_meta` ordenava por
uma tabela de fraqueza de três valores num campo escrito com quatro, e
`human_approved` caía no `default=0`. Medido: `merge("human_approved",
"extracted")` devolvia `human_approved` e `merge("extracted", "human_approved")`
devolvia `extracted` — a mesma fusão com dois resultados conforme a ordem dos
argumentos, isto é, conforme qual página o curador clicou primeiro. Não é a regra
errada; é a **ausência de regra**, com um acidente de dicionário respondendo no
lugar dela.

**Adotado**: três eixos com vocabulário fechado em `kernel/ontology.py`
(`derivation_method`, `resolution_status`, `governance_status`); o quarto
(`evaluation_status`) **não** é redefinido, porque já existe fechado em
`epistemic/model.py` aplicado a mecanismo — a segunda definição do mesmo termo é
o defeito que o ADR combate. A fusão passa a decidir eixo a eixo: derivação fica
com a mais fraca, resolução fica ambígua se qualquer lado for, e governança só
permanece `ratified` se **ambos** forem — ratificação é ato sobre um conteúdo, e a
fusão produz outro conteúdo. `ontology.toml` vira o terceiro contrato
legível-por-máquina, com verbetes que declaram a raiz etimológica e, sobretudo, o
que a palavra **não** significa; `ontology lint` entra no gate nas três fontes
que `test_pr0_gate` cruza.

**Rejeitado**: renomear `confidence` agora (migração do bundle canônico por um
ganho que não depende dela) e validar o campo contra os quatro valores sem
separar os eixos (fecharia a porta congelando a conflação).

**Adiado com condições de reentrada**: `Assertion`/`EvidenceLink`/`AuthorityGrant`
como entidades (RFC-004 §6). Implementar antes de medir uma consulta que a
granularidade de página responde errado seria fazer o que este ADR acusa —
inventar estrutura onde falta evidência.

### ADR-55 — A re-mira executada: as decisões técnicas de V1–V6 e F6 (RFC-006, PR #48)
**Direção em [`docs/29`](29-rfc-006-re-mira.md); dicionário em [`docs/30`](30-dicionario-da-re-mira.md); fechamento em [`docs/18`](18-backlog-consolidado.md) §10.**
Este ADR registra, depois do fato, as decisões que os oito pacotes tomaram sem
ADR próprio — o `docs/14` §1 pedia "ao iniciar uma fase, ela vira ADR" e o
`docs/15` §3 prescrevia ADR para schema aditivo; o PR mudou schema, modelo de
contrato e domínio de sujeito e o registro de decisões parou na ADR-54.

**Adotado (por pacote):**
- **V1** — os subkinds de `standard` (iso/nbr/rfc/nist/ieee/eu_reg + o detector
  novo de circulares) entram em `CONTRADICTION_IDS`, a MESMA maquinaria da
  RFC-005; `regulator` fica fora (nomeia um referente, não um documento) e
  `STRONG_IDS` da reconciliação não muda — congelado por teste;
- **V2** — o sentido mora no CANÔNICO (`Entropia (física)`), não num campo
  `sense` paralelo; precedência entre camadas (seed < reference < bundle) é
  resolução, colisão dentro da camada é ambiguidade (`confidence=ambiguous`:
  não reescreve, não indexa, não liga); `policy.alias_conflict` nomeia o ato
  que resolve. Zero schema, zero migração;
- **V3** — estabilidade editorial como DERIVAÇÃO declarada em `DERIVATIONS`
  (lê Git + frontmatter, nunca `runtime.db`), um sentido só entre os quatro
  de "estabilidade"; sem limiar de "núcleo";
- **F6** — `ask_misses` em `runtime.db` como dado de USO (rebuild não apaga),
  chave determinística (`kernel/sketch.miss_key`: entidades da pergunta;
  sem entidade, SimHash), gravação no retorno TERMINAL da abstenção,
  fechamento só por re-ask que responde;
- **V4** — dificuldade como COMPOSIÇÃO pura de cinco sinais de cinco donos,
  pesos e tetos DECLARADOS não calibrados, `low_yield` fora, silêncio ≠
  facilidade (`medida=false`), SEM derivação em `DERIVATIONS` (dois sinais são
  de uso e não movem o HEAD); o limiar de sobreconfiança é constante repetida
  presa a `validate_policy({})`, porque a memória não importa `cognitive/`;
- **V5** — vocabulário FECHADO de relações (`applies_to`/`exemplifies`/
  `refines`), estrito na escrita (o ato recusa fora do vocabulário) e
  tolerante na leitura (projeção converte desconhecido em `NULL`);
  `graph_edges.rel` aditivo + migração idempotente + `INDEX_GENERATION` g6;
  a aresta vale para a PÁGINA inteira e `ambiguous_fraction` mede o preço
  do nível (zero aresta ⇒ `None`);
- **V6** — a ficha sem campo de `value`/`gain`/`roi` (recusa estrutural:
  não há onde escrever número não medido), `not_measured` como conteúdo,
  borda LLM desligada por default e o rodapé de ressalvas re-anexado DEPOIS
  do modelo.

**Rejeitado**: campo `sense` separado (segundo dono do mesmo fato); campo de
ganho na ficha (autocertificação); derivação declarada para a dificuldade
(prometeria frescor que a cadeia não entrega); mudar `STRONG_IDS` por carona
da V1.

**Migrações e projeções**: `page_stability`, `page_difficulty` (projeções
recomputáveis), `ask_misses` (uso), `graph_edges.rel` (`ALTER TABLE`
idempotente); reindexação completa na primeira subida (g5 → g6).

**Condições de reentrada**: a marca `contested` no canônico e o nível da
AFIRMAÇÃO (RFC-004 §6) esperam `ambiguous_fraction` medido em corpus real
(`docs/18` §11 Q-21); calibração de pesos de V4 e da tolerância de 1%
esperam desfechos de prática e golden (idem); a superfície no cockpit das
capacidades V3/V5/V6 é o primeiro bloco da fila corrente (Q-1…Q-7) — este
ADR registra que elas saíram CLI/facade-only e que isso é dívida, não
entrega.

### ADR-56 — O contrato epistêmico declara o que ESCREVE (C6, PR #48)
**Documento: [`docs/11`](11-epistemic-contracts.md) §7b; achado de origem:
[`docs/17`](17-auditoria-integridade.md) C6.** Um `POST /ask` com
`memory.auto_recycle` reidratava uma página, escrevia no bundle e movia o HEAD
do Git — e o `EpistemicContract` não tinha campo onde isso pudesse ser dito,
logo nenhuma regra de lint podia acusar. A lacuna era geradora.

**Adotado**: enum fechado `SideEffect` (`none` · `canonical_write` ·
`projection_write` · `state_write` — donos distintos, não graus); campo
`side_effects` no contrato, opcional com default vazio (registro antigo segue
válido; `schema_version` continua 1); duas regras de lint —
`canonical_write` exige `high_impact` (o bundle é a autoridade e o commit é
para sempre) e `none` ao lado de outro efeito é contradição; os 28 contratos
declarados um a um; superfície no painel Qualidade.

**A guarda, e a correção de nível que ela sofreu**: a declaração é cruzada
com o código por AST — se um módulo citado em `implementation_refs` importa o
`BundleWriter`, ALGUÉM entre os mecanismos que o citam tem de declarar
`canonical_write`. A primeira versão procurava a substring (acusava sete,
cinco eram comentário); a segunda exigia a declaração de TODO mecanismo do
módulo — e `inferred_cooccurrence_edges` mostrou o erro de nível (`docs/28`
§2): vive em `detect_communities.py`, que escreve páginas de comunidade, mas o
MECANISMO só monta adjacência em memória; a regra forçaria uma declaração
FALSA para calar o teste. O invariante honesto é por MÓDULO — mais fraco, e
verdadeiro.

**Rejeitado**: graus de efeito (uma escala) em vez de donos distintos;
tornar o campo obrigatório de imediato (invalidaria 25 contratos por
retroatividade).

**Resíduo declarado**: a resposta do `/ask` ainda não diz que reciclou nem
emite evento único — `docs/18` §11 Q-5.

### ADR-57 — Registros com dentes: NFRs, invariantes, documentação e o mapa gerado (PR #48)
**Contexto medido em 2026-09-02.** Seis lentes de auditoria sobre o
repositório encontraram o mesmo padrão em quatro lugares: o que estava
DECLARADO não era cobrado por nada. Os requisitos não funcionais viviam em
prosa com selo (`docs/10` §5–§17), e o selo citava arquivo em vez de teste
(`INV-PRIV-001 → harness/local_policy.py`, que só exige o campo); §5.2 e §15
diziam coisas opostas sobre o mesmo `PRAGMA synchronous`; a tabela de
invariantes tinha 15 linhas no `AGENTS.md` e 16 no `docs/10`; nenhum teste
abria um documento de `docs/` (o índice dizia "17 verbetes" com 22 no
registro; a spec dizia "1.5.0, 248 testes" com o produto em 2.0.0 e 900+); o
mapa de camadas estava copiado em seis arquivos com quatro conteúdos; cinco
planos congelados não diziam ao leitor que eram fotografias; e o context
pack prometido em `docs/10` §18.4 nunca existiu.

**Adotado** — o mesmo tratamento que `architecture.toml [gate]` e
`epistemics.toml` já recebiam, agora para o resto:
- [`nfr.toml`](../nfr.toml): um requisito por entrada com `level`
  (`guarantee` · `premise` · `target`), `status` (`pinned` · `measured` ·
  `declared`) e `verified_by` — `test_nfr_toml.py` recusa teste que não
  existe, `pinned` sem prova, `declared` sem `notes`; três requisitos
  ganharam a prova que não tinham (PRAGMAs aplicados, handshake 0600,
  loopback por default). A contradição de durabilidade foi resolvida como
  PREMISSA (NFR-DUR-003): "RPO 0 após ACK" vale contra crash de processo;
- `architecture.toml [[invariant]]` como dono único da tabela do `AGENTS.md`
  §4, com `verified_by` resolvendo (`test_architecture_toml.py`);
  `INV-PRIV-001` passou a citar os testes reais e a metade sem teste virou
  NFR-PRIV-002 `declared`;
- `test_docs_contract.py`: todo `docs/*.md` declara `Altitude` e `Status`
  (`vivo` \| `histórico`) na cabeça, histórico aponta para a fonte viva,
  `AGENTS.md` não roteia histórico como destino, o índice lista todo
  arquivo, todo link relativo resolve (fora de crase), doc VIVO não crava
  contagem de mecanismos/termos/testes (ledgers e RFCs podem);
- `corpusmith context` / `just context` (`context_pack.py`): o mapa
  determinístico — versão, HEAD, camadas, gate, invariantes, NFRs por
  status, registros, bancos, derivações, eventos, jobs, rotas, use cases,
  ADRs, altitude/status de cada doc e a fila corrente — lido das fontes que
  já são autoridade (TOMLs, constantes, o fonte por AST), preso por
  `test_context_pack.py`. Regra: o que é enumerável é gerado; à mão fica só
  o porquê;
- as skills param de copiar o gate e de mandar cravar contagem
  (`test_pr0_gate.py`); estratégia de merge única (squash, como o
  CONTRIBUTING).

**Rejeitado**: um documento novo de direção (RFC-007) — a direção do
RFC-006 não mudou e seria o sexto plano sobre o mesmo assunto; tornar
`test_docs_contract` capaz de verificar contagens dentro de ADRs e RFCs
(eles registram o que era verdade no commit — é ledger, não estado);
gerar os documentos conceituais inteiros (o porquê continua à mão).

**Consequências**: `docs/10` deixa de carregar estado (contagens, versão,
lista de comandos) e passa a ser doutrina; o estado vem dos registros e do
mapa. Um selo ✅ que cite arquivo em vez de teste passa a ser bug de
documentação com guarda. **Dívidas declaradas**: docs gerados com teste de
frescor e cabeçalho de contrato por módulo (`docs/18` §11 Q-19); o ledger
de versões (`v2.1` em `ontology.toml`/ADR-54 com produto 2.0.0 — Q-26).

### ADR-58 — PyO3 0.29 e a extensão nativa que passa a ser EXERCITADA, não só construída (v2.0.0)
**Compute plane: ADR-39; precedente de processo: ADR-47 (o binário
empacotado) e G-2 (o ramo `[ml]`).**

**Contexto medido.** O Dependabot abriu o bump de `pyo3` 0.23.5 → 0.29.0 e a
perna `native` da CI reprovou com **seis** erros `E0599`, todos o mesmo:
`no method named allow_threads found for struct Python<'py>`. A causa não é
defeito do bump — é renomeação de API: o PyO3 0.25 trocou o vocabulário do
GIL (`Python::allow_threads` → `Python::detach`, `Python::with_gil` →
`Python::attach`) e o 0.29 removeu os nomes antigos. Os seis erros são os
seis pontos onde este crate libera o intérprete durante trabalho pesado —
nenhuma outra parte da migração de seis versões menores tocou o código, que
já usava a API `Bound` desde a 0.23.

**O achado que o bump revelou, e que é maior que ele.** A perna `native`
construía o wheel com `maturin build` e **nunca o instalava**. Como
`backend/tests/test_compute_differential.py` abre com
`pytest.importorskip("corpusmith_native")`, os testes diferenciais do
ADR-39 — igualdade exata no determinístico, `|Δ| ≤ 1e-8` em PPR/Brandes —
**pulavam em todas as pernas da CI**. A equivalência Rust≈Python, que é a
única prova de que o acelerador não muda o significado, nunca era
exercitada. O bump quebrou a COMPILAÇÃO e por isso foi visto; uma mudança
de COMPORTAMENTO na fronteira FFI teria passado verde.

**Adotado**: (1) `pyo3 = "0.29"` e os seis `py.allow_threads(…)` →
`py.detach(…)` — mesma semântica, nome novo, com a razão registrada no
docstring do módulo para quem vier do vocabulário antigo; (2) a CI instala
o wheel e **roda** os diferenciais; (3) o token
`test_compute_differential.py` entra em `[gate].ci_enforced`; (4) uma
asserção direta sobre o `ci.yml`
(`test_a_extensao_nativa_e_instalada_e_exercitada_pela_ci`) exige a
instalação **e** a execução — porque o token não guarda a si mesmo:
medido por mutação, apagá-lo deixava a suíte verde; (5) `nfr.toml`
NFR-PKG-002 registra o requisito com o limite dito (o `importorskip`
continua pulando fora da CI, e o fallback Python segue suportado).

**Rejeitado**: permanecer em 0.23 e fechar o PR do Dependabot — a migração
custou seis renomeações e a dívida na única dependência de fronteira FFI
cresceria a cada versão; trocar o `importorskip` por falha dura — o
fallback Python é comportamento suportado pelo ADR-39, e exigir Rust para
rodar a suíte contradiria "o produto funciona sem Rust".

**Consequências**: a suíte local com a extensão instalada passa de 1098
para 1112 testes (os 14 diferenciais deixam de pular); o wheel abi3-py311
segue compatível; nenhuma mudança de comportamento, de schema ou de
autoridade. **Limite declarado**: nem o token nem a asserção provam que o
wheel instalado é o do commit — a CI o constrói e instala no mesmo job, e
essa cadeia é premissa, não garantia.

### ADR-59 — Um dono para o refresh das projeções, e o vazio que diz qual vazio é (Q-1)

**Contexto.** As três capacidades da re-mira que o cockpit não alcançava
(V3 "o que menos muda", V5 "onde se aplica", V6 "a ficha") são também as
três que dependem de projeções calculadas. Ao levá-las à tela, a auditoria
da Q-1 mediu um defeito de desenho que estava debaixo delas: **havia três
caminhos para o mesmo número**. `ComputeStability`/`ComputeDifficulty`
recomputavam e persistiam (CLI); `observatory.insights` lia o persistido;
e `ConceptSheet` recomputava ao montar — `git log` da história inteira
mais o lint do corpus inteiro, por abertura de ficha. Três donos do mesmo
valor podem responder três coisas diferentes à mesma pergunta na mesma
máquina, e o terceiro cobrava o preço mais alto no momento mais sensível
(o resíduo de custo P-11 dentro de um clique).

**Decisão.**

1. **Quem escreve é o refresh, e ele é um só**: os comandos/jobs que já
   persistiam (`corpusmith stability`, `corpusmith difficulty`, e a
   reindexação para `page_entities`). Nenhuma leitura recomputa.
2. **Quem lê passa por `retrieval/projections.py`** — ficha, rotas do
   cockpit e painel Indicadores. Um leitor, uma SQL, um vocabulário.
3. **A passada de lint tem um dono** (`ComputeDifficulty`) e alimenta
   DUAS projeções na mesma transação: `page_difficulty` (os números) e a
   nova `page_divergence` (com QUEM a página desacorda). Rodar o lint uma
   segunda vez na abertura da ficha custaria o dobro e as duas leituras
   poderiam discordar.
4. **`computed` viaja em toda projeção lida.** São três estados, não
   dois: nunca calculado (não diz nada sobre página nenhuma), calculado e
   sem sinal (`measured=false` — um resultado), calculado com número.

**Por que não um "job leve" no scheduler.** Era a alternativa óbvia e
teria criado um TERCEIRO recomputador ao lado do CLI e da ficha, movendo
o problema em vez de resolvê-lo. O refresh já tem dono; o que faltava era
tirar os outros dois, não acrescentar mais um.

**Consequência aceita, e dita na tela.** A ficha pode servir projeção
velha. É o preço de não pagar o corpus por clique, e por isso ela mostra
`freshness` (do checkpoint `stability`), `computed_from` (o HEAD do
cálculo) e o comando que atualiza — em vez de esconder a idade
recomputando. Um número velho rotulado como velho é honesto; um número
fresco cobrado em silêncio a cada abertura de tela não é sustentável.

**O que o vazio deixou de poder mentir.** Antes daqui a ficha e o painel
diziam "nada observado ainda" para os DOIS vazios — inclusive quando a
projeção nunca havia rodado. Isso é vender silêncio como medição: o
avesso exato da autocertificação que o contrato `concept_sheet` recusa, e
igualmente falso. O `computed` separa os casos, `_CONTRATOS` ganhou
`alias_conflict` e `factual_conflict` (as duas linhas novas da ficha), e
`epistemics.toml` foi atualizado no MESMO commit — inclusive a suposição
que dizia, literalmente, que a ficha recomputava.

**Verificado por execução.** `test_q1_ficha_no_cockpit.py` e
`ConceptSheetView.test.tsx`, com onze mutações executadas: empatar "nunca
calculado" com `0`; a ficha voltar a chamar `Compute*`; remover o
`DELETE FROM page_divergence`; remover o consumidor da rota; tirar
`alias_conflict` de `_CONTRATOS`; deixar a própria página no grupo de
divergência; remover `difficulty_computed` do observatório; dar aos dois
vazios a mesma frase no cockpit; remover o bloco do que NÃO foi medido;
pôr o ✅ na primeira célula da linha da fila (o mapa larga o item em
silêncio); e trocar a testemunha da lente. Todas mataram.

**Um achado que só a execução deu.** A primeira versão usava
`page_entities` como testemunha de "o índice rodou" — e numa execução
sobre bundle sintético a ficha respondeu "ainda não calculado" para um
índice FRESCO que simplesmente não reconheceu identidade nenhuma. É o
mesmo erro deste ADR cometido do outro lado: resultado lido como
silêncio. A testemunha certa é `page_index_state` (o índice VIU a página,
ache ele o que achar), e a lição — a testemunha de "calculado" tem de ser
o registro do CÁLCULO, nunca o do achado — está presa por teste.

**Limite declarado.** `page_divergence` herda o recall do lint: só enxerga
desacordo entre páginas que compartilham identificador forte (DOI/ISBN/
norma). Duas páginas que se contradizem em prosa, sem identificador
comum, saem da ficha como se não divergissem — está no
`known_failure_modes` do contrato, não só aqui.
