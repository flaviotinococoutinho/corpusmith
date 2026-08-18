# 23 · Ontologia e etimologia — o léxico do Corpusmith

> **O que este documento é.** A leitura humana de [`ontology.toml`](../ontology.toml),
> que é a fonte executável. O TOML declara; `corpusmith ontology lint` prova;
> aqui está o **argumento**: por que cada palavra foi escolhida, o que a raiz
> dela proíbe, e quais palavras ainda respondem a mais de uma pergunta.
>
> Eixos e regra de fusão: [RFC-004](22-rfc-ontologia-da-assercao.md) ·
> Vocabulário de produto: [`01`](01-conceitos.md) · O que o produto pode
> alegar: [ADR-53](21-adr-categoria-corpusmith.md)

---

## 0. Por que um produto de software teria um documento de etimologia

Porque a alternativa já foi tentada e falhou de um jeito medido.

Um campo do produto, `confidence`, acumulou seis sentidos. Não por descuido de
ninguém em particular: cada PR que precisava marcar alguma coisa procurou o
campo mais próximo, e o campo mais próximo aceitou. Quando três desses sentidos
passaram a dividir literalmente o mesmo campo do frontmatter, a regra que
decidia o valor numa fusão virou um `dict.get(c, 0)` — e a mesma fusão passou a
dar resultados diferentes conforme a ordem dos argumentos
([RFC-004](22-rfc-ontologia-da-assercao.md) §2.2).

A lição não é "escreva melhor a documentação". É que **um vocabulário sem
fronteira declarada não resiste ao tempo**, e a fronteira mais barata de
declarar é a que a própria palavra já carrega. `canon` vem de *régua de medir*:
uma régua mede, não é verdadeira — e é daí, não de modéstia, que sai a proibição
de dizer "fonte da verdade". `index` vem de *dedo indicador*: um dedo aponta,
não é a coisa apontada — e é daí que sai o axioma de que a projeção nunca decide
sobre o canônico.

A etimologia não é ornamento culto. É o argumento mais curto de por que uma
regra é essa e não outra, e é o que sobra quando ninguém se lembra do PR.

## 1. Como um termo entra no léxico

Toda palavra nova do produto responde a quatro perguntas, e o verbete só é
aceito quando as quatro têm resposta:

| Campo | Pergunta | Por que é obrigatório |
|---|---|---|
| `roots` | de onde a palavra vem | é o argumento de por que ela, e não a vizinha |
| `means` | o que ela significa **aqui** | um significado sem lugar é dicionário, não contrato |
| `not_means` | o que ela **não** significa | é a fronteira; sem ela, o sentido novo entra sem resistência |
| `constrains` | que regra operacional a raiz impõe | é o que torna o verbete verificável, e não opinião |

`not_means` é o campo que faz o trabalho. Um verbete que só diz o que a palavra
significa não impede a próxima ampliação — só a fronteira impede. Por isso o
teste `test_cada_termo_diz_o_que_NAO_e` exige os quatro campos preenchidos em
todos os verbetes.

## 2. Os eixos: quatro perguntas independentes

Um **eixo** é uma pergunta cuja resposta não determina a resposta das outras.
Existe página em qualquer combinação — uma extração ambígua não ratificada, uma
asserção humana ratificada e depois aposentada, uma inferência resolvida e ainda
proposta — e é essa independência que prova que são eixos distintos, e não
níveis de uma mesma escala.

| Eixo | Pergunta | Raiz | Valores |
|---|---|---|---|
| `derivation_method` | COMO isto passou a existir? | lat. *derivare*, "desviar água do rio" | `extracted` · `inferred` · `asserted` · `imported` |
| `resolution_status` | as leituras concorrentes foram assentadas? | lat. *resolvere*, "desatar" | `resolved` · `ambiguous` · `contested` |
| `governance_status` | quem autorizou isto a contar? | lat. *gubernare* ← gr. *kybernân*, "pilotar" | `proposed` · `ratified` · `retired` |
| `evaluation_status` | o quanto isto foi medido? | lat. *ex + valere*, "extrair o valor" | `unevaluated` … `invalidated` (hoje só para **mecanismo**) |

