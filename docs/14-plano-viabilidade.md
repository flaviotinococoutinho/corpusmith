# 14 · Plano de viabilidade — do sinal ao ATO

> **Especialidade deste documento:** produto + arquitetura de software +
> epistemologia aplicada. Não é ADR (nenhuma decisão foi tomada) nem
> código — é o **plano de viabilidade** priorizado por **complexidade
> decrescente**, a pedido: atacar primeiro o problema mais difícil, porque
> aqui o mais difícil é um **modelo** que todos os outros herdam. Cada
> problema traz evidência em `arquivo:linha`, mecanismo proposto,
> contrato de `epistemics.toml` quando obrigatório, DoD verificável e o
> que **rejeitar**. Ao iniciar uma fase, ela vira ADR.

Continua [`13`](13-plano-experiencia-memoria.md) (cujas receitas R1+R3
foram entregues na v1.8) e não o substitui: o `13` perguntou *"como tornar
o sinal visível?"*; este pergunta *"o que falta para o produto ser usável
por alguém que não é o autor?"*. Fontes internas: [`01`](01-conceitos.md) ·
[`06`](06-referencia.md) · [`08`](08-decisoes.md) ·
[`10`](10-engenharia-ai-friendly.md) · [`11`](11-epistemic-contracts.md) ·
`architecture.toml` · `epistemics.toml`.

**Método.** Seis auditorias independentes (memória · curadoria ·
mapeamento de padrões · gaps semânticos · relações · viabilidade/UX), cada
uma lendo o código real, seguidas de uma rodada de **refutação
adversarial** por dimensão (instruída a provar que a capacidade já existe
— este núcleo esconde muita coisa em CLI e facades). Das **30 lacunas
levantadas, 2 foram refutadas** e 28 sobreviveram, consolidadas nos **14
problemas** abaixo. Os achados de maior consequência foram reverificados
manualmente, um por um, antes de entrar aqui.

---

## 0. Tese central

O núcleo é excepcional e o problema **não é falta de sinal — é que o sinal
não fecha em ato.**

O produto **detecta** quase tudo: contradição candidata (AGM), ponte
frágil (persistência 0-dim), lacuna estrutural sob o modelo de
configuração de Newman, esquecimento por P(recall) do ACT-R, calibração de
Brier, near-duplicata por SimHash/NCD. E **materializa** quase nada:
existe **um** caminho de escrita (`okf/writer.py:40-58`) e ele só é
dirigido por use cases de **máquina**. Nenhuma operação humana de
suceder, invalidar, fundir, editar, linkar ou desfazer existe no
repositório — `_supersede` é método *protegido* de `MachinePageUseCase`
(`usecases/base.py:141`).

A consequência é direta e desconfortável: **a fila única da v1.8 — a única
chamada-para-ação por design (UX-1) — ranqueia no topo itens
irresolvíveis dentro do app.** O item de maior valor (`contradiction`,
0.85) leva à aba Qualidade, que tem **zero** `<button>`
(`desktop/src/panels/QualityPanel.tsx`); o de maior densidade valor/custo
(`bridge`) leva ao Grafo, que não tem afordância de aresta. Pior: a fila
não tem estado de *resolvido*, *julgado* ou *aposentado* — `gap_items`
devolve toda página `type: question` **para sempre**
(`usecases/plan_attention.py:68-91`) e `review_items` propõe revisar
páginas **congeladas, que o freeze removeu do bundle**
(`usecases/cold_memory.py:133`). A fila aprende a mentir, e o usuário
volta a decidir sozinho.

Em paralelo, a camada de padrões **não é um objeto**: Leiden roda sem
seed, o id de tema é um inteiro reatribuído a cada execução,
`communities/*.md` acumula um arquivo novo por rótulo de LLM, e
`graph_data` refaz Brandes em Python puro **a cada request** — sem passar
pelo `ComputeKernel` (`retrieval/observatory.py:66`), portanto sem os
45,3× de Rust nem o cache por geração que a v1.7 mediu e entregou.

