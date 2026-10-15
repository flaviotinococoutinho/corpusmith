# 25 · Fronteira e diferencial — o que o Corpusmith não faz, e por que isso é o produto

> **Altitude:** produto · **Status:** vivo

> Esta página delimita o escopo do Corpusmith entre aquisição, compilação e
> publicação de conteúdo. Também compara decisões de arquitetura com outro
> projeto do autor. Essa comparação é um exemplo de aplicação, sem demonstrar
> generalização do método.
>
> A categoria e a fronteira de honestidade: [ADR-53](21-adr-categoria-corpusmith.md) ·
> A explicação do produto: [`00`](00-o-que-e-corpusmith.md)

---

## 1. A cadeia real: adquirir → compilar → publicar

O fluxo de trabalho pode ser dividido em três etapas:

| Etapa | Pergunta | Estado natural do artefato |
|---|---|---|
| **adquirir** | como isto chega até mim? | arquivo bruto, credencial, agendamento, retomada de download |
| **compilar e governar** | isto pode contar como conhecimento? | página canônica, proveniência, ato datado |
| **publicar sob norma** | como isto sai daqui na forma exigida? | PDF, artigo, entrega formatada sob regra externa |

As três têm ferramentas boas. A primeira tem coletores, agendadores, gerenciadores
de download. A terceira tem LaTeX, Pandoc, normas ABNT, templates de revista.

O Corpusmith concentra-se na compilação e na governança: registrar a origem,
a aceitação, a validade temporal e a possibilidade de revisão. Coleta e
publicação podem ser feitas por ferramentas externas.

## 2. As três fronteiras

### 2.1 Não é coletor

O produto **não** baixa, não agenda coleta, não autentica em serviço externo,
não retoma upload. `knowledge/raw/` é uma pasta: o que a preenche é problema de
quem coleta.

**Por que a fronteira é boa.** Coleta é dominada por credencial, rate limit,
retomada e política de site — todas preocupações de *transporte*, com ciclo de
mudança rápido e superfície de risco alta. Absorvê-las traria segredo, rede e
agendamento para dentro de um produto cujo núcleo é **puro** e cujo trunfo é o
determinismo. O gradiente de mutabilidade (`architecture.toml [[tier]]`) existe
justamente para que o volátil não encoste no estável.

**Onde a fronteira encosta.** O único contrato necessário é o mais simples
possível: um arquivo aparece em `raw/`, e o produto o trata como *captura não
absorvida*. Nenhum acoplamento, nenhuma API entre os dois lados.

### 2.2 Não é publicador

O produto **não** diagrama, não aplica norma editorial, não gera PDF. Ele
compila para Markdown OKF versionado, e a saída para forma externa é trabalho de
quem publica.

**A observação interessante** é que a etapa de publicação sob norma, quando
feita com seriedade, faz *à mão* exatamente o que a §6 do
[RFC-004](22-rfc-ontologia-da-assercao.md) descreve. Uma conversão normativa
honesta produz, para cada elemento, um registro com três colunas — *o que a
fonte trazia*, *o que a norma vigente exige*, *o que foi adotado* — e uma regra
explícita: **nada é aplicado silenciosamente**.

Isso é uma asserção com `derivation_method`, `resolution_status` e
`governance_status` separados, escrita em prosa numa tabela de decisões porque
não havia onde escrevê-la em estrutura. É a melhor evidência disponível de que
os eixos do RFC-004 descrevem uma necessidade real de quem trabalha com material
sob norma — e não uma abstração inventada para o prazer de abstrair.

### 2.3 Não é agente

O produto **não** é um assistente que age no mundo, não executa tarefas, não
persegue objetivos. Ele responde, cita, abstém e registra.

**Por que a fronteira é boa.** Um agente que age precisa decidir rápido e com
informação incompleta; um registro de conhecimento precisa decidir devagar e por
regra. São regimes opostos. Misturá-los produz o pior dos dois: um agente lento
e um registro impulsivo.

A relação certa é de **cliente**: agentes propõem, o Corpusmith governa. É a
direção declarada em ADR-53 — *agents propose, policies constrain, humans
ratify, Git remembers* — e é visão-alvo, não descrição do comportamento atual
([`00`](00-o-que-e-corpusmith.md) §5).

## 3. O diferencial, contra o que já existe

| Categoria vizinha | Foco habitual | O que verificar na implementação |
|---|---|---|
| memória de agente | recall entre sessões, personalização | autor da aceitação, ato de curadoria e reversão |
| RAG / vector store | achar trecho relevante rápido | validade temporal, sucessão e revogação |
| knowledge graph | representar entidades e relações | evidência e proveniência das relações |
| gestão de documentos | guardar, versionar, encontrar | políticas de aceitação e critérios de resposta |
| wiki / PKM | escrever e ligar bem | granularidade da proveniência |

O contraste no nível do **mecanismo de contradição** — o que cada sistema faz
com o fato perdedor, medido por um levantamento independente — está em
[`26`](26-pesquisa-da-camada-epistemica.md) §4, junto com o que a escolha do
Corpusmith custa em troca.

Essas categorias incluem implementações com recursos distintos. A tabela não
atribui uma ausência de recursos a todos os produtos de uma categoria.
O conjunto que o Corpusmith implementa deve ser avaliado pelos contratos,
testes e limites registrados no próprio repositório.

## 4. Evidência de que o método generaliza

O Corpusmith não é o único lugar onde esta disciplina foi aplicada. O
[Gridsmith](https://github.com/flaviotinococoutinho/p7m-design) — ferramenta
visual de desenvolvimento de jogos 2D, domínio sem nenhuma relação com
conhecimento — apresenta decisões estruturais semelhantes:

| Decisão | No Gridsmith | No Corpusmith |
|---|---|---|
| **modelo canônico + projeções** | o usuário edita um modelo próprio; adapters projetam em runtimes concretos | o usuário edita o bundle; `index.db` e o grafo são projeções |
| **um caminho único de mutação** | comando → store → evento → hooks → projeção | `produce → normalize → reconcile → write → done` |
| **governança como teste** | regras arquiteturais verificadas por ferramentas e testes, conforme o contrato do projeto | `architecture.toml` + `epistemics.toml` + `ontology.toml`, cada um preso ao código por uma suíte |
| **recusa registrada, nunca silenciosa** | evento não suportado é `skipped`/`deferred` e **exige** `reason` | decisão de reconciliação vai para `reconcile_log` com motivo; abstenção é resposta, não falha |

Os exemplos mostram o uso de modelo canônico, projeções e verificações em dois
projetos do autor. São casos de aplicação; não bastam para comprovar eficácia
em outros domínios ou equipes.

## 5. O que isto implica para o roadmap

- **não construir coletor** — nem "só um downloader simples". A primeira
  credencial dentro do produto derruba o argumento do §2.1;
- **não construir publicador** — mas manter o Markdown OKF fácil de consumir por
  quem publica: a fronteira é boa enquanto for barata de atravessar;
- **investir na compilação e governança** — a proposta de asserção com eixos
  separados está em [RFC-004](22-rfc-ontologia-da-assercao.md) §6. O ato datado,
  a reversão e a evidência consultável orientam o escopo;
- **tratar agentes como clientes**, não como habitantes. A API e o MCP existem
  para que eles proponham; o gate existe para que a proposta não vire fato sem
  passar por regra.