Cada raiz carrega a regra:

- *derivare* é **desviar água de um rio**: o curso vem de outro lugar e o
  percurso é rastreável. Por isso o valor descreve o **percurso**, nunca a
  qualidade do resultado nem quem o aprovou;
- *resolvere* é **desatar**, não cortar. Por isso nenhuma fusão, recompilação ou
  reindexação assenta sozinha o que ninguém assentou — só um ato posterior desata;
- *kybernân* é **pilotar**: quem governa conduz e responde pelo rumo, não possui
  o navio. Por isso ratificação é ato datado e atribuído, e ausência de ato é
  `proposed` — nunca silêncio a favor;
- *ex-valere* é **extrair o valor**: o que não foi medido não teve valor
  extraído. Por isso `unevaluated` é o default, e não uma falha.

O quarto eixo é o caso interessante: ele **já existia**, fechado e validado, em
`epistemic/model.py` — só que aplicado a *mecanismo*, não a afirmação.
Redefini-lo criaria a segunda definição do mesmo termo, que é exatamente o
defeito que este léxico combate. Ele fica declarado com `applies_to = "mechanism"`
e com o vão explícito.

## 3. O léxico

### 3.1 O corpus e seu ofício

**corpus** · lat. *corpus*, "corpo" — o conjunto trabalhado como **um**: tem
partes, fronteira e integridade verificável. Não é uma pilha de arquivos nem um
bucket. Operação que não preserva a integridade do todo não é operação de
corpus: por isso toda escrita passa por **um** gate.

**smith** · ing. ant. *smiþ* — ofício sobre material que já existe. Forjar é dar
forma, não criar matéria. Não é gerar conteúdo. O produto compila fontes, e
quando não há fonte suficiente **abstém**.

**compile** · lat. *compilare*, "juntar em monte" — montar um artefato a partir
de fontes, sob regras, de forma repetível. Não é resumir nem reescrever. A mesma
fonte sob as mesmas regras produz o mesmo artefato: determinismo antes de
modelo, com o LLM como estágio cercado.

**canon** · gr. *kanṓn*, "régua, vara de medir" (de *kánna*, "cana") — aquilo com
que se mede o resto. **Não** é aquilo que é verdadeiro. O registro diz o que foi
*aceito*, e por quem; aceitação não é veracidade.

**index** · lat. *index*, "o dedo indicador" — a projeção consultável que
**aponta** para o canônico, e nunca o conteúdo apontado. Apagá-lo não perde
conhecimento. O defeito que [RFC-002](19-rfc-escada-reconciliacao.md) corrigiu
foi exatamente uma projeção decidindo sobre o canônico.

### 3.2 O que se afirma

**assertion** · lat. *asserere*, *ad* + *serere*, "atar a si" (mesma raiz de
"série") — uma afirmação atada a quem a sustenta e à evidência que a prende. Não
é uma frase nem um chunk. Quem afirma fica atado — e é por isto que a **página**,
que pode conter duas asserções de fontes diferentes, é boa unidade *editorial* e
má unidade *epistêmica* (RFC-004 §6).

**evidence** · lat. *evidentia*, de *videre*, "ver" — literalmente *aquilo que se
dá a ver*. Não é a alegação de que existe suporte: é o trecho exato que se pode
olhar. Evidência que não pode ser **exibida** não conta como evidência, e daí
spans com offset em vez de apenas nome de página.

**provenance** · lat. *provenire*, "vir de" — o caminho percorrido desde a fonte,
**região a região**. Não é um rótulo colado na página inteira. Uma página com
duas fontes tem duas proveniências.

