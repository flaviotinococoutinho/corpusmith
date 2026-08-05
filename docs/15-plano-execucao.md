# 15 · Plano de execução — como desenvolver as lacunas (produto e processo)

> **Especialidade deste documento:** engenharia de entrega e processo. Não
> é diagnóstico (isso é [`14`](14-plano-viabilidade.md)) nem ADR — é o
> **plano de execução**: pacotes de trabalho PR a PR, ordem revisada com
> as divergências justificadas, lacunas do **processo** de engenharia,
> dependências ocultas, colisões de arquivo e o limiar de RFC. Usa o
> protocolo que o projeto **já define** em `AGENTS.md`, não um inventado.

Fonte do "o quê": [`14`](14-plano-viabilidade.md) (14 problemas por
complexidade decrescente). Fonte do "como": [`AGENTS.md`](../AGENTS.md)
§2/§8/§9 · `architecture.toml [commands]` · [`10`](10-engenharia-ai-friendly.md)
§19–23.

**Método.** As duas fases-modelo foram decompostas em pacotes por agentes
lendo o código real, e a decomposição passou por uma crítica de
sequenciamento que procurou colisões de arquivo, dependências ocultas e
conformidade com o protocolo. Os dois achados que **mudam o plano** foram
reverificados por execução própria (documentados em §5, D-A e D-B).

---

## 1. O processo que já existe (usar, não reinventar)

O projeto define um protocolo normativo de 8 passos em **`AGENTS.md` §8**,
fechado por um **DoD** (§9) e um **gate único** (§2), com as regras
estruturais duplicadas em forma legível por máquina em `architecture.toml`
— que não é decorativo: `test_architecture_toml.py` cruza o TOML com as
mesmas constantes que `test_architecture.py` aplica ao código.

**Todo pacote deste plano segue, sem exceção:**

1. ler `AGENTS.md` + a spec (`10`) + o ADR relacionado (`08`);
2. localizar o teste de arquitetura/contrato que cobre a área;
3. **declarar no PR os invariantes afetados** (INV-AI-001);
4. identificar a **autoridade** do dado e as projeções;
5. **escrever o teste que falha ANTES** de implementar;
6. menor mudança; **sem refactor incidental**;
7. rodar o gate; atualizar docs + `architecture.toml`;
8. registrar **evidência executável** no PR.

### 1.1 Quando é RFC, e não só ADR

`AGENTS.md` §8 exige RFC para: novo datastore · breaking API · mudança de
autoridade/CAP/privacidade · dependência runtime relevante · schema
**não-aditivo** · **heurística no caminho de escrita** · remoção de
fallback. Aplicando a regra a este plano:

| Fase | Artefato | Por quê |
|---|---|---|
| F1 (ato de curadoria) | **ADR-41** | Escrita humana é determinística; tabela nova é aditiva no banco existente; endpoints novos não quebram API |
| **F2-PR2** (theme_id) | **RFC + ADR-42** | O casamento de partições por Jaccard **decide UPDATE vs SUPERSEDE de página canônica** — é heurística no caminho de escrita |
| **F3** (P-7, colisão) | **RFC** | `promote` passa a consultar `ReconcileCandidate`, cuja escada inclui árbitro LLM opcional — heurística entrando no caminho de escrita humano |
| F4 | ADR | O plano publica `support` **ao lado** de `uncertainty` justamente para não ser breaking API. Se algum dia substituir o campo, vira RFC |
| F5, F6, F7 | ADR | Schema aditivo; vocabulário fechado validado pelo Harness; nenhuma autoridade muda |

---

## 2. Lacunas de PROCESSO (o que falta na engenharia, não no produto)

Estas não estão no `14` porque o `14` auditou o produto. São o que faz o
plano ser **verificável** — e a primeira é o risco número 1 de tudo:

