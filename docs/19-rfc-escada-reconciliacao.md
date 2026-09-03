# 19 · RFC-002 — Ressuscitar o degrau de similaridade da reconciliação

> **Altitude:** governança · **Status:** vivo

> `AGENTS.md` §8 exige RFC — não só ADR — para **heurística no caminho de
> escrita**. Corrigir a SQL não é um conserto neutro: ela é o degrau que, ao
> voltar a funcionar, liga os cortes HI/LO, o NCD **e o árbitro LLM local**
> sobre a decisão ADD/UPDATE/SUPERSEDE da página canônica. Fazer o gesto de
> uma linha sem este documento seria introduzir decisão de modelo generativo
> sobre o canônico por efeito colateral de um conserto.

| | |
|---|---|
| **Status** | Proposto |
| **Pacote** | F3-PR0 (`docs/15` §3.1) — pré-requisito da F3 |
| **Sucede** | RFC-001 (identidade de tema), ADR-46 (checkpoints) |
| **Origem** | `docs/17` B1 e B2 — os dois achados de maior consequência da auditoria |

---

## 1. Contexto

`ReconcileCandidate` é a escada que decide, para cada documento que entra, se
ele vira página nova (`ADD`), atualiza uma existente (`UPDATE`), aposenta uma
antiga (`SUPERSEDE`), não muda nada (`NOOP`) ou reidrata memória fria
(`RECYCLE`). É a decisão mais consequente do produto: é a única que pode criar
**duas páginas canônicas vivas para o mesmo objeto do mundo**, e desfazer isso
depois exige um merge com supersede.

A escada tem três degraus, do mais determinístico ao menos:

1. **identificador forte** compartilhado (DOI, ISBN, ISSN, arXiv, git SHA);
2. **similaridade composta** — `0.4·rank(FTS) + 0.3·Jaccard(entidades) +
   0.3·(1 − NCD)`, com cortes `LO = 0.55` e `HI = 0.82`;
3. **árbitro LLM local**, atrás da flag `reconcile.llm_arbiter`, só na zona
   cinzenta `LO ≤ score < HI`.

## 2. Problema mensurado

### 2.1 O degrau 2 nunca executou (B1)

```
sqlite 3.45.1
  MIN(bm25(...)) + GROUP BY   -> OperationalError: unable to use function
                                 bm25 in the requested context
  bm25(...) sem agregado      -> [('b.md', -1.157e-06), ('a.md', -1e-06), …]
  subquery: bm25 dentro       -> OperationalError: (idem)
```

Não é caso de borda: **toda** execução desde a v0.9. Um `except Exception`
cego engolia, `matches` saía `[]`, e o resultado — *"nenhum candidato acima do
corte"* — era **byte a byte igual** ao de uma busca bem-sucedida e vazia. Com
isso, os cortes HI/LO, o termo NCD e o árbitro LLM eram código morto sem que
nada acusasse.

A terceira linha da medição descarta a correção óbvia: a restrição do SQLite é
da consulta que carrega o `MATCH`, não do nível de aninhamento. Nem `MIN` no
mesmo `SELECT` nem `MIN` numa subquery externa funcionam.

### 2.2 A projeção decide como se fosse autoridade (B2)

`index.db` é projeção reconstruível; o bundle é a autoridade. A escada lê
`page_entities` no índice para achar o identificador forte. Índice atrasado ⇒
a página existente é **invisível** ⇒ `ADD` ⇒ duas páginas canônicas vivas com
o mesmo DOI. Reproduzido na auditoria e reproduzido de novo aqui, como teste.

E o defeito é auto-agravante: `compile_source` só reindexa em `_after_write`,
depois de decidir.

### 2.3 A reindexação vaza conexão no caminho de erro

O único `idx.close()` estava no caminho de sucesso. Medido: com transação
aberta na conexão vazada, a escrita seguinte no `index.db` responde
`OperationalError: database is locked` após ~30 s de timeout — com a causa a
uma indexação de distância do sintoma. Registrado em `docs/17` como CONFIRMADO
e não pago na época.

## 3. Opções consideradas

