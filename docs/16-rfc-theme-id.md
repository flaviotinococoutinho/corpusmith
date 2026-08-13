# 16 · RFC-001 — Identidade de tema (`theme_id`) por casamento de partições

> **Este é o primeiro RFC do projeto.** O `docs/10` §19 define o template e o
> marcava "🎯 a instanciar"; esta é a instanciação. O `AGENTS.md` §8 exige RFC
> — não só ADR — para **heurística no caminho de escrita**, e é exatamente o
> que o F2-PR2 introduz: o casamento de partições decide `UPDATE` vs
> `SUPERSEDE` de página canônica.

| | |
|---|---|
| **Status** | Proposto |
| **Pacote** | F2-PR2 (`docs/15` §4) |
| **Orçamento de complexidade** | 2 tabelas novas = **4 pontos** ⇒ limiar de RFC (`docs/10` §20.1) |
| **Sucede** | ADR-43 (partição repetível), ADR-44 (centralidade persistida) |

---

## 1. Contexto

A camada de padrões nasceu em três degraus. O ADR-43 tornou a partição
**repetível** (mesmo bundle ⇒ mesma partição, rótulo a rótulo) e o ADR-44
tirou a centralidade do request. O que ainda não existe é **identidade**: o
rótulo inteiro da comunidade é derivado do menor membro, o que o torna
*estável* mas não *identificador* — se a composição do tema muda, o rótulo
muda, e nada liga a versão nova à antiga.

Sem identidade, `communities/` apodrece. E isso não é previsão: é medido.

## 2. Problema mensurado

### 2.1 O mesmo tema vira duas páginas canônicas

`_CommunitySummaryPage` deriva o `rel_path` de `_slug(label)`, e `label` vem
do membro de maior grau (ou do rótulo que o LLM inventa). Experimento com um
tema de 5 páginas em que a página mais conectada muda de `ana` para `elo`,
**sem nenhuma página entrar ou sair do tema**:

```
1. tema nomeado pela mais conectada:   ['ana.md', 'index.md']
2. `elo` vira a mais conectada:        ['ana.md', 'elo.md', 'index.md']

MESMO tema (as 5 páginas continuam juntas), arquivos: 1 -> 2
arquivo antigo SOBREVIVEU descrevendo o mesmo tema: ['ana.md']
  ana.md: ['# ana']
  elo.md: ['# elo']
```

**Duas páginas canônicas afirmando o mesmo tema, nenhuma supersedida.** O
produto fabrica a contradição que o próprio `policy.contradiction_candidate`
existe para acusar. Cada rodada do job pode acrescentar uma.

### 2.2 O limiar de Jaccard não pode ser escolhido

Calibração contra perturbações que um curador de verdade faz, com os
**caminhos das páginas preservados** (a primeira versão do experimento
renomeava as páginas, e aí o Jaccard media *deleção*, não mudança de tema):

| perturbação | melhor Jaccard do tema afetado | forma do casamento |
|---|---:|---|
| 1 página nova (6 → 7) | 0,86 | 1↔1 |
| 3 páginas novas (6 → 9) | 0,67 | 1↔1 |
| 2 páginas saem (6 → 4) | 0,67 | 1↔1 |
| **tema DOBRA (6 → 12)** | **0,50** | 1↔1 |
| **tema PARTE em dois trios** | **0,50** | **1 → 2** |
| tema DISSOLVE (páginas migram para outros) | 0,17 | 1 → 0 |
| tema novo nasce (antigos intactos) | 1,0 nos antigos | 0 → 1 |

Duas conclusões, e as duas contradizem o desenho ingênuo:

**(a) τ = 0,5 é o pior valor possível.** É exatamente o Jaccard de um
crescimento legítimo (dobrar) **e** de um split. Um limiar ali classifica os
dois casos pelo bit menos significativo de uma divisão.

**(b) o valor do Jaccard não distingue `split` de `grew`.** Nos dois casos ele
é 0,50. O que distingue é a **forma do casamento**: no split, UMA comunidade
antiga casa com DUAS novas. Detectado corretamente nos três limiares testados
(0,2 · 0,33 · 0,5).

Há uma **banda vazia medida entre 0,17 e 0,50**: nenhum evento legítimo caiu
ali. É a única região em que o limiar não decide nada por acidente.

### 2.3 `merged` não foi observado