| # | Lacuna de processo | Evidência | Entra em |
|---|---|---|:--:|
| **G-1** | **A CI não executa o gate que o `AGENTS.md` declara.** Dez pacotes prometem *"gate completo: pytest + tsc + compose + epistemics lint"*; `ci.yml` roda pytest, tsc+vite, compose e cargo — **nunca** `epistemics lint`, **nunca** `doctor`. Um agente roda `just verify`, vê verde, e mergeia um `epistemics.toml` com `implementation_ref` inexistente | `.github/workflows/ci.yml:12,19,24,32`; `justfile:20-24` (3 dos 8 comandos); `harness/epistemics.py` `lint()` já devolve `{ok: bool}` — há API pronta para exit code | **PR-0** |
| **G-2** | **A perna `[ml]` não existe em lugar nenhum** — o algoritmo de particionamento **de produção** nunca é executado por teste. Verifiquei: `import igraph` ⇒ `ModuleNotFoundError`; CI instala só `[dev]`. O ramo Leiden real é onde o `seed` da F2 tem de entrar, e é código morto na suíte | `backend/pyproject.toml:21`; `ci.yml:11`; `detect_communities.py:135-146` (produção) vs `:147-162` (fallback, o único exercitado) | **F2-PR1** |
| **G-3** | **O doctor é CLI-only** — o único verificador de invariantes não tem facade nem endpoint (zero ocorrências de `doctor`/`diagnose` em `api/`, `facades/`, `daemon.py`, `desktop/src`). Pior: `diagnose.py:179` desliga a checagem de jobs em silêncio para qualquer chamador que não passe `known_jobs` | `cli.py:157-166` é o único chamador; `diagnose.py:40` `REPAIRABLE` e reparo sempre `rebuild_index(full=True)` | **F0** |
| **G-4** | **`bench compare` não compara com nada.** `benchmarks/baseline.json` é a autoridade declarada de performance (`AGENTS.md:95`: *"ganho sem medição registrada é proibido"*) e **nada o lê** — e ele está em `1.7.0` contra produto `1.8.0`. É de lá que vem o número (88 s de Brandes) que justifica a F2 | `bench.py:386-390` só imprime; grep por `baseline.json` em `backend/`, `.github/`, `justfile` ⇒ zero leituras | **PR-0** + F2 |
| **G-5** | **O Scheduler é a única automação recorrente e nenhum teste assere o que ele agenda.** Zero ocorrências de `dedupe_key` nos testes. `leiden`, `index_rebuild` e `eval_memory` estão no REGISTRY e **nunca** são enfileirados; `backup` não está nem no REGISTRY | `runtime/scheduler.py:24-40`; `jobs/__init__.py:16-31` (14 jobs, 5 agendados) | **F2-PR1** |
| **G-6** | **Migração de schema não tem gate de versão nem fixture de banco antigo** — `_migrate` decide por **presença de coluna**, nunca por versão; não há prova do caminho de *upgrade* (só guarda contra versão futura). O plano encadeia **quatro** migrações, três no mesmo banco | `runtime/db.py:114-155`; `test_architecture_toml.py:41-45` só compara números | **PR-0** |
| **G-7** | **Nada proíbe exceção de domínio vazar como 500** — 24 `HTTPException` e **zero** `add_exception_handler` no `api/`. `HarnessRejection` já carrega `.findings` estruturados e sobe crua de `/cockpit/promote` e `/cockpit/tags`. O DoD §9 exige "erro com código estável" | `api/cockpit.py`; `harness/runner.py:6-12`; `okf/writer.py:44-45` | **F1-PR1** (com teste **transversal**, não só do ato novo) |
| **G-8** ✅ **FECHADA no PR-0.1** (ADR-47): `exclude_binaries=True`, job `package` que **sobe** o binário, `release.yml` com trigger de tag e conferência tag↔versões | **Release e empacotamento fora de qualquer automação** — e é o caminho **empacotado** que produz o P-13: `sidecar.ts:44-46` aponta para um binário que a CI **nunca constrói**, então todo terceiro cai no ramo não-empacotado, cujo fallback é o `return` mudo. `desktop/package.json` está em `0.7.0` contra `1.8.0` | `build.spec` e `electron-builder.yml` existem; `ci.yml:2` sem trigger de tag | **F0** + PR-0 |
| **G-9** | **A doc do próprio gate não recebe o tratamento que `architecture.toml` recebe** — quatro inventários divergentes do mesmo gate (AGENTS.md 8 comandos, justfile 3, ci.yml 4, `architecture.toml [commands]`), e `AGENTS.md:22` diz **"345 testes"** quando a suíte coleta **389** | contraste: `architecture.toml` está preso por `test_architecture_toml.py`; `AGENTS.md` e `justfile` não têm equivalente | **PR-0** |
| **G-10** ✅ **FECHADA no PR-0.1** (ADR-47): `EXPECTED_MECHANISMS` (error) + `PROMISED_MECHANISMS` (warn) + `[registry].version` semver com fingerprint do conjunto | **`epistemics.toml` não tem gate de versão de registro nem de completude** — quatro PRs prometem `1.1.0 → 1.2.0` e nada quebra se esquecerem; nada lista mecanismos **devidos mas ausentes** (é como "nenhum mecanismo de padrão tem contrato" virou achado de auditoria em vez de item de backlog) | `test_epistemics_toml.py` testa parâmetros, não o conjunto nem `[registry] version` | **F2-PR1** |

