# 18 · Backlog consolidado — o que ainda falta

> Estado em 2026-07-27, HEAD `83c5983`; §9–§10 atualizados em 2026-08-22
> (F4-PR3 entregue; fila reordenada pela re-mira do
> [RFC-006](29-rfc-006-re-mira.md)). Consolida `docs/14` (14 problemas de
> viabilidade), `docs/15` (plano, D-A…D-K, G-1…G-10), `docs/17` (auditoria
> adversarial) e as medições desta sessão.

**Cada item declara o nível de evidência**, e essa é a informação mais útil
deste documento:

| nível | significa |
|---|---|
| 🔴 **medido** | eu rodei nesta árvore e observei |
| 🟠 **confirmado** | um cético independente rodou código e observou (`docs/17`) |
| 🟡 **declarado** | um ADR admite a dívida por escrito |
| 🔵 **planejado** | `docs/14`/`docs/15` descreve, sem verificação recente |
| ⚪ **alegado** | achado de auditoria de gravidade média/baixa, **não verificado** |

Nada aqui é opinião sobre estilo. Onde não há evidência, está dito.

---

## 1. Bugs

| # | O quê | Evidência | Consequência |
|---|---|---|---|
| **B1** ✅ **RESOLVIDO** (F3-PR0, RFC-002 + ADR-48) | **A escada de similaridade é código morto desde a v0.9.** `MIN(bm25(chunks_fts))` levanta `OperationalError: unable to use function bm25 in the requested context` em SQLite 3.45.1 — sempre. O `except Exception` cego devolvia lista vazia | 🔴 medido + 🟠 confirmado | Similaridade composta, limiares HI/LO, NCD e árbitro LLM **nunca executam**. Toda reconciliação decide por identificador forte ou cai em ADD. O silêncio já foi corrigido (`similarity_error`); a SQL **não**, porque corrigi-la ativa o árbitro LLM no caminho de escrita e exige **RFC** |
| **B2** ✅ **RESOLVIDO** (F3-PR0: pré-condição de frescor + `index_stale` declarado) | **`index.db` — projeção declarada sem autoridade — decide ADD/UPDATE/SUPERSEDE.** Mesmo candidato, só o estado da projeção muda → `UPDATE` ou `ADD`, com `doctor.ok=True` nos dois | 🟠 confirmado | O cético produziu **duas páginas canônicas vivas para o mesmo DOI** pelo mesmo use case. Viola `AGENTS.md` §6 e `architecture.toml` (`authority = "nenhuma (projeção)"`) |
| **B3** ✅ **RESOLVIDO** (F3-PR0) | **`rebuild_index` sem `try/finally`**: exceção no meio vaza a conexão com transação aberta e trava `index.db` por 30 s no processo | 🟠 confirmado | Recuperável, mas o produto parece travado |
| **B4** ✅ **RESOLVIDO** | **`out_of_scope` recebe `validity_scope` sem negação** (`evaluate_memory.py:184`), e o painel renderiza como "Fora de escopo" | 🟠 confirmado → 🔴 medido | Inversão exata do significado: o painel diz que o escopo **avaliado** está fora do escopo. O campo passou a carregar os `known_failure_modes` do contrato ("onde NÃO foi medido"), com teste prendendo a não-inversão |
| **B5** ✅ **RESOLVIDO** (PR-0.1, ADR-47) | `build.spec:12` faz `EXE(...)` sem `exclude_binaries=True` — obrigatório em onedir. `just sidecar` **não constrói mais** | 🟠 confirmado | Nem a receita manual de empacotamento funciona. Com o token, constrói (3,4 MB) |
| **B6** ✅ **RESOLVIDO** (PR-0.1, ADR-47) | `collect_dynamic_libs("sqlite_vec")` devolve `[]` porque `sqlite-vec` só existe no extra `[ml]` e `just bootstrap` instala `.[dev]` | 🟠 confirmado | O binário sairia **sem a extensão nativa vec0, em silêncio** — o `build.spec` agora falha alto quando o extra `[ml]` não está presente |

---

## 2. Fluxos incompletos — backend pronto, sem superfície

Sete achados com a **mesma forma**: use case completo, endpoint completo, às
vezes até método de cliente declarado — e nenhuma tela.

| # | Capacidade | Evidência |
|---|---|---|
| **F1** | **`undo` inalcançável pelo app.** `/curation/acts` e `/curation/history` não têm consumidor: sem listar os atos, não há `act_id` para desfazer | 🔴 medido (teste `test_o_undo_segue_inalcancavel_pelo_app`) |
| **F2** | **Doctor sem superfície.** Endpoint, use case e método de cliente existem; nenhum painel chama. A StatusBar acusa problema em vermelho **sem ato** | 🟠 confirmado |
| **F3** | **Revisão semanal**: job agendado + preview + commit, nenhuma tela. Toda segunda nasce uma página que o usuário nunca é convidado a ler | 🟠 confirmado |
| **F4** | **Fila de jobs**: `cancel` e `retry` existem no backend e não na UI. `dead_lettered` não tem volta; job travado não tem parada | 🟠 confirmado |
| **F5** | **44 de 45 tipos de evento nunca chegam à UI.** O `EventSource` registra 5. O `Stepper` do Inbox e a barra de progresso de Processos são **código já escrito** esperando `page.stage` e `stage.progress` | 🔴 medido |
| **F6** | **12 de 92 rotas (13 %) sem nenhum consumidor** — incluindo analogias cognitivas, episódios, referência e export | 🔴 medido |
| **F7** | `curation.applied` é emitido por **todo** ato e não chega à UI: fora do dialog, nenhuma superfície sabe que o canônico mudou | 🔴 medido |

