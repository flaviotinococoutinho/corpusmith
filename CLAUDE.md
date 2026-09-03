# Corpusmith

**`AGENTS.md` é a fonte normativa deste repositório. Leia-o antes de qualquer
alteração** — as regras lá são MUST/MUST NOT (RFC 2119) e este arquivo não as
substitui nem as resume por completo.

Complementos: [`architecture.toml`](architecture.toml) traz as regras
legíveis por máquina (presas à realidade por
`backend/tests/test_architecture_toml.py`) e
[`docs/10-engenharia-ai-friendly.md`](docs/10-engenharia-ai-friendly.md) a
arquitetura-alvo.

## O gate

Toda mudança precisa passar pelo gate. Atalho na raiz:

```bash
just verify
```

Ele executa a suíte do backend (pytest), o typecheck e o smoke do cockpit
(`npx tsc --noEmit` + `npm test`), a validação do compose e os linters dos
registros epistêmico e ontológico. Os testes Rust, o `doctor`, o `backup` e
o build empacotado (PyInstaller) são impostos na CI. O conjunto exato **não é decidido aqui**: `architecture.toml [gate]`
é a fonte única, e `backend/tests/test_pr0_gate.py` cruza gate, CI e justfile
— se a CI deixar de rodar algo do gate, a suíte quebra. Não contorne isso
editando só um dos três lados.

`bench compare` fica fora do gate por PR de propósito (razão de speedup varia
entre máquinas); é guarda de mesma-máquina/nightly.

## Ferramentas de operação (não são testes)

```bash
cd backend && .venv/bin/python -m corpusmith.cli doctor            # invariantes INV-*
cd backend && .venv/bin/python -m corpusmith.cli epistemics lint   # contratos epistêmicos
cd backend && .venv/bin/python -m corpusmith.cli backup create     # backup verificável
just context                                                       # o mapa gerado do repositório (leia antes de mudar algo)
```

Registros legíveis por máquina, todos presos a teste: `architecture.toml`
(camadas, gate, invariantes), `epistemics.toml` (mecanismos),
`ontology.toml` (termos e eixos), `nfr.toml` (requisitos não funcionais com
`status`). A fila viva é `docs/18` §11; todo `docs/*.md` declara altitude e
status na cabeça e doc vivo não crava contagem (`test_docs_contract.py`).

## Forma do projeto

Plataforma local-first de memória e conhecimento: bundle canônico versionado
em Git + daemon de compilação/consulta + cockpit Electron. **Núcleo
determinístico; LLM e I/O ficam na borda** — não introduza chamada de modelo
nem I/O no núcleo para "resolver" um problema de borda.

- `backend/` — Python, ambiente em `backend/.venv`
- `native/` — kernels Rust (workspace Cargo)
- `desktop/` — cockpit Electron/TypeScript
- `docs/` — conceitos e engenharia; `benchmarks/baseline.json` é referência medida

Skills do projeto em `.claude/skills/`: `docs-sync`, `ship-pr`, `verify-env`.
