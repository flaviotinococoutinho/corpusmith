# Documentação do Corpusmith

Índice **roteado por especialidade**. Cada documento cobre UMA disciplina,
para que revisor humano e agente de IA saibam exatamente onde uma decisão
mora e não misturem as camadas de raciocínio. A regra de ouro é única:
**o código é a fonte da verdade — a doc nunca descreve o que o teste não
confirma.**

## Onde começar

| Se você é… | Comece por |
|---|---|
| **agente de IA / mantenedor fazendo mudança** | [`../AGENTS.md`](../AGENTS.md) → [`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md) |
| **revisor de arquitetura** | [`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md) + [`../architecture.toml`](../architecture.toml) |
| **entendendo o produto pela primeira vez** | [`00-o-que-e-corpusmith.md`](00-o-que-e-corpusmith.md) — a explicação inteira, do zero |
| **procurando o vocabulário exato** | [`01-conceitos.md`](01-conceitos.md) — e [`23`](23-ontologia-e-etimologia.md) para a raiz e a fronteira de cada termo |
| **procurando uma regra/endpoint/tabela** | [`06-referencia.md`](06-referencia.md) |

## Mapa por especialidade

### 🧭 Produto — o QUE é e para QUEM
Conceitos do sistema como produto, sem detalhe de implementação.

| Doc | Conteúdo |
|---|---|
| [00-o-que-e-corpusmith.md](00-o-que-e-corpusmith.md) | **A explicação completa, do zero**: o problema, a categoria (governar ≠ recordar), a tese de compilação, **um fato seguido do PDF à resposta**, o modelo de autoridade, o que torna as alegações verificáveis e o que o produto NÃO alega |
| [01-conceitos.md](01-conceitos.md) | OKF, camadas de memória, bi-temporalidade, escala de confiança, controle de autoridade, epistemologia (abstenção, desfecho, eval) |
| [23-ontologia-e-etimologia.md](23-ontologia-e-etimologia.md) | **O léxico**: os quatro eixos de uma afirmação, 17 verbetes com raiz etimológica e o que a raiz PROÍBE, a deriva semântica ainda aberta e os falsos amigos do mercado |
| [28-escada-de-abstracao-e-topologia.md](28-escada-de-abstracao-e-topologia.md) | **A escada de abstração** (offset → menção → região → afirmação → página → tema → grafo, com o nível 3 vazio), **erro de nível como classe de defeito** (os três defeitos mais caros do repositório são o mesmo erro) e a **topologia como instrumento epistêmico**: a pergunta de qualidade que cada mecanismo responde, e o que ele NÃO diz |
| [24-axiomas-e-oticas.md](24-axiomas-e-oticas.md) | **Os oito axiomas** (cada um com a asserção executável que o paga) e as **oito óticas** sobre o mesmo corpus, com unidade e frescor de cada uma |
| [25-fronteira-e-diferencial.md](25-fronteira-e-diferencial.md) | **As três fronteiras que o produto não cruza** (coletor, publicador, agente), o lugar dele na cadeia adquirir→compilar→publicar e a evidência de que o método generaliza |

### 🔬 Ciência & teoria — POR QUE funciona
Fundamentos teóricos e científicos, com papers. Não descreve código.

| Doc | Conteúdo |
|---|---|
| [03-teoria.md](03-teoria.md) | Teoria da informação (NCD, entropia, surprisal, Hedge), topologia (persistência 0-dim, centralidade de Brandes), heurísticas de coordenação (RRF, heat, escada de reconciliação), fundamentos cognitivos (CLS, BLA) |
| [26-pesquisa-da-camada-epistemica.md](26-pesquisa-da-camada-epistemica.md) | **A pesquisa da camada epistêmica**: `capta` vs `data`, discordância como traço estrutural, as anomalias de escrita que a literatura tipifica (e que encontramos por mutação), como os vizinhos resolvem contradição, e **onde o Corpusmith não é novo** — nanopublications, micropublications, CRMinf, PROV-O |

