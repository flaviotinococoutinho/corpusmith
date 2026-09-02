# Epistemologia operacional

O portal separa conteúdo organizado de conteúdo justificado.

## Classes de conhecimento

| Código | Classe | Uso |
|---|---|---|
| `OF` | fato público oficial | documentação, vaga ou publicação primária |
| `RA` | relato anedótico | experiência pública sem garantia de generalidade |
| `INF` | inferência | conclusão explícita, nunca apresentada como fato |
| `PU` | prática universal | engenharia geral, independente de empresa |
| `PF` | fato pessoal | somente no perfil privado e com evidência autorizada |
| `PS` | síntese pessoal | reflexão ou narrativa a confirmar |

## Estado e confiança

Uma afirmação usa um estado:

- `supported`: evidência suficiente no escopo declarado;
- `provisional`: útil, mas ainda incompleta;
- `disputed`: existe contraevidência relevante;
- `deprecated`: deixou de valer no escopo/versionamento;
- `unknown`: evidência pendente.

Confiança alta não significa validade universal. Ela só expressa quão bem a evidência sustenta a frase dentro do escopo.

## Graus de evidência

- **A:** especificação, documentação primária, teste ou medição reproduzível;
- **B:** código, postmortem ou evidência empírica primária contextualizada;
- **C:** fonte secundária tecnicamente confiável;
- **D:** relato, heurística ou inferência a confirmar.

## Contrato de entrevista

Uma resposta madura percorre:

```text
conclusão
→ mecanismo causal
→ cenário e invariante
→ falhas e limites
→ observabilidade e teste
→ trade-off e mecanismo durável
```

A régua 0–4 mede evidência:

- 0: inseguro;
- 1: superficial;
- 2: happy path;
- 3: produção;
- 4: Staff com influência e mecanismo durável.

## Regra para stack pública

A frase “a empresa usa X” exige fonte pública primária, data, sistema/time descrito e limite. Uma vaga ou artigo não prova uma stack única. Repositórios comunitários são material de estudo, não evidência empresarial.
