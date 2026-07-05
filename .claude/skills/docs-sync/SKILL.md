---
name: docs-sync
description: Auditar e atualizar a documentação conceitual em docs/ contra a estrutura real do código do LLM Wiki. Usar após qualquer mudança em funcionalidade core (regras do Harness, endpoints, tabelas, jobs, use cases, detectores, constantes calibráveis) ou quando o usuário pedir para revisar/sincronizar a documentação.
---

# docs-sync — manter docs/ fiel ao código

Regra de ouro: **o código é a fonte da verdade**. A documentação nunca
descreve o que o código não faz; se divergirem, corrija a doc (ou, se a
doc descrevia o comportamento desejado, trate como bug de código e
pergunte ao usuário antes).

## Mapa código → documento

| Mudou isto no código | Atualize |
|---|---|
| Regra nova/alterada em `harness/okf_conformance.py` ou `harness/local_policy.py` | `docs/06-referencia.md` §1 (tabela de regras) + `docs/01-conceitos.md` §2/§7 se mudar a divisão conformidade×política ou máquina×humano |
| Endpoint em `api/system.py` ou `api/cockpit.py` | `docs/06-referencia.md` §2 + `docs/05-fluxos-operacionais.md` §11 (mapa endpoint→facade→use case) |
| Tabela/coluna em `db/schema_*.sql` ou `runtime/db.py:_migrate` | `docs/06-referencia.md` §3 + o fluxo que a consome em `docs/05` |
| Job no `jobs/__init__.py:REGISTRY` ou `runtime/scheduler.py` | `docs/06-referencia.md` §4 + `docs/05` §0 |
| Use case novo em `usecases/` ou método de facade | `docs/06-referencia.md` §10 + `docs/05` §11 + `docs/02-metodologias.md` §6 |
| Detector/subkind em `normalize/detectors/` ou seeds do gazetteer | `docs/06-referencia.md` §8 + `docs/01-conceitos.md` §5/§6 |
| Constante calibrável (RRF k, HI/LO, η, clamps, pesos, meia-vida, chunk) | `docs/06-referencia.md` §11 + a fórmula em `docs/03-teoria.md` |
| Campo tipado em `okf/document.py:OKFFrontMatter` | `docs/06-referencia.md` §7 + `docs/01-conceitos.md` §4 se temporal |
| Flag em `settings.py`/`config/default.yaml` | `docs/06-referencia.md` §5 |
| Algoritmo novo em `kernel/` | `docs/03-teoria.md` (com o paper de origem) + `docs/07-sinergias.md` (matriz + receita se abrir composição nova) |
| Fluxo fim-a-fim alterado (ordem de etapas, laço novo) | `docs/05-fluxos-operacionais.md` + diagrama de laços em `docs/07` §1 |
| Teste de arquitetura alterado | `docs/02-metodologias.md` §8 + `docs/06-referencia.md` §9 |
| Painel/cliente desktop | `docs/04-tecnologias.md` §4 (só se mudar contrato, não estética) |

## Procedimento de auditoria

Execute a partir de `backend/` e compare cada saída com a seção citada:

```bash
# 1. Regras do Harness (compare com 06-referencia §1)
grep -rhoE '"(okf|policy)\.[a-z_]+"' src/llmwiki/harness/ src/llmwiki/normalize/engine.py | sort -u

# 2. Endpoints (compare com 06-referencia §2)
grep -rhoE '@app\.(get|post)\("[^"]+"' src/llmwiki/api/ | sort -u

# 3. Tabelas (compare com 06-referencia §3)
grep -hoE 'CREATE (VIRTUAL )?TABLE IF NOT EXISTS \S+' db/*.sql | sort -u

# 4. Jobs (compare com 06-referencia §4)
sed -n '/^REGISTRY = {/,/^}/p' src/llmwiki/jobs/__init__.py

# 5. Use cases: classes e método público único (compare com 06-referencia §10)
grep -rhE '^class \w+\(.*UseCase' src/llmwiki/usecases/

# 6. Facades e métodos (compare com 05 §11)
grep -rhE '    def [a-z_]+' src/llmwiki/facades/*.py

# 7. Detectores/subkinds (compare com 06-referencia §8)
grep -rhoE '"(cpf|cnpj|doi|arxiv|isbn|issn|orcid|cve|uuid|semver|iban|git_sha|iso|nbr|rfc|nist|ieee|eu_reg|regulator|country|uf|cep|address|date|qty)"' src/llmwiki/normalize/detectors/ | sort -u

# 8. Tipos OKF recomendados (compare com 06-referencia §6)
sed -n '/RECOMMENDED_TYPES = {/,/}/p' src/llmwiki/harness/local_policy.py

# 9. Flags e config (compare com 06-referencia §5)
sed -n '1,60p' config/default.yaml

# 10. Constantes calibráveis (compare com 06-referencia §11)
grep -rnE '(RRF_K|HI, LO|eta: float|floor: float|ceiling|HALF_LIFE|CHUNK_CHARS|1\.15|0\.8\}|BETWEEN 2 AND 30|max\(p99, 8\))' src/llmwiki | grep -v tests

# 11. A suíte é o juiz final — doc que contradiz teste verde está errada
.venv/bin/pytest -q
```

## Checklist de atualização

1. Rode a auditoria acima; anote cada divergência (código × doc).
2. Corrija começando pelo `06-referencia.md` (tabela da verdade), depois
   propague para os documentos conceituais afetados pelo mapa acima.
3. Se surgiu conceito/mecanismo NOVO (não só valor mudado):
   - `01-conceitos.md` ganha a definição (o vocabulário arbitra);
   - `03-teoria.md` ganha o fundamento com paper citado, se houver;
   - `07-sinergias.md` ganha a linha na matriz §2 e, se abrir composição
     nova, uma receita em §3 e o ponto de extensão em §5.
4. Verifique que `docs/README.md` ainda descreve todos os arquivos da
   pasta (adicione linha na tabela se criou doc novo).
5. Releia o diagrama de laços (`07` §1) — laço novo ou removido precisa
   aparecer/sair do desenho.
6. Commit da doc junto com o commit da mudança de código (nunca em
   commit separado "atualiza docs" dias depois).

## Estilo dos documentos

- Português; denso mas legível; tabelas para fatos enumeráveis, prosa
  para o porquê; diagramas ASCII para fluxos.
- Referências a código no formato `caminho/arquivo.py:Símbolo`.
- Papers citados com autores, título e veículo/ano (docs/03 é o padrão).
- Cada documento mantém sua altitude (ver tabela em docs/README.md):
  não duplique referência dura fora do 06; não explique teoria fora do
  03 — linke.
- Valores literais do sistema (`extracted`, `local_only`, nomes de
  regra/tabela) sempre em crase, exatamente como no código.
