# Documentação do Corpusmith

> **Altitude:** índice · **Status:** vivo

Use este índice para localizar explicações, procedimentos, referências e
decisões. Os documentos marcados como históricos preservam o raciocínio da
época. A fila atual está em [Backlog consolidado](18-backlog-consolidado.md), §11.

## Onde começar

| Objetivo | Documento |
|---|---|
| Entender o produto | [O que é o Corpusmith](00-o-que-e-corpusmith.md) |
| Instalar e verificar o ambiente | [Instalação](12-instalacao.md) |
| Contribuir ou alterar código | [AGENTS.md](../AGENTS.md) e [Contribuição](../CONTRIBUTING.md) |
| Revisar arquitetura | [Especificação de engenharia](10-engenharia-ai-friendly.md) e [`architecture.toml`](../architecture.toml) |
| Consultar termos | [Conceitos](01-conceitos.md) e [Léxico](23-ontologia-e-etimologia.md) |
| Consultar regras, rotas ou tabelas | [Referência](06-referencia.md) |

## Mapa por especialidade

### Produto — o que é e para quem

Estes documentos explicam o produto e seus limites:

| Documento | Conteúdo |
|---|---|
| [00-o-que-e-corpusmith.md](00-o-que-e-corpusmith.md) | Fluxo de uma fonte até a resposta, autoridade de escrita e limites das alegações |
| [01-conceitos.md](01-conceitos.md) | OKF, memória, validade temporal, confiança, autoridade, proveniência e avaliação |
| [23-ontologia-e-etimologia.md](23-ontologia-e-etimologia.md) | Eixos epistêmicos, significado dos termos e deriva semântica registrada |
| [24-axiomas-e-oticas.md](24-axiomas-e-oticas.md) | Axiomas do produto, verificações associadas e óticas de leitura do corpus |
| [25-fronteira-e-diferencial.md](25-fronteira-e-diferencial.md) | Limites de escopo entre aquisição, compilação, publicação e ação de agentes |
| [28-escada-de-abstracao-e-topologia.md](28-escada-de-abstracao-e-topologia.md) | Unidades de análise, erros de nível e limites dos sinais topológicos |

### Ciência e teoria

Consulte os fundamentos e as fontes de pesquisa:

| Documento | Conteúdo |
|---|---|
| [03-teoria.md](03-teoria.md) | Fundamentos dos mecanismos e limites de sua transposição para o produto |
| [26-pesquisa-da-camada-epistemica.md](26-pesquisa-da-camada-epistemica.md) | Literatura sobre asserção, proveniência, discordância e contradição |

### Engenharia e contratos

Estes documentos descrevem a organização do software e seus contratos:

| Documento | Conteúdo |
|---|---|
| [02-metodologias.md](02-metodologias.md) | Normalização, reconciliação, use cases, facades e testes de arquitetura |
| [04-tecnologias.md](04-tecnologias.md) | Contratos de SQLite, Git, backend, modelos e desktop |
| [10-engenharia-ai-friendly.md](10-engenharia-ai-friendly.md) | Arquitetura-alvo BC-ENG-001, com estado de implementação por mecanismo |
| [11-epistemic-contracts.md](11-epistemic-contracts.md) | Pressupostos, garantias relativas, modos de falha e envelopes de avaliação |
| [../architecture.toml](../architecture.toml) | Camadas, invariantes e verificações obrigatórias |
| [../epistemics.toml](../epistemics.toml) | Registro dos contratos epistêmicos |
| [../ontology.toml](../ontology.toml) | Termos, eixos, blocos do projeto, dependências e dívidas |
| [../nfr.toml](../nfr.toml) | Requisitos não funcionais e estado de verificação |

Para consistência, durabilidade, escala, segurança e privacidade, consulte
as seções 5–17 da especificação de engenharia e o estado em `nfr.toml`.

### Referência e operação

Use a referência para consulta e os guias para executar tarefas:

| Documento | Conteúdo |
|---|---|
| [06-referencia.md](06-referencia.md) | Regras do Harness, rotas, tabelas, jobs, configuração e constantes |
| [05-fluxos-operacionais.md](05-fluxos-operacionais.md) | Compilação, consulta, curadoria, revisão, avaliação e implantação |
| [07-sinergias.md](07-sinergias.md) | Interações entre mecanismos, procedimentos de ajuste e pontos de extensão |
| [12-instalacao.md](12-instalacao.md) | Instalação local, Docker, serviço do daemon, modelos e diagnóstico |
| [../benchmarks/README.md](../benchmarks/README.md) | Execução dos benchmarks e resultados de referência |

### Governança e planejamento