> Os dois números viraram **teto de teste** (`test_pontas_soltas.py`): piorar
> quebra, e melhorar exige baixar o teto no mesmo commit.

---

## 3. Funcionalidades ainda não construídas (`docs/14`, fases 3 a 7)

Das 14 lacunas de viabilidade, **P-1** (ato de curadoria) e **P-2** (camada de
padrões) foram entregues nas Fases 1 e 2. Restam:

| # | Problema | pt | Depende de |
|---|---|:--:|---|
| **P-3** | **Nada fecha e nada aposenta** — perguntas eternas, padrões reaparecem sem consentimento, a fila propõe trabalho sobre página morta | 4 | F1 + F2 (prontas) ⇒ **desbloqueada** |
| **P-7** | **Colisão de caminho** — promoção humana e compilação de máquina se sobrescrevem em silêncio | 3 | idem. **Exige RFC** (heurística no caminho de escrita) |
| **P-4** ✅ **RESOLVIDO** (F4-PR1, ADR-52) | **Suficiência ≠ dispersão** — a "confiança" mede dispersão da fusão e satura em quase toda resposta | 4 | `support` 2D (4 parcelas com saturação declarada) AO LADO de `uncertainty`, contrato `evidence_sufficiency` pago (registro 1.9.0), selo "sustentação fraca" no painel — base rasa deixa de virar certeza máxima muda |
| **P-5** ✅ **rename entregue** (F4-PR2, ADR-52) · detector na F4-PR3 | **Conflito × impopularidade** — o produto chama "em disputa" o que só deu beco | 4 | `contested → low_yield` em valor, chave e rótulo (overlay + fila + insights + review + domínio cognitivo + 4 painéis), migração index.db 9→10 com CHECK recriado, `allow_contested` legado traduzido (snapshots persistidos), registro 1.9.1. O conflito REAL (`policy.factual_conflict`) chega na F4-PR3 |
| **P-9** ✅ **RESOLVIDO no fluxo novo** (F4-PR1, ADR-52) | **`valid_at` = tempo de escrita** — a bi-temporalidade degenera | 3 | o default de escrita morreu: página nova só carrega `valid_at` quando o conhecimento o fornece (ausente = válida em qualquer `as_of`, semântica pinada). **Legado** (~todas as páginas de máquina existentes) fica para o ato em lote com preview da F4-PR3 |
| **P-6** | **A aresta tem sintaxe, não semântica** — nenhuma relação tipada; co-menção não materializada | 4 | F1 (formato de link resolvido no ADR-41.2) |
| **P-10** | **Entidade ↔ página** — vínculo existe no canônico e é jogado fora na projeção | 3 | F5 |
| **P-8** ✅ **rastro e fechamento entregues** (F6, RFC-006 §6) | **A memória não lembra o que falhou** — abstenção não deixa rastro | 3 | `ask_misses` + fechamento por re-ask + superfície nos Indicadores + contrato `abstention_trace`. O que RESTA do P-8 original: o minerador de co-recuperação (lift/PMI sobre `ask_provenance` → propor `LinkPages`) — associação entre páginas que respondem juntas é outra pergunta e não entrou |
| **P-11** | **Custo das superfícies** — reprocessam o bundle a cada abertura | 2 | **parcialmente pago** pelo ADR-44 (grafo 2571 → 139 ms); resta o resto |
| **P-12** | **O ritual semanal inalcançável** | 2 | = F3 acima |
| **P-14** ✅ **RESOLVIDO** | **Durabilidade invisível** — backup excelente, nunca automático | 2 | Job `backup` semanal no Scheduler (dedupe por semana ISO, prioridade mínima): cria, **verifica cada sha256** e só então poda além de `backup.keep` (default 4); a quiescência exclui o próprio job; `backup.verify_failed` declarado e repassado à UI |

---

## 4. Pacotes que a auditoria impôs (`docs/15` §3.1)

| # | Pacote | pt | Por quê |
|---|---|:--:|---|
| **PR-0.1** ✅ **ENTREGUE** (ADR-47) | **Release executável** — `exclude_binaries=True`, `sqlite-vec` no build, job de release com trigger de tag, token de release em `[gate].ci_enforced`, `expected_mechanisms` no registro | 4 | **G-8 e G-10 reabertas.** Sem o token no gate, `test_ci_executa_todo_o_gate_declarado` **estruturalmente nunca** poderá acusar |
| **F3-PR0** ✅ **ENTREGUE** | **Fechar o laço da decisão canônica** — B1 **com RFC**, pré-condição de frescor ou INV de cobertura bundle→índice, `try/finally` no rebuild, teste do degrau de similaridade | 6 | **Pré-requisito da F3**: o P-7 faz `promote` consultar uma escada com dois degraus mortos |
| **F-UI** ✅ **ENTREGUE** (ADR-49) | **As superfícies órfãs num PR só** — doctor, histórico com undo, cancel/retry, repasse genérico de SSE | 8 | Cinco achados, um arquivo de cliente, cinco painéis. Muito mais barato junto. **Pré-requisito: smoke de UI, hoje inexistente** |
| **F-EPIST** ✅ **CONCLUÍDA** (exceto C6) | Trilha epistêmica | 5 | ✅ B4 · ✅ `retrieval_rrf_hedge` heuristic (C13) · ✅ `rglob`/import absoluto (T7) · ✅ contratos de `memory_freeze` e `consolidate_inbox` (registro 1.8.0, 18 mecanismos; P(recall) declarado PROXY de heat; efeito colateral do `auto_recycle` dito em voz alta; `cold_memory.py` saiu dos refs de `abstention`) · **resta**: campo de efeito colateral no `EpistemicContract` (C6 — exige mudança de modelo) |