### ⚙️ Engenharia, algoritmos & paradigmas — COMO se constrói
Disciplina de software, técnicas de algoritmo, padrões e paradigmas.

| Doc | Conteúdo |
|---|---|
| [10-engenharia-ai-friendly.md](10-engenharia-ai-friendly.md) | **Spec de arquitetura-alvo (BC-ENG-001)**: Functional Core/Imperative Shell, tipos/ADTs, transações, fila, estruturas de dados, padrões, Object Calisthenics — **com selo ✅ implementado / ⚠️ parcial / 🎯 proposto** |
| [11-epistemic-contracts.md](11-epistemic-contracts.md) | **Contratos epistêmicos (ADR-38)**: o que cada mecanismo heurístico pode legitimamente alegar — vieses, pressupostos, garantias RELATIVAS, failure modes, Generalization Envelopes (`epistemics.toml`) |
| [02-metodologias.md](02-metodologias.md) | Método de construção: sanduíche determinístico, precisão>recall, use cases + facades, Template Method, arquitetura-como-teste, golden tests |
| [04-tecnologias.md](04-tecnologias.md) | Stack e contratos de infra: SQLite/FTS5/WAL, Git, FastAPI/SSE, Electron/Vite, roteador de modelos |

### 📐 Requisitos não funcionais (NFR)
Consistência, durabilidade, escala, segurança — tratados como contrato.

| Doc | Conteúdo |
|---|---|
| [10-engenharia-ai-friendly.md](10-engenharia-ai-friendly.md) §5–17 | CAP por operação, `StoragePolicy`, SLI/SLO/RPO/RTO, estágios de escala S0–S3, threat model, segurança de token/privacidade |

### 📖 Referência dura — a tabela da verdade
Constantes, regras, endpoints, tabelas — o que a skill `docs-sync` audita.

| Doc | Conteúdo |
|---|---|
| [06-referencia.md](06-referencia.md) | Todas as regras do Harness, endpoints, tabelas dos 5 bancos, jobs, flags, tipos OKF, frontmatter |
| [../architecture.toml](../architecture.toml) | Contrato de arquitetura legível-por-máquina (preso a `test_architecture_toml.py`) |
| [../epistemics.toml](../epistemics.toml) | Contratos epistemológicos legíveis-por-máquina (presos a `test_epistemics_toml.py`; lint em `corpusmith epistemics lint`) |
| [../ontology.toml](../ontology.toml) | Eixos, léxico com etimologia e registro de deriva semântica (presos a `test_ontology.py`; lint em `corpusmith ontology lint`) |

### 🔄 Fluxos operacionais — QUANDO / ONDE
| Doc | Conteúdo |
|---|---|
| [05-fluxos-operacionais.md](05-fluxos-operacionais.md) | Fluxos fim-a-fim: compilar, perguntar, promover, desfecho→reflect, revisão, comunidades, eval, implantação |
| [07-sinergias.md](07-sinergias.md) | Matriz de interação entre conceitos + receitas de composição e extensão |
| [12-instalacao.md](12-instalacao.md) | Instalação validada (local, Docker, launchd), smoke tests da API e solução de problemas reais (`scripts/install.sh`) |

