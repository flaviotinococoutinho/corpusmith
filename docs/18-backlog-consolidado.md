# 18 · Backlog consolidado — o que ainda falta

> **Altitude:** governança · **Status:** vivo

> Estado em 2026-09-02 (HEAD `de9e5fb` + o PR que abre a §11). **A única
> fila viva é a §11**; as seções 1–10 são o histórico de fechamento — cada
> linha ✅ diz o teste ou o ADR que a fechou, e nada nelas volta a ser
> editado exceto para marcar fechamento. Consolida `docs/14` (14 problemas
> de viabilidade), `docs/15` (plano, D-A…D-K, G-1…G-10), `docs/17`
> (auditoria adversarial), `docs/13` (fases B–D), `docs/09` (portas) e
> `docs/10` §21 (riscos A-01..A-10).
>
> **Convenção de identificadores** (uma patologia catalogada em `docs/28`
> §2 acontecia aqui dentro: `F1…F7` nomeava FLUXO na §2 e FASE na §3/§8/§10):
> `S-n` = superfície que falta (§2) · `P-n` = problema de viabilidade (§3) ·
> `T-n` = débito declarado (§5) · `X-n`/`DOC-n` = experiência/documentação ·
> `O-n` = questão ontológica (§9) · `V-n`/`C6`/`F6` = pacotes da re-mira (§10,
> concluídos) · **`Q-n` = item da fila corrente (§11)**. `corpusmith context`
> lê a §11 e conta abertos/fechados.

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
| **B1** ✅ **RESOLVIDO** (F3-PR0, RFC-002 + ADR-48) | **A escada de similaridade era código morto desde a v0.9.** `MIN(bm25(chunks_fts))` levantava `OperationalError` em SQLite 3.45.1 — sempre — e o `except Exception` cego devolvia lista vazia | 🔴 medido + 🟠 confirmado | Estado real: a SQL foi corrigida COM o RFC-002 (bm25 por chunk, redução em Python) e a falha ficou audível (`similarity_error`); o árbitro LLM segue atrás de `reconcile.llm_arbiter=false`; o regime posicional do degrau (HI só alcançável na posição 0) e a calibração de HI/LO seguem abertos — **§11 Q-9** |
| **B2** ✅ **RESOLVIDO** (F3-PR0: pré-condição de frescor + `index_stale` declarado) | **`index.db` — projeção declarada sem autoridade — decide ADD/UPDATE/SUPERSEDE.** Mesmo candidato, só o estado da projeção muda → `UPDATE` ou `ADD`, com `doctor.ok=True` nos dois | 🟠 confirmado | O cético produziu **duas páginas canônicas vivas para o mesmo DOI** pelo mesmo use case. Viola `AGENTS.md` §6 e `architecture.toml` (`authority = "nenhuma (projeção)"`) |
| **B3** ✅ **RESOLVIDO** (F3-PR0) | **`rebuild_index` sem `try/finally`**: exceção no meio vaza a conexão com transação aberta e trava `index.db` por 30 s no processo | 🟠 confirmado | Recuperável, mas o produto parece travado |
| **B4** ✅ **RESOLVIDO** | **`out_of_scope` recebe `validity_scope` sem negação** (`evaluate_memory.py:184`), e o painel renderiza como "Fora de escopo" | 🟠 confirmado → 🔴 medido | Inversão exata do significado: o painel diz que o escopo **avaliado** está fora do escopo. O campo passou a carregar os `known_failure_modes` do contrato ("onde NÃO foi medido"), com teste prendendo a não-inversão |
| **B5** ✅ **RESOLVIDO** (PR-0.1, ADR-47) | `build.spec:12` faz `EXE(...)` sem `exclude_binaries=True` — obrigatório em onedir. `just sidecar` **não constrói mais** | 🟠 confirmado | Nem a receita manual de empacotamento funciona. Com o token, constrói (3,4 MB) |
| **B6** ✅ **RESOLVIDO** (PR-0.1, ADR-47) | `collect_dynamic_libs("sqlite_vec")` devolve `[]` porque `sqlite-vec` só existe no extra `[ml]` e `just bootstrap` instala `.[dev]` | 🟠 confirmado | O binário sairia **sem a extensão nativa vec0, em silêncio** — o `build.spec` agora falha alto quando o extra `[ml]` não está presente |

---

## 2. Fluxos incompletos — backend pronto, sem superfície

Sete achados com a **mesma forma**: use case completo, endpoint completo, às
vezes até método de cliente declarado — e nenhuma tela. (Eram `F1…F7`;
renomeados para `S-n` porque `F-n` também nomeava FASE nas seções 3, 8 e 10.)

