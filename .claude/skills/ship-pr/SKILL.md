---
name: ship-pr
description: Entregar uma mudança do Corpusmith como PR seguindo o protocolo normativo do AGENTS.md — teste que falha antes, menor mudança, gate completo, PR com invariantes declarados e evidência executável, CI verde, merge e limpeza de branch. Usar sempre que uma mudança de código estiver pronta para sair do working tree.
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
just verify
```

A lista do que o gate executa tem UMA fonte — `architecture.toml [gate]`,
cruzada com o `ci.yml` e com o `justfile` por `test_pr0_gate.py`. Esta
skill não a copia (as cópias divergiam). **Nunca crave contagem de testes
em doc viva**: `test_pr0_gate` e `test_docs_contract` reprovam; cite
`corpusmith context`.

## 3. Sincronizar o que a mudança tocou

- Funcionalidade core mudou → invoque `/docs-sync` (mapa código→doc; o
  primeiro passo é `just context` e ler o diff do mapa).
- Item da fila fechado → mova a linha de `docs/18-backlog-consolidado.md`
  §11 para a seção histórica do mesmo documento, NO MESMO COMMIT, com o
  teste que prova. `docs/09` é histórico (congelado): não escreva lá.
- Camada/regra/invariante de arquitetura mudou → `architecture.toml`
  (`[gate]`, `[[invariant]]` — presos a teste).
- Requisito não funcional mudou de estado → `nfr.toml` (`declared` →
  `pinned` só com o teste em `verified_by`).
- Mecanismo heurístico novo/alterado → contrato em `epistemics.toml`
  (o lint proíbe garantia universal e autocertificação); termo ou valor
  novo em eixo → `ontology.toml` (RFC, não ADR).
- Doc novo em `docs/` → linha em `docs/README.md` e a linha
  `> **Altitude:** … · **Status:** vivo|histórico` na cabeça.

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
gh pr checks <n> --watch      # todas as pernas do ci.yml verdes
gh pr merge <n> --squash --delete-branch   # CONTRIBUTING.md: squash merge
git checkout main && git pull --ff-only && git fetch --prune
git branch -d claude/<tema-curto>
```

Merge sem CI verde é proibido. Depois do merge, confirme que `main`
local == remoto e que nenhum branch morto sobrou (`git branch -a`).