Não consegui produzir uma fusão. Mesmo com alfa e beta densamente
interligados (cada `alfa-i` ligando a todo alfa **mais** `beta-i` e
`beta-i+1`; cada `beta-i` ligando a todo beta mais `alfa-i`), o Leiden
manteve **3 comunidades de 6** e Jaccard 1,0. Modularidade resiste a fundir
cliques densos — é propriedade do critério, não defeito do experimento.

## 3. Opções consideradas

| # | Opção | Por que não |
|---|---|---|
| 1 | **`theme_id` = rótulo do LLM** | A identidade do tema passaria a depender de uma resposta de modelo: mesmo bundle, `theme_id` diferente. Destrói a repetibilidade que o ADR-43 pagou |
| 2 | **`theme_id` = hash dos membros** | Muda a cada página que entra ou sai. É um identificador de *conjunto*, não de *tema* — nunca haveria `grew` |
| 3 | **`theme_id` = rótulo inteiro da comunidade (ADR-43)** | Já existe e é estável para o mesmo bundle, mas é derivado do menor membro: sai da página menor, muda o tema todo |
| 4 | **casamento de partições por Jaccard + forma** | **Escolhida** |
| 5 | Casamento por similaridade de embedding dos sumários | Introduz dependência de modelo no caminho de escrita (o que este RFC existe para evitar) e não é reprodutível sem fixar o modelo |

## 4. Decisão

### 4.1 `theme_id` é opaco, estável e atribuído no casamento

Identificador opaco (`thm_` + 12 hex do primeiro conjunto de membros).
**Opaco de propósito**: um id derivado da composição atual voltaria a mudar
quando a composição muda. Ele é atribuído UMA vez, no nascimento, e
**sobrevive** a `grew`/`shrank`.

### 4.2 O casamento tem duas etapas, e a segunda é a que classifica

1. **relacionar**: Jaccard entre cada comunidade da época anterior e cada
   comunidade da nova, mantendo pares ≥ **τ = 1/3**;
2. **classificar pela forma** do casamento bipartido:

| forma | evento | efeito no canônico |
|---|---|---|
| 1 antiga ↔ 1 nova, membros iguais | *(nenhum evento)* | nada é escrito |
| 1 ↔ 1, cresceu | `grew` | **UPDATE** da página do tema |
| 1 ↔ 1, encolheu | `shrank` | **UPDATE** |
| 0 antigas → 1 nova | `born` | CREATE com `theme_id` novo |
| 1 antiga → 0 novas | `died` | **SUPERSEDE** — nunca apagar |
| 1 antiga → 2+ novas | `split` | a antiga é SUPERSEDIDA pelas filhas; cada filha nasce com `theme_id` novo e `supersedes` apontando para a mãe |
| 2+ antigas → 1 nova | `merged` | a nova HERDA o `theme_id` da antiga de maior interseção; as outras são supersedidas por ela |

**τ = 1/3, e o valor vem da banda vazia medida** (§2.2): estritamente abaixo
de 0,5 para um tema que dobra continuar sendo `grew`, e estritamente acima de
0,17 para um tema que dissolve ser `died`. 1/3 é o ponto médio da banda.

### 4.3 O `rel_path` passa a ser derivado do `theme_id`

`communities/thm_<id>.md`. O rótulo legível vai para o frontmatter (`title`) e
para o corpo — onde mudar não cria arquivo novo. **É isso que fecha o §2.1.**

### 4.4 O LLM volta a só rotular

O `theme_id`, o `rel_path` e o evento são **derivados de estrutura**. O modelo
contribui `title` e `description`; sua indisponibilidade degrada o rótulo, não
a identidade. Regra executável: nenhum campo que decida `UPDATE`/`SUPERSEDE`
pode vir de `ModelRouter`.

### 4.5 As páginas `communities/` já escritas

Não são apagadas. Na primeira execução com casamento, cada página existente é
**adotada** pelo tema cujo conjunto de membros ela descreve (comparando a
lista `## Membros centrais` do corpo com a partição, pelo mesmo τ), o que lhe
dá um `theme_id` e um `rel_path` novo; a página no caminho antigo é
**supersedida** apontando para o novo caminho. Página que não casa com tema
nenhum é supersedida com `invalid_at` — nunca removida
(invalidar-nunca-apagar).

## 5. Invariantes

**Preservados**: canônico ≠ projeção (`themes`/`theme_epochs` são projeção
reconstruível; a autoridade continua sendo bundle + Git) · gate de escrita
inescapável (o `_reconcile` passa pelo `BundleWriter`) · invalidar-nunca-apagar
· INV-002 · INV-004 · repetibilidade do ADR-43 (o casamento é determinístico:
Jaccard e ordenação por `theme_id`).

