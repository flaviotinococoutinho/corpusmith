# LLM Wiki — v0.7 (Consolidação para Implantação)

Knowledge base **OKF local-first** com daemon de compilação/consulta e
**Cockpit de Memória Agêntica** no Electron.

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
    okf/        document, links, bundle, index_file, log_file, git_store, writer, bootstrap
    harness/    findings, okf_conformance (SPEC), local_policy (política), runner (lint_bundle)
    runtime/    db, queue, slots, events, governor, scheduler, worker
    jobs/       compile, ask, review (compute/run), embed, rerank, leiden, ocr, lora
    retrieval/  fts (rebuild_index + busca), dense, fusion (RRF)
    models/     router (local Ollama × API Anthropic, privacidade + orçamento)
    api/        system (auth header OU ?auth=), cockpit (todas as telas)
    daemon.py · cli.py · settings.py
  db/           schema_runtime.sql · schema_index.sql
  config/       default.yaml (privacy.default: local_only)
  build.spec    PyInstaller onedir (AGPL fora do binário)
desktop/
  electron/     main, preload, sidecar (handshake via state/daemon.json)
  src/panels/   Dashboard, ChatEvidence(+PromoteDialog), Inbox, Explorer, Quality, Processes
  src/lib/      daemonClient (extensões do cockpit), client (singleton)
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

## Notas de implementação (desvios conscientes do doc v0.7)

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
