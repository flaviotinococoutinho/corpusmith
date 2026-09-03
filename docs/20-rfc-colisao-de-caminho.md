# 20 · RFC-003 — Colisão de caminho: o gesto de captura para de destruir em silêncio

> **Altitude:** governança · **Status:** vivo

> `AGENTS.md` §8 exige RFC para **heurística no caminho de escrita**. Este RFC
> põe a escada de reconciliação — ressuscitada pelo RFC-002, com árbitro LLM
> opcional — dentro do `promote`, que é o caminho de escrita **humano** mais
> usado do produto. `docs/15` §1.1 já tinha classificado a F3 assim antes de
> qualquer linha existir.

| | |
|---|---|
| **Status** | Proposto |
| **Pacote** | F3-PR1 (P-7, `docs/14` §P-7) |
| **Sucede** | RFC-002 (escada de reconciliação, pré-requisito declarado) |
| **Origem** | `docs/14` C3 — "o caminho destrutivo dominante não é UPDATE, é ADD sobre um `rel_path` existente" |

---

## 1. Contexto

Três escritores produzem `rel_path` por slug: `PromoteToMemory` (humano),
`compile_source`/`consolidate_inbox` (máquina) e a ingestão. A proteção
anticolisão existe **só** para `raw/` (`ingest_source.py:64`, sufixo
incremental). No bundle canônico, `BundleWriter.write` faz
`target.write_text(...)` incondicionalmente.

## 2. Problema mensurado

Reproduzido nesta árvore, antes de qualquer correção:

```
1º promote: ['concepts/docker.md']  (40 linhas de anotação humana)
2º promote: ['concepts/docker.md']  (rascunho de 2 linhas, MESMO título)
anotações do 1º sobreviveram? False
log: * 00:54 [Creation] promovido de chat: Docker
```

O trabalho humano é destruído e o log **mente**: registra "Creation" para o
que foi uma sobrescrita. O único vestígio é o histórico Git — que nenhuma
superfície do produto mostra como "você acabou de perder 40 linhas".

Três agravantes:

1. `ReconcileCandidate` **exclui a página residente** dos degraus
   (`if page != self._candidate.rel_path`) — a colisão é o único caso que a
   escada estruturalmente não vê;
2. `promote` **nem chama** a escada: dois títulos diferentes que slugificam
   igual ("Redis Cache" / "redis-cache!") colidem sem nenhuma similaridade;
3. no fluxo de máquina, um UPDATE **reconstrói o frontmatter do zero**
   (`base._document`): tags, `valid_at` e campos curados da residente
   sobrevivem apenas como `policy.metadata_shrink` — um **warn**.

## 3. Opções consideradas

| # | Opção | Veredito |
|---|---|---|
| A | Sufixo incremental automático (como `raw/`) | Recusada como default: cria `docker-2.md` em silêncio — duas páginas canônicas vivas para o mesmo conceito é exatamente o defeito B2 por outra porta. Fica como **saída humana explícita** |
| B | `promote` sempre funde na residente | Recusada: fundir sem perguntar também destrói (o corpo residente é substituído ou poluído sem consentimento). Viola o gate humano |
| C | Recusar sempre (erro seco) | Honesta mas inutilizável: o usuário digitou o conteúdo e o produto o joga fora sem oferecer caminho |
| D | **COLLISION como resposta de primeira classe + intenção declarada no Harness** | **Escolhida** — a colisão vira uma DECISÃO com três saídas humanas, e o gate impede a mentira do log |

## 4. Decisão

### 4.1 `policy.path_collision` — a intenção declarada chega ao gate

`BundleWriter.write` já recebe `log_kind`; o Harness passa a recebê-lo como
`intent`. A regra: **`intent="Creation"` sobre `rel_path` existente é
`error`**. Nenhum campo novo no frontmatter (frontmatter é conteúdo canônico,
não transporte), nenhuma mudança de fio: o dado já viajava até uma linha antes
do gate e era usado só para escrever o log.

É a mesma forma do `policy.citation_invalid`: o gate não adivinha intenção,
ele confere a intenção **declarada** contra o estado do mundo.

### 4.2 `promote` consulta a escada e devolve `COLLISION`

Antes de escrever, o `promote` roda `analyze()` sobre o conteúdo — detecção
pura, **nenhuma reescrita** de prosa (o que a v0.8 §1.2 proíbe é o sanduíche
de reescrita, não a leitura) — e passa o candidato pela MESMA escada do
RFC-002. Se o caminho do slug já existe **ou** a escada aponta UPDATE/RECYCLE
para outra página, o promote **não escreve**: devolve

```json
{"op": "COLLISION", "target": "concepts/docker.md", "score": 0.97,
 "reason": "...", "options": ["update", "new_slug", "cancel"]}
```

As três saídas humanas legítimas (`docs/14` §P-7):

- **`resolution="update"`** — escreve SOBRE o alvo com frontmatter **fundido**
  (`kernel/curation.py:merge_meta`, a mesma função do MergePages) e log
  `Update`. Substituir o corpo continua sendo substituir — mas agora é um
  gesto **explícito**, com a residente nomeada e o diff a um clique;