| # | Capacidade | Evidência |
|---|---|---|
| **S-1** ✅ **RESOLVIDO** (F-UI, ADR-49) | **`undo` inalcançável pelo app.** `/curation/history` sem consumidor: sem listar os atos, não há `act_id` para desfazer | 🔴 medido → `ActsHistory.tsx` chama `history` e `undo`; `test_pontas_soltas::test_as_superficies_orfas_do_f_ui_ganharam_consumidor` prende |
| **S-2** ✅ **RESOLVIDO** (F-UI, ADR-49) | **Doctor sem superfície.** Endpoint, use case e método de cliente existiam; nenhum painel chamava | 🟠 confirmado → `DoctorPanel.tsx`; mesma asserção positiva |
| **S-3** | **Revisão semanal**: job agendado + preview + commit, nenhuma tela (`review()` declarado no cliente sem chamador; `POST /cockpit/review/commit` órfã; `reviews/` fora do índice). A decisão binária de `docs/17` C11 (tela ou remover endpoint) nunca foi tomada | 🟠 confirmado → **§11 Q-8** |
| **S-4** ✅ **RESOLVIDO** (F-UI, ADR-49) | **Fila de jobs**: `cancel` e `retry` existiam no backend e não na UI | 🟠 confirmado → `ProcessesPanel.tsx`; `test_f0_doctor_api::test_cancel_e_retry_de_job_por_http` |
| **S-5** ✅ **RESOLVIDO** (F-UI, ADR-49) | **44 de 45 tipos de evento nunca chegavam à UI** | 🔴 medido → o cliente pergunta `/events/types` e escuta o vocabulário inteiro; `MAX_EVENTOS_MUDOS = 0` |
| **S-6** | **Rotas sem consumidor**: 11 de 94 pelo instrumento (`GET /`, `/cockpit/export` — falso positivo por template literal —, `/cockpit/reference` ×3, `/cockpit/review/commit`, `/cognitive/analogies` ×3, `/cognitive/episodes`, `/curation/acts`); o preset `exploracao` liga analogias que ninguém alcança. A trilha V3/V5/V6 acrescentou a forma inversa: **facade sem rota** (`stability`, `applications`, `concept_sheet`), que o instrumento não vê | 🔴 medido → **§11 Q-1, Q-2, Q-8** |
| **S-7** ✅ **RESOLVIDO** (F-UI, ADR-49) | `curation.applied` era emitido por **todo** ato e não chegava à UI | 🔴 medido → `test_pontas_soltas::test_os_dois_eventos_nomeados_como_mudos_agora_chegam` |

> Os dois números viraram **teto de teste** (`test_pontas_soltas.py`): piorar
> quebra, e melhorar exige baixar o teto no mesmo commit. O instrumento tem
> pontos cegos medidos (template literal, método declarado ≠ chamado,
> `bus.emit(canal, tipo)`) — **§11 Q-2**.

---

## 3. Funcionalidades ainda não construídas (`docs/14`, fases 3 a 7)

Das 14 lacunas de viabilidade, **P-1** (ato de curadoria) e **P-2** (camada de
padrões) foram entregues nas Fases 1 e 2. Restam:

| # | Problema | pt | Depende de |
|---|---|:--:|---|
| **P-3** ✅ **RESOLVIDO** (F3-PR2, ADR-51) | **Nada fecha e nada aposenta** — perguntas eternas, padrões reaparecem sem consentimento, a fila propõe trabalho sobre página morta | 4 | veredito e vitalidade: `CloseQuestion`, `paginas_vivas` em todas as fontes da fila (`test_f3_vitalidade.py`) |
| **P-7** ✅ **RESOLVIDO** (RFC-003 + ADR-50) | **Colisão de caminho** — promoção humana e compilação de máquina se sobrescreviam em silêncio | 3 | `policy.path_collision` vira decisão humana (`test_f3_colisao.py`) |
| **P-4** ✅ **RESOLVIDO** (F4-PR1, ADR-52) | **Suficiência ≠ dispersão** — a "confiança" mede dispersão da fusão e satura em quase toda resposta | 4 | `support` 2D (4 parcelas com saturação declarada) AO LADO de `uncertainty`, contrato `evidence_sufficiency` pago (registro 1.9.0), selo "sustentação fraca" no painel — base rasa deixa de virar certeza máxima muda |
| **P-5** ✅ **RESOLVIDO** (F4-PR2 + F4-PR3b, ADR-52, RFC-005) | **Conflito × impopularidade** — o produto chamava "em disputa" o que só deu beco | 4 | `contested → low_yield` em valor, chave e rótulo (registro 1.9.1); o conflito REAL é `policy.factual_conflict` como refinamento do grupo de identificador (`test_f4_pr3b_conflito_factual.py`) |
| **P-9** ✅ **RESOLVIDO** (F4-PR1 + F4-PR3c, ADR-52) | **`valid_at` = tempo de escrita** — a bi-temporalidade degenerava | 3 | página nova só carrega `valid_at` quando o conhecimento o fornece (ausente = válida em qualquer `as_of`); o legado é removido pelo ato em lote `ClearLegacyValidAt` com preview (`test_f4_pr3c_valid_at_legado.py`). Resíduo: detector de datas propondo `valid_at` com span — porta com RFC |
| **P-6** ⚠️ **metade paga** (V5) | **A aresta tem sintaxe, não semântica** — relação tipada ✅ (`applies_to`/`exemplifies`/`refines`, `graph_edges.rel`, contrato `typed_application_edges`); **co-menção materializada NÃO** — e a dívida convive com o contrato `inferred_cooccurrence_edges`, que descreve um laço em memória que o grafo da UI nunca desenha (`retrieval/patterns.py` nunca criado; dupla contagem armada, §5.3) | 4 | decisão registrada — **§11 Q-12** |
| **P-10** ⚠️ **metade paga** (V2) | **Entidade ↔ página** — o gazetteer carrega `page=rel_path` em memória desde a V2, mas `entities` segue sem coluna de página, o Explorer casa por string de título e o PPR não é semeado pela página que É a entidade | 3 | dependência: nenhuma (a V2 já entregou a fonte) — **§11 Q-11** |
| **P-8** ✅ **rastro e fechamento entregues** (F6, RFC-006 §6) | **A memória não lembra o que falhou** — abstenção não deixa rastro | 3 | `ask_misses` + fechamento por re-ask + superfície nos Indicadores + contrato `abstention_trace`. O que RESTA do P-8 original: o minerador de co-recuperação (lift/PMI sobre `ask_provenance` → propor `LinkPages`) — associação entre páginas que respondem juntas é outra pergunta e não entrou |
| **P-11** | **Custo das superfícies** — reprocessam o bundle a cada abertura | 2 | **parcialmente pago** pelo ADR-44 (grafo 2571 → 139 ms); resta `contradiction_items` rodando `check_corpus` sobre todas as páginas a cada chamada, sem memoização por `(page, sha)` — **§11 Q-10** |
| **P-12** | **O ritual semanal inalcançável** | 2 | = **S-3** (§2) — **§11 Q-8** |
| **P-14** ✅ **RESOLVIDO** | **Durabilidade invisível** — backup excelente, nunca automático | 2 | Job `backup` semanal no Scheduler (dedupe por semana ISO, prioridade mínima): cria, **verifica cada sha256** e só então poda além de `backup.keep` (default 4); a quiescência exclui o próprio job; `backup.verify_failed` declarado e repassado à UI |

