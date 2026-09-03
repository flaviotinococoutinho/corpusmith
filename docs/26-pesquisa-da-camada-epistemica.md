# 26 · A pesquisa por trás da camada epistêmica — e onde o Corpusmith **não** é novo

> **Altitude:** ciência · **Status:** vivo

> [`03-teoria.md`](03-teoria.md) fundamenta os mecanismos: NCD, entropia, Hedge,
> persistência, Brandes, RRF. Nenhum deles responde à pergunta da camada
> epistêmica — *o que é uma afirmação, e o que se pode dizer sobre ela*. Esta
> página cobre esse vão: a literatura em que os eixos de
> [RFC-004](22-rfc-ontologia-da-assercao.md) se apoiam, o que ela já resolveu
> melhor que nós, e onde a divergência do Corpusmith é deliberada.
>
> Regra desta página, herdada de [ADR-53](21-adr-categoria-corpusmith.md) §3:
> **onde existe arte prévia, ela é citada como arte prévia.** Um produto que
> vende governança não pode reivindicar como invenção o que uma comunidade
> publicou em 2010.

---

## 1. `capta`, não `data` — a base do "canônico ≠ verdadeiro"

[`23`](23-ontologia-e-etimologia.md) argumenta pela etimologia: *canon* é régua
de medir, logo o canônico mede e não é verdadeiro. A literatura chega ao mesmo
lugar por outro caminho, e o nome que ela dá é mais preciso.

**Drucker (2011)** distingue **data** — estados de coisas tidos como
independentes de observador — de **capta**, *o que é apreendido, registrado ou
afirmado por agentes cognitivos*. **Vitali & Pasqual (2026)**, revisando o
estado da arte em grafos de conhecimento, são categóricos:

> *"Knowledge graphs overwhelmingly deal with capta"* — atribuições de autoria,
> datações, classificações **não são medidas objetivas**, e sim o resultado de
> análise, tipicamente reportado junto com fontes e justificativas.
> — [arXiv:2606.15246](https://arxiv.org/abs/2606.15246), §2

Consequência que os autores tiram, e que vale palavra por palavra para o
Corpusmith: *"For data, the identification of provenance is largely irrelevant…
For capta, provenance is culturally significant: the identification of who made
a statement, when, and under which authority is essential."*

**O que isso muda aqui.** A proibição de "fonte da verdade" deixa de ser
modéstia e passa a ser **classificação correta do material**. O bundle é um
corpus de capta. Um registro de capta que se anuncia como fonte da verdade está
errado sobre o próprio conteúdo, não apenas exagerando.

## 2. Discordância não é anomalia — por que `contested` é valor de primeira classe

O eixo `resolution_status` tem três valores: `resolved`, `ambiguous`,
`contested`. A tentação de projeto era ter dois — resolvido e pendente — tratando
divergência como estado transitório a caminho da resolução.

A literatura desaconselha:

> *"disagreement is not an anomaly but a structural feature of the domain. The
> epistemic state of capta is also not uniform: some may be widely accepted,
> others contested, provisional, hypothetical, abandoned, illusory, or
> idiosyncratic."* — Vitali & Pasqual (2026), §2

O exemplo que eles usam é bom porque não é das humanidades: a úlcera péptica
teve, por décadas, uma explicação por estresse e acidez; nos anos 1980 surgiu a
explicação por *H. pylori*; hoje há uma terceira, multifatorial. **Por um período
significativo, os modelos coexistiram** — cada um com evidência metodologicamente
séria. Um registro que colapsasse isso num valor só teria perdido justamente a
informação que importa.

**O que isso muda aqui.** `contested` fica no vocabulário mesmo sem escritor no
caminho legado — é destino declarado de RFC-004 §6, não valor decorativo. E a
regra de fusão do `merge_confidence` ganha um segundo fundamento: *"fundir não
assenta o que ninguém assentou"* não é conservadorismo; é a recusa de colapsar
divergência em consistência aparente.

## 3. O defeito que encontramos tem nome na literatura

O defeito medido em [RFC-004](22-rfc-ontologia-da-assercao.md) §2.2 — a mesma
fusão devolvendo resultados diferentes conforme a ordem dos argumentos, e a
ratificação evaporando — foi achado por mutação, sem nenhuma teoria em mãos.
Ele pertence a uma classe que **Wang (2026)** tipifica formalmente:

> Sistemas de produção resolvem contradição com quatro heurísticas —
> *last-writer-wins*, *evidence-weighted merge*, *await-confirmation*,
> *per-rule policy* — *"yet none declares the isolation level it assumes or the
> write-time anomalies it admits"*. Contradiction resolution **é controle de
> concorrência no caminho de escrita**.
> — [arXiv:2606.06240](https://arxiv.org/abs/2606.06240), abstract e §1

O artigo nomeia três falhas que um juiz-modelo introduz e que o alfabeto
clássico de anomalias não cobre:

| Falha (Wang 2026) | O que é | Onde ela apareceu aqui |
|---|---|---|
| **replay inconsistency** | re-adjudicar a mesma contradição devolve um vencedor diferente | a assimetria de `merge_meta`: `merge(a,b) ≠ merge(b,a)` — mesmo par, vencedor conforme a ordem |
| **belief-drift skew** | revisões concorrentes de confiança corrompem uma partição | não observado (escrita é serializada pelo gate único) |
| **audit erasure** | o fato sobrescrito se torna irrecuperável | não no conteúdo (Git guarda tudo), **mas no eixo**: a ratificação sumia sem registro de que sumiu |

A terceira linha é o achado interessante. O produto sempre protegeu o
**conteúdo** contra apagamento — *aposentar não é apagar* é o axioma A-2. O que
não estava protegido era o **atributo epistêmico**: o `human_approved` era
destruído por uma regra de derivação, e nada em `curation_acts`, no `log.md` ou
no diff registrava que uma ratificação tinha deixado de valer. Apagamento
silencioso de metadado de governança é apagamento — a lição é que o axioma A-2
precisava valer eixo a eixo, não só página a página.

**A dimensão do problema no mercado**, medida pelo mesmo artigo: *BeliefShift*
deixa até **42% das contradições entre sessões sem resolução** em sete famílias
de modelos; e a varredura de implantações dos autores encontra vocabulário de
*isolation*, *contradiction*, *audit* e *bitemporal* **largamente ausente** nos
sistemas de memória de agente amplamente usados.

## 4. Como os vizinhos resolvem contradição

Levantamento de Wang (2026) §5, com a coluna do Corpusmith acrescentada por nós:

| Sistema | O que faz com o fato perdedor |
|---|---|
| mem0 v2 | vota entre `add`/`update`/`delete`/`none` e **descarta o perdedor** |
| mem0 v3 | adia a adjudicação para o momento da recuperação |
| Zep / Graphiti | invalida arestas antigas **no caminho de leitura** |
| Letta | organiza memória em blocos versionados |
| WorldDB | proveniência por ancestralidade Merkle endereçada por conteúdo |
| **Corpusmith** | **sucede escrevendo para a frente**: o perdedor continua no bundle, no Git e no índice, com `superseded_by` apontando o sucessor, e some apenas da fila de trabalho novo |

A escolha do Corpusmith não é melhor por decreto — ela troca uma coisa por
outra. **Ganha**: o histórico é o mesmo artefato que o usuário lê e edita, sem
audit row paralela, sem store extra, e `git log` é a interface de auditoria.
**Perde**: sem transação multi-escritor de verdade, o produto depende do gate
único e de escrita serializada, e não teria resposta se precisasse absorver
escritas concorrentes de vários agentes — o problema que Wang tipifica com
níveis de isolamento é real e está **fora** do envelope atual. Isso pertence ao
envelope de generalização, não a uma nota de rodapé.

## 5. Onde o Corpusmith **não** é novo

Esta é a seção que uma página de "diferencial" costuma não ter.

**A asserção como entidade de primeira classe, empacotada com proveniência, já
existe — e é de 2010.**

- **Nanopublications** (Groth, Gibson & Velterop, 2010; Kuhn & Dumontier)
  empacotam **assertion + provenance + publication info** em grafos distintos.
  É, estruturalmente, a proposta de RFC-004 §6;
- **Micropublications** (Clark, Ciccarese & Goble, 2014) vão além e representam
  a alegação científica junto com **evidência, suporte, contestação e estrutura
  de argumento**;
- **CIDOC-CRM / CRMinf** modelam *inference making* e **belief adoption como
  evento executado por um agente no tempo** — que é exatamente "ratificação é
  ato datado e atribuído";
- **Wikidata** já tem ranks (`preferred`/`normal`/`deprecated`) e referências
  por statement;
- **PROV-O** é o modelo de proveniência consolidado (Entity / Activity / Agent);
- **Datomic** e **XTDB** já entregam tempo, proveniência e acumulação
  bitemporal como modelo de informação;
- **Snodgrass** e o SQL:2011 (`AS OF`) fixaram bi-temporalidade décadas atrás.

Um produto que apresentasse "asserções com proveniência e validade temporal"
como invenção estaria fazendo o que ADR-53 §3 proíbe. **Não é invenção. É
adoção tardia, e a honestidade de dizê-lo é parte do produto.**

## 6. Onde a divergência é deliberada

O que a arte prévia deixa em aberto, e onde a escolha do Corpusmith é uma
escolha e não ignorância:

**(a) A asserção mora no artefato editorial, não num grafo paralelo.** Nanopubs,
micropubs e RDF-star põem a asserção num grafo RDF ao lado do documento. O
Corpusmith exige que ela seja **lida do Markdown**, por região com offset de
span, como a proveniência já é (`okf/regions.py`). O motivo é o axioma A-1: um
grafo paralelo editável seria um **segundo lugar onde o conhecimento mora**, e o
canônico deixaria de ser um só. O custo dessa escolha é real — perde-se
raciocínio RDF pronto — e está registrado como condição de reentrada em RFC-004
§6.

**(b) A ratificação é um commit, não um triplo.** CRMinf modela *belief
adoption* como evento; o Corpusmith usa a infraestrutura que já existe para
eventos datados, atribuídos e reversíveis — o Git. `curation_acts` é **índice**
de atos, não verdade paralela.

**(c) A proveniência é semanticamente carregada, e não neutra.** Vitali &
Pasqual apontam que *"PROV-O treat[s] provenance as an external addition to an
otherwise unqualified statement, without addressing its epistemic status"*, e
que Wikidata *"introduce[s] rankings and uncertainty indicators, but… in a
coarse and largely informal manner"*. Os quatro eixos de RFC-004 são uma resposta
pequena e operacional a essa crítica: em vez de um *rank* informal, quatro
perguntas com vocabulário fechado e lint. É menos ambicioso que a lógica modal
que os autores propõem — e é executável hoje, com um custo de anotação que não
recai sobre o usuário.

**(d) A independência entre atribuição e conteúdo, adotada literalmente.** O
artigo formula o ponto melhor do que estava formulado aqui: *"the truth of the
attribution and the truth of φ are logically independent"* — uma afirmação pode
ser corretamente atribuída e falsa, ou incorretamente atribuída e verdadeira. É
a versão forte de *"canônico registra o que foi aceito, e por quem"*, e é o
argumento de por que `governance_status` **não pode** morar no mesmo campo que
`derivation_method`.

## 7. O que esta leitura muda no roadmap

| Achado | Consequência |
|---|---|
| capta ≠ data | a proibição de "fonte da verdade" é classificação, não modéstia — vale reescrever assim em material de produto |
| discordância é estrutural | `contested` fica; e a fila de atenção deveria, no futuro, **propor** revisão de contestações em vez de esperar que sejam resolvidas |
| replay inconsistency / audit erasure | o axioma A-2 vale **eixo a eixo** — ✅ **pago**: `ratificacao_perdida` declara a perda no preview do MergePages e no evento/resultado do fluxo de máquina; a chave ausente deixou de herdar ratificação (`merge_meta`) |
| nanopubs/micropubs como arte prévia | RFC-004 §6 deve **começar** citando-os; a contribuição é o lugar de morada, não a entidade |
| isolamento multi-escritor | está **fora** do envelope atual e deve ser dito assim, não omitido |

## Referências

- Drucker, J. **"Humanities Approaches to Graphical Display"**, DHQ, 2011 — a
  distinção *data* / *capta*.
- Vitali, F. & Pasqual, V. **"Provenance-Enhanced Statements in Knowledge
  Graphs"**, [arXiv:2606.15246](https://arxiv.org/abs/2606.15246), 2026 —
  proveniência como *estance* epistêmica; mundos cognitivos; desacordo,
  delusão, assentamento; crítica à neutralidade semântica de PROV-O e aos ranks
  de Wikidata.
- Wang, Z. **"TOKI: A Bitemporal Operator Algebra for Contradiction Resolution
  in LLM-Agent Persistent Memory"**,
  [arXiv:2606.06240](https://arxiv.org/abs/2606.06240), 2026 — as quatro
  heurísticas de produção como operadores tipados; *replay inconsistency*,
  *belief-drift skew*, *audit erasure*; varredura de sistemas implantados.
- Groth, P., Gibson, A. & Velterop, J. **"The anatomy of a nanopublication"**,
  Information Services & Use, 2010; Kuhn, T. & Dumontier, M., trabalho
  subsequente — assertion / provenance / publication info.
- Clark, T., Ciccarese, P. & Goble, C. **"Micropublications: a semantic model
  for claims, evidence, arguments and annotations"**, J. Biomedical Semantics,
  2014.
- **CIDOC-CRM / CRMinf** — *inference making* e *belief adoption* como eventos.
- Snodgrass, R. **temporal data models**; SQL:2011 (`AS OF`) — bi-temporalidade.
- Moreau, L. et al. **PROV-O**, W3C, 2013 — Entity / Activity / Agent.
