# Contrato de conteúdo

## Conceito

```js
{
  id, moduleId, slug, title, kind,
  summary, mechanism, rule, trap,
  priority, epistemic, confidence,
  versionScope, prerequisites, relations,
  sourceIds, tags
}
```

## Fonte

```js
{
  id, title, type, organization,
  locator, bundled, visibility,
  epistemicGrade, reviewedAt, scope
}
```

`locator` é um identificador relativo ou pesquisável; nunca uma URL completa.

## Questão

```js
{
  id, conceptIds, prompt, targetSeconds,
  answer30, answer120, mustMention,
  traps, followUps, rubric
}
```

## Progresso

```js
{
  score: 0..4,
  attempts: [{ attemptedAt, score, errors, evidence }],
  nextReviewAt,
  stage: "R0" | "R1" | "R3" | "R7" | "R14"
}
```

Progresso não pode alterar conceito, afirmação ou fonte.

## Checklist para uma contribuição

1. o ID é estável e único;
2. o resumo define sem circularidade;
3. o mecanismo explica causa, não só benefício;
4. a regra diz quando aplicar;
5. a armadilha mostra uma falha observável;
6. o escopo e a versão estão visíveis;
7. a fonte sustenta exatamente a afirmação;
8. relações apontam para IDs existentes;
9. nenhum dado privado foi copiado;
10. a interface continua funcional offline.