---

## 4. Pacotes que a auditoria impôs (`docs/15` §3.1)

| # | Pacote | pt | Por quê |
|---|---|:--:|---|
| **PR-0.1** ✅ **ENTREGUE** (ADR-47) | **Release executável** — `exclude_binaries=True`, `sqlite-vec` no build, job de release com trigger de tag, token de release em `[gate].ci_enforced`, `expected_mechanisms` no registro | 4 | **G-8 e G-10 reabertas.** Sem o token no gate, `test_ci_executa_todo_o_gate_declarado` **estruturalmente nunca** poderá acusar |
| **F3-PR0** ✅ **ENTREGUE** | **Fechar o laço da decisão canônica** — B1 **com RFC**, pré-condição de frescor ou INV de cobertura bundle→índice, `try/finally` no rebuild, teste do degrau de similaridade | 6 | **Pré-requisito da F3**: o P-7 faz `promote` consultar uma escada com dois degraus mortos |
| **F-UI** ✅ **ENTREGUE** (ADR-49) | **As superfícies órfãs num PR só** — doctor, histórico com undo, cancel/retry, repasse genérico de SSE | 8 | Cinco achados, um arquivo de cliente, cinco painéis. Muito mais barato junto. **Pré-requisito: smoke de UI, hoje inexistente** |
| **F-EPIST** ✅ **CONCLUÍDA (inteira)** | Trilha epistêmica | 5 | ✅ B4 · ✅ `retrieval_rrf_hedge` heuristic (C13) · ✅ `rglob`/import absoluto (T7) · ✅ contratos de `memory_freeze` e `consolidate_inbox` (registro 1.8.0, 18 mecanismos; P(recall) declarado PROXY de heat; efeito colateral do `auto_recycle` dito em voz alta; `cold_memory.py` saiu dos refs de `abstention`) · ✅ **C6** (campo `side_effects` no modelo + duas regras de lint + cruzamento por módulo) · ✅ as duas dívidas `PROMISED` PAGAS (`temporal_partition` e `inferred_cooccurrence_edges`: os mecanismos existiam desde a v0.8, a dívida era de contrato) — **`PROMISED_MECHANISMS` está vazia e o lint epistêmico sai com 0 findings pela primeira vez** |

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
| **T11** | `bench compare` está fora do gate por PR (variação entre máquinas), e o baseline segue em `1.7.0` contra produto `2.0.0` — nenhum teste amarra as duas versões (só "não vem do futuro") | G-4 — **§11 Q-10** |

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
| 6 | **V5 como medição** ✅ **ENTREGUE** | vocabulário FECHADO de relações semânticas (`kernel/semantics.py`: `applies_to`/`exemplifies`/`refines`, cada um com a pergunta que responde e o que NÃO significa), gate de escrita no ato de curadoria (construtor recusa fora do vocabulário; leitura tolerante converte desconhecido em `NULL`), `graph_edges.rel` + migração + `INDEX_GENERATION` g6, `PracticalCases` respondendo "que caso prático sustenta X?" nas duas direções, `corpusmith applications`, `rel` no payload do grafo, contrato `typed_application_edges` (registro 1.15.0) — 18 testes + 6 mutações. **A medição da RFC-004 §6 existe**: `ambiguous_fraction` = fração de páginas-alvo com 2+ sujeitos fortes, onde "aplica-se a esta página" não diz a QUAL afirmação. Zero aresta ⇒ `None`, nunca 0.0 | novo; **O-2 segue ressignificada, não resolvida** — a medição é a 1ª das quatro condições de reentrada (RFC-004 §6), e o NÚMERO exige corpus real (§11 Q-21) |
| 7 | **C6** ✅ **ENTREGUE** | campo de efeito colateral no `EpistemicContract`: enum `SideEffect` fechado (`none`/`canonical_write`/`projection_write`/`state_write`), duas regras de lint (`canonical_write` ⇒ `high_impact`; `none` ao lado de outro efeito é contradição), os **25 contratos declarados** um a um, cruzamento por AST com o `BundleWriter` (declaração que vira prova), superfície no painel Qualidade (✍️ escreve no canônico) e registro 1.16.0 — 10 testes + 4 mutações. O caso que gerou o item (`/ask` com `auto_recycle` movendo o HEAD do Git) está DITO no contrato de `abstention` | levemente **promovida**: pré-requisito do fact sheet de V6 — cumprido |
| 8 | **V6 fact sheet** ✅ **ENTREGUE** | `ConceptSheet` + `corpusmith sheet [--prose]`: custo de LEITURA (mesma constante da fila, com o método junto do número), estabilidade (V3), dificuldade (V4), aplicações+medição (V5) e as `misinterpretations` de cada contrato ao lado do valor que qualificam. **A recusa é estrutural**: não existe campo `value`/`gain`/`roi` para alguém preencher com constante não calibrada, e `not_measured` diz na própria ficha que ganho e importância não foram medidos. Borda LLM default DESLIGADA; ligada, o rodapé de ressalvas é re-anexado DEPOIS do modelo (ele não pode esquecê-lo porque não passa por ele) e sem modelo a ficha seca fica inteira. Contrato `concept_sheet` (registro 1.17.0, 26 mecanismos) — 13 testes + 5 mutações | novo; por último — projeta o que 1–7 produzem |
| 9 | **F7** ⚠️ **parcial** | o contrato `temporal_partition` foi PAGO no reforço dos registros (§4, F-EPIST); o que resta é o resíduo de custo P-11 (`check_corpus` sem memoização) — **§11 Q-10** | **rebaixada**: performance, não visão; não bloqueia nada acima |

