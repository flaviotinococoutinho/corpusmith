# 00 · O que é o Corpusmith

> **A explicação inteira, do zero, em uma sentada.** Os outros documentos
> deste diretório são roteados por especialidade — ótimos quando você já sabe
> o que procura. Este é o único que assume que você não sabe nada, e conta a
> história completa seguindo **um fato** da fonte bruta até a resposta.
>
> Vocabulário: [`01`](01-conceitos.md) · Por que funciona:
> [`03`](03-teoria.md) · Como é construído: [`10`](10-engenharia-ai-friendly.md)

---

## 1. O problema, antes da solução

Você acumula conhecimento em lugares que não conversam: PDFs, notas soltas,
conversas com modelos, decisões que só existem na sua cabeça. Quando uma IA
te ajuda, ela ajuda **naquela sessão** — e o que ela "aprendeu" morre no
contexto, ou vira um fato solto num banco que você não inspeciona.

Seis meses depois aparecem as perguntas caras:

- *Isso que o agente respondeu — de onde veio?*
- *Ainda vale? Valia quando foi escrito?*
- *Quem decidiu que isso era verdade? Eu aprovei, ou a máquina inferiu?*
- *Duas páginas dizem coisas diferentes sobre o mesmo artigo. Qual manda?*
- *Preciso revogar esta informação. Onde ela está sendo usada?*

Nenhuma dessas perguntas é sobre *recuperar melhor*. Todas são sobre
**governar** — e é aí que o Corpusmith mora.

## 2. A categoria: governar, não recordar

> **Outras memórias ajudam agentes a recordar. O Corpusmith governa o que
> humanos e agentes podem tratar como conhecimento.**

| Categoria | A pergunta que ela responde |
|---|---|
| Memória de agente | "O que este agente deve recordar?" |
| RAG | "Que trechos devo recuperar para responder?" |
| Knowledge graph | "Que entidades e relações consigo representar?" |
| Gestão de documentos | "Onde estão os documentos?" |
| **Corpusmith** | **"O que foi aceito como conhecimento, com base em quê, por quem, em qual período e sob quais limites?"** |

Repare que a pergunta do Corpusmith **contém** as outras: para respondê-la é
preciso recuperar, representar e guardar — mas nenhuma das outras responde a
dele. É por isso que a categoria é diferente, e não uma variação.

O nome traduz o ofício: **corpus** é o material trabalhado, **smith** é quem
o trabalha. Fontes brutas → curadoria → corpus durável.

## 3. A tese: conhecimento como alvo de compilação

Um compilador tem código-fonte, um binário auditável e artefatos
descartáveis. O Corpusmith trata conhecimento igual:

| No compilador | No Corpusmith | Consequência |
|---|---|---|
| código-fonte | `knowledge/raw/` (PDFs, notas, capturas) | é insumo, não verdade |
| **binário auditável** | `knowledge/bundle/` — Markdown OKF + Git | **a autoridade**; todo ato é um commit |
| artefatos de build | `index.db`, embeddings, grafo, temas | **descartáveis**: apague e reconstrua |

Três consequências normativas saem daí, e elas governam o produto inteiro:

**O índice nunca é a verdade.** `index.db` pode ser deletado a qualquer
momento (`corpusmith okf index` reconstrói). Nada de conhecimento se perde.
Corolário prático: qualquer experimento de retrieval é seguro — o pior caso
é reindexar. Corolário epistêmico: uma projeção **nunca** pode decidir sobre
o canônico (e quando ela decidia, foi tratado como defeito — ver
[RFC-002](19-rfc-escada-reconciliacao.md)).

**Git é o juiz.** Arquivar ≠ apagar; depreciar ≠ deletar; errar ≠ perder.
Toda escrita passa por um gate único e vira commit com trilha em `log.md`.

**Determinismo antes de modelo.** O que regex, checksum ou grafo resolvem
não passa por LLM. O modelo é um estágio cercado por passadas
determinísticas — o "sanduíche" — nunca a autoridade final.

