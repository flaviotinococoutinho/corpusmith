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
- Item da fila fechado → marque ✅ na PRÓPRIA linha de
  `docs/18-backlog-consolidado.md` §11, NO MESMO COMMIT, com o teste ou ADR
  que prova — a linha fica: `corpusmith context` conta abertos e fechados
  lendo a §11. `docs/09` é histórico (congelado): não escreva lá.
- Arquivo ou pasta nova → bloco que a cobre em `ontology.toml` §4 (o
  `ontology lint` reprova arquivo versionado sem bloco); unidade Python nova
  → camada em `architecture.toml [[tier]]` + bloco homônimo; import novo
  entre blocos → `depends_on` (e `debts`, com motivo, se apontar para fora
  do gradiente). `corpusmith ontology where <caminho>` diz onde algo mora.
- Camada/regra/invariante de arquitetura mudou → `architecture.toml`
  (`[[tier]]`, `[gate]`, `[[invariant]]` — presos a teste).
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
gh pr create --base main --body-file <corpo preenchido>
```

O corpo do PR segue as seções de `.github/PULL_REQUEST_TEMPLATE.md`
(`--body` sem o template pula as duas perguntas que `docs/30` §3 deixa
como guarda humana). MUST ter: o que muda e por quê · **Invariantes
(INV-AI-001)** afetados/preservados · autoridade e projeções · NFR (algum
`status` muda?) · termo novo responde a UMA pergunta? · em que NÍVEL da
escada o atributo é afirmado · **Evidência executável** (saídas reais do
gate e do teste-que-falhava) · risco e rollback · desvios conscientes.

## 5. CI, merge e limpeza

```bash
gh pr checks <n> --watch      # todas as pernas do ci.yml verdes
gh pr merge <n> --squash --delete-branch   # CONTRIBUTING.md: squash merge;
                                            # --delete-branch já apaga o local e o remoto
git checkout main && git pull --ff-only && git fetch --prune
```

Merge sem CI verde é proibido. Depois do merge, confirme que `main`
local == remoto e que nenhum branch morto sobrou (`git branch -a`).