- **`resolution="new_slug"`** — sufixo determinístico (`docker-2.md`), log
  `Creation` legítimo. Duas páginas vivas viram um item de consolidação
  futura, que é reversível; fusão errada não é;
- **cancelar** — do lado do cliente; nada a persistir.

Sem `resolution`, colisão NUNCA escreve. O default é a recusa informativa.

### 4.3 O árbitro LLM continua atrás da flag — e fora do gesto humano

A escada que o promote consulta é a do RFC-002, incluindo a zona cinzenta. No
caminho humano o árbitro **não decide nada**: um `UPDATE` sugerido pela escada
vira `COLLISION` apresentado ao humano, nunca uma escrita. A heurística
**informa** o gesto; quem escreve continua sendo a pessoa. É o que torna esta
entrada da heurística no caminho humano compatível com "gate humano para
efeito cognitivo".

### 4.4 O fluxo de MÁQUINA funde frontmatter em UPDATE

`base.execute` em op UPDATE/RECYCLE passa a fundir o frontmatter da residente
no documento (`merge_meta`: o novo manda, o que falta vem da residente, listas
se unem, `confidence` cai para a mais fraca). Tags e campos curados por humano
param de evaporar a cada recompilação — e `policy.metadata_shrink` deixa de
ser o único guarda de um caminho que o produto percorre sozinho.

## 5. Invariantes

Gate humano (colisão nunca resolve sozinha — nem por sufixo, nem por fusão,
nem por LLM) · precisão > recall (na dúvida, recusar e perguntar) · log que
não mente (`Creation` só quando cria) · invalidar-nunca-apagar (nada aqui
deleta; `update` explícito preserva histórico Git e funde frontmatter) ·
LLM cercado (informa, não escreve) · 1 método público por use case.

## 6. CAP e concorrência

Nenhum banco novo. A checagem de existência e a escrita acontecem sob o mesmo
lock do bundle que o writer já usa. A pré-condição de frescor do RFC-002 já
roda antes da escada.

## 7. Migração

Nenhuma. Bundles existentes continuam válidos; a regra nova só olha escrita
futura.

## 8. Modos de falha

- **falso COLLISION** (escada aponta UPDATE para página não relacionada):
  custo = um diálogo a mais; o humano escolhe `new_slug`. Precisão > recall;
- **colisão não detectada** (índice irreparavelmente atrasado): o
  `path_collision` do §4.1 ainda segura o caso `rel_path` idêntico — a regra
  do gate lê o FILESYSTEM, não a projeção;
- **dois promotes concorrentes**: o segundo encontra a página do primeiro no
  gate (lock do bundle) e recebe COLLISION;
- **fluxo de máquina com slug colidindo**: o gate rejeita `Creation` sobre
  existente; `compile` já loga `Update` para não-ADD, e ADD verdadeiro sobre
  residente vira erro **audível** em vez de sobrescrita muda.

## 9. Observabilidade

Toda colisão detectada no promote é respondida com `op="COLLISION"` (contável
pelo cliente) e as resoluções ficam no log do bundle com o kind verdadeiro
(`Update` ou `Creation`). `reconcile_log` continua registrando as decisões da
escada, agora também as vindas do promote.

## 10. Rollout e rollback

Sem flag nova. Rollback = reverter o commit. A API é aditiva: `promote` ganha
`resolution` opcional; a resposta ganha o valor novo `op="COLLISION"` — o
cliente antigo que ignorar o campo continua funcionando (nada é escrito, e a
UI mostra "nada criado" em vez de mentir sucesso).

## 11. Risco de overengineering

A alternativa mínima (só o `policy.path_collision`) pararia a destruição mas
transformaria todo título repetido num erro seco sem saída — opção C. O
COLLISION com três saídas é o menor acréscimo que devolve ao humano a decisão
que sempre foi dele.

## 12. Condições de reentrada

- **auto-fusão na zona alta** (score ≥ HI fundir sem perguntar): só com
  golden set de reconciliação e avaliação registrada (`RFC-002` §12);
- **undo de criação** (ADR-41.1): `new_slug` cria via `promote`, que não é
  ato de curadoria — o dia em que um CurationAct criar página continua sendo
  o dia dessa decisão, e continua registrado como dívida;
- **detecção de colisão na consolidação em lote** (`consolidate_inbox`):
  herda §4.4 nesta fase; tratamento interativo fica para F6.

## 13. Evidências

- a sobrescrita muda reproduzida por execução (§2), com o log mentindo;
- `ReconcileCandidate` excluindo a residente: `reconcile_candidate.py`
  (degraus 1 e 2, `page != self._candidate.rel_path`);
- anticolisão existente só em `raw/`: `ingest_source.py:64`;
- `merge_meta` puro e já testado pelo MergePages (`kernel/curation.py:82`);
- mutação por correção na suíte do PR (cada correção desfeita derruba
  exatamente o teste que a cobre).