**§10 está concluída.** As oito capacidades saíram com núcleo, facade, CLI,
contrato e mutações executadas; o que NÃO saiu — a superfície no cockpit,
as decisões pendentes, os NFRs ainda só declarados e as pontas soltas —
está na **§11**, que é a única fila viva a partir daqui.

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

---

## 11. Fila corrente — a superfície de estudo, os registros com dentes e as pontas soltas

> **Esta é a única fila viva.** Aberta em 2026-09-02 a partir de uma
> auditoria de seis lentes (produto, roadmap, experiência onto-epistêmica,
> NFRs, documentação para agentes, pontas soltas no código) consolidada em
> 57 achados e verificada contra o working tree. Cada `Q-n` fecha movendo
> a linha para a seção histórica **no mesmo commit**, com o teste ou ADR
> que a fechou; `corpusmith context` conta abertos e fechados daqui.
> Ordem = dependência real; dentro de um bloco, o que destrava mais vem
> primeiro.

**O que este mesmo PR já pagou, e que a fila usa como base**: o registro de
requisitos não funcionais [`nfr.toml`](../nfr.toml) com `status`
cruzado pela suíte (`test_nfr_toml.py`); os invariantes com dono único
(`architecture.toml [[invariant]]`, cada `verified_by` resolvendo para
um teste); o contrato de documentação (`test_docs_contract.py`: altitude e
status em todo doc, índice completo, links, contagens não cravadas em doc
vivo); o mapa gerado (`corpusmith context` / `just context`,
`test_context_pack.py`); a contradição de durabilidade resolvida como
premissa (NFR-DUR-003); docs/10, AGENTS, skills e a história pública
sincronizados; e ADR-55/56/57 em `docs/08`.

### 11.1 A superfície de estudo — a re-mira chega ao cockpit

A patologia de `docs/17` §1.4 ("backend termina onde a interface começa")
reincidiu na trilha V1–V6: três capacidades saíram CLI/facade-only. Todos
os mecanismos já têm contrato — a única pré-condição que `docs/29` §5
impõe está paga. Regra de sempre: nenhum número epistêmico na tela sem a
ressalva do contrato ao lado; dado na tela carrega frescor e origem.

