# 25 · Fronteira e diferencial — o que o Corpusmith não faz, e por que isso é o produto

> Um produto se define tanto pelo que recusa quanto pelo que entrega. Esta
> página delimita as três fronteiras que o Corpusmith **não** cruza, mostra o
> lugar exato que ele ocupa numa cadeia que já existe, e registra a evidência de
> que o método por trás dele generaliza para além de conhecimento.
>
> A categoria e a fronteira de honestidade: [ADR-53](21-adr-categoria-corpusmith.md) ·
> A explicação do produto: [`00`](00-o-que-e-corpusmith.md)

---

## 1. A cadeia real: adquirir → compilar → publicar

Quem acumula material sério faz três coisas distintas, e costuma confundi-las
porque nenhuma ferramenta as separa:

| Etapa | Pergunta | Estado natural do artefato |
|---|---|---|
| **adquirir** | como isto chega até mim? | arquivo bruto, credencial, agendamento, retomada de download |
| **compilar e governar** | isto pode contar como conhecimento? | página canônica, proveniência, ato datado |
| **publicar sob norma** | como isto sai daqui na forma exigida? | PDF, artigo, entrega formatada sob regra externa |

As três têm ferramentas boas. A primeira tem coletores, agendadores, gerenciadores
de download. A terceira tem LaTeX, Pandoc, normas ABNT, templates de revista.

**A do meio é onde não há nada** — e é a única em que a pergunta é sobre
*autorização*, não sobre transporte ou formato. Adquirir não precisa saber se o
material é confiável; publicar assume que a decisão já foi tomada. Só a etapa do
meio precisa responder *"de onde veio, quem aceitou, ainda vale, e o que
acontece se eu revogar"*.

É por isso que o Corpusmith não é "mais uma ferramenta de PKM": ele ocupa a
etapa em que a governança é a **única** coisa que faz sentido fazer.

## 2. As três fronteiras

### 2.1 Não é coletor

O produto **não** baixa, não agenda coleta, não autentica em serviço externo,
não retoma upload. `knowledge/raw/` é uma pasta: o que a preenche é problema de
quem coleta.

**Por que a fronteira é boa.** Coleta é dominada por credencial, rate limit,
retomada e política de site — todas preocupações de *transporte*, com ciclo de
mudança rápido e superfície de risco alta. Absorvê-las traria segredo, rede e
agendamento para dentro de um produto cujo núcleo é **puro** e cujo trunfo é o
determinismo. O gradiente de mutabilidade (`architecture.toml [layers]`) existe
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

| Categoria vizinha | O que ela resolve bem | O que ela não responde |
|---|---|---|
| memória de agente | recall entre sessões, personalização | *quem aceitou isto?* — o registro não tem ato, autor nem reversão |
| RAG / vector store | achar trecho relevante rápido | *ainda vale?* — não há tempo de mundo, nem sucessão, nem revogação |
| knowledge graph | representar entidades e relações | *com base em quê?* — a aresta não carrega a evidência que a justifica |
| gestão de documentos | guardar, versionar, encontrar | *isto pode contar como conhecimento?* — não há gate, nem política, nem abstenção |
| wiki / PKM | escrever e ligar bem | *de onde veio cada parte?* — proveniência é por documento, quando existe |

A pergunta do Corpusmith — *"o que foi aceito como conhecimento, com base em
quê, por quem, em qual período e sob quais limites?"* — **contém** as outras:
para respondê-la é preciso recuperar, representar e guardar. Nenhuma das outras
responde a dele. É por isso que a categoria é diferente, e não uma variação.

**E o diferencial não é a lista de recursos.** Qualquer um pode escrever
"proveniência, bi-temporalidade, governança" num README. O que é caro de imitar
é cada elo ser **asserção executável**: um `import sqlite3` no núcleo puro
quebra a suíte; um contrato epistêmico que mente sobre uma constante quebra a
suíte; um termo que passa a responder a duas perguntas quebra a suíte; um gate
declarado que a CI não executa quebra a suíte. A promessa e a prova são o mesmo
artefato.

## 4. Evidência de que o método generaliza

O Corpusmith não é o único lugar onde esta disciplina foi aplicada. O
[Gridsmith](https://github.com/flaviotinococoutinho/p7m-design) — ferramenta
visual de desenvolvimento de jogos 2D, domínio sem nenhuma relação com
conhecimento — chegou às mesmas quatro decisões estruturais de forma
independente:

| Decisão | No Gridsmith | No Corpusmith |
|---|---|---|
| **modelo canônico + projeções** | o usuário edita um modelo próprio; adapters projetam em runtimes concretos | o usuário edita o bundle; `index.db` e o grafo são projeções |
| **um caminho único de mutação** | comando → store → evento → hooks → projeção | `produce → normalize → reconcile → write → done` |
| **governança como teste** | ~25 regras arquiteturais como *fitness functions* que quebram o CI com o arquivo infrator no erro | `architecture.toml` + `epistemics.toml` + `ontology.toml`, cada um preso ao código por uma suíte |
| **recusa registrada, nunca silenciosa** | evento não suportado é `skipped`/`deferred` e **exige** `reason` | decisão de reconciliação vai para `reconcile_log` com motivo; abstenção é resposta, não falha |

Duas ferramentas, domínios sem interseção, mesma conclusão: **a arquitetura que
sobrevive a agentes de IA é a que se verifica sozinha**. Isso é o que sustenta a
alegação de método — não a afirmação de que o método é bom, mas a observação de
que ele foi aplicado duas vezes, longe uma da outra, e as duas vezes produziu
regra executável no lugar de convenção de revisão.

## 5. O que isto implica para o roadmap

- **não construir coletor** — nem "só um downloader simples". A primeira
  credencial dentro do produto derruba o argumento do §2.1;
- **não construir publicador** — mas manter o Markdown OKF fácil de consumir por
  quem publica: a fronteira é boa enquanto for barata de atravessar;
- **investir na etapa do meio** — o que ninguém mais faz é a asserção com eixos
  separados, o ato datado e reversível, e a evidência exibível. É onde
  [RFC-004](22-rfc-ontologia-da-assercao.md) §6 mora;
- **tratar agentes como clientes**, não como habitantes. A API e o MCP existem
  para que eles proponham; o gate existe para que a proposta não vire fato sem
  passar por regra.
