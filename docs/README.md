# Documentação do LLM Wiki

Documentação conceitual e operacional do projeto — o **suporte para
combinar e extrair o melhor dos conceitos**. Cada documento cobre uma
altitude; a última seção (sinergias) é o mapa de como os conceitos se
compõem entre si.

| Doc | Altitude | Conteúdo |
|---|---|---|
| [01-conceitos.md](01-conceitos.md) | O QUE | Conceitos abstratos: OKF, camadas de memória, bi-temporalidade, escala de confiança, controle de autoridade, epistemologia (abstenção, desfecho, eval) |
| [02-metodologias.md](02-metodologias.md) | COMO se constrói | Sanduíche determinístico, precisão>recall, reescreve-grafia/anota-semântica, use cases + facades, Template Method, Object Calisthenics, arquitetura-como-teste, golden tests |
| [03-teoria.md](03-teoria.md) | POR QUE funciona | Fundamentos com papers: teoria da informação (NCD, entropia, surprisal, Hedge), topologia (persistência 0-dim), heurísticas de coordenação (RRF, heat, escada de reconciliação) |
| [04-tecnologias.md](04-tecnologias.md) | COM O QUÊ | Stack e contratos de infraestrutura: SQLite/FTS5/WAL, Git, FastAPI/SSE, pydantic, Electron/Vite, PyInstaller, roteador de modelos |
| [05-fluxos-operacionais.md](05-fluxos-operacionais.md) | QUANDO/ONDE | Todos os fluxos fim-a-fim: compilar, perguntar, promover, desfecho→reflect, revisão, comunidades, eval, implantação |
| [06-referencia.md](06-referencia.md) | Tabela da verdade | Referência dura: todas as regras do Harness, endpoints, tabelas, jobs, flags, tipos OKF, frontmatter — o que a skill de sincronização audita |
| [07-sinergias.md](07-sinergias.md) | COMBINAR | Matriz de interação entre conceitos + receitas de composição e extensão |
| [08-decisoes.md](08-decisoes.md) | DECIDIR | ADRs: conceitos adotados, adaptados e rejeitados com razão registrada (CLS, ACT-R, AGM, DTT, CRDTs, WFST…) e portas de reentrada |

## Como manter esta documentação

A skill local **`docs-sync`** (`.claude/skills/docs-sync/SKILL.md`) contém
o procedimento de atualização: o mapa código→documento, os comandos que
extraem a verdade atual do código (regras, endpoints, tabelas, jobs) e o
checklist de auditoria. Invoque-a (`/docs-sync`) sempre que uma mudança
tocar funcionalidade core; a regra de ouro é **o código é a fonte da
verdade — a doc nunca descreve o que o teste não confirma**.

## Convenções de leitura

- Trechos `caminho/arquivo.py:Símbolo` apontam para a implementação.
- "Página de máquina" = `generated_via: api:*|local:*`; "página humana" =
  `generated_via: human:*`. A distinção governa quase todas as regras.
- Termos da escala única de confiança aparecem sempre em inglês
  (`extracted`/`inferred`/`ambiguous`) porque são valores literais no
  banco e no frontmatter.