### PR-0 · O instrumento antes da obra (~3 pontos, **não** estava no `14`)

Um PR de processo que **não inverte a ordem por complexidade — insere o
instrumento que a mede**:

- job `gate` no `ci.yml`: `epistemics lint` com exit code · `doctor` sobre
  HOME sintético (`bench.synthetic_bundle` já é determinístico com seed) ·
  `backup create && verify` no mesmo HOME. Nenhum exige rede ou modelo;
- perna `backend-ml` (`pip install -e "backend[dev,ml]"` + `pytest -m ml`);
- **fixture de `index.db` v6** + `test_upgrade_de_banco_antigo` (linhas
  preservadas, colunas novas, `_meta.schema_version` final, trilha em
  `schema_migrations`);
- `bench compare --against benchmarks/baseline.json --tolerance` com exit
  ≠ 0 em regressão; baseline atualizado para 1.8.0;
- teste que cruza `architecture.toml [commands]` com o `justfile` e o
  `ci.yml` — **gate como fonte única**; e o `# 345 testes` do AGENTS.md
  substituído por um piso verificado;
- teste amarrando as **quatro** versões (`architecture.toml`,
  `__version__`, `desktop/package.json`, `baseline.json`) — hoje só duas.

---

## 3. Ordem de execução revisada

Divergências do `14` marcadas com ⚠ e justificadas.

| # | Pacote | pt | Nota |
|---|---|:--:|---|
| 1 | ✅ **F0 ampliada** (P-13 + `GET /system/doctor` com facade) — **ENTREGUE** | 3 | ⚠ O `14` trata a F0 como exceção opcional; ela é **pré-requisito da F2**: a F2-PR1 entrega o INV-004 e a F2-PR4 promete badge de frescor *com ação* — sem porta HTTP, o invariante nasce invisível na única superfície que a fase existe para melhorar (G-3). Também torna os 10 PRs seguintes depuráveis |
| 2 | ✅ **PR-0 · gate executável** — **ENTREGUE** | 3 | ⚠ Novo. Sem ele, dez DoDs são inverificáveis e quatro migrações sobem sem prova de upgrade |
| 3 | ✅ **F1-PR1** · `CurationAct` + Supersede/Invalidate ponta a ponta (preview, `curation_acts`, 422, CLI) — **ENTREGUE** (ADR-41) | 8 | Fatia **vertical**: o custo da fase está no esqueleto, não nos atos. Emendas aplicadas: rotas em `api/curation.py` via `mount_curation` e transformação de frontmatter em `kernel/curation.py` — **não** em `curate/base.py`, senão o eixo máquina importa o eixo humano |
| 4 | ✅ **F1-PR2** · `UndoCurationAct` (revert registrado como ato novo) — **ENTREGUE** (ADR-41.1) | 5 | Segundo de propósito: torna reversível tudo o que vem depois. **Rito reformulado** — ver D-C |
| 5 | ✅ **F1-PR4** · `LinkPages`/`UnlinkPages` — **ENTREGUE** (ADR-41.2) | 5 | ⚠ Antecipado (era 4º). É o ato de maior densidade valor/custo da fila e o único ato de corpo cujo valor não depende de UI que a fase não constrói. **Traz a decisão do `MD_LINK` para dentro da F1** — ver D-A |
| 6 | ✅ **F1-PR6** · deep-link da fila + `CurationDialog` — **ENTREGUE** (ADR-41.3) | 6 | ⚠ Antecipado (era 6º). Com PR1+PR2+PR4, os **dois** itens do topo da fila já têm ato com preview: converte quatro PRs de infraestrutura em algo perceptível meses antes |
| 7 | ✅ **F1-PR3** · `EditPage` — **ENTREGUE** (ADR-41.4) | 5 | ⚠ Atrasado (era 3º). Nenhum DoD da fase inclui campo de edição de corpo — o `CurationDialog` é diff+confirmar. Ou entra **depois** do PR6 levando a superfície de edição no escopo, ou o valor prometido é reescrito para **"editável por CLI/HTTP"**. Um DoD que promete app e entrega terminal é a forma mais barata de perder a confiança que a fase existe para construir. **Resolvido pela 1ª saída**: o PR levou a superfície (`textarea` pré-preenchido, declarado pela oferta) — ver ADR-41.4 |
| 8 | ✅ **F1-PR5** · `MergePages` — **ENTREGUE** (ADR-41.5) | 6 | Último da fase: escolher a vencedora é decisão humana sem UI, e o preview depende de `check_corpus` — ver D-D. **D-D resolvida por uma terceira saída**: o preview é O(páginas do ato), não O(bundle) |
| 9 | ✅ **F2-PR1** · seed, carimbo, poda, INV-004, job semanal — **ENTREGUE** (ADR-**43**, não 42 — ver nota) | 6 | Duas emendas **obrigatórias**: exigir a perna `[ml]` no mesmo PR (G-2 — **já paga pelo PR-0**, o PR usou o instrumento em vez de recriá-lo) e **excluir `communities/`** da construção do grafo (D-E) |
| 10 | ✅ **F2-PR2** · `theme_id` por casamento de partições — **ENTREGUE** ([RFC-001](16-rfc-theme-id.md) + ADR-45) | 8 | **RFC** (§1.1) — o primeiro do projeto; o template do `docs/10` §19 estava marcado "a instanciar". Único PR da F2 que escreve no canônico |
| 11 | ✅ **F2-PR3 + F2-PR4 como UM merge** — **ENTREGUE** (ADR-44) | 10 | ⚠ Divirjo da decomposição em quatro. O próprio PR3 admite que "os dois devem sair na mesma semana", porque sozinho mostra `betweenness: null` e o grafo perde o tamanho por influência. Um pacote que só não é regressão se outro sair junto é **um commit, não um PR** |
| 12 | **F3 → F4 → F5 → F6 → F7** | — | Daí em diante a ordem do `14` se sustenta. F3 exige **RFC** (§1.1); F5 herda a dívida do `MD_LINK` já resolvida na F1 |