| # | Opção | Por que não / por que sim |
|---|---|---|
| A | Corrigir a SQL e nada mais | Ativa o árbitro LLM sem documento. É o gesto que este RFC existe para não fazer sozinho |
| B | Manter o degrau morto e apagar o código | Honesto, mas joga fora NCD, cortes e árbitro — e a escada volta a ter um degrau só, o que reintroduz o B2 com mais força |
| C | Corrigir a SQL **e** deixar a flag do árbitro como está (desligada) | **Escolhida.** O degrau volta; a decisão de ligar o LLM continua sendo um gesto explícito do usuário |
| D | Corrigir + recalibrar HI/LO | Recusada: calibrar sem golden set é adivinhar, e o registro epistêmico proíbe declarar `calibrated_empirical` sem evidência |
| E | Negar a escrita quando o índice está atrasado | Recusada: o documento precisa entrar. Recusar transforma um risco de duplicata num travamento de ingestão |
| F | Reindexar antes de decidir, incremental | **Escolhida** para 2.2 — ver §4.2 |

## 4. Decisão

### 4.1 O ranking sai por chunk; a redução por página é feita em Python

```sql
SELECT c.page, bm25(chunks_fts) r FROM chunks_fts
JOIN chunks c ON c.id = chunks_fts.rowid
WHERE chunks_fts MATCH ? ORDER BY r LIMIT 64
```

…e o melhor rank de cada página é mantido, com corte final de 8 **páginas**.
A deduplicação não é acidental: o escore usa `1/(1+position)`, e sem ela uma
página longa ocuparia várias posições do top-N, empurraria concorrentes para
fora **e** inflaria o próprio termo posicional. O `MIN(...) + GROUP BY`
original queria exatamente isso — e era o que o tornava inexecutável.

### 4.2 A escada torna a projeção fresca antes de usá-la como autoridade

`_ensure_fresh_projection()` consulta o checkpoint `index` (ADR-46) e, se ele
não estiver `fresh`, chama `rebuild_index` **uma vez**. A reindexação é
incremental por delta de git: índice já fresco custa uma leitura de
checkpoint; índice atrasado custa exatamente as páginas que mudaram.

Se ainda assim não ficar fresco, a decisão **diz isso**: `index_stale` viaja
no dicionário de decisão e na trilha `reconcile_log`, e um `ADD` que se apoia
em ausência de evidência sai com `confidence = "ambiguous"` em vez de
`"extracted"`. *Ausência de evidência num índice atrasado não é evidência de
ausência* — e o produto passa a saber a diferença.

`absent` conta como atraso aqui e **não** conta como defeito no doctor. São
perguntas diferentes: para o doctor, instalação nova não tem derivação velha,
tem derivação nenhuma; para esta escada, índice nunca computado esconde tanto
quanto índice velho.

### 4.3 Os cortes NÃO mudam

Medido, com corpo **idêntico** ao da página existente:

| fixture | escore | decisão |
|---|---:|---|
| sem `authority_record` (nenhuma entidade curada) | **0.686** | `ADD`, `ambiguous`, "zona cinzenta" |
| com `authority_record` (entidade compartilhada) | **0.976** | `UPDATE`, `inferred` |

O teto sem acordo de entidades é `0.4·1 + 0.3·0 + 0.3·(1−NCD) ≈ 0.7`, abaixo
de `HI = 0.82`. Isso não é fraqueza do degrau: é a exigência de que os **três
sinais concordem** antes de sobrescrever página canônica. Está fixado por
teste justamente para que ninguém "conserte" HI para 0.65 achando o contrário.

### 4.4 O árbitro LLM continua desligado por default

`reconcile.llm_arbiter` permanece como está. O que muda é que a zona cinzenta
passa a ser **alcançável** — antes ela era inatingível porque nenhum escore
existia. Ligar a flag passa a ter efeito; ligá-la continua sendo decisão de
quem opera, e o `privacy="local_only"` da chamada não muda.

### 4.5 `rebuild_index` fecha a conexão no `finally`

O corpo vira `_rebuild(s, idx, *, full)` e `rebuild_index` fica com a abertura
e o `finally`. Nenhuma reindentação do corpo, nenhuma mudança de comportamento
no caminho feliz. Deixa de ser higiene e vira **pré-requisito** de §4.2: a
partir daqui `rebuild_index` roda dentro do caminho de escrita, onde uma
conexão vazada travaria o próprio ato que a provocou.