Portanto o que falta não são features: são **dois modelos ausentes** — o
**ato de curadoria humana** sobre o canônico e a **camada de padrões como
objeto** identificável, carimbado e histórico. Os outros doze problemas
são instâncias que os herdam. É por isso que atacar o mais complexo
primeiro não é bravata: é a única ordem que não obriga a refazer o resto.

---

## 1. Veredito de viabilidade

**Hoje o produto é viável para exatamente um perfil: o autor.** Alguém que
tem o repo, sabe Python, roda `corpusmith` no terminal, conhece o SPEC OKF e
aceita que **toda resolução aconteça fora do app** (abrir o `.md` no
editor, editar YAML à mão, `git revert` quando algo se perde). Para esse
perfil ele já é notável: gate de escrita inescapável, reconciliação
determinística-primeiro, esquecimento com critério validado, base fria que
reidrata byte-a-byte, índice honestamente incremental (7,1 s para 5.000
páginas; busca FTS em 14 ms), backup com manifesto e sha256 — e o produto
**declara por escrito os modos de falha dos próprios mecanismos**, o que é
raríssimo.

Para quem **não** é o autor, ele falha em cinco pontos datáveis:

| Quando | O que acontece | Evidência |
|---|---|---|
| **Minuto 1** | venv em outro caminho ⇒ o sidecar desiste **em silêncio**; todas as abas ficam em "Carregando…" terminal, com uma bolinha de 8 px como única pista | `desktop/electron/sidecar.ts:50` (`if (!existsSync(venv)) return;`); 9 `connect()` sem `.catch` |
| **1ª correção** | painel Wiki é read-only com um botão ("marcar stale"); **não existe** use case, endpoint ou CLI de edição — corrige-se por fora, e o doctor nem detecta a divergência | `facades/curation.py:23-77`; `api/cockpit.py` sem POST/PUT de corpo |
| **2ª promoção** | título genérico ⇒ slug colide, o corpo anterior **desaparece do HEAD** sem supersede, e o log diz "Creation" | `usecases/promote_memory.py:47-51`; `okf/writer.py:46-52` escreve sem checar existência |
| **Mês 3** | a fila só cresce; o item de maior valor leva a uma tabela sem botões; toda pergunta capturada entra para nunca sair, ordenada por caminho alfabético | `plan_attention.py:68-91`; `QualityPanel.tsx` (0 botões) |
| **Ano 1-2** | Grafo e Indicadores param de funcionar (**84,3 s** por request, payload de 3,2 MB) e a base fria — o mecanismo caro que existe para conter isso — segue vazia porque ninguém aperta o botão página por página | `retrieval/observatory.py:66` |

**Em uma frase: o produto sabe pensar e não sabe agir sob comando humano.**
Para ser viável para um terceiro bastam três coisas, nesta ordem — o **ato
de curadoria**, o **ciclo de vida da atenção** e a **camada de padrões como
objeto**. Nenhuma exige cálculo novo nem rede.

---

## 2. Os 14 problemas, por complexidade decrescente