### 🏛️ Governança — DECIDIR e o que falta
| Doc | Conteúdo |
|---|---|
| [08-decisoes.md](08-decisoes.md) | ADRs: conceitos adotados, adaptados e rejeitados com razão registrada (CLS, ACT-R, AGM, DTT, CRDTs, WFST…) e portas de reentrada |
| [09-backlog.md](09-backlog.md) | Backlog priorizado (P0–P3) e estado de fechamento por frente |
| [13-plano-experiencia-memoria.md](13-plano-experiencia-memoria.md) | **Plano avançado** de experiência de memória/curadoria/classificação — auditoria de consistência + receitas mineradas de projetos externos + roadmap em 4 fases |
| [14-plano-viabilidade.md](14-plano-viabilidade.md) | **Plano de viabilidade** — o que falta para o produto ser usável por quem não é o autor: 14 problemas por complexidade DECRESCENTE (o ato de curadoria e a camada de padrões como objeto) + roadmap em 8 fases + matriz de não-adoção |
| [15-plano-execucao.md](15-plano-execucao.md) | **Plano de execução** — pacotes de trabalho PR a PR das duas fases-modelo, ordem revisada, 10 lacunas de PROCESSO (a CI não executa o gate que o AGENTS.md declara), dependências ocultas, colisões de arquivo e o limiar de RFC |
| [16-rfc-theme-id.md](16-rfc-theme-id.md) | **RFC-001** — identidade de tema por casamento de partições (τ = 1/3 calibrado contra a banda vazia; vocabulário fechado de épocas) |
| [17-auditoria-integridade.md](17-auditoria-integridade.md) | **Auditoria adversarial de integridade** — achados de um cético independente rodando o código (garantias infladas, buracos de lint/gate), com nível de evidência |
| [18-backlog-consolidado.md](18-backlog-consolidado.md) | **Backlog consolidado (fonte VIVA do que falta)** — bugs, fluxos incompletos, débito técnico e experiência, cada item com nível de evidência; atualizado no PR que resolve cada item |
| [19-rfc-escada-reconciliacao.md](19-rfc-escada-reconciliacao.md) | **RFC-002** — a escada de reconciliação volta a ter três degraus (B1: o degrau de similaridade era código morto; árbitro LLM segue atrás de flag desligada) |
| [20-rfc-colisao-de-caminho.md](20-rfc-colisao-de-caminho.md) | **RFC-003** — colisão de caminho entre promoção humana e compilação de máquina (P-7) |
| [21-adr-categoria-corpusmith.md](21-adr-categoria-corpusmith.md) | **ADR-53** — Corpusmith: o nome, a categoria (*governed knowledge compiler*) e a **fronteira de honestidade** — o que o produto pode e não pode alegar hoje |
| [27-rfc-conflito-factual.md](27-rfc-conflito-factual.md) | **RFC-005** — conflito factual como REFINAMENTO da contradição candidata (o `canonical` de uma quantidade é o próprio valor, então o sujeito tem de vir do grupo de identificador); a primeira tolerância numérica do Harness, declarada NÃO calibrada; e o primeiro **leitor** de `contested` (a correção "escritor→leitor" foi medida — §5.3) |
| [29-rfc-006-re-mira.md](29-rfc-006-re-mira.md) | **RFC-006** — **a re-mira: do compilador de corpus ao instrumento de estudo** — o pitch (conceitos comparáveis, rastreáveis, explicáveis e acionáveis: sob qual lente, o que permanece, onde diverge, como se aplica, quanto custa adotar), as seis capacidades V1–V6 verificadas contra o código (V1, V2 e V3 **entregues**), a ficha do conceito como norte da UI, a LLM-wiki/memória de IA como nome de uso, e a fila reordenada (`docs/18` §10) |
| [30-dicionario-da-re-mira.md](30-dicionario-da-re-mira.md) | **Dicionário da re-mira** — os termos que poderiam significar duas coisas, fixados com dono e TESTE que prende (estabilidade em 4 sentidos, lente≠tema≠goal≠eixo, os dois conjuntos de "sujeito forte", conflito≠coexistência≠low_yield); a memória por NÍVEL DE ACESSO (quem escreve, por qual porta, o que sobrevive a quê); e os 11 conceitos de engenharia que pagam manutenção/expansão, cada um com sua asserção executável |
| [22-rfc-ontologia-da-assercao.md](22-rfc-ontologia-da-assercao.md) | **RFC-004** — a ontologia da asserção: os eixos que `confidence` fundia (com a assimetria medida na fusão), o registro de deriva, e `Assertion`/`EvidenceLink`/`AuthorityGrant` como proposta com condições de reentrada |