**epistemic** · gr. *epistḗmē*, "conhecimento", em oposição a *dóxa*, "opinião" —
a fronteira entre o que se sabe e o que se acha, marcada explicitamente. Não é
certeza nem rigor: toda garantia é **relativa** a um regime declarado, e
`universal_guarantee = true` é proibido pelo lint.

### 3.3 Quem responde

**authority** · lat. *auctoritas* ← *auctor* ← *augere*, "fazer crescer" — quem
pode fazer o corpus crescer, e responde por isso. **Não** é quem tem razão.
Autoridade é sobre permissão de escrita e origem, nunca sobre acerto. (É também
o termo mais sobrecarregado do código — §4.2.)

**curation** · lat. *curare* ← *cura*, "cuidado, zelo" — responder pelo estado do
corpus ao longo do tempo. Não é controlar, aprovar ou filtrar. Todo ato de
curadoria tem preview antes do efeito e é reversível: **cuidado sem
possibilidade de desfazer é controle**.

**ratification** · lat. *ratus*, "calculado, fixado" + *facere* — tornar fixo. Não
é concordar nem deixar de contestar: é o ato datado, com autor, em
`curation_acts`. Ela cobre um **conteúdo** — e conteúdo alterado perde a
cobertura, que é a regra nova de `merge_confidence`.

**verdict** · lat. *vere dictum*, "dito com verdade" — o juízo humano sobre um
objeto **computado**, com prazo declarado. Não é o resultado do cálculo.
Veredito suprime *com motivo* e com `until`; jamais apaga o objeto computado.

### 3.4 O tempo

Quatro tempos, quatro nomes — a separação que o produto **já** fez, e que agora
é protegida contra regressão pelo lint (§4.4):

| Nome | Tempo de | Pergunta |
|---|---|---|
| `valid_at` / `invalid_at` | **mundo** | quando o fato passou (ou deixou) de valer |
| `timestamp` | **registro** | quando escrevemos |
| `stale_as_of` | **código** | desde que commit isto pode estar parado |
| `resolved_at` | **governança** | quando o curador declarou fechada |

**stale** · fr. ant. *estale*, "parado, estagnado", dito de líquido — parado
desde uma referência de código, podendo precisar de revisão. **Não** é falso nem
vencido no mundo. Confundir `stale_as_of` com `invalid_at` deprecia fato que
continua valendo.

### 3.5 O aparato

**harness** · fr. ant. *herneis*, "arreio, equipamento" — o que prende e habilita
ao mesmo tempo: o caminho único de escrita. Não é um validador opcional. Não há
escrita fora do arreio, e conformidade OKF e política local ficam em camadas
**separadas**, para que o produto nunca invente exigência do SPEC.

**vitality** · lat. *vita* — estar vivo = **aceitar trabalho novo**. Não é
existir nem estar presente. Aposentar não apaga: a página sucedida continua no
bundle, no Git e no índice, e só deixa de ser endereço de trabalho.

**ontology** · gr. *ón, óntos*, "aquilo que é" + *-logía* — o discurso sobre o que
**existe** no sistema: quais entidades há e quais eixos as descrevem. **Não** é
uma ontologia formal com semântica lógica, e declarar que algo existe não é
alegar que é verdadeiro. ADR-53 §3 proíbe "ontologia formal", e este léxico não
a introduz.

## 4. Deriva semântica: onde o léxico ainda não fechou

Registro **vivo**, não confissão decorativa. Cada entrada aponta arquivo e
marcador; `corpusmith ontology lint` confere os dois lados a cada execução.

### 4.1 `confidence` — seis sentidos, três no mesmo campo · **aberta**

| Sentido | Onde |
|---|---|
| como derivou (`extracted`/`inferred`) | `compute/python_kernel.py` |
| se a leitura foi assentada (`ambiguous`) | `usecases/reconcile_candidate.py` |
| quem autorizou (`human_approved`) | `usecases/promote_memory.py` |
| autorrelato preditivo em [0,1] | `usecases/cognitive_journey.py` |
| três taxas estatísticas distintas | `usecases/metacognition.py` |
| intervalo de avaliação | `epistemic/model.py` |