| # | C | Problema | Dimensões | Tipo |
|---|:--:|---|---|---|
| P-1 | **5** | **Não existe o ATO DE CURADORIA** — o único caminho de escrita é dirigido só por máquina; nenhuma operação humana é possível, previsível ou reversível | curadoria, memória, relações, UX | inexistente |
| P-2 | **5** | **A camada de padrões não é um objeto** — tema sem identidade estável, projeção sem carimbo, recomputada em pleno request, sem história | padrões, relações, memória, UX | inexistente + quebra |
| P-3 | **4** | **Nada fecha e nada aposenta** — perguntas eternas, padrões reaparecem sem consentimento, a fila propõe trabalho sobre páginas que já não existem | gaps, padrões, curadoria, memória | inexistente |
| P-4 | **4** | **Suficiência ≠ dispersão** — a "confiança" mede dispersão da fusão, satura em quase toda resposta, e o grounding por span da v1.8 nasce e morre no JSON | gaps, memória, UX | quebra |
| P-5 | **4** | **Conflito × impopularidade** — o produto chama "em disputa" o que só deu beco, e não detecta conflito factual fora de DOI/ISBN | gaps, curadoria, memória | inexistente |
| P-6 | **4** | **A aresta tem sintaxe, não semântica** — nenhuma relação tipada, wikilink nunca canonicalizado, co-menção que a fila manda linkar e o grafo não desenha | relações, padrões, curadoria | inexistente |
| P-7 | **3** | **Colisão de caminho** — promoção humana e compilação de máquina se sobrescrevem em silêncio, logadas como "Creation" | memória, curadoria | quebra |
| P-8 | **3** | **A memória não lembra o que falhou** — abstenção não deixa rastro; co-recuperação nunca é minerada | gaps, padrões, memória | inexistente |
| P-9 | **3** | **`valid_at` = tempo de escrita** — a bi-temporalidade degenera; a consulta histórica re-ranqueia com a data errada | memória, gaps | quebra |
| P-10 | **3** | **Entidade ↔ página** — o vínculo existe no canônico e é jogado fora na projeção; sem gesto de desambiguação | relações, gaps, UX | invisível |
| P-11 | **2** | **Custo das superfícies de curadoria** — reprocessam o bundle inteiro a cada abertura, e a fila desaparece em silêncio enquanto isso | curadoria, UX | quebra |
| P-12 | **2** | **O ritual semanal** — completo, agendado toda segunda, e **inalcançável** na interface (`client.review()` nunca é chamado) | curadoria, UX | invisível |
| P-13 | **2** | **Daemon morto é beco sem saída** — painéis presos para sempre e barra de status verde mentindo | UX | quebra |
| P-14 | **2** | **Durabilidade invisível** — backup excelente, nunca automático, atrás de um único subcomando; protege justamente o estado declarado *não reconstruível* | UX, memória | invisível |

### P-1 · O ato de curadoria (C5) — o modelo que todo o resto instancia

**Diagnóstico.** O gate é único e inescapável (`okf/writer.py:40-58` →
`harness/runner.py:18-21`) e **todos** os chamadores são máquina ou
operações degeneradas. `_supersede()` — o único lugar que grava
`superseded_by`/`invalid_at` — é protegido em `usecases/base.py:141-158`.
`facades/curation.py` oferece promote/stale/lint/freeze/recycle/tag/export
e **nenhuma** sucessão, fusão, edição ou link. O finding instrui
literalmente *"resolva com supersede/invalid_at ou funda as páginas"*
(`harness/local_policy.py:155-159`) e **merge de páginas não existe**.
`GitStore` expõe só commit/has_commit/head — **sem undo**. A única
operação em lote (`RenameTag`) reescreve todas as páginas da tag num
único write, disparada por um botão sem confirmação, sem contagem e sem
`.catch`.

**Proposta.** `CurationAct` — Template Method do eixo **humano**, irmão de
`MachinePageUseCase`, em `usecases/curate/base.py`:
`_plan()` **puro** devolve o preview (diff por página, findings previstos
rodando `HarnessRunner` em `mode='write'` **sem escrever**, páginas
tocadas, dependentes TMS) → `_apply()` faz **uma** chamada ao
`BundleWriter` com `log_kind` explícito → registra em
`curation_acts(id, act, params_json, commit, pages_json, created_at,
undone_by)` → `rebuild_index` incremental. `execute(dry_run)` segue como
único método público. Instâncias: `SupersedePage`, `InvalidatePage`,
`EditPage` (a primeira escrita humana de corpo — **sem**
`normalize_machine_body`: prosa humana não é reescrita),
`LinkPages`/`UnlinkPages`, `MergePages` (política de união declarada; a
perdedora é **supersedida, nunca removida**; cluster de candidatos vem do
SimHash/NCD que já existe), `UndoCurationAct` (`GitStore.revert`, o undo
registrado como **novo** ato). Superfície: facade + `POST /cockpit/curate`
com `dry_run` + `corpusmith curate …` + **deep-link da fila** (o item já
carrega `target`/`pages`/`src`/`dst`; hoje o Dashboard os descarta em
`DashboardPanel.tsx:12-13`).