## 5. Invariantes

Local-first (a escada não ganha rede) · **canônico ≠ projeção** — este RFC
existe em boa parte para restaurar essa distinção, que estava violada de fato
· LLM cercado (o árbitro segue atrás de flag, só na faixa cinzenta, e nunca
nomeia `rel_path`: ele escolhe entre operações sobre um alvo que a parte
determinística já apontou) · precisão > recall (empate na zona cinzenta sem
árbitro escreve página nova marcada, não sobrescreve) · invalidar-nunca-apagar
(nada aqui apaga) · toda decisão vai para `reconcile_log`.

## 6. CAP e concorrência

Nenhum banco novo, nenhuma tabela nova. A pré-condição roda **antes** de abrir
a conexão de leitura da escada, então não há duas conexões de escrita vivas ao
mesmo tempo — que é o cenário que o vazamento de §2.3 tornava fatal.

## 7. Migração

Nenhuma. Sem schema novo, sem dado a converter. Instalações existentes passam
a ter o degrau 2 funcionando na próxima ingestão.

## 8. Modos de falha

- **falso `UPDATE`**: dois documentos distintos com entidades e compressão
  parecidas acima de 0.82 fundem-se indevidamente. Mitigado pela exigência dos
  três sinais; reversível por `MergePages`/supersede; não silencioso (a decisão
  fica em `reconcile_log` com escore);
- **custo da pré-condição**: um índice cronicamente atrasado faz cada
  documento pagar uma reindexação incremental. Coberto por teste
  (`test_indice_fresco_nao_paga_reindexacao`);
- **índice irreparável**: se `rebuild_index` falhar, a escada não tenta de
  novo — decide com o que há e marca `index_stale` com o motivo;
- **árbitro ligado com modelo ruim**: decisão de modelo generativo sobre o
  canônico na faixa cinzenta. É por isso que a flag continua desligada e é por
  isso que este documento existe.

## 9. Observabilidade

`similarity_error` (a consulta estourou) e `index_stale` (a decisão saiu de
projeção atrasada) viajam na decisão e são persistidos em `reconcile_log`.
*"Quantas decisões saíram de um índice atrasado?"* passa a ser uma consulta e
não uma suposição — que é a diferença entre este defeito e o anterior.

## 10. Rollout e rollback

Sem flag nova. Rollback = reverter o commit; nenhum dado escrito neste PR
precisa ser desfeito.

## 11. Risco de overengineering

Real e considerado. A alternativa mínima (corrigir a SQL e ir embora) foi
recusada por §3-A. A pré-condição de frescor é o acréscimo que mais se parece
com escopo extra — mas sem ela o degrau 1 continua decidindo sobre uma
projeção que ninguém garante, e resolver B1 deixando B2 de pé entregaria uma
escada que funciona sobre dados que podem não existir.

## 12. Condições de reentrada

- **calibrar HI/LO**: quando existir golden set de reconciliação (trilha
  F-EPIST). Só então o contrato pode declarar `calibrated_empirical`;
- **ligar `reconcile.llm_arbiter` por default**: exige avaliação registrada em
  `epistemics.toml` com escopo e out-of-scope — hoje não há;
- **consolidar `index_meta.bundle_head` no checkpoint**: dívida do ADR-46,
  ainda aberta.

## 13. Evidências

Tudo abaixo foi executado nesta árvore, não inferido:

- as três variantes de SQL contra FTS5 (§2.1), SQLite 3.45.1;
- `OperationalError: database is locked` após o timeout, com transação aberta
  na conexão vazada (§2.3) — e o mesmo teste passa em ~0.3 s com o `finally`;
- os dois escores de §4.3, em bundles construídos do zero;
- **mutação, uma a uma**: repor `MIN(bm25)` derruba 4 testes; remover a
  pré-condição de frescor derruba 3; remover o `try/finally` derruba 1 (com 30 s
  de timeout no caminho). A primeira versão do teste do `finally` **passava com
  e sem** a correção — conexão vazada sem transação aberta não tranca nada; foi
  preciso escrever antes de estourar para que o teste pudesse reprovar.