ADRs e RFCs registram decisões e propostas. O estado de uma proposta deve
ser lido no próprio documento; a ordem de trabalho atual está no §11 do backlog.

| Documento | Conteúdo |
|---|---|
| [08-decisoes.md](08-decisoes.md) | Registro de decisões arquiteturais e condições de reconsideração |
| [18-backlog-consolidado.md](18-backlog-consolidado.md) | §11: fila atual. §1–§10: histórico de fechamento e evidências |
| [16-rfc-theme-id.md](16-rfc-theme-id.md) | RFC-001: identidade de tema entre recomputações |
| [19-rfc-escada-reconciliacao.md](19-rfc-escada-reconciliacao.md) | RFC-002: decisões e atualização das projeções usadas na reconciliação |
| [20-rfc-colisao-de-caminho.md](20-rfc-colisao-de-caminho.md) | RFC-003: colisão entre promoção humana e compilação de máquina |
| [21-adr-categoria-corpusmith.md](21-adr-categoria-corpusmith.md) | ADR-53: nome, categoria e limites das alegações públicas |
| [22-rfc-ontologia-da-assercao.md](22-rfc-ontologia-da-assercao.md) | RFC-004: eixos da asserção e proposta de unidade epistêmica própria |
| [27-rfc-conflito-factual.md](27-rfc-conflito-factual.md) | RFC-005: divergência numérica dentro de grupos de identificador forte |
| [29-rfc-006-re-mira.md](29-rfc-006-re-mira.md) | RFC-006: direção para o instrumento de estudo, capacidades e estados de entrega |
| [30-dicionario-da-re-mira.md](30-dicionario-da-re-mira.md) | Vocabulário da direção de produto, níveis de acesso e verificações de engenharia |

Os documentos abaixo são históricos. Para planejar trabalho, consulte o
backlog atual e o protocolo do `AGENTS.md`:

| Documento | Registro preservado |
|---|---|
| [09-backlog.md](09-backlog.md) | Backlog anterior |
| [13-plano-experiencia-memoria.md](13-plano-experiencia-memoria.md) | Plano de experiência de memória, curadoria e classificação |
| [14-plano-viabilidade.md](14-plano-viabilidade.md) | Plano de viabilidade para novos usuários |
| [15-plano-execucao.md](15-plano-execucao.md) | Sequência anterior de pacotes de execução |
| [17-auditoria-integridade.md](17-auditoria-integridade.md) | Auditoria de integridade e evidências dos achados |

## Guia rápido de roteamento (para não misturar especialidades)

| Pergunta | Referência |
|---|---|
| O que um termo significa? | `23`, `30` e `ontology.toml` |
| Em qual unidade um sinal é válido? | `28` |
| O que uma heurística pode alegar? | `11` e `epistemics.toml` |
| Por que uma técnica foi adotada? | `03`, `08` e a RFC correspondente |
| Qual decisão de arquitetura rege uma mudança? | `10` e `AGENTS.md` §8 |
| A que bloco um arquivo pertence? | `corpusmith ontology where <caminho>` |
| O que falta fazer e em que ordem? | `18` §11 |
| Quais contagens e registros estão vigentes? | `corpusmith context` ou `just context` |

## Como manter esta documentação

A skill local `docs-sync`, em `.claude/skills/docs-sync/SKILL.md`, descreve
os vínculos entre código e documentos e os comandos de auditoria. Use o
procedimento quando uma alteração mudar os fatos documentados.

Ao alterar arquitetura, atualize a especificação e `architecture.toml`
quando aplicável. Os testes comparam o contrato com a implementação.
O contrato documental está em `backend/tests/test_docs_contract.py`:

- Todo `docs/*.md` declara altitude e status nas primeiras linhas.
- Um documento histórico aponta para a fonte atual em `18`.
- O índice lista todos os documentos e os links relativos resolvem.
- Documentos vivos usam registros e comandos para contagens de mecanismos,
  termos, testes e contratos. ADRs, RFCs e registros de fechamento podem
  preservar números do commit ao qual se referem.
- As tabelas de tipos de garantia em `11` são comparadas a `epistemics.toml`.
- O estado dos requisitos não funcionais vem de `nfr.toml`.

## Convenções de leitura

`caminho/arquivo.py:Símbolo` identifica uma implementação. O documento `10`
distingue implementado, parcial e proposto. `pinned`, `measured` e `declared`
são estados de verificação; uma proposta não deve ser descrita como entregue.

Páginas de máquina usam `generated_via: api:*` ou `local:*`. Páginas humanas
usam `human:*`. Valores como `extracted`, `inferred`, `ambiguous` e
`local_only` permanecem em inglês porque fazem parte dos dados e contratos.