**Pago em parte**: os três primeiros — que dividiam o campo do frontmatter —
foram separados em eixos por `kernel/ontology.py`, e a fusão passou a decidir
eixo a eixo. Os três últimos dividem só o nome, e continuam. A entrada **não**
pode ser fechada: fechá-la seria alegar um conserto que o código não tem.

### 4.2 `authority` — cinco sentidos · **aberta**

| Sentido | Onde |
|---|---|
| autoridade de **nome** — o gazetteer decide a grafia canônica | `okf/authorities.py` |
| autoridade de **armazenamento** — o bundle manda sobre as projeções | `kernel/checkpoints.py` |
| autoridade de **decisão** — quem pode ratificar e reverter | `usecases/curate/base.py` |
| autoridade de **referência** — o baseline medido arbitra regressão | `bench.py` |
| **tipo de página** protegida contra congelamento | `usecases/cold_memory.py` |

Nenhum é ilegítimo; todos são reais e distintos. Falta o qualificador no nome.

### 4.3 `evidence` — três sentidos · **aberta**

De **qualidade** do mecanismo (como ele foi validado, vocabulário fechado em
`epistemics.toml`), de **suporte** da resposta (os trechos que sustentam o que
foi respondido) e de **observação** (os registros por trás de uma proposta
metacognitiva). Três coisas legítimas com um nome só.

### 4.4 tempo — quatro sentidos, quatro nomes · **resolvida**

Fica registrada justamente por estar resolvida. O lint confere que os quatro
nomes continuam distintos no código: se um sumir, `ontology.drift_regressed` é
**erro**, não aviso. Uma separação conquistada e não guardada volta.

## 5. Falsos amigos

Palavras que o mercado usa com outro sentido, e que aqui significam coisa
diferente. A confusão não é de vocabulário — é de categoria.

| Palavra do mercado | O que costuma significar | O que significa aqui |
|---|---|---|
| *memory* | o que um agente recorda entre sessões | o corpus governado, que não pertence a nenhum agente |
| *ground truth* | o rótulo correto de um dataset | **não existe** no produto; existe o que foi aceito, e por quem |
| *source of truth* | o sistema que manda | o canônico **manda**, mas não é verdadeiro — é a régua |
| *knowledge graph* | entidades e relações representadas | uma **projeção** do bundle, descartável e reconstruível |
| *confidence score* | probabilidade calibrada | aqui era um rótulo de proveniência, e virou três eixos |
| *hallucination* | o modelo inventou | resposta sem evidência exibível — o produto **abstém** em vez disso |

## 6. Como este léxico se defende

Documento de vocabulário apodrece de duas formas, e as duas têm guarda:

1. **descrevendo código que mudou** — `ontology.toml` declara o vocabulário de
   cada eixo, e `test_toml_declara_o_vocabulario_real_do_kernel` cruza a
   declaração com as constantes de `kernel/ontology.py`. Divergiu, a suíte quebra;
2. **cobrando dívida já paga** — cada deriva traz marcadores. Marcador que some
   numa deriva `open` vira **warn** ("o sentido saiu do código; pare de
   cobrá-lo"); marcador que some numa deriva `resolved` vira **erro** ("a
   separação regrediu"). Um registro que só sabe cobrar treina o leitor a
   ignorá-lo.

`ontology lint` está no gate (`architecture.toml [gate]`, cruzado com a CI e o
justfile por `test_pr0_gate.py`) pelo mesmo motivo que `epistemics lint` está:
registro normativo que ninguém executa não é normativo.

```bash
cd backend && .venv/bin/python -m corpusmith.cli ontology axes
cd backend && .venv/bin/python -m corpusmith.cli ontology terms
cd backend && .venv/bin/python -m corpusmith.cli ontology drift
cd backend && .venv/bin/python -m corpusmith.cli ontology lint
```
