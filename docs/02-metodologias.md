# 02 · Metodologias

> COMO o sistema é construído. Cada metodologia aqui é executável — ou
> está no caminho crítico da pipeline, ou é asserção em teste.

## 1. O sanduíche determinístico

A maior fonte de degradação da memória semântica não é retrieval — é a
**entropia de superfície** que o LLM injeta na compilação (`Postgres` /
`postgres` / `PostgreSQL`; datas em três formatos; ISBN alucinado). O LLM
é cercado por duas passadas determinísticas:

```
fonte raw ──► [PRÉ] normalize.analyze()          anota entidades canônicas
                 │   o anexo entra no prompt: "use EXATAMENTE estas grafias"
                 ▼
             LLM (sumarização)                    único estágio não-determinístico
                 │
                 ▼
             [PÓS] normalize.rewrite()            grafia canônica (só máquina)
                 │  + re-annotate                 anexo sobre o texto FINAL
                 ▼
             ReconcileCandidate                   ADD/UPDATE/SUPERSEDE/NOOP
                 ▼
             Harness (conformidade + política)    gate: erro = rejeição
                 ▼
             BundleWriter (lock → arquivos → index.md → log.md → commit)
```

Implementação: o esqueleto é `usecases/base.py:MachinePageUseCase.execute`
(ver §5); o PRÉ é específico do `CompileSource._produce`.

Propriedades exigidas por teste:
- **Idempotência**: `rewrite(rewrite(x)) == rewrite(x)` — sem isso,
  recompilações acumulariam drift.
- **Regiões protegidas invioláveis**: cercas de código (inclusive não
  fechadas — protege até o fim), código inline, blockquotes, alvos de
  link e a seção `# Citations` inteira. `k8s` dentro de um comando
  continua `k8s`.

## 2. Reescreve grafia, anota semântica

Lição do MemPalace (texto integral vence resumo no LongMemEval):
normalização **nunca é compressão destrutiva**. Três destinos possíveis
para cada classe detectada:

| Destino | Critério | Exemplos |
|---|---|---|
| **Reescrever** | existe UMA forma correta e a troca é semanticamente neutra | `postgres→PostgreSQL`, `52998224725→529.982.247-25`, `iso 27001→ISO 27001`, tipografia |
| **Anotar** (anexo) | a superfície carrega estilo/contexto | datas em prosa (ISO vai para `page_entities`), quantidades (SI no anexo), semver |
| **Nem tocar** | região protegida | fences, inline code, quotes, alvos de link, `# Citations` |

O anexo tem duas formas: lista curta legível no frontmatter (`entities:`)
e registro completo no `index.db` (`page_entities` com `data` JSON —
`{"iso": ...}`, `{"si": {...}}`). O retrieval e o filtro temporal usam o
anexo; o leitor humano lê prosa natural.

## 3. Precisão > recall na reescrita; recall > precisão na anotação

Custos de erro assimétricos ⇒ limiares assimétricos:
- reescrita errada corrompe o bundle (caro, ainda que reversível) ⇒ só
  matches `extracted` com checksum não-inválido entram na reescrita;
- anotação errada polui o índice (barato, recomputável) ⇒ `inferred`
  entra no anexo; só `ambiguous` fica de fora.

Padrões de alto risco (siglas de UF, unidades de 1 letra, `Go`/`R`/`C`)
exigem âncora de contexto (`", SP"`), viram `inferred`, ou estão em
`UNSAFE_BARE` e nunca casam sozinhos.

## 4. Checksums como detector de alucinação