## 4. Um fato, do PDF à resposta

Acompanhe **uma** informação atravessando o sistema. Este é o produto
inteiro, em sete passos.

### Passo 1 — a fonte entra (`raw/`)

Você joga um PDF em `knowledge/raw/`. Nada acontece com o corpus ainda: a
fonte é insumo. Ela aparece na fila de trabalho como *"captura não
absorvida"*.

### Passo 2 — compilar (`produce → normalize`)

O job `compile_source` extrai o texto e produz um rascunho. Aí entra o
**sanduíche**: passada determinística **antes** (detectores de entidade,
datas, identificadores, PII), o LLM no meio (só para redigir), passada
determinística **depois** (reescreve a grafia canônica e re-anota sobre o
texto final). O que sai é uma página OKF candidata — Markdown com
frontmatter.

### Passo 3 — reconciliar: isto já existe? (`reconcile`)

Antes de escrever, a **escada de reconciliação** decide entre `ADD`,
`UPDATE`, `SUPERSEDE`, `NOOP` ou `RECYCLE`, do mais determinístico ao menos:

1. **identificador forte** compartilhado (DOI, ISBN, arXiv, git SHA) —
   determinístico, decide sozinho;
2. **similaridade composta** — `0.4·rank(FTS) + 0.3·Jaccard(entidades) +
   0.3·(1 − NCD)`. Os três sinais precisam concordar: com corpo idêntico mas
   sem entidade curada em comum, o escore empaca em ~0.69 e **não** vira
   `UPDATE` (medido);
3. **árbitro LLM local**, só na zona cinzenta, **atrás de flag desligada**.

Se o caminho colide com uma página existente, o produto **não escreve**:
devolve `COLLISION` e a decisão volta para você, com três saídas legítimas
(escrever sobre, criar com outro slug, cancelar) — [RFC-003](20-rfc-colisao-de-caminho.md).

### Passo 4 — o gate (`write`)

Um único caminho de escrita, inescapável. O Harness roda **duas camadas
separadas**:

- **conformidade OKF** — só o que o SPEC exige (nunca inventa exigência);
- **política local** — as nossas regras: `privacy` obrigatório, checksum de
  fonte para página de máquina, PII exige `local_only`, sucessor apontado
  precisa existir, intenção declarada precisa bater com o mundo
  (`Creation` sobre página existente é **erro**).

Erro bloqueia a escrita. Passou, vira commit.

### Passo 5 — projetar (`done`)

O índice é reconstruído de forma incremental: chunks, FTS, entidades com
**offsets de span**, arestas do grafo. Nada aqui é verdade nova — é a mesma
verdade em formato consultável.

### Passo 6 — perguntar (`/ask`)

A consulta funde streams (FTS, vetorial, grafo, hierárquico) por RRF, e a
resposta vem com **evidência**: qual página, qual trecho, quais spans
justificam. Se o suporte for fraco, o produto **abstém** em vez de inventar.
Cada resposta carrega um `ask_id` que é a trilha decodificável do que foi
feito.

### Passo 7 — o laço fecha

Você diz se a resposta foi útil. Isso alimenta os pesos de stream, o calor
das páginas, a fila de revisão espaçada — e, quando algo está errado,
**você tem o gesto para consertar**: oito atos de curadoria (`edit`,
`supersede`, `invalidate`, `merge`, `link`, `unlink`, `close_question`,
`undo`), todos com **preview antes do efeito** e todos reversíveis.

## 5. Quem pode mudar o quê — o modelo de autoridade

Esta é a seção que separa o Corpusmith de uma memória comum, e é onde a
honestidade importa mais.

| Fonte de verdade | Autoridade | Projeções |
|---|---|---|
| conhecimento | `knowledge/bundle` + Git | `index.db` (FTS, grafo, entidades) |
| config vigente | `Settings` + overrides | histórico de linhagem |
| jobs/telemetria | `runtime.db` | métricas |

**A alegação honesta, hoje**:

