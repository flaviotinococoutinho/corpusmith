# 22 · RFC-004 — A ontologia da asserção: separar os eixos que `confidence` fundiu

> `AGENTS.md` §8 exige RFC para **heurística no caminho de escrita** e para
> **mudança de schema não-aditiva**. Este RFC toca as duas coisas: a regra que
> decide `confidence` numa fusão está no caminho de escrita, e a entidade
> `Assertion` proposta na §6 é mudança de schema. Por isso ele é entregue em
> duas metades — a §5 é implementada agora, a §6 exige ratificação antes de
> uma linha de código.

| | |
|---|---|
| **Status** | Parcialmente implementado (§5 entregue; §6 proposto) |
| **Sucede** | ADR-53 §5 (a lacuna registrada: "a página não é unidade epistêmica atômica") |
| **Origem** | `docs/00` §7 — limite conhecido; auditoria de deriva semântica |
| **Artefato** | [`ontology.toml`](../ontology.toml) · `kernel/ontology.py` · `harness/ontology.py` |

---

## 1. Contexto

O produto tem dois contratos legíveis por máquina, e ambos existem pelo mesmo
motivo: impedir que a documentação minta sobre o código.
[`architecture.toml`](../architecture.toml) declara o que pode depender de quê;
[`epistemics.toml`](../epistemics.toml) declara o que cada mecanismo pode
alegar. Nenhum dos dois responde à pergunta anterior a ambos: **o que cada
palavra significa**.

Isso não é filosofia. Um vocabulário sem fronteira declarada não resiste ao
tempo: cada PR que precisa marcar algo procura o campo mais próximo, e o campo
mais próximo aceita — porque `OKFFrontMatter` tem `extra="allow"` e o Harness,
que valida `privacy`, checksum de fonte, PII e sucessão, **não valida
`confidence`**. Não há vocabulário fechado; qualquer string passa.

## 2. Problema mensurado

### 2.1 Um campo, seis perguntas

Levantado nesta árvore, por leitura direta do código:

| Onde | O que `confidence` significa ali |
|---|---|
| `compute/python_kernel.py:17` — `EDGE_WEIGHT = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}` | **como derivou** |
| `usecases/reconcile_candidate.py:79` — `"ambiguous"` quando a projeção está atrasada | **se a leitura foi assentada** |
| `usecases/promote_memory.py:173` — `"confidence": "human_approved"` | **quem autorizou** |
| `usecases/cognitive_journey.py:315` — `confidence_before ∈ [0,1]` | **autorrelato preditivo** |
| `usecases/metacognition.py:129,161,180` — `rate`, `hi_rate - lo_rate`, `gap` | **três taxas estatísticas diferentes** |
| `epistemic/model.py:194` — `confidence_intervals` | **intervalo de avaliação** |

As três primeiras dividem literalmente o **mesmo campo do frontmatter**. As
três últimas dividem só o nome — e `epistemic/model.py:4` já registrava a
esquiva: *"NÃO reutiliza o campo `confidence` existente do produto"*. Alguém
percebeu, desviou, e não havia onde registrar o desvio.

### 2.2 A conflação tinha consequência executável

`kernel/curation.py:merge_meta` ordenava por uma tabela de fraqueza com **três**
valores, num campo que o produto escreve com **quatro**:

```python
fraqueza = {"extracted": 0, "inferred": 1, "ambiguous": 2}
out[chave] = max(atual, valor, key=lambda c: fraqueza.get(c, 0))
```

`human_approved` caía no `default=0`, empatando com `extracted`; e `max` devolve
o **primeiro** dos empatados. Medido antes da correção:

```
merge("human_approved", "extracted") -> "human_approved"   # ratificação fica
merge("extracted", "human_approved") -> "extracted"        # ratificação some
merge("human_approved", "inferred")  -> "inferred"         # ratificação some
```

Dois defeitos, não um:

1. **assimetria** — a mesma fusão dá resultados diferentes conforme a ordem dos
   argumentos, isto é: conforme qual página o curador clicou primeiro;
2. **governança decidida por regra de derivação** — se a ratificação sobrevive
   ou não a uma fusão estava sendo respondido por um `default=0` que ninguém
   escolheu.

Nenhum dos dois é "a regra errada". É a **ausência de regra**, com um acidente
de dicionário respondendo no lugar dela — a mesma forma de defeito que a
auditoria (`docs/17`) descreveu como a marca do projeto: *constrói bem e
verifica mal aquilo que construiu*.

### 2.3 Deriva além de `confidence`

