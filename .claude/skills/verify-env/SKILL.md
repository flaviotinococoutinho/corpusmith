---
name: verify-env
description: Validar o ambiente de desenvolvimento e a saúde do Corpusmith de ponta a ponta — gate completo (pytest, tsc, compose), smoke de runtime isolado (bootstrap/seed/lint/doctor/epistemics) e smoke autenticado da API do daemon. Usar após clonar, após mudar dependências/toolchain, antes de release, ou quando "funciona na CI mas não aqui".
---

# verify-env — provar que o ambiente funciona (não supor)

Procedimento validado em máquina real (2026-07). Regra de ouro: cada
passo tem uma SAÍDA ESPERADA — se divergir, é achado, não ruído.

## 1. Gate único (o mesmo do CI e do AGENTS §2)

```bash
cd backend && .venv/bin/python -m pytest tests -q   # → N passed (AGENTS §2 diz o N vigente)
cd desktop && npx tsc --noEmit                      # → sem saída
docker compose config -q                            # → sem saída
```

Sem venv ainda? `scripts/install.sh --with-tests` (sonda interpretadores
criando venv real — Python 3.14 do Homebrew tem ensurepip quebrado; a
sonda pula sozinha; detalhes em `docs/12-instalacao.md` §7).

## 2. Smoke de runtime SEM tocar ~/corpusmith

`CORPUSMITH_HOME` redireciona TODOS os dados — sempre valide num
descartável:

```bash
export CORPUSMITH_HOME=$(mktemp -d)/corpusmith-home
backend/scripts/corpusmith okf bootstrap    # → "bundle criado"
backend/scripts/corpusmith seed             # → seed ok: terms/quotations/facts (+pipelines)
backend/scripts/corpusmith okf lint         # → 0 finding(s), 0 erro(s)
backend/scripts/corpusmith doctor           # → {"ok": true, "counts": {"error": 0, ...}}
backend/scripts/corpusmith epistemics lint  # → N mecanismo(s), 0 finding(s)
```

## 3. Smoke da API (daemon vivo, auth real)

```bash
backend/.venv/bin/python -m corpusmith.daemon &   # → "corpusmith daemon em http://127.0.0.1:8377"
TOKEN=$(python3 -c "import json,os;print(json.load(open(os.environ['CORPUSMITH_HOME']+'/state/daemon.json'))['token'])")
curl -s -H "x-corpusmith-auth: $TOKEN" http://127.0.0.1:8377/health/full   # → "ok": true
curl -s -X POST -H "x-corpusmith-auth: $TOKEN" -H "Content-Type: application/json" \
     -d '{"query":"pergunta sem cobertura"}' http://127.0.0.1:8377/ask  # → "abstained": true
```

Armadilhas conhecidas: o header é `x-corpusmith-auth` (não Bearer); o corpo
do /ask usa `query` (não question); abstenção em base vazia é CONTRATO,
não erro; sem Ollama tudo degrada para extrativo (esperado). Mate o
daemon e `rm -rf` o HOME descartável ao final.

## 4. Interpretação

- Passo 1 falha → problema de CÓDIGO ou dependência: pare, corrija antes
  de qualquer outra coisa (AGENTS §2: nada entra sem o gate).
- Passo 1 passa e 2 falha → problema de AMBIENTE/dados (git identity,
  permissões, disco); ver `docs/12-instalacao.md` §7.
- Passo 3 falha com 401 → header/token errados; com 500 → abra issue com
  o traceback do log do daemon (500 nunca é aceitável na borda).