---

## 3.1 Pacotes novos que a AUDITORIA impôs (`docs/17`)

Verificação adversarial de 2026-07-27: 84 pontos levantados, os 22 de gravidade
alta submetidos a cético com obrigação de **executar código** — **18
confirmados, 4 refutados**. O veredito de uma frase: *"o projeto não tem crise
de arquitetura, tem crise de fechamento de laço — constrói bem e verifica mal
aquilo que construiu"*. Todo defeito confirmado é uma **ausência que passou
verde**.

| # | Pacote | pt | Por quê |
|---|---|:--:|---|
| **PR-0.1** ✅ **ENTREGUE** (ADR-47, v1.9.5) | **release executável** — `exclude_binaries=True` no `build.spec`, `sqlite-vec` no build, job de release com trigger de tag, token de release em `[gate].ci_enforced`, `expected_mechanisms` no registro epistêmico | 4 | G-8 e G-10 reabertas. Sem o token no gate, `test_ci_executa_todo_o_gate_declarado` **estruturalmente nunca** poderá acusar isso |
| **F3-PR0** | **fechar o laço da decisão canônica** — `MIN(bm25)` → `bm25` (**exige RFC**: ativa o árbitro LLM no caminho de escrita), pré-condição de frescor ou INV de cobertura bundle→índice, `try/finally` no `rebuild_index`, teste do degrau de similaridade | 6 | **Pré-requisito da F3**: o P-7 faz `promote` consultar `ReconcileCandidate`, hoje uma escada com **dois degraus mortos** — a SQL de similaridade estoura em toda execução desde a v0.9, engolida por `except Exception` |
| **F-UI** | **as superfícies órfãs**, num PR só: doctor com findings e reparo, histórico de atos com desfazer, cancel/retry de job, repasse genérico de SSE (que ressuscita Stepper e barra de progresso já escritos) | 8 | Cinco achados confirmados com a MESMA forma: use case completo, endpoint completo, e nenhuma tela. Muito mais barato junto que espalhado por cinco fases. Pré-requisito: smoke de UI, hoje inexistente |
| **F-EPIST** | trilha epistêmica, um PR por item e todos independentes: `out_of_scope`, rebaixar `retrieval_rrf_hedge` para `heuristic`, contratos de `memory_freeze` e `consolidate_inbox`, `rglob` + import absoluto no `test_architecture` | 5 | Barato e paralelizável |

**Regra de processo adotada**: o gate verifica presença e conformidade; precisa
passar a verificar **completude**. Três instrumentos que teriam pego a maioria:
`expected_mechanisms` no registro, cruzamento rotas-do-backend × métodos-do-
cliente, e uma perna de CI que **não silencie dependências** (o precedente
`backend-ml` já existe e funciona; falta o simétrico para `embed` — foi o
`conftest` hermético que cegou 100% da suíte para a FK de `embeddings`).

---

## 4. Pacotes de trabalho das duas fases-modelo

