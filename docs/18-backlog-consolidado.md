# 18 · Backlog consolidado — o que ainda falta

> Estado em 2026-07-27, HEAD `83c5983`. Consolida `docs/14` (14 problemas de
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
| **B3** | **`rebuild_index` sem `try/finally`**: exceção no meio vaza a conexão com transação aberta e trava `index.db` por 30 s no processo | 🟠 confirmado | Recuperável, mas o produto parece travado |
| **B4** | **`out_of_scope` recebe `validity_scope` sem negação** (`evaluate_memory.py:184`), e o painel renderiza como "Fora de escopo" | 🟠 confirmado | Inversão exata do significado: o painel diz que o escopo **avaliado** está fora do escopo. Correção de uma linha |
| **B5** | `build.spec:12` faz `EXE(...)` sem `exclude_binaries=True` — obrigatório em onedir. `just sidecar` **não constrói mais** | 🟠 confirmado | Nem a receita manual de empacotamento funciona. Com o token, constrói (3,4 MB) |
| **B6** | `collect_dynamic_libs("sqlite_vec")` devolve `[]` porque `sqlite-vec` só existe no extra `[ml]` e `just bootstrap` instala `.[dev]` | 🟠 confirmado | O binário sairia **sem a extensão nativa vec0, em silêncio** |

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
| **P-4** | **Suficiência ≠ dispersão** — a "confiança" mede dispersão da fusão e satura em quase toda resposta | 4 | F3 |
| **P-5** | **Conflito × impopularidade** — o produto chama "em disputa" o que só deu beco | 4 | F3 |
| **P-9** | **`valid_at` = tempo de escrita** — a bi-temporalidade degenera | 3 | 🟡 **declarado** no ADR-41; o parâmetro `when` já está aberto |
| **P-6** | **A aresta tem sintaxe, não semântica** — nenhuma relação tipada; co-menção não materializada | 4 | F1 (formato de link resolvido no ADR-41.2) |
| **P-10** | **Entidade ↔ página** — vínculo existe no canônico e é jogado fora na projeção | 3 | F5 |
| **P-8** | **A memória não lembra o que falhou** — abstenção não deixa rastro | 3 | F3 (deliberadamente depois) |
| **P-11** | **Custo das superfícies** — reprocessam o bundle a cada abertura | 2 | **parcialmente pago** pelo ADR-44 (grafo 2571 → 139 ms); resta o resto |
| **P-12** | **O ritual semanal inalcançável** | 2 | = F3 acima |
| **P-14** | **Durabilidade invisível** — backup excelente, nunca automático | 2 | — |

---

## 4. Pacotes que a auditoria impôs (`docs/15` §3.1)

| # | Pacote | pt | Por quê |
|---|---|:--:|---|
| **PR-0.1** ✅ **ENTREGUE** (ADR-47) | **Release executável** — `exclude_binaries=True`, `sqlite-vec` no build, job de release com trigger de tag, token de release em `[gate].ci_enforced`, `expected_mechanisms` no registro | 4 | **G-8 e G-10 reabertas.** Sem o token no gate, `test_ci_executa_todo_o_gate_declarado` **estruturalmente nunca** poderá acusar |
| **F3-PR0** ✅ **ENTREGUE** | **Fechar o laço da decisão canônica** — B1 **com RFC**, pré-condição de frescor ou INV de cobertura bundle→índice, `try/finally` no rebuild, teste do degrau de similaridade | 6 | **Pré-requisito da F3**: o P-7 faz `promote` consultar uma escada com dois degraus mortos |
| **F-UI** ✅ **ENTREGUE** (ADR-49) | **As superfícies órfãs num PR só** — doctor, histórico com undo, cancel/retry, repasse genérico de SSE | 8 | Cinco achados, um arquivo de cliente, cinco painéis. Muito mais barato junto. **Pré-requisito: smoke de UI, hoje inexistente** |
| **F-EPIST** | Trilha epistêmica, um PR por item | 5 | B4, rebaixar `retrieval_rrf_hedge`, contratos de `memory_freeze` e `consolidate_inbox`, `rglob` no `test_architecture` |

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
| **T6** | `_CommunitySummaryPage` reescreve o sumário a cada execução mesmo com conteúdo idêntico → o HEAD move a cada job | ADR-45 |

### 5.2 Buracos no gate (🟠 confirmado)

| # | O quê | Consequência |
|---|---|---|
| **T7** | `INV-ARCH-003/004` só inspecionam imports **relativos**, e o scan de `api/` usa `glob` em vez de `rglob` | O cético plantou violações que passaram verdes |
| **T8** ✅ **RESOLVIDO** (PR-0.1) | `epistemics lint` fica verde com **contrato obrigatório apagado** (G-10) | Esquecer um contrato na F3/F4/F5 é silencioso |
| **T9** | O `conftest` derruba o Ollama e com isso cega 100 % da suíte para a única FK do `index.db` | Foi assim que o defeito da FK sobreviveu |
| **T10** | Nenhum teste cobre `/events`, `/system/doctor` por HTTP, `/jobs/{id}/cancel` nem qualquer superfície de UI | O bloco inteiro do §2 é invisível ao gate |
| **T11** | `bench compare` está fora do gate por PR (variação entre máquinas), e o baseline segue em `1.7.0` contra produto `1.9.x` | G-4 |

### 5.3 Dependências ocultas ainda abertas (`docs/15` §5)

- **D-H** — o lock protege o bundle, não a projeção: o `rebuild_index` de cada
  `_apply` escreve fora do lock. A Fase 1 multiplicou por sete os escritores
  humanos. 🔵 planejado, não verificado recentemente;
- **co-menção contada duas vezes** — o laço em memória do F2-PR1 colidirá com a
  materialização que a F5 (P-6) promete: o mesmo par somaria 0,5 (lido) + 0,25
  (recomputado). 🟠 confirmado, e **muda o escopo da F5**;
- **`retrieval/patterns.py`** — mitigação de colisão prescrita "já no PR1" pelo
  `docs/15` §6 e **nunca criada**. 🟠 confirmado.

---

## 6. Experiência de uso

| # | Problema | Evidência |
|---|---|---|
| **X1** | **Numa máquina sem o extra `[ml]` compilado, "comunidade" é componente conexo** — o `backend` do carimbo hoje declara isso, mas nenhuma superfície mostra | 🔴 medido (o campo existe; o painel não usa) |
| **X2** | O badge de frescor do grafo existe (F2-PR3+4); os demais artefatos derivados **não têm badge** | 🔴 medido |
| **X3** | A fila propõe ato de escrita sobre página que pode estar aposentada — `gap_items` não filtra vitalidade | ⚪ alegado; **não reproduzi** no cenário testado (a página supersedida não entrou na fila), mas não descartei: pode ser que ela nunca fosse candidata a gap |
| **X4** ✅ **RESOLVIDO** (F-UI, ADR-49) | Não existe runner de teste de UI no desktop — só `tsc --noEmit` | 🔴 medido; `vitest` + `jsdom` entraram com config separada, e `npm test` está em `[gate]`. Medido de novo na entrada: com o `onClick` do reparo desligado, `tsc --noEmit` sai **0** e o smoke reprova |

---

## 7. Documentação

| # | O quê | Evidência |
|---|---|---|
| **DOC1** | `docs/15` §8 (estado da execução) desatualizado em relação às Fases 1 e 2 | ⚪ alegado |
| **DOC2** | `docs/11-epistemic-contracts.md` desatualizado em relação aos 15 mecanismos atuais | ⚪ alegado |
| **DOC3** | O template de RFC do `docs/10` §19 foi **instanciado** (RFC-001), mas o `docs/10` ainda o marca "🎯 a instanciar" | 🔴 medido |
| **DOC4** | `docs/17` continha uma linha desatualizada que fez um cético gastar um ciclo inteiro refutando alegação já corrigida — **já corrigida**, mas mostra a classe | 🟠 confirmado |
| **DOC5** ✅ **RESOLVIDO** (PR-0) | `AGENTS.md` cita contagem de teste desatualizada (a suíte cresce a cada PR e o número no doc não) | 🔵 → 🔴 verificado: nenhuma contagem literal de testes resta no `AGENTS.md` (o piso verificado do PR-0 substituiu o número); e o índice `docs/README.md` — que não listava os docs 16–20 — passou a listá-los |

---

## 8. Ordem sugerida, e por quê

> **Estado em 2026-08**: os itens 1 e 2 estão **entregues** (ADR-47; RFC-002 +
> ADR-48). A ordem abaixo fica como registro do raciocínio — e porque os itens
> 3 a 5 seguem valendo.

1. ✅ **PR-0.1** — sem release executável, nada do que foi construído chega a um
   terceiro. E é o único item cujo custo **cresce** com o tempo (cada PR novo
   aumenta o que não está empacotado);
2. ✅ **F3-PR0** — pré-requisito técnico da F3 e do B1/B2, os dois de maior
   consequência. Exige RFC: o casamento entre "corrigir uma linha de SQL" e
   "ativar um árbitro LLM sobre o canônico" é exatamente o que a regra existe
   para impedir;
3. ✅ **F-UI** — converte sete capacidades já pagas em produto. Depende de um
   smoke de UI, que é o pré-requisito real;
4. **F3** (P-3 + P-7) — a fila para de mentir;
5. **F-EPIST** em paralelo, a qualquer momento: itens independentes e baratos.

> **O que NÃO fazer**: corrigir o B1 sem RFC. É uma linha, é tentador, e ativa
> decisão de modelo generativo sobre o canônico por efeito colateral de um
> conserto. — *cumprido: `docs/19` (RFC-002) precedeu a correção, e a flag
> `reconcile.llm_arbiter` continua desligada por default.*
