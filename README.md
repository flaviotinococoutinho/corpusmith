# LLM Wiki — v0.8 (Qualidade Epistêmica da Memória Não-Episódica)

Knowledge base **OKF local-first** com daemon de compilação/consulta e
**Cockpit de Memória Agêntica** no Electron.

## Novidades da v0.8

- **`normalize/`** (stdlib puro, zero deps novas): o sanduíche determinístico
  em volta do LLM — PRÉ anota entidades canônicas no prompt, PÓS reescreve
  grafia curada (`postgres → PostgreSQL`) SÓ em páginas de máquina, com
  regiões protegidas (fences, inline code, blockquotes, alvos de link,
  `# Citations`) e idempotência garantida por teste. Datas/quantidades nunca
  são reescritas: viram anexo (`entities:` + `page_entities` no index.db).
- **Checksums anti-alucinação**: CPF/CNPJ (numérico e alfanumérico 2026),
  ISBN-10/13, ISSN, ORCID, IBAN — identificador inválido em página de
  máquina é `policy.identifier_invalid` (error). PII com checksum válido
  força `privacy: local_only` (`policy.pii_requires_local`).
- **Controle de autoridade**: gazetteer curado vive no bundle como páginas
  `type: authority_record` (aliases + QID) — corrigir grafia é um commit.
- **Reconciliação** ADD/UPDATE/SUPERSEDE/NOOP no compile: identificador
  forte compartilhado (DOI/ISBN/arXiv/sha) decide deterministicamente;
  similaridade depois; LLM local só na zona cinzenta (flag). Auditoria em
  `reconcile_log`.
- **Bi-temporalidade**: `valid_at`/`invalid_at` tipados (tempo de MUNDO;
  `stale_as_of` continua tempo de código); o `/ask` extrai `as_of` da
  pergunta e despriosiza evidência fora da validade; SUPERSEDE grava
  `superseded_by` + `invalid_at` — invalidar, nunca apagar.
- **Grafo com confiança**: `graph_edges.confidence` pesa o Leiden; arestas
  `inferred` por co-menção de entidade; super-hubs (p99) fora do
  particionamento; páginas `communities/*.md` (`community_summary`) geradas.
- **Heat/outcomes/reflect**: `✅ útil · 🚫 beco · ✏️ corrigi` no chat →
  `ask_outcomes`; reflect semanal recalcula `page_heat` e o overlay
  `preferred/tentative/contested` que ajusta a fusão RRF (+15%/−20%);
  correção vira memória nova no inbox (`raw/correcoes/`).
- **Descida hierárquica** L0/L1 (`page_levels` + `fts_levels`) com
  `trajectory` visível no painel de evidências.
- **Abstenção** (LongMemEval): sem cobertura, `abstained: true` + `gaps` —
  nunca resposta fabricada. **Eval de memória** em 5 categorias
  (extract · multi_session · temporal · update · abstain) contra
  `bundle/harness/golden_eval.jsonl`, com barras no painel Qualidade.

- **Bundle OKF versionado em Git** (`~/llmwiki/knowledge/bundle/`): páginas
  Markdown com frontmatter tipado, `index.md`/`log.md` reservados, escrita
  exclusivamente via `BundleWriter` (gate do Harness).
- **Harness em duas camadas**: conformidade OKF (só o SPEC — `# Citations`
  é SHOULD, nunca emite finding) × política local (privacy obrigatório,
  `source_sha256` só para páginas geradas por máquina, citações exigidas só
  para conteúdo `api:*`).
- **Runtime**: fila de jobs SQLite + worker + scheduler + governor de
  orçamento de API + eventos SSE; índice FTS5 (+denso opcional) derivado.
- **Cockpit**: Dashboard → Consulta com Evidências → Inbox → Wiki →
  Qualidade → Processos, com o botão **⭐ Promover para memória**
  (`generated_via: human:promote`, sem exigência de `source_sha256`).

## Montagem

```bash
just bootstrap        # venv + pip install -e backend[dev]
just models           # ollama pull (opcional — tudo degrada p/ modo extrativo)
just test             # golden bundles: 42 testes de contrato
just daemon &         # sobe em 127.0.0.1:8377 com token efêmero
backend/scripts/llmwikictl status
backend/scripts/llmwiki okf lint        # 0 erros num bundle recém-bootstrapado
cd desktop && npm i && npm run dev      # cockpit (Electron + Vite)
```

O bundle é bootstrapado automaticamente pelo daemon (ou `llmwiki okf
bootstrap`): `index.md` raiz com frontmatter contendo **apenas**
`okf_version`, `log.md` com headings ISO, commit inicial.

## Estrutura