O mesmo levantamento encontra cinco sentidos de **autoridade** (nome no
gazetteer, armazenamento canônico, decisão de curadoria, baseline de
performance, tipo de página protegida) e três de **evidência** (validação do
mecanismo, suporte da resposta, observação por trás de uma proposta). Nenhum
deles é ilegítimo — todos são reais e distintos. O que falta é o qualificador
no nome e o lugar onde a distinção fique registrada.

**Tempo** é o contraexemplo útil: quatro sentidos, quatro nomes distintos
(`valid_at`/`invalid_at`, `timestamp`, `stale_as_of`, `resolved_at`), separados
desde a v0.8 §6.3 e F3-PR2. Prova de que a separação é possível dentro deste
produto — e de que ela só se sustenta se alguém a proteger contra regressão.

## 3. Opções consideradas

| Opção | Por que não |
|---|---|
| **A. Não fazer nada; documentar em prosa** | é o estado atual; a prosa não impede o próximo PR de reusar o campo, e nada acusa quando ela apodrece |
| **B. Validar `confidence` no Harness contra os quatro valores** | fecha a porta, mas congela a conflação: os quatro valores continuariam respondendo a três perguntas |
| **C. Renomear `confidence` para `derivation_method` já** | migração de bundle canônico + toda superfície, por um ganho que não precisa da migração para existir |
| **D. Eixos separados no kernel, campo legado intacto** ✅ | a regra passa a ser escrita e testável hoje, sem tocar em nenhum arquivo do bundle; a migração vira decisão própria (§6) |

## 4. O que é um eixo

Um **eixo** é uma pergunta cuja resposta não determina a resposta das outras. O
teste de que um valor está no eixo certo é conseguir responder *a pergunta
deste eixo* com ele — e não a de outro. `extracted` responde "como derivou".
`ambiguous` responde "resolveu?". `human_approved` responde "quem autorizou".
Três perguntas, e a prova de que são independentes é que existe página em
qualquer combinação: uma extração ambígua não ratificada, uma asserção humana
ratificada e depois aposentada, uma inferência resolvida e proposta.

Por isso `ontology.toml` exige `question` em todo eixo: um eixo que não declara
a pergunta que responde não permite testar se um valor entrou nele por engano —
que é exatamente como a conflação se instala.

## 5. Decisão — implementada agora

### 5.1 Três eixos no núcleo puro

`kernel/ontology.py` declara os eixos com vocabulário **fechado**:

| Eixo | Pergunta | Valores |
|---|---|---|
| `derivation_method` | COMO esta afirmação passou a existir? | `extracted` · `inferred` · `asserted` · `imported` |
| `resolution_status` | as leituras concorrentes foram assentadas? | `resolved` · `ambiguous` · `contested` |
| `governance_status` | quem autorizou isto a contar como conhecimento? | `proposed` · `ratified` · `retired` |

O quarto eixo do desenho — `evaluation_status` — **já existe**, fechado e
validado, em `epistemic/model.py`, aplicado a *mecanismo* e não a afirmação.
Declará-lo de novo criaria a segunda definição do mesmo termo, que é o defeito
que este RFC combate. Ele fica registrado em `ontology.toml` com
`applies_to = "mechanism"` e com o vão explícito.

### 5.2 Leitura, não escrita

`classificar(meta)` **lê** o frontmatter que já existe e devolve os eixos. Não
exige campo novo, não escreve nada, e onde o campo legado cala a resposta vem
de outra chave que já carrega o mesmo sentido (`generated_via`,
`superseded_by`/`invalid_at`). Só quando todas calam entra o default que o
código já aplica (`COALESCE(confidence,'extracted')`), e entra por ser o
comportamento vigente — não por ser a leitura mais generosa.

Ausência é resposta: página de máquina sem ato humano registrado é `proposed`.
Chamá-la de ratificada seria a alegação que ADR-53 §3 proíbe.

### 5.3 A fusão decide eixo a eixo

`merge_confidence(a, b)`, chamada por `merge_meta`:

- **derivação** fica com a mais fraca — fundir não promove a qualidade do que
  se afirma. A ordem é por *distância até a fonte*, não por prestígio de quem
  produziu: `extracted` (literal na fonte) → `imported` (literal em outro
  registro, cuja extração não presenciamos) → `asserted` (afirmado sem fonte
  externa) → `inferred` (derivado por regra ou modelo — o único que pode estar
  errado sem que ninguém tenha errado);
- **resolução** fica ambígua se qualquer lado for ambíguo — fundir não assenta
  o que ninguém assentou;
- **governança** só permanece `ratified` se **ambos** os lados forem.