| # | Pacote | O quê (entrega + prova) | Depende de | Gate | Fecha |
|---|---|---|---|---|---|
| **Q-1** | **Ficha do conceito no cockpit** (V6 + V3 + V5 com rota) | Rotas read-only via facade (INV-ARCH-004): `GET /cockpit/sheet?page=`, `/cockpit/stability`, `/cockpit/applications?page=`; a ficha no Explorer ao abrir uma página, com as CINCO linhas do pitch — as duas que faltam, **"sob qual lente"** (entidades da página por `base()`/`sentido()`, nível MENÇÃO→PÁGINA declarado) e **"onde diverge"** (`contradiction_candidate`/`factual_conflict` cujo grupo inclui a página), entram em `ConceptSheet` com `alias_conflict`/`factual_conflict` em `_CONTRATOS`; `cost.how`, `means`, `guarantees[].misinterpretations` e `not_measured` renderizados como conteúdo; bloco "o que menos muda" nos Indicadores lendo `page_stability` persistida com carimbo do checkpoint `stability`. **UM dono do refresh** (verificado: hoje `ConceptSheet` recomputa dificuldade/estabilidade ao montar, o CLI persiste e o Indicadores lê o persistido — três caminhos): a ficha passa a LER as projeções persistidas e o refresh mora num lugar só (o comando/job que já persiste), nunca na abertura da tela (P-11). V4 já tem superfície parcial ("Onde o estudo trava"); o que falta é V3/V5/V6 e o refresh. As duas linhas novas mudam, no MESMO commit, `_CONTRATOS`, `contratos_citados` e `composite_components` do contrato `concept_sheet` — o registro é o dono do que a ficha compõe; a linha "lente" declara o nível (menção → página), como o preview do `link` já faz. **Prova**: asserção positiva em `test_pontas_soltas` (as rotas deixam de ser órfãs) + vitest da ficha com `not_measured` e com "nunca computado ≠ vazio"; o status por linha da ficha fica AQUI (não em `docs/29` §5, que é RFC) | nada | PR | M-01, M-02 |
| **Q-2** | **Instrumentos de pontas soltas que só apertam** | `test_pontas_soltas`: consumo medido por CHAMADA real (`client.<método>(` nos painéis, resolvendo método→rota), não por literal — `/cockpit/export` deixa de ser falso positivo e `review()` deixa de contar como consumido; `GET /` fora do teto; regex de emissão que vê `bus.emit(canal, tipo)`; um terceiro instrumento — **método público de facade sem rota** (teto medido, só desce); o teste da SQL `MIN(bm25)` (que mede o SQLite, não o produto) substituído por asserção positiva (`similarity_error is None` com índice fresco). **Prova**: teste do teste — plantar método declarado sem chamada faz o instrumento acusar | nada | PR | M-35, M-01 (instrumento) |
| **Q-3** | **Atos a partir da página** — `link rel=` alcançável pela UI | Oferta `link` com `needs=["rel"]` e as opções vindas de `RELACOES` (kernel) via `/curation/acts` (que passa a expor as relações com a pergunta que cada uma responde e deixa de ser órfã); `acts_for_page(path)` ao lado de `acts_for`, preso por teste de assinatura, abrindo o mesmo `CurationDialog` no Explorer (edit/supersede/invalidate/link/close_question); "perguntar sobre esta página" navega para Consulta com a pergunta pré-preenchida (sem filtro novo no `/ask` antes de medir); frontmatter com rótulos humanos. Verificado: o diálogo JÁ renderiza `preview.note` (o nível declarado pelo ato) — o que falta é só o campo `rel` chegar ao ato; e um `POST /curation/act` manual já aceita `rel`, logo a ausência é de SUPERFÍCIE, não de transporte. Dos nove atos, sete são "da página aberta" (`undo` e `clear_legacy_valid_at` não). **Prova**: vitest — o diálogo de `link` mostra as três relações e envia `rel`; o teste do backend cruza as relações expostas com `RELACOES` (não copia a lista); `MAX_ROTAS_ORFAS` baixa de 11 para 10 no mesmo commit | Q-1 (a ficha é o lugar natural dos atos) | PR | M-03, M-04 |
| **Q-4** | **O léxico na tela, e os nomes da UI presos ao léxico** | `GET /cockpit/ontology` (mesma facade) + seção Léxico (eixos com pergunta e valores; termos com é/não é/o que impõe; derivas abertas com sentidos); dois componentes — `<Termo id>` (lê o léxico) e `<Ressalva mecanismo>` (lê `misinterpretations` de `/cockpit/epistemics/{id}`) — aplicados em Consulta, Indicadores, Qualidade e Foco; o "Dicionário do domínio" servido de `harness.ontology.overview()["axes"]`, nunca de lista literal (teste cruzando com `kernel/ontology.AXES`); varredura de rótulos: "confiança" só com qualificador (derivação/resolução/governança; "autoconfiança declarada" no Foco; "dispersão × desfecho" na Cognição), "VoI" vira "prioridade de projeto (não calibrada)" ou some, "linke mais" vira "olhe aqui" (`docs/28` §4), "Gaps epistêmicos" repartido por pergunta, 🪫 único para `low_yield`, "Evidências" → "Trechos de suporte"; os `.tsx` viram markers de `[drift.confidence]` e `[drift.evidence]`. **Prova**: teste que reprova "confiança"/"valor de informação" em `.tsx` fora de allowlist qualificada; vitest por rótulo; os cinco textos que alegavam "painel/API" do léxico passam a ser verdade | nada | PR | M-05, M-07, M-08, M-10, M-12 (componentes), M-37 (rótulo) |
| **Q-5** | **O `/ask` que explica** | Bloco `epistemic` DETERMINÍSTICO na resposta, montado por módulo puro do kernel: `uncertainty{value, threshold, means}`, `support{score, components, means}`, `abstention{threshold, top_score, entities_not_found, streams_consulted, as_of, means}` e as ressalvas lidas do registro; `degraded_reason` com vocabulário fechado (`model_unavailable` \| `citations_fabricated`) em `VOCABULARIES` + verbete (é vocabulário de OUTRO objeto, não eixo: ADR, não RFC); o chat mostra sempre os dois números com o `means` ao lado e sem "%", spans realçados ("por que este trecho"), badge SUPERSEDIDA; o CLI imprime `[n] page ← resource` e ganha `--json`; **`recycled`**: a resposta carrega `side_effects:[{kind:"canonical_write", what:"recycled", page, commit}]`, UM evento (unificar `page.recycled`/`memory.recycled`), o chat diz "♻️ esta consulta reciclou X". **Prova**: cross-check em `test_epistemics_toml` (limiar do TSX some — vem do payload); `test_c6` cobre o payload de `recycled`; mutação: apagar o emit reprova | nada | ADR (vocabulário `degraded_reason`; gate humano para `canonical_write` no `/ask`, ou não) | M-06, M-14 |
| **Q-6** | **Contratos que dizem o que o default faz** | `abstention_trace` e `explanation_difficulty` declaram que, com `ask.abstain_threshold = 0.0`, o rastro só nasce de evidência VAZIA (parâmetro cruzado nos dois; teste que prova o buraco: evidência fraca-positiva + 0.0 ⇒ nenhum miss); `abstain_threshold` vigente ao lado do bloco "lacunas" nos Indicadores; regra de lint `epistemic.misinterpretations_missing` (error para `guarantee_kind != deterministic`, mutação apagando o campo); painel Qualidade renderiza `to_dict()` completo com rótulos pt-BR (parâmetros com valor, evidência, quem avalia, componentes, os três efeitos, o envelope inteiro, os findings do lint); `evaluation_status` só quando `evaluated_by` não vazio, senão `not_applicable` com a evidência ao lado; dificuldade nos Indicadores com `medida`, componentes, `level="page"` e o `means`; ramo zero da abstenção com a frase do contrato | nada | PR | M-33, M-17, M-09, M-11 |
| **Q-7** | **Exportação citável e proveniência por região** | Formato `cite` no exportador e em `/cockpit/page`: `{path, title, commit do último ato, generated_via, source_sha256, valid_at/invalid_at, superseded_by}` + BibTeX `@misc` com `note=path@commit` (sem norma editorial: a fronteira de `docs/25` §2.2 fica); projeção read-only `regions(page)` servida em `/cockpit/page` e renderizada como faixas ("este trecho veio de Y pelo ato #n"; o resto é "do autor" por definição). **Prova**: a chave muda quando a página muda; vitest das faixas | Q-1 | PR | M-13 |