---

## 5. Débito técnico

### 5.1 Declarado em ADR (🟡 — está por escrito, ninguém agendou)

| # | Dívida | Onde |
|---|---|---|
| **T1** | **Carimbos de frescor duplicados**: `index_meta.bundle_head` continua ao lado do `checkpoints`. Consolidar exige mexer no INV-002, o invariante mais exercitado da suíte | ADR-46 |
| **T2** | `superseded_meta` carimba `invalid_at` com o tempo de **escrita**, não de mundo | ADR-41 (= P-9) |
| **T3** | **Desfazer uma criação não é expressável** — `BundleWriter.remove` não roda o Harness. O ato recusa com 409 nomeado | ADR-41.1 |
| **T4** | O commit acontece **antes** do registro na trilha: janela em que o canônico mudou e a trilha não sabe | ADR-41.1 |
| **T5** | `merged` está no vocabulário fechado e **não foi observado** na calibração | RFC-001 §2.3 |
| **T6** ✅ **RESOLVIDO** | `_CommunitySummaryPage` reescreve o sumário a cada execução mesmo com conteúdo idêntico → o HEAD move a cada job | ADR-45. `source_sha256` (fingerprint dos membros) decide: conjunto idêntico ⇒ nem rotula nem escreve — HEAD imóvel medido por teste, e o job semanal para de re-sortear rótulo de tema que ninguém pediu para mudar |

### 5.2 Buracos no gate (🟠 confirmado)

| # | O quê | Consequência |
|---|---|---|
| **T7** ✅ **RESOLVIDO** | `INV-ARCH-003/004` só inspecionam imports **relativos**, e o scan de `api/` usa `glob` em vez de `rglob` | O cético plantou violações que passaram verdes. Fechado com `_internal_imports` (relativo E absoluto) + `rglob` — reprovação verificada com violação plantada, e o teste antigo confirmado cego à mesma planta |
| **T8** ✅ **RESOLVIDO** (PR-0.1) | `epistemics lint` fica verde com **contrato obrigatório apagado** (G-10) | Esquecer um contrato na F3/F4/F5 é silencioso |
| **T9** ✅ **RESOLVIDO** (na consequência) | O `conftest` derruba o Ollama e com isso cega 100 % da suíte para a única FK do `index.db` | A FK ganhou testes que a exercitam SEM Ollama (inserção direta em `embeddings` + rebuild/repair — regressão do incidente). O redirecionamento hermético do conftest permanece, por design: o que mudou é que a FK deixou de depender dele |
| **T10** ✅ **RESOLVIDO** (por partes) | Nenhum teste cobre `/events`, `/system/doctor` por HTTP, `/jobs/{id}/cancel` nem qualquer superfície de UI | Doctor HTTP: F0 (`test_f0_doctor_api`) · UI: F-UI/X4 (vitest no gate) · vocabulário `/events/types` + laço SSE: F-UI (`test_eventos`) · `cancel`/`retry` por HTTP com 409 nomeado: coberto agora (a superfície já se comportava certo; o gate é que não a via) |
| **T11** | `bench compare` está fora do gate por PR (variação entre máquinas), e o baseline segue em `1.7.0` contra produto `1.9.x` | G-4 |

### 5.3 Dependências ocultas ainda abertas (`docs/15` §5)

- **D-H** ✅ **RESOLVIDO no processo** — o lock protegia o bundle, não o rito:
  medido por teste de corrida (o plan de B invadia a janela do apply de A e B
  concluía antes). O esqueleto do ato agora segura um mutex do plan ao
  rebuild no processo do daemon, onde todos os atos HTTP rodam. **Resíduo
  declarado**: CLI × daemon são processos distintos — o flock segue
  garantindo a escrita, mas um plano pode envelhecer entre processos;
- **co-menção contada duas vezes** — o laço em memória do F2-PR1 colidirá com a
  materialização que a F5 (P-6) promete: o mesmo par somaria 0,5 (lido) + 0,25
  (recomputado). 🟠 confirmado, e **muda o escopo da F5**;
- **`retrieval/patterns.py`** — mitigação de colisão prescrita "já no PR1" pelo
  `docs/15` §6 e **nunca criada**. 🟠 confirmado.

---

## 6. Experiência de uso

| # | Problema | Evidência |
|---|---|---|
| **X1** ✅ **RESOLVIDO** | **Numa máquina sem o extra `[ml]` compilado, "comunidade" é componente conexo** — o `backend` do carimbo hoje declara isso, mas nenhuma superfície mostra | 🔴 medido → o carimbo viaja em `graph_data.freshness` e o fallback é dito em voz alta no Grafo e nos Indicadores ("mapa por componentes (sem [ml])"), com vitest prendendo o caso enganoso |
| **X2** ✅ **RESOLVIDO** | O badge de frescor do grafo existe (F2-PR3+4); os demais artefatos derivados **não têm badge** | 🔴 medido → `insights` e `gaps` repassam `freshness` (partição, centralidade, `computed_at`, `bundle_head`) em vez de descartar, e o painel Indicadores data o mapa — "nunca computado" não passa por atual |
| **X3** ✅ **RESOLVIDO** (F3-PR2, ADR-51) | A fila propõe ato de escrita sobre página que pode estar aposentada — `gap_items` não filtra vitalidade | ⚪ alegado → 🔴 medido e fechado: `gap_items` pula `aposentada(meta)` e pergunta `answered_by`; todas as fontes da fila compartilham `paginas_vivas`. O defeito foi reproduzido e preso por `test_f3_vitalidade.py` (`test_a_fila_para_de_propor_pagina_aposentada_e_inexistente`, pergunta fechada sai da fila, ponte com ponta aposentada) |
| **X4** ✅ **RESOLVIDO** (F-UI, ADR-49) | Não existe runner de teste de UI no desktop — só `tsc --noEmit` | 🔴 medido; `vitest` + `jsdom` entraram com config separada, e `npm test` está em `[gate]`. Medido de novo na entrada: com o `onClick` do reparo desligado, `tsc --noEmit` sai **0** e o smoke reprova |