A terceira regra é a única que muda comportamento, e muda para menos:
`merge("human_approved", "extracted")` deixa de devolver `human_approved`.
Ratificação é ato sobre um conteúdo; a fusão produz outro conteúdo, que ninguém
ratificou. Se a fusão merece ratificação, ela volta por um ato humano registrado
em `curation_acts` — não por herança silenciosa.

### 5.4 A perda é DECLARADA, nunca silenciosa

Derrubar a ratificação é correto; derrubá-la sem registro é a falha que a
literatura chama de *audit erasure* ([`docs/26`](26-pesquisa-da-camada-epistemica.md) §3).
`kernel/ontology.py:ratificacao_perdida` diz se a fusão desfaz uma ratificação
e de qual lado ela era, e os dois eixos de escrita a consomem:

- **humano** — o preview do `MergePages` declara *"esta fusão PERDE a
  ratificação de X"* antes do efeito, que é o contrato de todo ato;
- **máquina** — o evento `page.stage` (etapa `write`) e o resultado do use
  case carregam `ratification_lost` quando um UPDATE/RECYCLE derruba a
  aprovação da residente.

E a porta lateral fechada junto: um rascunho **sem** a chave `confidence`
herdava `human_approved` da residente pela regra genérica de fusão ("o que
falta vem da fonte"). Ausência tem default documentado (`extracted`, o
`COALESCE` de toda leitura), então `merge_meta` agora funde a chave com o
default aplicado — medido por teste que reprovava antes.

### 5.5 A perda de expressividade que fica registrada

O vocabulário legado não tem casa para o par (`asserted`, `proposed`) — que é
justamente o que sobra quando a fusão desfaz a cobertura de uma ratificação. A
reescrita desce para `inferred`: também não é exato, mas erra para o lado que
**reduz influência** (peso 0.5 contra 1.0 em `compute/python_kernel.py`) em vez
do lado que **inventa proveniência**. Esta perda não se conserta reescrevendo
melhor; ela é o argumento concreto da §6.

### 5.6 O registro de deriva não pode apodrecer

`ontology.toml` §3 lista as derivas com `markers`: pares (arquivo, string) que,
existindo, provam que aquele sentido está no código. `corpusmith ontology lint`
lê os dois lados:

- marcador some numa deriva `open` → **warn**: o sentido saiu do código; se a
  dívida foi paga, o registro precisa parar de cobrá-la;
- marcador some numa deriva `resolved` → **erro**: a separação perdeu um de
  seus nomes distintos — regressão.

Sem isto, um registro de dívida só sabe cobrar, e apodrece de um jeito
silencioso: alguém conserta a conflação, ninguém volta ao arquivo, e o
documento passa a acusar defeito inexistente — o que treina o leitor a ignorar
o documento inteiro.

## 6. Proposto — a asserção como entidade (NÃO implementado)

Esta seção é decisão pendente. Nada dela existe em código.

**Arte prévia, antes de qualquer coisa.** Empacotar uma asserção com sua
proveniência não é invenção nossa e é anterior a este produto por mais de uma
década: **nanopublications** (Groth, Gibson & Velterop, 2010) separam
*assertion*, *provenance* e *publication info* em grafos distintos;
**micropublications** (Clark, Ciccarese & Goble, 2014) acrescentam evidência,
suporte, contestação e estrutura de argumento; **CRMinf** modela *belief
adoption* como evento de um agente no tempo; **PROV-O**, **Wikidata** (ranks e
referências por statement) e o modelo bitemporal de **Snodgrass**/SQL:2011
cobrem o resto. Apresentar a §6 como novidade seria exatamente a alegação que
ADR-53 §3 proíbe. O levantamento completo, com o que cada um resolve melhor que
nós, está em [`docs/26`](26-pesquisa-da-camada-epistemica.md).

**A contribuição possível não é a entidade — é o LUGAR DE MORADA dela**, e essa
é a única parte desta seção que não tem precedente confortável: nanopubs,
micropubs e RDF-star colocam a asserção num grafo ao lado do documento; aqui ela
teria de ser **lida do Markdown**, por região, porque um grafo paralelo editável
seria um segundo lugar onde o conhecimento mora e o axioma A-1 cairia.

**O problema.** A unidade epistêmica hoje é a **página**, e a página é boa
unidade *editorial* e má unidade *epistêmica*: uma página sobre Docker pode
conter uma linha extraída de um PDF de 2019 (válida até 2022), uma inferência
do compilador e uma nota que o autor escreveu de cabeça. Hoje as três recebem
**um** `confidence`, **uma** proveniência de região e **um** par
`valid_at`/`invalid_at`. Qualquer resposta que cite a página herda o menor
denominador — ou, pior, o maior.