### Fase 1 — O ato de curadoria (ADR-41)

Estratégia: **PR1 é uma fatia vertical** (modelo + 2 atos + preview +
registro + CLI + endpoint + 422). Depois dele, cada ato novo é um arquivo
em `usecases/curate/` mais uma entrada no registro `ACTS`, herdando
preview, `curation_acts`, endpoint e CLI **de graça**. Toda a interface
fica concentrada no último PR (um `CurationDialog` genérico) para não
existir UI pela metade. **Só o PR1 toca schema** — e já nasce com as
colunas do undo para a fase não precisar de segunda migração.

| PR | Entrega | Teste que falha antes | Valor se o plano parar aqui |
|---|---|---|---|
| **PR1** | `CurationAct` (`_plan()` puro → `_apply()` com **uma** chamada ao writer) + Supersede/Invalidate + `curation_acts` (runtime 7→8) + handler 422 + CLI | `test_supersede_preview_nao_move_head_e_nao_registra_ato`: preview devolve diff/findings/dependentes **e** HEAD imóvel **e** `curation_acts` vazio | O item de VoI 0.85 deixa de ser irresolvível: `llmwiki curate supersede A B --dry-run`. De brinde, toda rejeição do Harness deixa de parecer bug (500) e passa a 422 nomeado |
| ✅ **PR2** | undo como **escrita para a frente** + ato novo — **ENTREGUE** | `test_undo_restaura_bytes_e_cria_novo_ato`: bytes idênticos, HEAD **novo**, commit antigo ainda alcançável, duas linhas em `curation_acts` | Arrepender-se passa a existir sem terminal e sem `RestoreBackup` (que restauraria o HOME inteiro) |
| ✅ **PR4** | `LinkPages`/`UnlinkPages` escrevendo no **canônico** (bloco `## Relacionados` idempotente) + decisão do formato de link | round-trip de `parse_links` com o formato final | A ponte frágil do topo da fila passa a ser reparável, e o reparo **sobrevive ao rebuild** |
| ✅ **PR6** | `item.acts` no payload + `CurationDialog` — **ENTREGUE** | contrato de shape no backend + tipagem no cliente (**não** grep em `.tsx`) | Os dois itens do topo abrem ato com preview em vez de levar a uma tabela sem botões — a promessa literal do `14` |
| ✅ **PR3** | `EditPage` — primeira escrita humana de corpo, **sem** `normalize_machine_body` — **ENTREGUE** | edição que viola política ⇒ 422 e bundle intacto; e o preview deixa de **subdeclarar** (diff contra os bytes crus, reformatação nomeada na nota) | A correção mais comum passa a acontecer no produto — CLI, HTTP **e app**: a oferta declara `multiline`/`prefill` e o `CurationDialog` abre `textarea` com o corpo atual (a 1ª das duas saídas da nota do §3) |
| ✅ **PR5** | `MergePages` — união declarada, perdedora **supersedida** — **ENTREGUE** | merge preserva tags/`valid_at` e não perde byte no HEAD; região absorvida **antes** de `# Citations` (senão desarma `policy.citation_invalid` — medido) | Duas versões da mesma verdade param de conviver sem ninguém perder informação. **Emenda ao DoD**: `source_sha256`/`source`/`resource` NÃO são herdados — descrevem a fonte da origem, e a proveniência do texto absorvido fica na página de origem, linkada da região (por referência, não por cópia) |

### Fase 2 — A camada de padrões como objeto (RFC + ADR-43)

> **Numeração**: o `ADR-42` foi publicado por outro PR (escada de modelo
> local) que saiu em paralelo. A Fase 2 usa **ADR-43** em diante — renumerar
> ADR já publicada seria pior que um buraco na sequência reservada.

Estratégia: **não é uma feature em quatro pedaços — é um objeto que nasce
em três camadas de baixo para cima**, e a ordem é forçada por dependência
epistêmica: primeiro o snapshot precisa ser **repetível e datado** (senão o
casamento de partições compara ruído com ruído), depois a **identidade**
(único PR que toca o canônico, por isso isolado), depois o **custo** (só é
honesto quando existe carimbo para servir com aviso em vez de recomputar).
`[mechanisms.pattern_layer_snapshot]` **nasce no PR1 e cresce** nos
seguintes — evita um segundo mecanismo mentindo sobre o primeiro.