---

## 7. Documentação

| # | O quê | Evidência |
|---|---|---|
| **DOC1** ✅ **RESOLVIDO** | `docs/15` §8 (estado da execução) desatualizado em relação às Fases 1 e 2 | ⚪ alegado → 🔴 medido: dizia "Próximo passo: F1-PR2" com F1–F3 inteiras entregues. O §8 passou a fechar com o estado real e a apontar para este documento como fonte viva |
| **DOC2** ✅ **RESOLVIDO** | `docs/11-epistemic-contracts.md` desatualizado em relação aos 15 mecanismos atuais | ⚪ alegado → 🔴 medido: dizia 7 contratos (são 16) e que o golden não é distribuído (o QA-1 entregou o seed). Corrigido apontando `epistemics.toml` como fonte viva |
| **DOC3** ✅ **RESOLVIDO** | O template de RFC do `docs/10` §19 foi **instanciado** (RFC-001), mas o `docs/10` ainda o marca "🎯 a instanciar" | 🔴 medido — corrigido: ✅ com links para RFC-001/002/003 |
| **DOC4** | `docs/17` continha uma linha desatualizada que fez um cético gastar um ciclo inteiro refutando alegação já corrigida — **já corrigida**, mas mostra a classe | 🟠 confirmado |
| **DOC5** ✅ **RESOLVIDO** (PR-0) | `AGENTS.md` cita contagem de teste desatualizada (a suíte cresce a cada PR e o número no doc não) | 🔵 → 🔴 verificado: nenhuma contagem literal de testes resta no `AGENTS.md` (o piso verificado do PR-0 substituiu o número); e o índice `docs/README.md` — que não listava os docs 16–20 — passou a listá-los |

---

## 8. Ordem sugerida, e por quê

> **Estado em 2026-08 (atualizado após RFC-004)**: itens 1 a 4 **entregues**
> (ADR-47; RFC-002 + ADR-48; ADR-49; RFC-003 + ADR-50/51). F4-PR1 e PR2 também
> (ADR-52). A ordem abaixo fica como registro do raciocínio; a fila corrente
> mora na seção 9.

1. ✅ **PR-0.1** — sem release executável, nada do que foi construído chega a um
   terceiro. E é o único item cujo custo **cresce** com o tempo (cada PR novo
   aumenta o que não está empacotado);
2. ✅ **F3-PR0** — pré-requisito técnico da F3 e do B1/B2, os dois de maior
   consequência. Exige RFC: o casamento entre "corrigir uma linha de SQL" e
   "ativar um árbitro LLM sobre o canônico" é exatamente o que a regra existe
   para impedir;
3. ✅ **F-UI** — converte sete capacidades já pagas em produto. Depende de um
   smoke de UI, que é o pré-requisito real;
4. ✅ **F3** (P-3 + P-7) — a fila para de mentir;
5. ✅ **F-EPIST** (exceto C6) em paralelo: itens independentes e baratos.

> **O que NÃO fazer**: corrigir o B1 sem RFC. É uma linha, é tentador, e ativa
> decisão de modelo generativo sobre o canônico por efeito colateral de um
> conserto. — *cumprido: `docs/19` (RFC-002) precedeu a correção, e a flag
> `reconcile.llm_arbiter` continua desligada por default.*

---

## 9. Trilha ontológica (RFC-004) e a fila corrente

O RFC-004 (`docs/22`) e a leitura de literatura (`docs/26`) abriram uma trilha
própria e **mudaram a forma do F4-PR3**: o detector `policy.factual_conflict`
deixa de ser só "o conflito real que faltava" e passa a ser o primeiro
**leitor** do eixo `resolution_status` — a versão inicial deste parágrafo
dizia "escritor", e a correção foi medida (RFC-005 §5.3): o valor não
sobrevive ao caminho de volta pelo campo legado, então o que se entrega é o
SINAL recomputado, e O-2 segue aberta.

| # | O quê | Evidência | Estado |
|---|---|---|---|
| **O-1** | **Perda de ratificação silenciosa na fusão** — a regra nova derruba `human_approved` quando só um lado o tem (correto), mas derrubava sem registro; e a chave `confidence` AUSENTE no rascunho herdava a ratificação da residente pela regra genérica de fusão ("o que falta vem da fonte") | 🔴 medido (dois testes reprovando antes das correções) | ✅ **RESOLVIDO**: `kernel/ontology.py:ratificacao_perdida` + declaração no preview do MergePages (eixo humano) e em `page.stage`/resultado (eixo de máquina); `merge_meta` aplica o default documentado `extracted` à chave ausente |
| **O-2** | **`contested` não tem escritor PERSISTENTE.** O vocabulário fechado declara o valor; nada no produto o grava no canônico | 🔴 **medido** (não mais só declarado) | 🟨 **o SINAL é pago; a MARCA não.** O F4-PR3b entrega `policy.factual_conflict`, que faz `contested` aparecer na fila e no painel — recomputado a cada leitura. A marca no canônico **não entra**, e a razão foi medida: o único campo epistêmico persistido é `confidence` (extensão privada), e `LEGACY_CONFIDENCE` não tem entrada para `contested` — `_legado` **apaga** (→ `extracted`), `classificar` na releitura **assenta** (→ `resolved`, violando `ontology.toml:53`) e `merge_confidence` **lava**. Não há análogo de `ratificacao_perdida` para declarar a perda. **O que falta não é o detector**: é ato humano de contestação e/ou o nível 3 (`docs/28` §1), porque o eixo declara `applies_to = "assertion"` e marcar a PÁGINA por um número dentro dela é o erro de nível do `docs/28` §2. Herda as condições de reentrada de O-5 |
| **O-3** | **Isolamento multi-escritor está fora do envelope.** O produto depende do gate único + rito serializado; escritas concorrentes de vários agentes não têm resposta (a classe de anomalia que arXiv:2606.06240 tipifica) | 🟡 declarado (`docs/26` §4) | fica declarado; só entra no roadmap se o produto ganhar multi-agente — condição, não plano |
| **O-4** | **Os sentidos numéricos de `confidence` seguem no mesmo nome** (autorrelato `confidence_before`, taxas da metacognição, intervalos de avaliação) | 🔴 medido (`docs/22` §2.1) | deriva `open` em `ontology.toml [drift.confidence]`, lint confere os marcadores; rename é decisão própria (não acompanha F4-PR3) |
| **O-5** | **`Assertion` como entidade** — a unidade epistêmica atômica | 🟡 declarado (RFC-004 §6) | **quatro condições de reentrada**, a primeira é MEDIR uma consulta que a página responde errado; arte prévia citada (nanopubs/micropubs/CRMinf) |

