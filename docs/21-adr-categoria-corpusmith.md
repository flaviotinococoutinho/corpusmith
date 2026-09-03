# 21 · ADR-53 — Corpusmith: o nome, a categoria e o que o produto pode alegar

> **Altitude:** governança · **Status:** vivo

| | |
|---|---|
| **Status** | Adotado (v2.0.0) |
| **Substitui** | as identidades "Brain Compiler", "LLM Wiki", pacote `llmwiki` e crates `braincore-*` |
| **Origem** | análise estratégica de posicionamento (2026-08) |

---

## 1. Contexto: três identidades concorrentes diluíam o produto

Até a v1.10 o projeto atendia por **quatro nomes** simultâneos: o repositório
`brain-compiler`, a comunicação "LLM Wiki", o pacote Python `llmwiki` e os
crates Rust `braincore-*`. Nenhum deles dizia o que o produto é — "brain" e
"wiki" apontam para categorias erradas (cérebro artificial; wiki para LLM), e
a dispersão obrigava cada leitor a reconciliar os nomes antes de entender a
proposta.

## 2. Decisão: Corpusmith, e a categoria antes do nome

> **Corpusmith — the local-first governed knowledge compiler**
> *(o compilador local e governado de conhecimento)*

"Corpus" identifica o material trabalhado; "smith" comunica ofício,
transformação e construção intencional: **fontes brutas → trabalho de
curadoria → corpus durável**. O nome sozinho não explica o produto — por
isso ele nasce SEMPRE acompanhado da categoria.

A mudança importante não é nominal. Ela redefine a categoria:

> **Outras memórias ajudam agentes a recordar. Corpusmith governa o que
> humanos e agentes podem tratar como conhecimento.**

A pergunta que o produto responde — e que nenhuma categoria vizinha
responde — é: *"o que foi aceito como conhecimento, com base em quê, por
quem, em qual período e sob quais limites?"*. Memória de agente responde "o
que recordar"; RAG responde "o que recuperar"; knowledge graph responde "o
que representar". O espaço defensável de Corpusmith é a **combinação**:

corpus aberto **+** registro canônico em Git **+** autoridade humana
explícita **+** projeções descartáveis **+** validade temporal **+**
curadoria reversível **+** contratos epistêmicos executáveis.

Cada elo dessa combinação já existe no produto **como asserção testada**,
não como slogan: canônico ≠ projeção é invariante da suíte; o gate de
escrita é único e inescapável; os contratos de `epistemics.toml` quebram a
suíte quando mentem sobre o código; a colisão de caminho devolve a decisão
ao humano; o `undo` escreve para a frente.

## 3. O que o produto PODE e NÃO PODE alegar (fronteira de honestidade)

Este ADR fixa a fronteira, porque um produto que vende governança não pode
começar exagerando a própria:

**Alegação honesta, hoje**:
> Máquinas escrevem sob políticas; humanos governam, revisam e podem
> reverter.

O caminho de máquina PODE adicionar, atualizar e suceder páginas depois de
passar pelas políticas, e o árbitro LLM existe atrás de flag. Dizer "somente
humanos alteram o canônico" seria falso hoje.

**Visão-alvo** (direção declarada, não estado atual):
> *Agents propose. Policies constrain. Humans ratify. Git remembers.*

**Proibido alegar no estado atual**: "source of truth" (canônico ≠
verdadeiro — o registro diz o que foi *aceito*, e por quem) · "zero
hallucination" · "ontologia formal" · "somente humanos escrevem" ·
prontidão para decisões clínicas ou reguladas.

## 4. O rename mecânico, e as escolhas dentro dele

| antes | depois |
|---|---|
| pacote `llmwiki` | `corpusmith` |
| CLI `llmwiki` / `llmwikictl` | `corpusmith` / `corpusmithctl` |
| binário `llmwiki-server` | `corpusmith-server` |
| header `x-llmwiki-auth` | `x-corpusmith-auth` |
| env `LLMWIKI_HOME`/`_CONFIG` | `CORPUSMITH_HOME`/`_CONFIG` |
| `window.llmwiki` (preload) | `window.corpusmith` |
| appId `dev.flavio.llmwiki` | `dev.flavio.corpusmith` |
| crates `braincore-*`, `llmwiki-native-*` | `corpusmith-*` |
| módulo PyO3 `llmwiki_native` | `corpusmith_native` |

**Compatibilidade deliberada** (renomear o produto não pode desligar a
memória de ninguém em silêncio): `LLMWIKI_HOME`/`LLMWIKI_CONFIG` seguem
aceitos como fallback, e uma instalação sem env var cujo `~/llmwiki` existe
e `~/corpusmith` não, continua usando o HOME antigo — o corpus com dados
vence o diretório novo vazio. Verificado por execução no binário empacotado.

**Versão 2.0.0**, porque o rename É breaking (CLI, env, header, binário,
appId) — e não havia release pública anterior, então não há base instalada a
migrar além dos ambientes do próprio autor, cobertos pelo fallback.

**Artefatos históricos** (ADRs, RFCs, auditoria) foram renomeados junto: os
caminhos que eles citam mudaram de verdade com o `git mv`, e um documento
apontando para arquivo inexistente é pior que um documento editado. A
história dos nomes fica registrada AQUI, e o histórico Git preserva cada
original — que é exatamente a filosofia do produto.

## 5. Consequências

- O repositório deve ser renomeado para `corpusmith` (GitHub redireciona o
  nome antigo); URLs em docs já apontam para o nome novo;
- "Brain Compiler" e "LLM Wiki" saem da comunicação; podem ser citados como
  nomes históricos;
- A arquitetura de marca fica reservada para as próximas fases: Corpusmith
  **Core** (compilador/runtime), **Cockpit** (curadoria), **Bridge**
  (MCP/SDKs), **Trust Report** (assurance) — nomes de espaço, não promessas;
- O gap estratégico nomeado pela análise — a página é boa unidade
  *editorial* mas não é unidade *epistêmica* atômica — vira trilha futura
  (Assertion/EvidenceLink como entidades de primeira classe), exigindo RFC
  próprio quando iniciar. Este ADR não a antecipa.