**A forma proposta.**

| Entidade | O que é | Onde viveria |
|---|---|---|
| `Assertion` | uma afirmação atada a quem a sustenta, com os quatro eixos próprios | região do Markdown, endereçada por span — **não** uma tabela paralela |
| `EvidenceLink` | o vínculo entre uma asserção e o trecho de fonte que a prende | derivado, reconstruível do bundle |
| `AuthorityGrant` | o ato datado que concede a alguém o direito de ratificar um tipo de asserção | canônico, versionado em Git |

**A restrição inegociável**: nenhuma delas pode virar autoridade paralela ao
bundle. `Assertion` tem de ser *lida do Markdown*, como a proveniência por
região já é (`okf/regions.py`), ou o produto ganha um segundo lugar onde o
conhecimento mora — e o axioma A-1 cai.

**Condições de reentrada** (o que precisa ser verdade antes de implementar):

1. existir pelo menos uma consulta real que a granularidade de página responde
   errado, **medida**, não imaginada;
2. o custo de anotação por asserção não recair sobre o humano no caminho comum;
3. `EvidenceLink` ser reconstruível do bundle sozinho — se precisar de estado
   próprio, a proposta está errada;
4. haver resposta a *"por que não adotar nanopublications e pronto?"* que não
   seja preferência — a resposta candidata é a condição 3 aplicada ao formato,
   e ela precisa ser demonstrada, não afirmada.

Enquanto as três não forem verdade, a §6 continua proposta. Implementá-la antes
disso seria fazer o que este RFC acusa: inventar estrutura onde falta evidência.

## 7. Invariantes

- **I-1** — todo valor de eixo aparece em exatamente **um** eixo
  (`test_nenhum_valor_responde_a_duas_perguntas`);
- **I-2** — o vocabulário declarado em `ontology.toml` é idêntico ao do kernel
  (`test_toml_declara_o_vocabulario_real_do_kernel`);
- **I-3** — `merge_meta` é **simétrica** em `confidence`
  (`test_fusao_e_simetrica`, por `merge_meta`, não pela função nova);
- **I-4** — fusão nunca produz `ratified` a partir de um lado não ratificado
  (`test_ratificacao_nao_sobrevive_a_fusao_com_nao_ratificado`);
- **I-5** — toda deriva `resolved` continua com seus nomes distintos no código
  (`ontology.drift_regressed`).

## 8. Migração

Nenhuma. Nenhum arquivo do bundle muda, nenhum schema de banco muda, nenhum
valor novo é escrito no frontmatter. O único comportamento alterado é a
`confidence` resultante de uma fusão — e apenas na direção de alegar menos.

## 9. Modos de falha

| Falha | Sintoma | Contenção |
|---|---|---|
| eixo novo criado sem verbete | `ontology.axis_undeclared` | erro no lint, gate quebra |
| valor reaproveitado em dois eixos | `ontology.term_off_axis` | erro no lint |
| deriva consertada e não atualizada | `ontology.drift_sense_gone` | warn — visível sem bloquear |
| separação regredida | `ontology.drift_regressed` | erro |
| binário empacotado sem árvore de código | `ontology.refs_uncheckable` | warn declarado: omitir a checagem é legítimo, omitir que ela foi omitida não |

## 10. Risco de overengineering

Real, e vale dizer onde ele mora. Três eixos, um TOML e um lint para um campo
com quatro valores é desproporcional **se a única justificativa for elegância**.
A justificativa não é: é um defeito medido de assimetria no caminho de escrita
humano mais usado do produto, com uma correção que só é escrevível depois de os
eixos existirem. O TOML e o lint custam ~200 linhas e pagam a mesma função que
`architecture.toml` e `epistemics.toml` já pagam duas vezes neste repositório.

O que **não** foi feito, de propósito: nenhuma tabela nova, nenhum campo novo
no frontmatter, nenhuma migração, nenhuma entidade `Assertion`. A §6 fica
proposta com condições de reentrada explícitas.

## 11. Evidências

- assimetria e perda de ratificação: reproduzidas por mutação — restaurar a
  tabela de três valores faz `test_fusao_e_simetrica[extracted-human_approved]`
  e `test_ratificacao_nao_sobrevive_a_fusao_com_nao_ratificado` reprovarem;
- ausência de validação de `confidence`: `grep -rn "confidence" harness/` não
  devolve nenhuma linha;
- os seis sentidos: tabela da §2.1, cada linha com arquivo e número;
- os quatro tempos já separados: `[drift.time]` com `status = "resolved"` e
  marcadores que o lint confere a cada execução.