**Fila corrente:** ✅ **F4-PR3 entregue inteiro** (a/b/c — §9.1 abaixo). A
ordem que valia aqui (F5 → F6 → F7 → C6) foi **reordenada pela re-mira do
[RFC-006](29-rfc-006-re-mira.md)** — a fila viva mora na **§10**.

### 9.1 · F4-PR3 partido em dois (RFC-005)

O levantamento para o `policy.factual_conflict` encontrou um problema de
desenho que muda a forma do pacote, e um achado colateral que vira
pré-requisito.

**O problema de desenho.** `docs/14` §P-5 pede "mesma entidade de kind
`quantity` com valores fora de tolerância", e isso **não é implementável**:
`quantities.py:67` faz `canonical = f"{value:g} {disp}"`, então o `canonical`
de uma quantidade É o valor — duas quantidades em conflito são entidades
*diferentes*, e não existe coluna ligando uma quantidade ao sujeito de que
ela é predicado. Sem sujeito, o detector compararia toda quantidade com toda
quantidade e inundaria a fila justamente no item de maior VoI (0.85).
[RFC-005](27-rfc-conflito-factual.md) resolve fazendo o detector um
**refinamento** de `contradiction_candidate` — o sujeito é o grupo de
identificador forte que já existe, e a precisão passa a ser por construção.

| # | Pacote | O quê | Estado |
|---|---|---|---|
| **F4-PR3a** | o instrumento | `kernel/factual.py` (puro, com a guarda de faixa que o plano não previa), `TOLERANCIA_RELATIVA = 0.01` declarada como NÃO calibrada, `classificar(em_conflito=)` produzindo `contested` | ✅ entregue |
| **F4-PR3b** | a obra | `check_corpus` emite `policy.factual_conflict`; fila distingue conflito factual de coexistência; `[mechanisms.factual_conflict]` em `epistemics.toml` com o nome MOVIDO de `PROMISED` para `EXPECTED`; código novo em `docs/06` §1 | ✅ entregue — com **três achados** que mudaram o desenho (abaixo) |

**Os três achados do F4-PR3b.** Nenhum estava no plano; os três vieram de
medir em vez de presumir.

1. **`check_corpus` tinha DOIS consumidores que não filtravam por regra** —
   `next_actions.contradiction_items` e `MergePages._identificadores_
   compartilhados`. Era seguro enquanto a função emitia um código só. Sem o
   despacho, o conflito factual entraria na fila **disfarçado** de
   coexistência (mesmo rótulo, mesmo custo, mesma chave de supressão) e a
   entrega "a fila distingue os dois" sairia não-entregue **com a suíte
   verde**, porque nenhuma fixture existente tem quantidades divergentes.
2. **Fundir SILENCIA o conflito em vez de resolvê-lo.** `merge` era o clique
   principal do item. A fusão põe os dois valores na mesma página, a guarda
   de faixa de `kernel/factual.py` descarta a dimensão inteira, e o finding
   some **sem que o número tenha sido corrigido** — enquanto o preview do
   `MergePages` declararia resolvido. `edit` passou a vir primeiro, e o
   preview declara a perda (mesma disciplina de `ratificacao_perdida`).
3. **A densidade sobe pelo CUSTO, não pelo valor.** O plano previa valor
   maior para o conflito factual. Subir o valor poria a tolerância de 1% —
   explicitamente NÃO calibrada — a governar o item de maior VoI do produto
   inteiro. O valor fica em 0.85 (igual ao genérico: o detector não mede
   importância) e o custo cai de 8 para 3 min, que é o que a evidência
   sustenta: conferir dois spans não custa ler duas páginas.
| **F4-PR3c** | o resíduo do P-9 | ato em lote com preview do `valid_at` legado | ✅ entregue — `ClearLegacyValidAt` |

**F4-PR3c: por que este pacote NÃO tem contrato epistêmico.** A assinatura
da corrupção é **igualdade**, não limiar: página de máquina cujo `valid_at`
é exatamente o `timestamp` (`base._document` usava o MESMO objeto `now` nos
dois campos). Não há número escolhido, logo não há garantia relativa a
declarar nem calibração a fazer — a diferença exata em relação ao
`factual_conflict`, que carrega 1% e por isso precisa de contrato.

Três decisões que o plano não trazia:

- **o ato REMOVE, não corrige.** Ausência de `valid_at` significa "nenhuma
  alegação", e o filtro `as_of` já tratava a ausência como "passa".
  Recuperar *quando* o fato passou a valer exigiria a FONTE. Apresentar-se
  como "conserta o `valid_at` legado" seria vender o que não se entrega;
- **página HUMANA fica de fora** mesmo com os carimbos iguais: `valid_at`
  humano vem de um ato com `when` declarado, e coincidir com a escrita é
  possível e legítimo. O default automático só existia no eixo de máquina;
- **teto de lote declarado.** ADR-52 diz que o legado é *"~toda página de
  máquina existente"*. Um preview com milhares de diffs torna a garantia
  central do eixo humano NOMINAL — ninguém lê 3.000 diffs, e "preview
  obrigatório" vira teatro. O lote tem limite, o preview diz quantas
  ficaram de fora, e repetir o ato avança o resto.

**O preview é o instrumento de medida.** Não há corpus real neste
repositório para dimensionar o estrago, e não precisa haver:
`execute(dry_run=True)` é puro, não escreve byte nenhum e não move o HEAD —
rodá-lo no corpus do usuário responde exatamente quantas páginas estão
sujas e mostra o diff de cada uma.

**Fora de escopo, declarado**: a outra metade do P-9 (`docs/14`) — *"o
detector de datas propõe candidatos com span sob gate"* — é heurística nova
no caminho de escrita e exige RFC próprio. Apagar um carimbo errado e
propor um carimbo novo são atos diferentes.

**Duas cláusulas de `docs/14` §P-5 caem, e a razão fica registrada**:
*unidade idêntica* (descartava `12 km` vs `12000 m`, exatamente o caso que a
normalização SI existe para pegar) e *sem ordenação temporal* (os candidatos
são `valid_at`, declarado corrompido pelo P-9 cuja limpeza é o F4-PR3c — usar
antes seria circular).

| # | Achado colateral | Evidência | Estado |
|---|---|---|---|
| **O-6** | **O renomeio `contested → low_yield` (ADR-52) ficou INCOMPLETO.** O levantamento inicial contou DUAS saídas; a varredura completa achou **nove**, e a contagem errada é ela própria parte do achado — o guarda existia (`test_f4_pr2_low_yield.py`) mas cobria só `gap_items` | 🔴 medido | ✅ **RESOLVIDO** — ver a lista abaixo |

**Os nove sítios, e por que o guarda não pegou.** Nenhum quebrava o gate: não havia teste sobre o vocabulário de SAÍDA de `curation_projection`, nem sobre as `reasons` de `scoring.py`, nem sobre a prosa dos contratos.

| # | Sítio | O que dizia | Classe |
|---|---|---|---|
| 1 | `usecases/cognitive_journey.py:537` | sinal literal `("contested", 0.8)` em `GET /cognitive/curation` | API |
| 2 | `cognitive/scoring.py:66` | *"⚔ contestada no canônico — há disputa aberta"* | UI |
| 3 | `epistemics.toml:382` | prosa *"contestada 0.8"* — e, na mesma linha, *"contradição 0.85 > pergunta 0.9"*, aritmeticamente falso (os parâmetros são 0.9 e 0.85) | contrato |
| 4 | `README.md:364` | overlay *"preferred/tentative/contested"* | README |
| 5 | `README.md:492` | *"página `contested` afunda na fusão"* | README |
| 6 | `docs/06:123` | *"CurationProjection: stale/contested/questions"* | referência |
| 7 | `docs/06:218` | `page_overlay(status∈…|contested)` — **mentia sobre o schema**: o CHECK real é `('preferred','tentative','low_yield')` (`runtime/db.py:154`, schema 10) | referência |
| 8 | `docs/06:408` | *"Overlay boost … contested ×0.8"* — o código diz `low_yield` (`retrieval/streams.py:71`) | referência |
| 9 | `usecases/curate/edit.py:9-12` | *"o ato que resolve `contested`"* no sentido ANTIGO, no docstring do ato que o F4-PR3b quer oferecer para o sentido NOVO | docstring |

Mais quatro identificadores INTERNOS (`_candidate_views`, `plan_attention`,
`reflect_usage`, `observatory`) renomeados junto, para que a próxima leitura
não reintroduza a confusão.

**E o renomeio ficou incompleto uma SEGUNDA vez.** Um QA adversarial achou
mais quatro linhas de PROSA de fonte no sentido antigo — três delas em
`next_actions.py`, que é `implementation_refs` do contrato
`factual_conflict`, o arquivo onde a ambiguidade custa mais caro. Nas duas
vezes nenhum teste pegou, porque nenhum teste varria o FONTE. Agora varre
(`test_nenhum_contested_no_sentido_ANTIGO_no_fonte_de_producao`), por
SENTIDO e não por palavra: a lista de donos legítimos é explícita, porque
`contested` é vocabulário vivo do eixo `resolution_status`.

**PRESERVADOS de propósito**, porque são do outro dono ou são ponte para o
legado: `kernel/ontology.py` (o eixo do ADR-54), `runtime/db.py` (a migração
9→10 precisa ler o valor antigo) e `cognitive/policy.py` (chave legada em
snapshots persistidos). É a razão de a separação ter de ser manual: um `grep`
cego destruiria o vocabulário novo.

---

## 10. A re-mira (RFC-006) e a fila reordenada

O [RFC-006](29-rfc-006-re-mira.md) fixou a direção de produto — **do
compilador de corpus ao instrumento de estudo** — e decompôs a demanda em
seis capacidades (V1–V6), cada uma verificada contra o código. A fila
abaixo substitui a ordem F5 → F6 → F7 → C6 da §9; a razão de cada
movimento está no RFC-006 §6, e o critério é **dependência real, não
preferência**.