**Reusa:** gate de escrita pronto · `HarnessRunner` já roda sem escrever ·
`MarkPageStale` como molde exato · `RenameTag` já calcula `updated` antes
de escrever (dry-run quase grátis) · clusterização de `ConsolidateInbox`.

**Rejeitar:** LLM para fundir prosa ou decidir o que contradiz o quê ·
undo com `reset --hard`/apagar arquivo · escrever relação/veredito só em
`index.db` (o próximo rebuild apaga o julgamento humano) · `RestoreBackup`
como undo de curadoria (restaura o HOME inteiro) · `dry_run` opcional
silencioso.

**DoD.** Teste que falha antes por ato · merge não perde nenhum campo e
supersede a perdedora · undo restaura byte-a-byte e cria novo registro ·
`--dry-run` não move o HEAD · `HarnessRejection` ⇒ **422 legível** (hoje
500) · gate completo.

### P-2 · A camada de padrões como objeto (C5)

**Diagnóstico.** Quatro defeitos do mesmo objeto ausente, e eles se travam
mutuamente. Leiden roda **sem seed**; o id de tema é o inteiro
`community`, reatribuído a cada execução — julgar "comunidade 3 ×
comunidade 7" é julgar um endereço que muda. O `rel_path` do sumário de
tema é derivado do **rótulo devolvido pelo LLM**
(`communities/{slug(rótulo)}.md`) — o único lugar do produto em que uma
saída de LLM decide o endereço de um arquivo do bundle, e a razão pela
qual `communities/` acumula arquivo novo a cada rodada. `communities` e
`graph_bridges` não têm carimbo (`bundle_head`/`computed_at`), então
ninguém sabe de quando é o mapa. E `graph_data` recomputa Brandes em
Python puro por request (`observatory.py:66`), **sem** o `ComputeKernel`:
84,3 s a 5.000 páginas.

**Proposta.** Tratar padrões como **snapshot versionado**, calculado por
job e servido com carimbo. (1) **Identidade:** `seed` fixo no Leiden +
`theme_id` estável por **casamento de partições** (`themes` +
`theme_epochs` com `event ∈ born|grew|shrank|merged|split|died` decidido
por Jaccard de membros — determinístico, puro, sem LLM); o `rel_path`
passa a derivar do `theme_id`, e `_CommunitySummaryPage` sobrescreve
`_reconcile` (UPDATE quando o tema casa, SUPERSEDE quando dividiu/fundiu)
— o LLM volta ao lugar certo: **rotular, nunca nomear endereço canônico**.
(2) **Carimbo:** `bundle_head`/`computed_at` nas duas tabelas, INV novo no
doctor espelhando o INV-002 dos chunks, job `leiden` no Scheduler com
dedupe semanal e poda de pontes para páginas ausentes. (3) **Custo:**
`graph_data` lê do snapshot e usa `ComputeKernel.betweenness` via
`compute/graph_cache.py`; `insights` e `structural_gaps` compartilham **um**
snapshot; `limit` nos endpoints e subgrafo no front.

**Contrato obrigatório:** `[mechanisms.pattern_layer_snapshot]` — hoje
**nenhum** mecanismo de padrão tem contrato (`structural_gaps`,
`fragile_bridges`, Leiden e o próprio VoI da fila estão **fora** do
registro). `heuristic` para partição/lacuna, `deterministic` para
persistência 0-dim; relativo a *"o grafo projetado nesta geração do
índice, não o conhecimento do usuário"*.

**Rejeitar:** trocar Brandes exato por amostragem **sem** declarar em
`epistemics.toml` · rótulo de LLM definindo `rel_path` · série histórica
que não seja reconstruível do Git + bundle · **recomputar em linha quando
o carimbo estiver velho** (servir com aviso de frescor é o certo; o
oposto é o congelamento de 84 s).