| PR | Entrega | Migração | Valor isolado |
|---|---|---|---|
| ✅ **PR1** | `seed` no Leiden · `bundle_head`/`computed_at` · poda de pontes órfãs · **INV-004** no doctor · job `leiden` no Scheduler · perna `[ml]` na CI — **ENTREGUE** | index 6→7 aditiva | O mapa passa a dizer **de quando é** e **quem o produziu** (`backend`: numa máquina sem `[ml]` compilado, "comunidade" era componente conexo em silêncio); o doctor acusa mapa velho (warn — mapa velho é servível) e ponte apontando para página aposentada |
| ✅ **PR2** | `theme_id` por casamento de partições (`themes`/`theme_epochs`, vocabulário fechado) · `rel_path` derivado do `theme_id` · adoção das páginas antigas · **o LLM volta a só rotular** · INV-005 no doctor — **ENTREGUE** | index **8→9** aditiva | `communities/` **para de apodrecer** — e o defeito foi MEDIDO antes: um tema cuja página mais conectada troca produzia duas páginas canônicas vivas. τ = 1/3 calibrado contra a banda vazia entre 0,17 e 0,50; `merged` declarado e **não observado** |
| ✅ **PR3+4** | Brandes **fora do request** via `ComputeKernel` · `graph_centrality` · `limit` + subgrafo · badge de frescor com ação — **ENTREGUE** | index **7→8** aditiva (o PR1 já usou o 7) | O produto deixa de ter data de morte: **2571 ms → 139 ms** a 1200 páginas (18,5×), medido. **Dois itens NÃO entraram, por razão declarada**: o "snapshot compartilhado" perdeu a premissa (com Brandes fora, sobram 139 ms; os três são requests separados e um cache serviria `heat` velho), e a "história do tema" depende do `theme_id` do PR2 — série temporal de um rótulo sem identidade |

---

## 5. Dependências ocultas (as que mudam o plano)

- **D-A · A bomba do `MD_LINK` — confirmada por execução.**
  `MD_LINK = r"\[([^\]]*)\]\(([^)\s]+)\)"` (`okf/links.py:5`): o
  `[^)\s]+` **para no espaço**. Rodei: `[t](/p.md)` casa;
  `[t](/p.md "rel:refines")` **não casa**. Ou seja, no dia em que a Fase 5
  escrever o formato anotado, `parse_links` deixa de ver o link e a aresta
  **desaparece de `graph_edges` em silêncio**. ⇒ **Decidir o formato na
  F1-PR4** (com `rel` NULL) e ajustar `MD_LINK` com teste de round-trip.
  É a descoberta mais barata de arrumar agora e a mais caro depois.