### 11.2 Decisões pendentes — cada uma é um ADR curto, e a ausência de decisão custa mais que qualquer escolha

| # | Decisão | Opções (escolher UMA) | Depende de | Gate | Fecha |
|---|---|---|---|---|---|
| **Q-8** | **Revisão semanal** (S-3, P-12; `docs/17` C11) | (a) cartão "Revisão da semana" no Dashboard consumindo `review()` + `/cockpit/review/commit`, escutando `review.done` (P-12 proíbe aba nova); (b) remover o endpoint de preview e declarar a revisão artefato de arquivo. Em ambos, `reviews/` passa a ser dito no índice ou explicado fora dele | nada | ADR | M-31 |
| **Q-9** | **Degrau de similaridade** (B1 residual) | (1) regime posicional (HI só alcançável na posição 0 do FTS: `0.4/(1+pos)` faz `pos=1` valer no máximo 0.80 < 0.82) declarado como failure mode em `reconciliation`, com teste: candidato jaccard≈1/NCD≈0 na 2ª posição ⇒ ADD; (2) testes do árbitro `_by_local_arbiter` com router stub (JSON válido, inválido, exceção ⇒ ADD silencioso, como o contrato diz); (3) **golden de reconciliação** como seed (pares mesmo-objeto / objetos-distintos) — a condição de reentrada da calibração de HI/LO que o RFC-002 §12 exige e que nunca existiu | nada | PR (calibração fica em Q-21) | M-34 |
| **Q-10** | **Resíduos de custo e medição** (P-11, T11) | memoizar `check_corpus` por `(page, sha)` em `contradiction_items` usando `page_index_state`; remedir `benchmarks/baseline.json` na máquina de referência e bumpar para 2.x; teste em `test_pr0_gate` que tolera no máximo N versões menores de atraso (ou exige `stale_since` declarado) — a autoridade de performance para de envelhecer em silêncio | nada | PR | M-27, M-26 |
| **Q-11** | **Entidade ↔ página** (P-10 literal) | coluna `entities.page` (ou `entity_pages`) preenchida no rebuild a partir do candidato `TIER_BUNDLE` (a V2 já carrega `page=rel_path` em memória); `/cockpit/page` e o Grafo linkam entidade → página-autoridade; o Explorer deixa de casar por string de título. **Prova**: `authority_record` em X.md ⇒ consulta devolve X.md; rebuild reconstrói (INV-DATA-003) | nada (a V2 entregou a fonte) | PR (schema aditivo) | M-29 |
| **Q-12** | **Onde vive a co-menção** (P-6 metade, §5.3) | (a) projeção persistida em `graph_edges` com `origin="cooccurrence"` e o laço em memória REMOVIDO; ou (b) só adjacência em memória, e o contrato `inferred_cooccurrence_edges` + P-6 reescritos para dizer isso. Antes de qualquer materialização: teste de idempotência (aresta já presente não é re-somada). `retrieval/patterns.py` fechado como recusado ou entregue | nada | ADR | M-24 |

### 11.3 Requisitos não funcionais — de `declared` a `pinned`, na ordem do risco

Cada item muda o `status` do NFR em `nfr.toml` **só com o teste em
`verified_by`**; o registro é o placar, `docs/10` a doutrina.

