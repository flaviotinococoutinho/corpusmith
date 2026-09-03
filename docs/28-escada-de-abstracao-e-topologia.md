# 28 · A escada de abstração, e a topologia como instrumento epistêmico

> **Altitude:** produto · **Status:** vivo

> [`03`](03-teoria.md) fundamenta os mecanismos topológicos (persistência,
> Brandes, lacuna estrutural). [`24`](24-axiomas-e-oticas.md) lista as óticas.
> Falta a camada entre as duas: **em que NÍVEL cada coisa é verdade**, e o que a
> forma do corpus diz sobre a **qualidade** do que há nele.
>
> Esta página existe porque o defeito mais caro que o produto já teve — e o que
> [RFC-005](27-rfc-conflito-factual.md) acabou de encontrar — é o mesmo:
> **afirmar num nível o que só vale em outro**.

---

## 1. A escada

Sete níveis. Cada um tem uma unidade, uma coisa que consegue afirmar, uma que
**não** consegue, e o artefato onde mora.

| # | Nível | Unidade | O que ele PODE afirmar | O que ele NÃO pode | Onde mora |
|---|---|---|---|---|---|
| 0 | **offset** | caractere | "isto começa no byte 412" | nada sobre significado | `span_start/end` |
| 1 | **menção** | span | "aqui aparece `12 km`" | que a página *afirma* 12 km | `page_entities` |
| 2 | **região** | bloco sentinelado | "este trecho veio DESTA fonte" | que o resto da página veio dela | `okf/regions.py` |
| 3 | **afirmação** | asserção | "isto é sustentado por aquilo" | — | **não existe ainda** (RFC-004 §6) |
| 4 | **página** | documento | "este é o endereço editorial do assunto" | que tudo nela tem a mesma origem, validade ou aprovação | bundle |
| 5 | **tema** | partição nomeada | "estas páginas andam juntas ao longo do tempo" | que elas são *sobre* a mesma coisa | `themes`, RFC-001 |
| 6 | **grafo** | corpus inteiro | "estes blocos se ligam assim" | que a ligação significa concordância | `graph_edges`, `communities` |

**O nível 3 é o buraco**, e é o mesmo que ADR-53 §5, doc 00 §7 e RFC-004 §6
registram: o produto salta da **região** (nível 2, que sabe de onde o texto veio)
direto para a **página** (nível 4, que é onde `confidence`, `valid_at` e
`generated_via` moram). Não há onde dizer *"esta afirmação, sustentada por
aquela evidência, vale neste período"*.

## 2. Erro de nível é a classe de defeito

Os três defeitos mais caros que este repositório mediu são o **mesmo** erro:

| Defeito | Erro de nível | Onde está documentado |
|---|---|---|
| `confidence` respondia a três perguntas | atributo de **nível 3** (a afirmação) morando no **nível 4** (a página) | [RFC-004](22-rfc-ontologia-da-assercao.md) §2 |
| `canonical` de uma quantidade é o próprio valor | uma **menção** (nível 1) promovida a **entidade** — e entidade é identidade, não valor | [RFC-005](27-rfc-conflito-factual.md) §2 |
| proveniência por documento em vez de por região | origem do **nível 2** aplicada ao **nível 4** | `okf/regions.py` — corrigido |

A regra que sai disso, e que vale como teste mental antes de qualquer desenho:

> **Um atributo só pode ser afirmado no nível onde ele é verdade para o objeto
> inteiro daquele nível.** Se metade da página tem outra origem, origem não é
> atributo de página.

É por isso que RFC-005 recusou "mesma entidade com valores diferentes": pedir
isso é pedir que o nível 1 carregue identidade, que é nível 4. A saída foi buscar
o sujeito onde ele já existe — o grupo de identificador forte — em vez de
promover a menção.

## 3. Topologia como instrumento de qualidade

A topologia do corpus é lida hoje como **estrutura**. Ela também é um instrumento
de **qualidade**, e cada mecanismo responde a uma pergunta epistêmica diferente:

