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
invariante "índice derivado" — medido 29× em 150 páginas), SimHash
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
negativo — precision-first). **Porta**: regra de lint corpus
(`policy.quote_misattributed`) quando o custo de varrer citações em
todo lint for medido; datasets maiores via import (CSV→payload).