## Guia rápido de roteamento (para não misturar especialidades)

- **Nunca vi este projeto antes** → `00` (leia inteiro; os outros são de consulta).
- É **o que o usuário vê / por que o produto existe**? → `00`, depois `01`.
- É **o que o produto pode ou NÃO pode alegar** (categoria, fronteira de
  honestidade, nomes históricos)? → `21`.
- É **o que uma palavra significa** (e o que ela não pode passar a
  significar)? → `23` + `ontology.toml`.
- É **uma suposição de base** que o produto assume? → `24` (axiomas), e se
  precisar violá-la, é RFC, não PR.
- É **por qual ângulo estou olhando** (editorial, epistêmico, temporal,
  topológico…)? → `24` §2.
- É **em que NÍVEL isto é verdade** (menção? região? página? corpus?), ou o
  que a topologia pode e não pode dizer sobre qualidade? → `28`.
- É **se o produto deveria fazer isto** (fronteira, escopo, concorrência)?
  → `25`.
- É **por que uma técnica funciona** (prova, paper, matemática)? → `03`.
- É **o que a literatura já resolveu sobre asserção, proveniência e
  contradição** (e o que aqui é adoção, não invenção)? → `26`.
- É **como o software é organizado** (camada, tipo, padrão, algoritmo)? → `10`, `02`, `04`.
- É **o que um mecanismo heurístico pode ALEGAR / onde foi avaliado**? → `11` + `epistemics.toml`.
- É **quanto/quão rápido/quão durável** (CAP, SLO, escala, segurança)? → `10` §5–17.
- É **uma constante/regra/endpoint** que preciso consultar? → `06`.
- É **uma decisão tomada ou o que ainda falta**? → `08`, `09`.
- É **para onde levar a experiência de memória/curadoria/classificação**? → `13`.
- É **o que falta para ser viável para um terceiro** (e em que ordem)? → `14`.
- É **como executar isso** (PR a PR, processo, RFC vs ADR)? → `15` + `AGENTS.md` §8.
- É **o que AINDA falta, com evidência**? → `18` (fonte viva; `14`/`15` são o registro do raciocínio).
- É **para onde o produto está mirando** (o instrumento de estudo, as seis
  capacidades, a ordem)? → `29` + `18` §10.
- É **um termo da re-mira com risco de ambiguidade** (estabilidade, lente,
  sujeito forte), a **memória por nível de acesso**, ou **qual disciplina
  de engenharia prende o quê**? → `30`.
- É **uma heurística no caminho de escrita**? → as RFCs `16`, `19`, `20` são os precedentes instanciados.
- É **como instalar/verificar o ambiente**? → `12` + `scripts/install.sh`.

## Como manter esta documentação

A skill local **`docs-sync`** (`.claude/skills/docs-sync/SKILL.md`) contém o
procedimento: o mapa código→documento, os comandos que extraem a verdade do
código (regras, endpoints, tabelas, jobs) e o checklist de auditoria.
Invoque-a (`/docs-sync`) sempre que uma mudança tocar funcionalidade core.
Ao mudar arquitetura, atualize também [`10-engenharia-ai-friendly.md`](10-engenharia-ai-friendly.md)
e [`../architecture.toml`](../architecture.toml) — este último **quebra o CI**
se divergir do código.

## Convenções de leitura

- Trechos `caminho/arquivo.py:Símbolo` apontam para a implementação.
- Selos de status em `10`: ✅ implementado (com teste) · ⚠️ parcial · 🎯 proposto.
- "Página de máquina" = `generated_via: api:*|local:*`; "página humana" =
  `generated_via: human:*`. A distinção governa quase todas as regras.
- Termos da escala única de confiança aparecem em inglês
  (`extracted`/`inferred`/`ambiguous`): são valores literais no banco e no
  frontmatter.