| # | Pacote | O quê (entrega + prova) | NFR | Depende de | Gate | Fecha |
|---|---|---|---|---|---|---|
| **Q-13** | **`BundleUnitOfWork` mínimo** (A-01/A-02, P0 desde o baseline 1.4.0) | lock → capturar HEAD → Harness SOB o lock → staging + `os.replace` → index/log → UM commit (SUPERSEDE de máquina no mesmo write) → evento; `expected_head` no `BundleWriter` (plano computado sobre HEAD ≠ HEAD sob lock ⇒ `policy.stale_plan`, o que fecha D-H entre processos); reconciliador de startup que RECUSA commitar sujeira alheia (ou a commita como `recovery:` nomeado); trilha do ato gravada na mesma transação (T4); lease com `RETURNING`. **Prova**: três injeções por monkeypatch — `GitStore.commit` levanta; `write_text` levanta `ENOSPC` no 2º doc (all-or-nothing); dois `BundleWriter.write` em `multiprocessing` no mesmo kb | nada | ADR | NFR-INT-002, NFR-INT-003, NFR-CON-003 (parte) | M-41, M-49 |
| **Q-14** | **Backup transacional e RPO de mídia** | durante o snapshot, segurar `.write.lock` e copiar cada banco por `VACUUM INTO`/backup API (ou 503 "backup em curso" nas escritas); catch-up (enfileira quando o zip mais novo tem > 7 d, não só às segundas); `backup_age_seconds` em `/health/full` + finding `OPS-BACKUP-AGE`; `backup.dir` configurável (outro volume) documentado em `docs/12`. **Prova**: escritor concorrente durante `CreateBackup` + restore com fingerprint igual; terça-feira com último backup de 9 d ⇒ job enfileirado | nada | PR | NFR-DUR-005 → guarantee | M-43 |
| **Q-15** | **Egresso `local_only` provado e a segurança residual** | `test_local_only_nunca_chega_ao_provedor_api` (monkeypatch `ModelRouter._api` para levantar; chave de API setada; Ollama morto ⇒ `ModelUnavailable`, nunca `_api`); `?auth=` aceito só em `/events`; log de acesso não contém o token (caplog); corpo Pydantic para `/cockpit/ingest` com teto e 413 nomeado | nada | PR | NFR-PRIV-002, NFR-SEC-004 | M-44, M-47 |
| **Q-16** | **Medir o que só está declarado** | `corpusmith bench slo --fixture large` (20k–50k páginas sintéticas, semente fixa) emitindo uma chave por SLO-id — nightly, não gate; família `OPS-*` no doctor (WAL, disco, DLQ, idade do backup, idade da fila) com limiares vindos de `nfr.toml`; política de retenção (`events` ≥ 30 d ou ≥ 50k linhas; jobs terminais ≥ 30 d) com job `prune`; `/health/full` sem `COUNT(*)` em tabela grande; SSE com `id: seq` + `Last-Event-ID` e evento `events.dropped` quando a fila do assinante enche; gatilhos de `docs/10` §16 reescritos sobre métricas que existem | nada | PR | NFR-SLO-001/002 → measured, NFR-OBS-002, NFR-QUE-004, NFR-SCALE-001 | M-42, M-46 |
| **Q-17** | **"Timeout" com dois nomes** | `soft_timeout_s` (thread: pede parada, emite `job.timeout`) ≠ `deadline_s` (isolamento: mata); resultado devolvido após o soft timeout vira `done` com `late=true`, nunca `failed: cancelado` com efeitos já aplicados; teste do watchdog com heartbeat/timeout monkeypatchados | nada | PR | NFR-QUE-003 | M-45 |
| **Q-18** | **Reprodutibilidade do índice** | bundle → `rebuild_index(full=True)` → fingerprint ordenado (chunks, page_entities, graph_edges, entities.canonical) → apagar → rebuild → fingerprint idêntico; `docs/06` §3 declara as tabelas sensíveis a ordem (excluídas com motivo) | nada | PR | NFR-REP-002 | M-48 |

### 11.4 Entropia de engenharia — crescer com agentes sem acumular contradição

| # | Pacote | O quê (entrega + prova) | Depende de | Gate | Fecha |
|---|---|---|---|---|---|
| **Q-19** | **Docs gerados, cabeçalho por módulo, camadas × árvore** | `docs/generated/{reference,epistemics-registry,ontology-lexicon}.md` produzidos pelo `context_pack` (uma linha por rota/mecanismo/termo com link para `implementation_refs`/`lives_in`) + `test_generated_docs_estao_frescos`; `docs/06` §2, `docs/05` §11, `docs/11` e `docs/23` mantêm só semântica e porquê; lista fechada `architecture.toml [[module_contract]]` com docstring de módulo em seções fixas (`Purpose:` / `Authority:` / `Side effects:` / `Invariants:` / `Related:`) presa por AST e cruzada com `side_effects` do contrato; teste de que a união de `layers`/`pure`/`domain` cobre `src/corpusmith` (iterdir) com a lista explícita de módulos de topo; `AGENTS` §3, `docs/06` §9 e README remetem ao TOML; decisão sobre `time`/`threading` no núcleo (injeção de relógio ou exceção declarada) | nada (o context pack existe) | PR | M-53, M-55, M-40 |
| **Q-20** | **Guia de estudo e ajuda por painel** | doc de altitude produto — "quem estuda": jogar PDF → compilar → perguntar → ler evidência → curar → ficha → exportar citação — roteado do `docs/README` como entrada "quem estuda"; um "?" por painel abrindo o trecho correspondente (texto embutido, sem rede); o card "Dicionário do domínio" renomeado "Vocabulário em uso (contagens)"; `cli.py:1` deixa de citar um manual que não existe | Q-1, Q-4 | PR | M-12 |

### 11.5 Condições e portas — dependem de DADO ou de decisão, não de código

| # | Condição / porta | O que a abre | Gate | Fecha |
|---|---|---|---|---|
| **Q-21** | **Medir em corpus real** — a pré-condição nomeada de O-2/O-5/V5-afirmação e de toda calibração | um corpus real (não há nenhum no repositório) em que `ambiguous_fraction` seja registrado em `docs/22` §6 (condição 1 das quatro); plano de calibração por constante com o dado que cada uma precisa (`ask_outcomes`/`retrieval_attempts` → pesos de V4: correlação `page_difficulty.score` × falha confiante, n mínimo e envelope; golden de reconciliação (Q-9) → HI/LO; tolerância 0.01; teto anti-hub 30; τ de tema); até lá, todas continuam **declaradas não calibradas** e nenhuma superfície as vende como medidas | condição (RFC-004 §6 reentra só depois) | M-18, M-23 |
| **Q-22** | **As três derivas ontológicas** (`evidence` 3 sentidos, `authority` 5, `confidence` 6) | um PR por deriva, começando por `evidence` (só falta o qualificador: `evidence_kind` / suporte / observação — os rótulos da UI entram em Q-4); depois `authority` (RFC-004 §6 — a V2 a contornou pondo o sentido no canônico); `confidence` por último (O-4); `status="resolved"` com markers distintos, o lint acusando regressão | ADR por deriva (o RFC já existe) | M-37 |
| **Q-23** | **Minerador de co-recuperação** (o que restou do P-8) | porta com condição mensurável: N consultas com 2+ páginas co-respondendo em `ask_provenance` num corpus real; então `kernel/association.py` (lift/PMI com suporte mínimo declarado) + `MineCoRetrieval` propondo `link` na fila (gate humano; `side_effects = none`) + contrato `co_retrieval_mining` (failure mode: popularidade ≠ relação) | contrato novo (heurística que propõe ato) | M-30 |

