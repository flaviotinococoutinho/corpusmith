# Documentação do Brain Compiler / LLM Wiki

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
| **entendendo o produto** | [`01-conceitos.md`](01-conceitos.md) |
| **procurando uma regra/endpoint/tabela** | [`06-referencia.md`](06-referencia.md) |

## Mapa por especialidade

### 🧭 Produto — o QUE é e para QUEM
Conceitos do sistema como produto, sem detalhe de implementação.

| Doc | Conteúdo |
|---|---|
| [01-conceitos.md](01-conceitos.md) | OKF, camadas de memória, bi-temporalidade, escala de confiança, controle de autoridade, epistemologia (abstenção, desfecho, eval) |

### 🔬 Ciência & teoria — POR QUE funciona
Fundamentos teóricos e científicos, com papers. Não descreve código.

| Doc | Conteúdo |
|---|---|
| [03-teoria.md](03-teoria.md) | Teoria da informação (NCD, entropia, surprisal, Hedge), topologia (persistência 0-dim, centralidade de Brandes), heurísticas de coordenação (RRF, heat, escada de reconciliação), fundamentos cognitivos (CLS, BLA) |

### ⚙️ Engenharia, algoritmos & paradigmas — COMO se constrói
Disciplina de software, técnicas de algoritmo, padrões e paradigmas.

| Doc | Conteúdo |
|---|---|
| [10-engenharia-ai-friendly.md](10-engenharia-ai-friendly.md) | **Spec de arquitetura-alvo (BC-ENG-001)**: Functional Core/Imperative Shell, tipos/ADTs, transações, fila, estruturas de dados, padrões, Object Calisthenics — **com selo ✅ implementado / ⚠️ parcial / 🎯 proposto** |
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

### 🔄 Fluxos operacionais — QUANDO / ONDE
| Doc | Conteúdo |
|---|---|
| [05-fluxos-operacionais.md](05-fluxos-operacionais.md) | Fluxos fim-a-fim: compilar, perguntar, promover, desfecho→reflect, revisão, comunidades, eval, implantação |
| [07-sinergias.md](07-sinergias.md) | Matriz de interação entre conceitos + receitas de composição e extensão |

### 🏛️ Governança — DECIDIR e o que falta
| Doc | Conteúdo |
|---|---|
| [08-decisoes.md](08-decisoes.md) | ADRs: conceitos adotados, adaptados e rejeitados com razão registrada (CLS, ACT-R, AGM, DTT, CRDTs, WFST…) e portas de reentrada |
| [09-backlog.md](09-backlog.md) | Backlog priorizado (P0–P3) e estado de fechamento por frente |

## Guia rápido de roteamento (para não misturar especialidades)

- É **o que o usuário vê / por que o produto existe**? → `01`.
- É **por que uma técnica funciona** (prova, paper, matemática)? → `03`.
- É **como o software é organizado** (camada, tipo, padrão, algoritmo)? → `10`, `02`, `04`.
- É **quanto/quão rápido/quão durável** (CAP, SLO, escala, segurança)? → `10` §5–17.
- É **uma constante/regra/endpoint** que preciso consultar? → `06`.
- É **uma decisão tomada ou o que ainda falta**? → `08`, `09`.

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