**DoD.** Duas execuções sobre o mesmo bundle ⇒ partição **idêntica** e
zero arquivos novos em `communities/` · `graph_data` **< 2 s** a 5.000
páginas · INV de carimbo no doctor, reparável · lint verde com o contrato
novo.

### P-3 · Veredito e vitalidade (C4) · depende de P-1, P-2

Dois níveis, separados pelo invariante. **(A)** Veredito sobre objeto
**canônico** mora no canônico: `answered_by`/`resolved_at` no frontmatter,
escritos por um `CloseQuestion`, com regra nova `policy.dangling_successor`
(que hoje não existe nem para `superseded_by`); o fechamento é
**verificado** — re-executa o retrieval e exige que a pergunta deixe de
abster. **(B)** Veredito sobre padrão **computado** mora em projeção
chaveada por evidência canônica: `pattern_verdicts(kind, key, status,
until, …)` com `key` derivada de rel_paths ordenados, **nunca** do inteiro
`community`; "rejeitado" suprime com `until`, jamais DELETE. **(C)**
Filtro de vitalidade: `review_items`/`bridge_items` exigem existência no
bundle e ausência de `superseded_by`; freeze e supersede **aposentam** o
estado derivado — e a migração de `accessibility` para a sucessora entra
como **proposta sob gate** (o usuário validou o texto **antigo**).

**Contrato obrigatório:** `[mechanisms.attention_queue]` — a fila da v1.8
não tem **nenhum** contrato. Failure modes a declarar: *"página nunca lida
pode ser a mais valiosa e apenas não ter sido procurada"*, *"recorrência
não é importância"*, *"custo por palavras/min ignora dificuldade"*.

**Rejeitar:** fechar pergunta automaticamente porque o `/ask` parou de
abster · `community` como chave de veredito · migrar acessibilidade sem
gate · **resolver a fila cheia aumentando `MAX_ACTIONS` ou confiando no
`truncated`** (esconder item não é ciclo de vida).

### P-4 · Suficiência da evidência (C4)

A "confiança" publicada é `1 − entropia da fusão`: satura em quase toda
resposta e **zera quando a base é rasa** — falsa certeza no pior momento.
Novo sinal **puro** em `kernel/sufficiency.py`, decomposto em quatro
parcelas que já existem: páginas distintas · streams que corroboram
(`FusedEvidence.provenance`) · fração de entidades da pergunta
**aterradas por span** (`ground_spans` + `page_entities.span_start/end` da
v1.8) · frescor. Publicado como campo **novo** `support`, mantendo
`uncertainty` rotulado pelo que é (dispersão) e ainda alimentando o
Hedge. O selo passa a ser 2D e auditável — *"sustentada por 3 páginas / 2
streams / 4 de 5 termos aterrados"* — e os **spans finalmente são
renderizados como highlight**: é o que fecha o sanduíche da v1.8.
Contratos: `[mechanisms.evidence_sufficiency]` novo + atualização de
`retrieval_uncertainty` e `cognitive_priority`. **Rejeitar:** chamar
`support` de "probabilidade de estar certo" · pedir ao LLM que
autoavalie · reescrever `ask_context.confidence` histórico (marcar
linhagem, senão o Brier compara maçã com laranja).

### P-5 · Conflito × impopularidade (C4) · P-6 · Relação com semântica (C4)

**P-5:** `page_overlay.status='contested'` é derivado de *desfecho de uso*
— "levou a beco" virou "está em disputa" em cinco superfícies. Como é
projeção recomputável, renomear para `low_yield` é livre; "em conflito"
fica reservado a conflito **factual**, detectado por regra nova
`policy.factual_conflict` (mesma entidade de kind quantity/date, mesma
dimensão SI, valores fora de tolerância declarada, sem sucessão nem
ordenação temporal entre as páginas; exige unidade idêntica e span nas
duas — precisão > recall). A resolução vira item de fila que **agora tem
destino real** (herda P-1).