Identificador fabricado por LLM quase nunca satisfaz o dígito
verificador: CPF/CNPJ (mod 11; CNPJ alfanumérico 2026 incluído),
ISBN-10/13, ISSN, ORCID (ISNI mod 11-2), IBAN (mod 97), EAN-13. Regra de
política: DV inválido em página de máquina = `policy.identifier_invalid`
(error). É a versão aritmética do `policy.bad_commit_ref` ("o commit
citado precisa existir") — a mesma família anti-alucinação.

## 5. Template Method: o esqueleto que ninguém pula

`MachinePageUseCase.execute()` (usecases/base.py) fixa a sequência
produce → normalize → document → reconcile → aplica operação → gate →
write → after_write. Subclasses (`CompileSource`, `PublishWeeklyReview`,
`_CommunitySummaryPage`) implementam **apenas hooks protegidos**:

| Hook | Obrigatório | Responsabilidade |
|---|---|---|
| `_produce() -> DraftPage \| None` | sim | gerar o rascunho (None = SKIP) |
| `_reconcile(doc, report) -> dict` | não (default ADD) | decidir ADD/UPDATE/SUPERSEDE/NOOP |
| `_after_write(doc, report)` | não | cache, reindex, eventos |
| `_extra_result() -> dict` | não | campos extras no retorno |

O teste `test_machine_page_template_is_closed_for_modification` assevera
que nenhuma subclasse redefine `execute` — o invariante epistêmico
(nenhuma página de máquina entra sem sanduíche + reconciliação + gate) é
**estruturalmente impossível de pular** (OCP: aberto para extensão por
hooks; fechado para modificação do esqueleto; LSP: toda subclasse é
substituível no registry de jobs).

## 6. Use cases e facades

- **Use case**: 1 classe = 1 operação de negócio = 1 método público
  `execute()`; dependências pelo construtor. A intenção está no NOME da
  classe (`PromoteToMemory`, `MarkPageStale`), não em qual método foi
  chamado. Regra verificada por introspecção em
  `test_every_usecase_has_single_public_method`.
- **Facade**: uma por área — `MemoryFacade` (memória em uso: ask,
  outcome, evaluate), `CompilerFacade` (em construção: compile, index,
  communities), `CurationFacade` (sob governo humano: promote, stale,
  lint, review, reflect). É o único lugar que COMPÕE use cases.
- **Adapters** (jobs/, api/, cli, desktop): tradução de transporte
  (fila/HTTP/argv) para chamadas de facade. A camada mais mutável; zero
  lógica de negócio. `test_api_speaks_only_to_facades` proíbe a api de
  pular camada.

## 7. Object Calisthenics (adaptado a Python)

Aplicado onde paga, não como dogma:
- **Coleções de primeira classe**: `Findings` (harness) responde
  `has_errors()/count()/rules()/to_dicts()`; `EvidenceStreams`
  (retrieval) encapsula fusão+overlay+temporal+entropia+proveniência.
  Ninguém reimplementa filtros sobre listas nuas.
- **Um método público por classe de aplicação** (use cases).
- **Wrap de primitivos com significado**: `DraftPage`, `MergeEvent`,
  `FusedEvidence`, `Match`, `NormReport` — dataclasses pequenas com
  vocabulário do domínio.
- **Sem abreviações** nos nomes novos (`question_entities`,
  `compression_affinity`).

## 8. Arquitetura como teste (a regra vira asserção)

`tests/test_architecture.py` transforma o desenho em contrato executável:

| Teste | Regra |
|---|---|
| `test_kernel_and_normalize_are_pure` | AST scan: nenhum import de sqlite3/httpx/subprocess/fastapi/git/pydantic/pathlib em `kernel/` e `normalize/` (functional core) |
| `test_usecases_do_not_reach_outward` | usecases não importam facades/api/jobs/fastapi (Dependency Rule) |
| `test_api_speaks_only_to_facades` | api não importa usecases nem jobs |
| `test_every_usecase_has_single_public_method` | introspecção: métodos públicos ⊆ {execute} |
| `test_machine_page_template_is_closed_for_modification` | nenhuma subclasse sobrescreve o esqueleto |

Gradiente de mutabilidade resultante (de dentro para fora, do estável
para o volátil): `kernel` → `normalize` → `okf`/`harness` → `usecases`
→ `facades` → `jobs`/`api`/`cli`/`desktop`.

## 9. CQS e consultas puras

Comando ≠ consulta em pares explícitos: `ComputeWeeklyReview` (puro, o
cockpit consome direto) × `PublishWeeklyReview` (materializa página);
`usage_candidates()` (puro) × `ReflectOnUsage` (recalcula heat/overlay);
`reconcile.plan` (puro — devolve o plano) × aplicação no template.
Consultas puras podem ser chamadas por endpoint GET sem medo; teste
`test_review_compute_is_side_effect_free` garante.

## 10. Golden tests e vetores publicados

- **Golden bundles**: casos canônicos de conformidade (arquivo sem
  frontmatter, YAML inválido, link quebrado, reservados) que nunca podem
  regredir.
- **Vetores publicados** para checksums: CPF `529.982.247-25`, CNPJ
  alfanumérico `12.ABC.345/01DE-35` (SERPRO), ISBN-10 `0-306-40615-2`,
  ISBN-13 `978-0-306-40615-7`, ISSN `0378-5955`, ORCID
  `0000-0002-1825-0097`, IBAN `GB82 WEST 1234 5698 7654 32` — com
  contrapartes inválidas.
- **Golden eval** (`bundle/harness/golden_eval.jsonl`): perguntas com
  resposta esperada por categoria, versionadas NO bundle do usuário —
  o eval mede a memória dele, não um benchmark alheio.

## 11. Único caminho de escrita

`BundleWriter.write()` é a única porta para o bundle: lock inter-processo
(fcntl) → Harness (rejeita em error) → arquivos → `index.md` regenerados
na cadeia de ancestrais → `log.md` → commit. Jobs, cockpit e CLI não
escrevem páginas por fora — qualquer novo produtor de página herda de
`MachinePageUseCase` (máquina) ou chama `PromoteToMemory` (humano).