### 11.6 Pequenos, e as disposições das pontas soltas

| # | Pacote | O quê | Gate | Fecha |
|---|---|---|---|---|
| **Q-24** | **Quatro achados vivos do `docs/17` + dois no-ops** | `recommended_actions` removido ou renderizado; `pending_count` único para `/cockpit/dashboard` e `/status` (teste com `retry_scheduled`); o plano da Cognição abre o `CurationDialog` como a fila; `plan_attention` aceita os sufixos do inbox (`.pdf`/`.epub`); `local_only` deixa de ser parâmetro no-op em `fts.search`; o `bang` de imagem capturado e nunca consumido é removido ou consumido | PR | M-38, M-28 (parte) |
| **Q-25** | **Rotas órfãs por decisão, e o preset honesto** | decisão por rota — analogias (superfície no Foco ou rebaixar), referência (Curadoria), episódios — cada uma baixando `MAX_ROTAS_ORFAS` no mesmo commit; o preset `exploracao` só liga `profile.analogies` quando houver superfície (teste); `GET /cockpit/themes` (identidade, épocas) + rótulo do tema no Grafo + toast em `themes.adopt_refused` | ADR | M-36, M-39 |
| **Q-26** | **Guardas de processo** | PR template com duas linhas obrigatórias — "termo novo responde a UMA pergunta (eixo em `ontology.toml`)?" e "em que nível da escada o atributo é afirmado, e por quê?"; `docs/30` §3 linhas 4 e 9 marcadas ⚠️ **guarda humana** até existirem guardas executáveis (campo `level` nos contratos que escrevem atributo; registro de mutações lido por teste); ledger de versões: "v2.1" em `ontology.toml`/ADR-54 com produto 2.0.0 — decidir o bump ou corrigir os rótulos, e um teste que impede versão citada > `__version__` | PR | M-56, M-54 |
| **Q-27** | **Smoke de UI nos painéis de estudo** | Explorer, Qualidade (contratos), Curadoria, Grafo, Foco, Cognição, Memória — cada um com vitest do caso enganoso antes de ser tocado por Q-1/Q-3/Q-4 (nunca computado ≠ vazio; ressalva ao lado do número) | PR | M-15 |

**Aceitas como premissa ou fora, com razão** (não são itens; mudar de ideia
exige ADR):

- **T1** (carimbos de frescor duplicados) — aceita até o PR que tocar
  INV-002; **T3** (undo de criação inexpressável, 409 nomeado) — aceita;
  **T5** (`merged` no vocabulário sem observação) — aceita até a
  calibração de RFC-001 (Q-21); **T4** entra em Q-13;
- **A-07** (estado e evento em transações separadas) — **premissa**: o
  evento é best-effort pós-commit, o estado é a autoridade e a UI reconcila
  por polling; registrar em `nfr.toml` quando Q-13 fechar;
- **NFR-A11Y-001 / NFR-I18N-001** — alvos declarados em `nfr.toml`, sem
  item: a ficha do conceito (Q-1) é a superfície certa para começar por
  `aria-label`/`role`;
- **`docs/17`, `docs/15`, `docs/13`, `docs/14`, `docs/09`** — congelados
  (linha `Status: histórico` na cabeça); não recebem tabela-índice nem
  marcações: o estado vivo de cada achado deles está aqui;
- **um RFC-007 "de direção"** — recusado: a direção do RFC-006 não mudou,
  e a superfície de estudo é a continuação dela. Documento novo de plano
  seria o sexto plano com o mesmo assunto — a entropia que este PR reduz.

### 11.7 Política de entropia documental — cada regra com a guarda que a prende

1. **Fato enumerável é gerado, à mão fica só o porquê** — `corpusmith
   context` (`test_context_pack.py`); Q-19 estende a docs gerados;
2. **Um dono por fato** — camadas/gate/invariantes em `architecture.toml`,
   NFRs em `nfr.toml`, mecanismos em `epistemics.toml`, termos em
   `ontology.toml`, a fila em `docs/18` §11 — `test_architecture_toml.py`,
   `test_nfr_toml.py`, `test_epistemics*.py`, `test_ontology.py`;
3. **Doc vivo não crava contagem nem versão de registro** —
   `test_docs_contract.py` (ledgers e RFCs podem, porque registram o que
   era verdade no commit);
4. **Todo doc declara altitude e status; histórico aponta para o vivo;
   `AGENTS.md` não roteia histórico como destino** — `test_docs_contract.py`;
5. **Skills citam `just verify` e nunca copiam o gate; uma estratégia de
   merge** — `test_pr0_gate.py`;
6. **Uma linha fecha movendo-se, no mesmo commit, com o teste** — guarda
   humana (skill `ship-pr`) + `corpusmith context` conta;
7. **Um nome, uma pergunta; ids com prefixo próprio (`S-`/`P-`/`T-`/`O-`/
   `Q-`)** — cabeçalho deste documento; Q-26 leva ao template de PR.

