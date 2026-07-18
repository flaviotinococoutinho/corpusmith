---
name: ship-pr
description: Entregar uma mudança do LLM Wiki como PR seguindo o protocolo normativo do AGENTS.md — teste que falha antes, menor mudança, gate completo, PR com invariantes declarados e evidência executável, CI verde, merge e limpeza de branch. Usar sempre que uma mudança de código estiver pronta para sair do working tree.
---

# ship-pr — do working tree ao main sem quebrar o contrato

O protocolo é o do `AGENTS.md` §8; esta skill é a ordem operacional.
NUNCA commite direto na `main`.

## 1. Antes de escrever código (se ainda não fez)

1. Leia `AGENTS.md`, o trecho da spec (`docs/10`) e o ADR da área (`docs/08`).
2. Localize o teste de arquitetura/contrato que cobre a área (tabela de
   invariantes do AGENTS §4).
3. **Escreva o teste que FALHA antes** — rode e guarde a saída da falha
   (ela vira evidência no PR).
4. Menor mudança possível; zero refactor incidental.

## 2. Gate (obrigatório, na raiz)

```bash
cd backend && .venv/bin/python -m pytest tests -q
cd desktop && npx tsc --noEmit
docker compose config -q
```

Se a contagem de testes mudou, atualize o número em `AGENTS.md` §2 e no
`README.md` (montagem) — eles citam a contagem exata de propósito.

## 3. Sincronizar o que a mudança tocou

- Funcionalidade core mudou → invoque `/docs-sync` (mapa código→doc).
- Item do backlog fechado → risque em `docs/09-backlog.md` com a versão
  (`~~ID~~ (vX.Y)`), como A-06 e DATA-1.
- Camada/regra de arquitetura mudou → `architecture.toml` (preso a teste).
- Mecanismo heurístico novo/alterado → contrato em `epistemics.toml`
  (o lint proíbe garantia universal e autocertificação).

## 4. Entrega

```bash
git checkout -b claude/<tema-curto>
git add <arquivos intencionais>          # nunca `git add .` às cegas
git commit                               # mensagem: o QUÊ + POR QUÊ + invariantes
git push -u origin claude/<tema-curto>
gh pr create --base main ...
```

Corpo do PR MUST ter: o que muda e por quê · **Invariantes (INV-AI-001)**
afetados/preservados · **Evidência executável** (saídas reais do gate e
do teste-que-falhava) · desvios conscientes, se houver.

## 5. CI, merge e limpeza

```bash
gh pr checks <n> --watch      # backend + desktop + compose verdes
gh pr merge <n> --merge --delete-branch
git checkout main && git pull --ff-only && git fetch --prune
git branch -d claude/<tema-curto>
```

Merge sem CI verde é proibido. Depois do merge, confirme que `main`
local == remoto e que nenhum branch morto sobrou (`git branch -a`).