| Mecanismo | Pergunta estrutural | Pergunta **epistêmica** que ele responde |
|---|---|---|
| **persistência H₀** (Edelsbrunner et al. 2002) — `fragile_bridges` | que aresta une dois componentes grandes com peso baixo? | *onde o corpus está fingindo ser um só?* Dois blocos que só se falam por um fio fraco são, na prática, dois corpora — e uma resposta que atravessa esse fio é mais frágil do que o número de páginas sugere |
| **intermediação de Brandes** (2001) — `betweenness_centrality` | por onde passam os caminhos mais curtos? | *que página o corpus não pode perder?* Alta intermediação = revogar aquela página desconecta o discurso. É o inverso do calor: popular ≠ estrutural |
| **lacuna estrutural** (déficit sob o modelo de configuração de Newman) — `structural_gaps` | que par de blocos compartilha muito MENOS arestas do que o acaso preveria? | *que pergunta ninguém fez ainda?* A ponte frágil aponta o fio que existe; a lacuna aponta o **ausente** |
| **Leiden** — `communities` | como o grafo particiona? | *o corpus tem os blocos que eu acho que tem?* Uma comunidade que não corresponde a nenhum tema declarado é sinal de que o mapa mental e o corpus divergiram |
| **identidade de tema** (τ = 1/3, [RFC-001](16-rfc-theme-id.md)) | esta partição é a mesma de antes? | *o que mudou desde a última vez?* Sem identidade estável, `nasceu/cresceu/fundiu/morreu` viraria ruído a cada recomputação |

**O ganho conceitual**: as três primeiras medem coisas que **nenhuma leitura
página-a-página encontra**. Você não descobre uma ponte frágil lendo as duas
páginas que ela liga — a fragilidade é propriedade do **corpus**, nível 6. É o
argumento mais forte a favor de o produto ter uma ótica topológica: ela vê
defeitos de conhecimento que são invisíveis do nível editorial.

## 4. O que a topologia NÃO diz

A mesma disciplina de [ADR-53](21-adr-categoria-corpusmith.md) §3, aplicada aqui:

- **comunidade ≠ tema.** A comunidade é uma partição do grafo sob uma hipótese
  nula (modularidade); o tema é um objeto **nomeado e curado**. RFC-001 existe
  justamente porque a passagem de uma para o outro precisa de identidade
  declarada — sem ela, recomputar renomeia tudo;
- **centralidade ≠ importância.** Brandes mede posição no fluxo de caminhos
  curtos. Uma página pode ser central porque é um índice mal escrito;
- **ponte frágil ≠ link faltando.** Ela diz que a conexão existente é fina, não
  que há uma conexão correta a fazer. A proposta é *"olhe aqui"*, não *"ligue
  isto"*;
- **lacuna estrutural ≠ contradição.** Ausência de aresta é ausência de
  **relação**, não presença de **conflito**. O conflito factual é medido no nível
  do conteúdo (RFC-005), e por isso é um detector separado — confundi-los seria
  outro erro de nível;
- **o grafo é projeção.** Tudo nesta seção é reconstruível do bundle e não decide
  nada sobre o canônico (axioma A-1).

E duas defesas contra a degeneração clássica de grafos de co-ocorrência —
o gigante conectado sem estrutura — que já estão no código e valem como
limitação declarada: **teto anti-hub na origem** (co-menção só gera aresta para
entidade presente em 2..30 páginas) e **exclusão de super-hubs** (p99 de grau,
mínimo 8) antes do particionamento, com atribuição pós-hoc por maioria.

## 5. Como a qualidade sobe e desce a escada

O sinal de qualidade **nasce** num nível e **é lido** em outro. Onde isso é feito
sem cuidado, aparece o defeito.

| Sinal | Nasce em | É lido em | Cuidado declarado |
|---|---|---|---|
| suporte da resposta (`support`) | menção + região (1–2) | resposta (fora da escada) | decomposto em 4 parcelas com saturação declarada — ADR-52 evitou que base rasa virasse certeza |
| conflito factual (RFC-005) | menção (1) | par de páginas (4) | o sujeito vem do grupo de identificador, não da menção — §2 |
| calor / baixo rendimento | uso (fora da escada) | página (4) | é **desfecho de uso**, não juízo sobre o conteúdo: ADR-52 renomeou `contested → low_yield` exatamente para não confundir os dois |
| ponte frágil | grafo (6) | par de temas (5) | proposta, nunca ação |
| ratificação | ato humano | página (4) | não desce para as afirmações da página, e a fusão a derruba com registro — RFC-004 §5.4 |

**O padrão**: todo sinal que *sobe* a escada (de menção para página) precisa de
um sujeito, e todo sinal que *desce* (de corpus para página) precisa de um
limite. Onde falta um dos dois, o produto já errou pelo menos uma vez.

## 6. Para onde isso aponta

O nível 3 vazio é o que explica por que três coisas diferentes doem pelo mesmo
motivo — e por que RFC-004 §6 tem condições de reentrada em vez de data. Enquanto
ele não existir:

- `confidence` continua sendo atributo de página falando de afirmação;
- conflito factual precisa emprestar sujeito do grupo de identificador;
- e a resposta do `/ask` cita **página + span**, que é o mais perto de "afirmação"
  que a escada atual alcança.

Nenhuma dessas três é defeito de implementação. As três são o mesmo nível
faltando, e é por isso que a §6 do RFC-004 é a única entrada do backlog cuja
primeira condição de reentrada é **medir** — não construir.