```
backend/
  src/llmwiki/
    okf/        document, links, bundle, index_file, log_file, git_store, writer,
                bootstrap, authorities (gazetteer do bundle, v0.8)
    normalize/  model, masking, grammar, gazetteer, engine +
                detectors/{dates,quantities,identifiers,standards,geo}   (v0.8 §3)
    harness/    findings, okf_conformance (SPEC), local_policy (política),
                runner (lint_bundle), eval_memory (5 categorias, v0.8 §10)
    runtime/    db (+migrate), queue, slots, events, governor, scheduler, worker
    jobs/       compile (sanduíche §6.1), ask (temporal/abstenção §6.2),
                reconcile (§5), reflect (§8), review, leiden (§7), embed,
                rerank, ocr, lora
    retrieval/  fts (rebuild_index + entidades + níveis), descend (§9),
                dense, fusion (RRF)
    models/     router (local Ollama × API Anthropic, privacidade + orçamento)
    api/        system (auth header OU ?auth=), cockpit (+outcome/eval/
                authorities/reflect, v0.8 §11)
    daemon.py · cli.py · settings.py (flags + get)
  db/           schema_runtime.sql · schema_index.sql (tabelas v0.8 §2.1)
  config/       default.yaml (privacy.default: local_only · flags v0.8)
  build.spec    PyInstaller onedir (AGPL fora do binário)
desktop/
  electron/     main, preload, sidecar (handshake via state/daemon.json)
  src/panels/   Dashboard(+candidatos reflect), ChatEvidence(+desfechos,
                as_of, trajetória, abstenção), PromoteDialog, Inbox,
                Explorer(+filtro authority), Quality(+5 barras de eval),
                Processes
  src/lib/      daemonClient (extensões do cockpit + v0.8), client (singleton)
```

## Aceite da v0.7 (verificado por teste)

- [x] arquivo sem `---` → `okf.frontmatter_missing` (error); YAML inválido →
      `okf.frontmatter_invalid` (error) — ambos via `lint_bundle` varrendo cru
- [x] `timestamp` ISO no arquivo, `datetime` no parse (roundtrip)
- [x] promoção humana passa sem `source_sha256`; `privacy` obrigatório
- [x] página `api:*` sem `# Citations` → bloqueada (política, não conformidade)
- [x] reservados validados quando presentes; ausência nunca invalida
- [x] promote cria página + `Creation` no `log.md` + commit + evento
      `memory.promoted`
- [x] `llmwiki okf lint` == painel Qualidade (mesma fonte: `lint_bundle`)

## Aceite da v0.8 (verificado por teste — `test_normalize.py` + `test_v08.py`)

- [x] pacote `normalize/` sem dependência nova; checksums com vetores-golden
      (CPF 529.982.247-25, CNPJ alfanumérico 12.ABC.345/01DE-35 do SERPRO,
      ISBN-10/13, ISSN, ORCID, IBAN); idempotência `rewrite(rewrite(x))==rewrite(x)`
- [x] "postgres"/"nodejs."/"NIPS 2017" → `PostgreSQL`/`Node.js.`/`NeurIPS 2017`
      com fence intocada (verificado ponta a ponta no compile)
- [x] ISBN/CPF com DV inválido em página de máquina → bloqueio no Harness
- [x] CPF válido + `api_allowed` → `policy.pii_requires_local`
- [x] mesmo DOI em duas fontes → `UPDATE` no `reconcile_log`
- [x] `/ask` com data → `as_of` + filtro de validade; sem cobertura →
      `abstained: true` com `gaps`
- [x] `eval_memory` grava as categorias em `eval_runs`; painel Qualidade
      mostra as 5 barras; `abstain` só passa com abstenção real
- [x] `reflect` popula `page_heat`/`page_overlay`; página `contested` afunda
      na fusão do `/ask`; Dashboard exibe candidatos
- [x] migração idempotente: bancos v0.7 ganham `graph_edges.confidence` e
      `chunks.valid_at/invalid_at` no primeiro `connect()`

## Notas de implementação (desvios conscientes dos docs)

- `OKFDocument.loads` remove o BOM antes de `frontmatter.loads` (não só na
  detecção) — senão arquivo com BOM parseava com metadata vazia.
- Auth aceita token válido em **qualquer** um dos canais (header ou
  `?auth=`), não "header primeiro": EventSource não envia headers e um
  header errado não pode vetar um `?auth=` correto.
- `InboxPanel` envia o caminho **relativo ao kb** (`raw/...`) no
  `compile_source`; o daemon resolve contra o kb (o doc montava um caminho
  absoluto inválido no frontend).
- `vite.config.mts` (não `.ts`): o plugin do Tailwind v4 é ESM-only e o
  pacote precisa continuar CJS para o main do Electron.
- Parsers AGPL (`pymupdf4llm`, `ebooklib`) só via extra `llmwiki[parsers]`,
  executados em subprocesso (`ingestion/extract.py`) — nunca no binário.

Desvios da v0.8:

- `rewrite()` só aplica matches `extracted` (o doc incluía `inferred`, mas o
  próprio doc marca semver como "anexo apenas; nunca reescreve" — alinhamos
  reescrita e finding pelo mesmo critério; precisão > recall).
- Termos de FTS filtram stopwords pt/en: OR sobre "do/com/qual" casava
  qualquer página via descida L0 e matava a ABSTENÇÃO.
- Score da fusão é RRF puro (~1/61 no topo): `ask.abstain_threshold`
  default é 0.0 (abstém sem evidência); o 0.05 sugerido no doc abstinha
  sempre nessa escala.
- `router.complete("reconcile", prompt, privacy_local_only=True)` do doc →
  assinatura real `router.complete(prompt, privacy="local_only")`; idem
  `s.index_db/s.runtime_db` → `s.app_support / "*.db"` e `fts_pages` →
  `chunks_fts` agregado por página.
- A correção (`✏️ corrigi`) vira arquivo em `raw/correcoes/` — o inbox real
  do projeto — em vez do job `capture_note` inexistente citado no doc.