**P-6:** `graph_edges.kind ∈ {wikilink, markdown}` é **sintaxe**, não
semântica (`schema_index.sql:26-32`); `rel_type` não existe em lugar
nenhum. Proposta de menor custo: **anotar o link markdown que já existe** —
`[título](/path "rel:refines")`, sintaxe Markdown padrão, mantendo
`parse_links` como único parser — com vocabulário **fechado** validado
pelo Harness e default `NULL` (todo o bundle existente continua válido).
`superseded_by` passa a projetar aresta navegável; wikilink resolve por
**título** na indexação (o não resolvido gera item acionável, **sem
reescrever prosa humana**); órfão ganha **definição única** (hoje três
painéis mostram números diferentes); co-menção é **materializada** como
`inferred` **com orçamento** dentro do job leiden — é o que faz a ponte
frágil que a fila põe no topo finalmente **ser desenhada** no grafo.
Contrato: `[mechanisms.inferred_cooccurrence_edges]`, declarando que
*"sugerir link por co-menção e depois usar o link como sinal de retrieval
é autoconfirmação"*.

### P-7 a P-14 (síntese)

- **P-7 Colisão (C3).** O caminho destrutivo dominante não é UPDATE — é
  **ADD sobre um `rel_path` existente**, e a reconciliação **exclui
  explicitamente** a página residente (`reconcile_candidate.py:70,101-103`).
  `promote` e `compile` geram slugs que colidem; a proteção anticolisão
  existe **só** para `raw/`. Proposta: `policy.path_collision`, `promote`
  consultando `ReconcileCandidate`, `op='COLLISION'` com três saídas
  humanas legítimas, e `_document` **fundindo** frontmatter em UPDATE em
  vez de reconstruir do zero.
- **P-8 Rastro de uso (C3).** Na abstenção o use case retorna **antes** de
  `_record_usage` (`ask_memory.py:177-180`): a ignorância mais caro — a
  que o usuário realmente tentou usar — não deixa rastro. `ask_misses`
  com chave determinística (entidades + SimHash), recorrência como fonte
  da fila com **fechamento verificado por re-ask**, e minerador lift/PMI
  de co-recuperação sobre `ask_provenance` (que já registra quais páginas
  responderam **juntas**) propondo `LinkPages`.
- **P-9 `valid_at` (C3).** `base._document` carimba `valid_at = now`
  junto com `timestamp = now` (`base.py:127-129`): tempo de **transação**
  no campo documentado como tempo de **mundo**. Correção mínima: **parar
  de defaultar** (ausência já significa "nenhuma alegação"), limpar o
  legado onde `valid_at == timestamp` como ato em lote com preview, e o
  detector de datas **propor** candidatos com span sob gate.
- **P-10 Entidade ↔ página (C3).** O canônico **já sabe** (uma página
  `authority_record` é exatamente essa declaração) e a projeção
  **descarta** o `rel_path` ao montar o gazetteer
  (`okf/authorities.py:88-95`); `entities` não tem coluna de página. A UI
  contorna casando **string** com o título (`ExplorerPanel.tsx:45`).
  Projetar o vínculo, semear o PPR com a página que **é** a entidade, e
  emitir `policy.alias_conflict`.
- **P-11 Custo (C2).** `contradiction_items` roda `analyze()` em **todas**
  as páginas a cada abertura do Dashboard (~16 s a 2.000 páginas; Qualidade
  35-40 s) — e `NextActionsQueue` retorna `null` tanto pendente **quanto
  em erro**: a única chamada-para-ação **desaparece em silêncio**.
  Memoizar por `(page, sha)` usando `page_index_state`, mantendo
  `check_corpus` como fonte única; skeleton + estado de erro; abort/timeout
  no cliente.
- **P-12 Ritual (C2).** `ComputeWeeklyReview`/`PublishWeeklyReview` estão
  completos, testados e **agendados toda segunda** — e `client.review()`
  **nunca é chamado** em `desktop/src`. Não criar 13ª aba: a fila ganha
  um seletor **"hoje | semana"**, com as sete seções e o botão de
  fechamento.
