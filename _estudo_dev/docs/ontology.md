# Ontologia

## Camadas

A ontologia segue a progressão:

1. método e evidência;
2. linguagens e runtime;
3. aplicação e dados;
4. eventos e distribuição;
5. plataforma e operação;
6. arquitetura e Staff.

Cada conceito tem um único módulo proprietário. Outras associações são relações, não cópias.

## Tipos de entidade

- `domain`: região ampla do conhecimento;
- `concept`: mecanismo ou ideia;
- `technology`: implementação nomeada;
- `tool`: instrumento de desenvolvimento ou operação;
- `pattern`: solução recorrente com contexto;
- `methodology`: processo de decisão ou trabalho;
- `rule`: restrição normativa ou guardrail;
- `system`: cenário integrador;
- `document`: fonte catalogada;
- `skill`: capacidade observável.

## Relações

| Relação | Leitura | Regra |
|---|---|---|
| `prerequisiteOf` | A deve vir antes de B | acíclica |
| `implements` | A materializa B | direção explícita |
| `constrainedBy` | A é limitado por B | registrar o limite |
| `contrastsWith` | A esclarece B por contraste | simétrica na UI |
| `failureModeOf` | A é modo de falha de B | exige mitigação |
| `mitigates` | A reduz risco de B | não implica eliminar |
| `measuredBy` | A é observado por B | métrica não é objetivo |
| `evidencedBy` | A tem suporte em B | aponta para evidência |
| `appliedIn` | A aparece no cenário B | não prova universalidade |
| `supersedes` | A substitui B | temporal e acíclica |

## Invariantes

- nenhum ID duplicado;
- nenhuma relação órfã;
- `prerequisiteOf`, `partOf` e `supersedes` sem ciclos;
- uma seta causal relevante aponta para uma afirmação verificável;
- o grafo visual possui alternativa textual;
- filtros não escondem a natureza epistemológica do nó.

## Regra de modelagem

Quando surgir um tema novo, pergunte:

1. é uma entidade, afirmação, evidência, fonte, prática ou progresso?
2. qual é o módulo proprietário?
3. de que depende?
4. o que habilita, limita ou mitiga?
5. que evidência sustenta a afirmação?
6. quando deve ser revista?