| # | Pacote | O quê | Movimento |
|---|---|---|---|
| 1 | **V3 estabilidade** ✅ **ENTREGUE** | `kernel/stability.py` (puro; 4 sentidos separados), `GitStore.edit_history`, `page_stability` no index.db, derivação `stability` em `DERIVATIONS` (doctor de graça), `MemoryFacade.stability()`, `corpusmith stability`, contrato `editorial_stability` (registro 1.11.0) — 11 testes + 5 mutações | dependência zero, cumprida |
| 2 | **V1 mínimo** ✅ **ENTREGUE** | normas como sujeitos: iso/nbr/rfc/nist/ieee/eu_reg/**circular** (detector novo, precisão>recall) em `CONTRADICTION_IDS`; `regulator` FORA (referente ≠ documento); `STRONG_IDS` da reconciliação INTOCADO e congelado por teste — 7 testes + 3 mutações | pequeno e localizado, cumprido |
| 3 | **F5 ⇒ V2** ✅ **ENTREGUE** | identidade-com-sentido: alias → LISTA de candidatos com precedência por camada (seed < reference < bundle), `sentido()`/`base()` lendo o qualificador do canônico (`Entropia (física)`), alias disputado vira `ambiguous` (não reescreve, não indexa, não liga páginas), `policy.alias_conflict` nomeando a edição que resolve, contrato `alias_conflict` (registro 1.12.0), fingerprint do gazetteer cobrindo todos os candidatos — 13 testes + 6 mutações | **promovida e cumprida** — era a fase mais estratégica |
| 4 | **F6** ✅ **ENTREGUE** | rastro de abstenção (P-8): `ask_misses` em runtime.db (uso, não projeção — rebuild não apaga), chave determinística em `kernel/sketch.miss_key` (entidades da pergunta; sem entidade, SimHash — "o que é a ISO 27001?" ≡ "explique a ISO 27001"), gravação no retorno TERMINAL da abstenção (auto_recycle que responde não duplica), fechamento VERIFICADO por re-ask (`closed_by` auditável, primeiro fechador preservado), superfície em `insights.gaps.abstention` + painel Indicadores, contrato `abstention_trace` (registro 1.13.0, 23 mecanismos) com recall limitado DECLARADO — 10 testes backend + 2 UI + 4 mutações executadas (todas reprovam). O minerador de co-recuperação (lift/PMI sobre `ask_provenance` propondo LinkPages) do docs/14 §303 NÃO entrou: é outra pergunta (associação, não abstenção) e fica como porta aberta | **promovida e cumprida**: era componente de V4 — o sinal existe |
| 5 | **V4 dificuldade** ✅ **ENTREGUE** | índice "difícil de explicar": `kernel/difficulty.py` puro (5 componentes de 5 donos, pesos 0.35/0.25/0.15/0.15/0.10 e tetos declarados), `ComputeDifficulty` colhendo prática (cognitive.db), conflito+alias (um lint só), pergunta aberta (bundle) e lacuna do F6 (ask_misses × page_entities), projeção `page_difficulty`, `MemoryFacade.difficulty()`, `corpusmith difficulty`, bloco em `insights.gaps.difficulty` + painel Indicadores, contrato `explanation_difficulty` (registro 1.14.0, `composite`, evidência human_feedback+deterministic_check) — 23 testes + 5 mutações. Três recusas presas por teste: `low_yield` FORA (não re-funde o que o F4-PR2 separou), silêncio ≠ facilidade (`medida=false`), saturação impede componente único dominar. SEM derivação em `DERIVATIONS`, de propósito: dois sinais são de uso e não movem o HEAD | novo; dependia de F6 — cumprido |
| 6 | **V5 como medição** ✅ **ENTREGUE** | vocabulário FECHADO de relações semânticas (`kernel/semantics.py`: `applies_to`/`exemplifies`/`refines`, cada um com a pergunta que responde e o que NÃO significa), gate de escrita no ato de curadoria (construtor recusa fora do vocabulário; leitura tolerante converte desconhecido em `NULL`), `graph_edges.rel` + migração + `INDEX_GENERATION` g6, `PracticalCases` respondendo "que caso prático sustenta X?" nas duas direções, `corpusmith applications`, `rel` no payload do grafo, contrato `typed_application_edges` (registro 1.15.0) — 18 testes + 6 mutações. **A medição da RFC-004 §6 existe**: `ambiguous_fraction` = fração de páginas-alvo com 2+ sujeitos fortes, onde "aplica-se a esta página" não diz a QUAL afirmação. Zero aresta ⇒ `None`, nunca 0.0 | novo; **O-2 segue ressignificada, não resolvida** — a medição é a 1ª das três condições de reentrada |
| 7 | **C6** ✅ **ENTREGUE** | campo de efeito colateral no `EpistemicContract`: enum `SideEffect` fechado (`none`/`canonical_write`/`projection_write`/`state_write`), duas regras de lint (`canonical_write` ⇒ `high_impact`; `none` ao lado de outro efeito é contradição), os **25 contratos declarados** um a um, cruzamento por AST com o `BundleWriter` (declaração que vira prova), superfície no painel Qualidade (✍️ escreve no canônico) e registro 1.16.0 — 10 testes + 4 mutações. O caso que gerou o item (`/ask` com `auto_recycle` movendo o HEAD do Git) está DITO no contrato de `abstention` | levemente **promovida**: pré-requisito do fact sheet de V6 — cumprido |
| 8 | **V6 fact sheet** ✅ **ENTREGUE** | `ConceptSheet` + `corpusmith sheet [--prose]`: custo de LEITURA (mesma constante da fila, com o método junto do número), estabilidade (V3), dificuldade (V4), aplicações+medição (V5) e as `misinterpretations` de cada contrato ao lado do valor que qualificam. **A recusa é estrutural**: não existe campo `value`/`gain`/`roi` para alguém preencher com constante não calibrada, e `not_measured` diz na própria ficha que ganho e importância não foram medidos. Borda LLM default DESLIGADA; ligada, o rodapé de ressalvas é re-anexado DEPOIS do modelo (ele não pode esquecê-lo porque não passa por ele) e sem modelo a ficha seca fica inteira. Contrato `concept_sheet` (registro 1.17.0, 26 mecanismos) — 13 testes + 5 mutações | novo; por último — projeta o que 1–7 produzem |
| 9 | **F7** | P-11 resíduo de custo; `temporal_partition` | **rebaixada**: performance, não visão; não bloqueia nada acima |

Guarda transversal (RFC-006 §8): todo PR desta trilha é revisado primeiro
contra as duas patologias já catalogadas — um nome carregando várias
perguntas, e atributo afirmado no nível errado.

**QA adversarial da V2 (3ª rodada) — e uma correção de alegação minha.**
As 6 mutações declaradas foram re-executadas: nenhuma sobreviveu, mas
**duas contagens da mensagem do commit estavam infladas** (declarei "4
REPROVAM" e "7 REPROVAM"; o medido foi 3 e 2). O commit já estava
publicado e não se reescreve histórico compartilhado — a correção fica
aqui, que é onde o repositório registra alegação corrigida. A causa da
primeira: o docstring do teste nomeava uma mutação que NÃO o mata
(trocar só a marca para `extracted` não reescreve, porque `rewrite`
também exige `canonical != surface` — são DUAS guardas). Corrigido.

Sete defeitos reais achados e corrigidos no mesmo dia:

1. **`aliases` escalar virava um alias por CARACTERE** — `aliases:
   entropia` sem hífen no YAML produzia oito aliases de uma letra, e com
   dois registros assim a V2 amplificava para findings de conflito sobre
   vogais soltas. O frontmatter tolera extras sem validar tipo;
2. **alias vazio** casava em toda fronteira de pontuação (spans de
   comprimento zero), alcançável por um item `- ` solto;
3. **o dedup deixava `qid`/`authority` serem decididos pela ordem do
   arquivo** — o mesmo "último a escrever vence" que a V2 existe para
   eliminar, sobrevivendo nos outros campos da identidade; e o
   fingerprint era cego a isso, então renomear um registro trocaria o
   `qid` servido pelo índice **sem** disparar rebuild;
4. **o filtro `taken` descartava o termo de referência INTEIRO** — um
   registro reivindicando só `entropia` apagava `entropy` e `entropie`,
   que ninguém disputou, e de quebra fazia o degrau `TIER_REFERENCIA`
   nunca engatar em produção (o gazetteer real só via as camadas [0, 2]);
5. **"pesa 0.15 no grafo" era falso**, e estava no CONTRATO: aresta nasce
   de LINK, não de entidade — o efeito real é o termo não ligar páginas.
   Corrigido nos cinco lugares (contrato incluso);
6. **conflito entre termos da referência prescrevia um ato impossível**
   ("edite os registros" sem registro no bundle) — agora nomeia o ato que
   existe: criar a curadoria, que vence por precedência;
7. **`canonical` de tipo errado derrubava o `rebuild_index`** inteiro.

Mais: `evidence` do contrato declarava `property_test` sem property test
(removido); `docs/29` dizia ENTREGUE com o parágrafo seguinte descrevendo
o comportamento antigo no presente (reescrito como diagnóstico + estado);
`ambiguous_aliases` era exposto pela API e não renderizado em painel
nenhum, apesar de o contrato dizer "painel" (agora aparece no Curadoria);
e `INDEX_GENERATION` foi bumpado para `g5`, para o full rebuild da
mudança de forma do fingerprint passar pelo knob declarado em vez de
acontecer de carona no hash.

Um dos testes novos **também era teatro** e a mutação provou: o guarda do
filtro `taken` montava o gazetteer à mão e não exercitava
`authorities.py`. Refeito pelo caminho real (`reference.db` →
`_build_derived`), e aí a mutação morre.

**QA adversarial da entrega (2ª rodada, worktree isolada).** As 8 mutações
declaradas foram re-executadas de forma independente: todas reprovam. E o
QA achou **cinco defeitos reais**, todos corrigidos no mesmo dia:

1. caminho não-ASCII quebrava `edit_history` (`core.quotepath` escapa em
   octal): "atenção.md" contava ZERO edições em silêncio — o pior tipo de
   defeito num corpus pt-BR. Corrigido com `-c core.quotepath=false` +
   teste com página acentuada;
2. "Carta Circular 3.978" era lida como "Circular 3.978" — falso conflito
   entre tipos documentais distintos. Lookbehinds + linhas negativas;
3. numeração de circular não é global (SUSEP 100 ≠ BCB 100, mesmo
   canônico) — declarado como failure mode; detecção de órgão fica fora;
4. o contrato declarava um FP impossível (caixa-alta não casa numa regex
   case-sensitive) e omitia o FN real — a linha foi reescrita para o que o
   código FAZ (FP: Title Case; FN: CAIXA-ALTA oficial e órgão no meio);
5. o docstring alegava falsificabilidade mais forte que a real (`re.I`
   passava em silêncio) — ganhou a linha negativa que mata a mutação.

Colateral corrigido junto: `ComputeStability` não inicializa mais
`kb/.git` por efeito colateral em settings sem repositório (projeção é
LEITURA); e o merge invisível ao `git log --name-only` entrou no contrato.