- **D-B · A Fase 2 não pode fechar verde com o DoD que declara** —
  confirmado: `import igraph` ⇒ `ModuleNotFoundError`, CI instala só
  `[dev]`. O DoD central ("mesmo bundle ⇒ mesma partição, nos dois
  backends") seria **verde por skip** sobre o algoritmo de produção. O
  repositório se recusa a aceitar autocertificação em contrato epistêmico
  (`validate.py`); a mesma postura vale para teste. ⇒ `[ml]` na CI **no
  mesmo PR**.
- **D-C · O rito de undo inverte gate→bytes.** `BundleWriter.write` roda o
  Harness **antes** de tocar o disco. O rito proposto ("revert no worktree
  → Harness → commit; rejeição restaura o worktree") coloca bytes antes do
  gate, e "restaurar o worktree" só é possível com `checkout`/`reset` — a
  operação que o `14` proíbe. Agrava: `GitStore.commit` faz
  `add(A=True)` sobre o `kb_root` inteiro, então um revert rejeitado e não
  limpo entra no **próximo** commit de qualquer ato. ⇒ Ler os blobs do
  commit pai, montar `OKFDocument`s e passar pelo `write()` normal: **o
  undo vira escrita para frente**. Aresta a declarar: desfazer a
  *criação* de página só é expressável por `BundleWriter.remove`, que
  **não** roda o Harness — "gate inescapável" e "um commit" não podem
  valer juntos nesse caso, e o DoD precisa dizer qual cede.
- **D-D · O preview da F1 não vê o finding que motiva o ato.**
  `HarnessRunner.run(mode='write')` compõe `okf_conformance` +
  `local_policy`; `check_corpus` — origem de
  `policy.contradiction_candidate` — só é chamado em `lint_bundle`. Logo o
  preview **nunca** inclui a contradição que a fila põe em primeiro lugar.
  ⇒ **RESOLVIDA no F1-PR5 por uma terceira saída** (ADR-41.5): a premissa
  estava errada — os 16-40 s são do `lint_bundle` (todos os checks), e o
  `check_corpus` sozinho sai por **~1,2 ms/doc + ~45 ms de gazetteer**
  (medido: 300 docs em 357 ms). E a pergunta do preview é sobre AS DUAS
  PÁGINAS do ato: ele roda o detector nos dois documentos antes e depois, e
  consulta `page_entities` (projeção já indexada por entidade) para a
  terceira página. Sem varredura e sem antecipar a memoização da F7.
- **D-E · O sumário de tema realimenta o grafo que gera o tema.**
  `_CommunitySummaryPage` escreve links para os membros; `rebuild_index`
  converte corpo em arestas; `_weighted_graph` lê `graph_edges` **sem
  filtrar `communities/`**. Hoje não morde porque `DetectCommunities` não
  reindexa — mas o DoD da F2-PR2 diz que passará a reindexar, e a partir
  daí cada execução **altera o grafo da seguinte**: épocas falsas de tema
  (`grew`/`split` espúrios) e sumários entrando no p99 de grau. ⇒ Excluir
  `communities/` na construção do grafo **já no PR1**, e o teste de
  determinismo rodar **com** `rebuild_index` entre as duas execuções.
- **D-F · Invariantes desligados para subpacotes.**
  `test_usecases_do_not_reach_outward` usa `glob('*.py')` — `curate/`
  **não é visitado**; e o teste de método público único filtra por
  `cls.__module__`, então uma classe em `curate/supersede.py` não é vista
  nem reexportada. ⇒ Nenhum ato pode entrar antes do PR1 corrigir a
  varredura para `rglob`/`walk_packages`.
- **D-G · `curation_acts` nasce sem o que F3 e F6 vão pedir.** A F3 precisa
  amarrar veredito a ato e a F6 precisa amarrar ato a `ask_misses`. ⇒ Nascer
  com `origin_kind`/`origin_key` **nullable**, ou a F3 abre a segunda
  migração que a F1 quis evitar.
- **D-H · O lock protege o bundle, não a projeção.** O `rebuild_index` que
  cada `_apply` roda escreve em `index.db` **fora** do lock, e o
  `harness.run` acontece **antes** dele — dois atos concorrentes podem
  passar o gate sobre o mesmo estado. Não é regressão do plano, mas a F1
  multiplica por sete os escritores humanos e é o momento honesto de
  declarar (ou estender o lock ao rebuild).
- **D-I · `INSERT` posicional em `graph_bridges`.**
  `INSERT OR REPLACE INTO graph_bridges VALUES (?,?,?,?,?)` quebra no
  instante em que o carimbo adiciona colunas. ⇒ Passar a listar colunas no
  PR1 (`communities` já usa nomeadas e não tem o problema).
- **D-J · Asserções de conjunto exato.** `test_fase5.py` assere
  `set(insights) == {gaps, topology, activity, classifiers}` e
  `test_v11_gaps.py` assere `all("betweenness" in n)`. Somar campo ao
  payload **obriga** a editar testes de duas suítes — previsto, mas a
  entrega da vitrine precisa listá-los também.
- **D-K · Duas identidades para o mesmo objeto.** Se o PR1 renumerar
  `community` canonicamente e cravar isso num teste, o PR2 torna o inteiro
  ruído — e o teste do PR1 precisa seguir verde, custo de manutenção sem
  valor. ⇒ PR1 promete apenas **ordenação determinística**; a semântica de
  rótulo é inteiramente do `theme_id`.

---

## 6. Colisões de arquivo e a regra de serialização

**Regra:** nunca duas fases com migração abertas ao mesmo tempo. As duas
fases-modelo são serializáveis; sobrepô-las gasta em rebase o que a fatia
vertical economizou em esqueleto.

| Arquivo | Fases | Mitigação |
|---|---|---|
| `runtime/db.py::SCHEMA_VERSIONS` + `architecture.toml` | 4 PRs de 2 fases | `test_architecture_toml` exige que os dois mudem no **mesmo commit**; em rebase, reaplicar o **número**, nunca aceitar o merge do hunk |
| `api/cockpit.py` (640 linhas) | **8 dos 10 pacotes** | Criar `api/curation.py` com `mount_curation` no PR1 (precedente `api/system.py:241`); PR2..PR6 tocam só arquivo novo |
| `facades/curation.py` (já com 20 métodos) | 6 PRs | Atos em `facades/curation_acts.py`; **temas em `CompilerFacade`** (tema é leitura de padrões, não curadoria) |
| `usecases/base.py` | F1-PR1, F2-PR2, F3 | Transformação de frontmatter em `kernel/curation.py` — puro; os **dois** eixos importam de lá e `base.py` não conhece `curate/` |
| `detect_communities.py` | 4 fases; `_weighted_graph` em 3 | Extrair a construção do grafo para `retrieval/patterns.py` **já no PR1** |
| `retrieval/patterns.py` (novo) | 4 PRs da F2 | Definir a assinatura **final** de `pattern_layer_snapshot(...)` no PR1, mesmo devolvendo campos vazios — a forma do dado é decisão de fase, não de PR |
| `epistemics.toml` | 4 PRs | **Um único PR por fase** mexe em `[registry] version`; contrato e arquivo referenciado sempre no mesmo commit |
| `next_actions.py` (139 linhas) | 4 fases | PR6 mantém `acts_for(kind)` como função pura **separada**, sem tocar ranking nem fontes — a F3 substitui uma função, não o módulo |
| `daemonClient.ts` | F1-PR6, F2-PR4 | Serializar; se houver sobreposição, adicionar `graphLimited(limit)` em vez de mudar a assinatura de `graph()` |
| `okf/links.py` | F1-PR4, F5 | **D-A** — decidir na F1 |

---

## 7. Como medir que funcionou

**Produto** (por fase, comparável): `graph_data` a 5.000 páginas
(84,3 s → < 2 s) · itens da fila que abrem ato com preview (0 → 100% de
`contradiction`/`bridge`) · páginas mortas devolvidas pelas fontes de
atenção (hoje > 0 → 0) · arquivos novos em `communities/` por rodada
(hoje 1 por rótulo → 0) · Recall@K do golden **inalterado** em todas.

**Processo** (o que o PR-0 torna observável): comandos do gate executados
pela CI (4/8 → 8/8) · migrações com prova de upgrade (0/4 → 4/4) ·
mecanismos de padrão com contrato (0 → 1 crescendo) · rotas de escrita que
devolvem 422 em vez de 500 (0 → todas) · idade do `baseline.json` (1
versão atrasada → 0).

## 8. Estado da execução

**PR-0 e F0 estão ENTREGUES** (commits `18d8d20` e `d108d2f`). O que mudou
de fato, além do que os DoDs prometiam:

- o gate passou de **4/8 comandos executados pela CI para 8/8**, com
  `architecture.toml [gate]` como fonte única cruzada por teste;
- a perna `[ml]` revelou que o ramo Leiden de produção **passa** — instalei
  o extra e rodei: os 3 testes novos passam e a suíte inteira segue verde
  com `igraph`/`leidenalg` presentes, então nada dependia do fallback;
- `bench compare --against` produziu o primeiro achado real: `graph.ppr` a
  −30,2%. **Não é regressão de código** — nesta máquina o Python ficou 15%
  mais rápido e o Rust 21% mais lento, sobre um denominador de ~2 ms. Daí a
  tolerância default frouxa e a decisão de manter `bench` **fora** do gate
  por PR (guarda de mesma-máquina). O baseline **continua em 1.7.0**:
  bumpá-lo sem remedir na máquina de referência seria alegar medição que
  não houve (`AGENTS.md` §6);
- duas derivas corrigidas de passagem: `backup verify` sem argumento
  estourava `TypeError` (agora verifica o mais recente, com erro de código
  estável) e `daemon.started` emitia `version: "0.7.0"` fixo.

**F1-PR1 também está ENTREGUE** (`7a07f96`, ADR-41). O modelo existe: o
esqueleto `CurationAct` com preview puro, `SupersedePage`/`InvalidatePage`,
`curation_acts`, o 422 transversal e o CLI. A pré-condição D-F foi paga
antes de qualquer ato (`glob`→`rglob`, `iter_modules`→`walk_packages`), e as
duas emendas de acoplamento da §3 foram aplicadas. Verificado num HOME real:
dry-run não move o HEAD, o apply faz exatamente 1 commit, a página antiga
segue legível e o doctor sai 0.

**Próximo passo: F1-PR2** — `UndoCurationAct`, com o rito **reformulado**
por D-C: nada de `git revert` no worktree antes do gate (os bytes entrariam
antes do Harness e recuperar de uma rejeição exigiria `checkout`/`reset`, a
operação que o `14` proíbe). O undo lê os blobs do commit pai, monta
`OKFDocument`s e passa pelo `write()` normal — **escrita para frente**,
registrada como ato NOVO. A aresta a declarar no DoD: desfazer a *criação*
de uma página só é expressável por `BundleWriter.remove`, que não roda o
Harness — "gate inescapável" e "um commit" não podem valer juntos nesse
caso, e o PR precisa dizer qual cede.