> Máquinas escrevem sob políticas; humanos governam, revisam e podem
> reverter.

O caminho de máquina **pode** criar, atualizar e suceder páginas — depois de
passar pelo gate. O que ele não pode é fazê-lo em silêncio: toda decisão
fica em `reconcile_log`, todo ato humano fica em `curation_acts` com o sha do
commit, e o `undo` desfaz **escrevendo para a frente** (nunca apagando).

**A visão-alvo** — *Agents propose. Policies constrain. Humans ratify. Git
remembers.* — é a direção declarada em [ADR-53](21-adr-categoria-corpusmith.md),
**não** uma descrição do comportamento atual.

## 6. O que torna isto verificável (e não slogan)

Cada elo da combinação é **asserção executável**, não promessa de README:

- **arquitetura como teste** — um `import sqlite3` dentro do núcleo puro
  quebra a suíte; `usecases` que importe `api` quebra a suíte; um `UseCase`
  com dois métodos públicos quebra a suíte;
- **contratos epistêmicos** ([`epistemics.toml`](../epistemics.toml)) — 19
  mecanismos heurísticos declaram pressupostos, garantia **relativa a quê**,
  modos de falha e fallback. Garantia universal é **proibida** pelo lint, e
  o teste cruza os parâmetros declarados com as constantes reais: um
  contrato que mente sobre o código **quebra a suíte**;
- **invariantes com reparo** — INV-001..006 verificam índice órfão, índice
  obsoleto, supersedida vazando para a recuperação, mapa de padrões velho,
  dois temas canônicos vivos e derivação atrasada. O painel 🩺 mostra os
  achados e oferece o reparo do que é reparável;
- **cadeia de frescor declarada** — `bundle → index → graph_map → themes` (e
  `index → centrality`): o doctor sabe dizer **qual elo** está atrás, em vez
  de acender alarmes desconexos.

## 7. O que o Corpusmith NÃO alega

Um produto que vende governança não pode começar exagerando a própria.
Estas alegações são **proibidas** no estado atual ([ADR-53](21-adr-categoria-corpusmith.md) §3):

- ❌ **"fonte da verdade"** — canônico ≠ verdadeiro. O registro diz o que foi
  *aceito*, e por quem. Aceitação não é veracidade;
- ❌ **"zero alucinação"** — o produto abstém quando o suporte é fraco e cita
  a evidência quando responde; isso reduz e torna auditável, não elimina;
- ❌ **"ontologia formal"** — o vocabulário é curado no bundle, não é uma
  ontologia com semântica formal;
- ❌ **"somente humanos escrevem"** — falso hoje, ver §5;
- ❌ **prontidão para decisões clínicas ou reguladas** — a arquitetura tem
  potencial para governança de evidência, e isso não é o mesmo que estar
  pronto para decidir sobre alguém.

**Limite conhecido e registrado**: a unidade epistêmica hoje é a **página**,
e a página é boa unidade *editorial* mas não é unidade *epistêmica atômica*
— uma página pode conter duas afirmações de fontes diferentes, com validades
diferentes. Tratar `Assertion` como entidade de primeira classe é trilha
futura, e exigirá RFC próprio.

## 8. Para onde ir agora

| Você quer… | Vá para |
|---|---|
| o vocabulário exato dos termos | [`01-conceitos.md`](01-conceitos.md) |
| por que as técnicas funcionam (papers) | [`03-teoria.md`](03-teoria.md) |
| instalar e verificar | [`12-instalacao.md`](12-instalacao.md) |
| a tabela dura (regras, endpoints, tabelas) | [`06-referencia.md`](06-referencia.md) |
| contribuir / mudar código | [`../AGENTS.md`](../AGENTS.md) |
| o que ainda falta, com evidência | [`18-backlog-consolidado.md`](18-backlog-consolidado.md) |
| a identidade e a categoria, por escrito | [`21-adr-categoria-corpusmith.md`](21-adr-categoria-corpusmith.md) |