**Novo**: **INV-005 — um tema, uma página canônica viva.** Nenhum par de
páginas `communities/` sem `superseded_by` descreve conjuntos de membros com
Jaccard ≥ τ. Verificável pelo doctor, e é a negação formal do §2.1.

## 6. CAP e concorrência

Nada muda: processo único, SQLite local, escrita serializada pelo lock do
`BundleWriter`. O casamento roda **dentro** do job `leiden`, no mesmo momento
em que a partição é produzida — não há janela entre "partição nova" e
"identidade atribuída".

## 7. Migração

`index.db` 8 → 9, **aditiva**:

```sql
CREATE TABLE themes(
  theme_id TEXT PRIMARY KEY, community INTEGER, rel_path TEXT NOT NULL,
  born_at REAL NOT NULL, died_at REAL, members TEXT NOT NULL);
CREATE TABLE theme_epochs(
  id INTEGER PRIMARY KEY, theme_id TEXT NOT NULL, event TEXT NOT NULL
    CHECK(event IN ('born','grew','shrank','merged','split','died')),
  at REAL NOT NULL, bundle_head TEXT, jaccard REAL, members TEXT,
  related TEXT);
```

Armadilha já paga uma vez (ADR-44): `CREATE TABLE IF NOT EXISTS` **não**
acrescenta coluna a tabela existente. Nenhuma coluna nova em tabela antiga
aqui — se vier, exige `ALTER` no `_migrate` com teste de upgrade.

## 8. Modos de falha

| falha | comportamento |
|---|---|
| primeira execução (sem época anterior) | tudo é `born`; não há casamento a fazer |
| partição vazia (bundle sem arestas) | nenhum evento; nenhuma escrita |
| LLM indisponível | rótulo cai no determinístico; `theme_id` e evento **não mudam** |
| backend do particionamento muda (`leiden` ↔ `components`) | partições incomparáveis por construção. O casamento **recusa** e registra `backend_changed` sem escrever — comparar mapas de backends diferentes produziria épocas falsas em massa |
| `merged` | **não observado na calibração** (§2.3). O ramo existe porque a forma 2→1 é bem definida e barata de detectar, mas **nenhuma interface deve pressupor que ele é comum** |

## 9. Observabilidade

`graph_snapshot` ganha `themes_matched` e `events`; `theme_epochs` é a trilha
auditável; o doctor passa a verificar INV-005. `corpusmith themes` lista tema,
`theme_id`, membros e a última época.

## 10. Rollout e rollback

**Rollout**: o casamento entra desligado por dado — sem época anterior, a
primeira execução só cria. **Rollback**: as duas tabelas são projeção
(`rebuild_index` as descarta); as páginas supersedidas continuam legíveis com
o corpo intacto, e o `curate undo` desfaz qualquer escrita pelo mesmo rito.

## 11. Risco de overengineering

O sinal mais forte contra este RFC é o §2.3: um vocabulário de seis eventos em
que **um não foi observado**. A mitigação é declarar isso aqui e no contrato
epistêmico, em vez de construir interface para um evento hipotético. Dois
eventos (`grew`, `born`) cobrem o caso comum medido; `died` e `split` foram
observados; `shrank` é simétrico a `grew`; `merged` fica declarado e não
recebe superfície.

## 12. Condições de reentrada

- se `merged` continuar não sendo observado em uso real por duas fases, o
  evento sai do vocabulário (migração não-aditiva ⇒ novo RFC);
- se τ = 1/3 produzir época falsa em bundle real, recalibrar **com o dado
  real**, não com síntese — e o carimbo do ADR-43 é o que torna isso possível;
- similaridade semântica no casamento só volta com evidência de que a
  estrutura é insuficiente, e viraria RFC próprio (modelo no caminho de
  escrita).

## 13. Evidências

Todos os números deste RFC foram medidos nesta árvore, com
`DetectCommunities` real:

- §2.1 — duplicação de página canônica reproduzida em `communities/`;
- §2.2 — sete perturbações, com os caminhos preservados; banda vazia entre
  0,17 e 0,50;
- §2.3 — fusão não observada com cliques densamente interligados;
- ADR-43 — partição repetível, o que torna a calibração comparação de sinal e
  não de ruído.