- **P-13 Daemon (C2).** `if (!existsSync(venv)) return;` +
  9 `connect()` sem `.catch` + `live.ts:40` engolindo a exceção do poll
  (bolinha verde mentindo) + EventSource sem `onerror`. Componente único
  `<DaemonUnavailable>` com motivo, comando e retry; `GET /system/doctor`
  + botão reparar.
- **P-14 Durabilidade (C2).** Backup excelente com **uma** porta
  (`cli.py:251`), sem job, sem scheduler, sem endpoint, sem painel, sem
  retenção, sem "último backup há N dias" — protegendo justamente
  `runtime.db`/`cognitive.db`, declarados **não reconstruíveis**.

---

## 3. Plano em 8 fases — do mais complexo ao mais simples

Cada fase é um PR que termina **verde** (pytest + tsc + compose +
`epistemics lint`), entrega valor sozinha, e vira ADR ao iniciar.

| Fase | Problemas | Por que aqui | Entrega |
|---|---|---|---|
| **0** ⚠️ *exceção* | P-13 | Única quebra de ordem que recomendo: 2 pontos, mecânica, **não toca nenhum arquivo das fases seguintes**, e é a razão nº 1 pela qual um terceiro nunca chega a ver o produto. Também torna as fases seguintes **depuráveis**. Se a ordem por complexidade for literal, pode ir para o fim — é a única com essa propriedade | app nunca mais em beco sem saída silencioso |
| **1** | **P-1** (C5) | O mais complexo, e primeiro porque é um **modelo**: nove das quatorze lacunas terminam a frase *"e então o humano resolve…"*. Construí-lo depois obrigaria a refazer todas | `CurationAct` + 7 atos, preview, 422 legível, `curation_acts`, undo por revert, deep-link da fila |
| **2** | **P-2** (C5) | O segundo modelo. Duas fases posteriores dependem de decisões que só existem aqui: a **chave** de veredito (P-3) e o job carimbado onde a co-menção é materializada (P-6) | `theme_id` estável, Leiden com seed, snapshot carimbado, `graph_data` < 2 s, história de temas |
| **3** | P-3, P-7 | Só possível com as duas anteriores (fechar é um ato; a chave é estável). É aqui que **a fila para de mentir** e o gesto de captura mais usado para de destruir trabalho em silêncio | `answered_by`, `pattern_verdicts` com `until`, filtro de vitalidade, `policy.path_collision`, VoI real no ranking |
| **4** | P-4, P-5, P-9 | Três problemas que compartilham o mesmo artefato normativo (`epistemics.toml`) e o mesmo risco — mexer no que o produto **afirma** saber. Agrupados, o registro é atualizado numa passada coerente de lint | `support` decomposto, spans em highlight, `low_yield` separado de conflito, `policy.factual_conflict`, fim do `valid_at` por transação |
| **5** | P-6, P-10 | O tipo de relação nasce no canônico por um **ato** (F1) e a co-menção só se materializa no job carimbado (F2); sem ciclo de vida (F3) materializar co-menção só encheria o grafo de ruído inlimpável | `rel_type`, `superseded_by` navegável, wikilink resolvido, órfão único, entidade↔página, `policy.alias_conflict` |
| **6** | P-8 | Deliberadamente **depois** de F3: alimentar a fila com rastro de abstenção **antes** do ciclo de vida reproduziria, com dado novo, a patologia das perguntas que nunca fecham | `ask_misses`, recorrência com fechamento verificado, minerador de co-recuperação, golden set com falhas reais |
| **7** | P-11, P-12, P-14 | Três itens de 2 pontos, todos "capacidade pronta e inalcançável". Dois dependem do que veio antes: o ritual usa a definição única de órfão (F5) e publica a seção de padrões (F2) | memoização por `(page, sha)`, revisão semanal como **modo** da fila, backup agendado com retenção visível |

---

## 4. Matriz de não-adoção (o que **não** fazer, com razão)

- **LLM para fundir prosa humana** ou decidir o que contradiz o quê — o
  sanduíche existe exatamente aqui: a máquina clusteriza (SimHash/NCD/
  identificador forte, tudo pronto), o humano confirma.
- **Job que congela sozinho** a cauda nunca-lida — viola o gate humano
  para efeito cognitivo. O certo é triagem que **propõe** em lote.
- **Identificador estável de memória no frontmatter** — o OKF fixa
  identidade = caminho por SPEC; inventar um segundo eixo criaria duas
  verdades.
- **Undo com `reset --hard`/`checkout` destrutivo/apagar arquivo** — undo
  é `revert` registrado como **novo** ato: invalidar-nunca-apagar vale
  também para o desfazer.
- **`RestoreBackup` como undo de curadoria** — restaura o HOME inteiro
  com `force`; desfazer um rename custaria todo o conhecimento novo.
- **Escrever relação, veredito ou vínculo apenas em `index.db`** — é
  projeção reconstruível: o próximo rebuild apaga o julgamento humano.
- **`community` (inteiro) como chave de veredito, cor ou identidade** — é
  reatribuído a cada Leiden.
- **Rótulo de LLM definindo o `rel_path`** do sumário de tema.
- **Brandes amostrado sem declarar** em `epistemics.toml` — aproximar é
  legítimo; esconder a aproximação não.
- **Recomputar a camada de padrões em linha** quando o carimbo está velho.
- **Migrar `accessibility` automaticamente** para a sucessora — o usuário
  validou o texto antigo.
- **Retro-preencher `valid_at` com `timestamp`** — é literalmente o bug.
- **Co-menção em N² arestas sem orçamento** por página e teto por entidade.
- **Aumentar `MAX_ACTIONS`** para "resolver" a fila que só cresce.
- **Proibir sobrescrita no mesmo slug** — é comportamento deliberado e
  testado; o certo é reconciliar com preview.
- **Passar prosa humana pelo sanduíche de normalização de corpo.**
- **13ª aba** para a revisão semanal — a v1.8 declarou que a fila
  **substitui** as chamadas-para-ação espalhadas; revisão é um **modo**.
- **Sync multi-dispositivo** (Git remote, CRDT, merge de `cognitive.db`) —
  MUST NOT explícito; mesclar dois `cognitive.db` não é operação que exista.
- **Refazer lacuna/comunidade/ponte com embeddings ou LLM** — o que existe
  (Newman, persistência 0-dim, Brandes, LSH exato) é melhor e determinístico.
- **Duplicar a heurística de contradição em SQL** para acelerar — a saída
  é memoizar por `(page, sha)`, preservando a fonte única.

---

## 5. Invariantes que o plano protege

Local-first (nada exige rede) · canônico ≠ projeção (veredito sobre objeto
canônico vai ao frontmatter; sobre padrão computado, a projeção
reconstruível chaveada por evidência canônica) · LLM/heurística cercada (o
LLM perde o poder de nomear endereço canônico; nenhuma inferência de
relação ou conflito sem gate) · garantia relativa (**quatro** contratos
novos obrigatórios: `pattern_layer_snapshot`, `attention_queue`,
`evidence_sufficiency`, `factual_conflict` + `inferred_cooccurrence_edges`,
`temporal_partition`) · invalidar-nunca-apagar (merge supersede, undo é
revert, veredito usa `until`) · gate humano para efeito cognitivo (todo
ato tem preview; migração de acessibilidade é proposta) · 1 método público
por use case (`execute(dry_run)`).

## 6. Próximo passo

**Fase 1 (P-1, o ato de curadoria)** — e, se meio dia estiver disponível,
a Fase 0 antes dela, porque torna todo o resto depurável. No dia em que a
Fase 1 sobe, o item de maior valor da fila e o de maior densidade
valor/custo **deixam de ser becos sem saída**: o clique passa a abrir um
ato com preview. Ao iniciar, vira **ADR-41**.
