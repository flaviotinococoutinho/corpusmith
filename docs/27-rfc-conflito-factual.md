# 27 · RFC-005 — Conflito factual: o primeiro limiar do Harness, e o primeiro escritor de `contested`

> `AGENTS.md` §8 exige RFC para **heurística no caminho de escrita** e para
> **termo novo em eixo epistêmico**. Este toca as duas: introduz a primeira
> constante calibrável do Harness e produz o primeiro valor `contested` do eixo
> `resolution_status`, que [RFC-004](22-rfc-ontologia-da-assercao.md) declarou
> sem escritor.

| | |
|---|---|
| **Status** | Proposto (§5 é F4-PR3a, entregue; §6 é F4-PR3b, pendente) |
| **Sucede** | ADR-52 (P-5: `contested → low_yield`); RFC-004 (o eixo `resolution_status`) |
| **Origem** | `docs/14` §P-5 · `docs/18` O-2 · `PROMISED_MECHANISMS` em `harness/epistemics.py` |
| **Paga** | a 1ª das três promessas de `epistemics.toml` (`factual_conflict`) |

---

## 1. Contexto

`policy.contradiction_candidate` detecta **coexistência**: o mesmo identificador
forte (DOI/ISBN/ISSN/arXiv) em 2+ páginas sem relação de sucessão. Ele não olha
o conteúdo — duas páginas podem citar o mesmo artigo e concordar em tudo.

`docs/14` §P-5 declarou o complemento: *"em conflito" fica reservado a conflito
**factual**, detectado por regra nova `policy.factual_conflict`*. E ADR-52
renomeou `contested → low_yield` no overlay justamente para liberar a palavra.
Desde então, `contested` existe em três lugares e é escrito em nenhum:

- `ontology.toml` e `kernel/ontology.py:RESOLUTION` declaram o valor;
- `docs/18` O-2 registra que ele **não tem produtor**;
- e o renomeio de ADR-52 ficou **incompleto** em duas saídas (§7).

## 2. O problema de desenho que o levantamento encontrou

A formulação de `docs/14` — *"mesma entidade de kind quantity/date com valores
fora de tolerância"* — **não é implementável como está**, e a razão é estrutural:

```
quantities.py:67   canonical = f"{value:g} {disp}"      # "250 ms"
schema_index.sql:49  entities UNIQUE(kind, canonical)
```

O `canonical` de uma quantidade **é o próprio valor**. Duas quantidades em
conflito são, por construção, **entidades diferentes** — nunca "a mesma entidade
com valores diferentes". E não existe coluna que ligue uma quantidade ao
**sujeito de que ela é predicado**: `page_entities` diz que a página menciona
`250 ms`, não que ela *afirma* que algo dura 250 ms.

Sem sujeito, um detector ingênuo compararia toda quantidade com toda quantidade
do corpus. Num corpus técnico onde `250 ms` e `10 GiB` aparecem em dezenas de
páginas, isso inunda a fila — e a fila ordena por `value/cost_min` com
contradição valendo **0.85**, o segundo maior valor do produto. O modo de falha
não é "detector impreciso": é **a fila inteira perder credibilidade**.

## 3. A decisão de desenho: refinamento, não detector paralelo

**O sujeito já existe, e é o grupo de identificador forte.** Duas páginas que
citam o mesmo DOI falam da mesma fonte; uma divergência numérica entre elas é
conflito factual. Duas páginas sem nada em comum que mencionam `250 ms` não são
conflito nenhum — são coincidência léxica.

Portanto `policy.factual_conflict` é um **refinamento** de
`policy.contradiction_candidate`: só olha **dentro** dos grupos que aquele
detector já sinalizou.

Três consequências, e todas são ganho:

1. **precisão por construção** — o detector é limitado pelo número de
   contradições candidatas. Ele não pode inundar a fila porque não pode produzir
   mais itens do que o detector que já existe;
2. **nenhum sujeito novo** — reusa a única noção de "estas duas páginas falam da
   mesma coisa" que o produto tem, em vez de inventar a segunda;
3. **`meta` compatível** — mesma forma (`identifier`, `pages`), então a chave de
   supressão de falso positivo (`pattern_key`) e o `MergePages` continuam
   funcionando sem mudança.

## 4. As cláusulas, e as duas que caem

`docs/14` §P-5 lista sete cláusulas. Duas não sobrevivem à leitura do código:

| Cláusula declarada | Decisão |
|---|---|
| mesma entidade de kind `quantity`/`date` | **substituída**: o sujeito é o grupo de identificador (§3) |
| mesma dimensão SI | **mantida** — `quantities.py:5` já produz `dim` |
| valores fora de tolerância declarada | **mantida**, e o número é proposto na §5.2 |
| sem sucessão entre as páginas | **mantida** — herdada do grupo, que já particiona por union-find |
| sem ordenação temporal | **adiada**: os candidatos são `valid_at` (declarado corrompido pelo P-9, cuja limpeza é o *outro* item do F4-PR3) e `stale_as_of` (tempo de código). Usar `valid_at` antes da limpeza é circular — fica registrado como resíduo, não silenciado |
| **unidade idêntica** | **removida** — ver abaixo |
| span nas duas | **mantida** — `page_entities.span_start/end` existe |

**Por que "unidade idêntica" cai.** Ela descarta exatamente o caso que a
normalização SI existe para pegar: `12 km` e `12000 m` são o **mesmo** valor com
unidades diferentes, e `12 km` contra `20000 m` é um conflito real que a
cláusula esconderia. Comparar em SI é mais preciso *e* mais simples. A cláusula
foi escrita antes de o payload `si` existir; hoje ela só compra falso negativo.

**O que fica FORA, declarado:**

- **temperatura** — `quantities.py:65` suprime `si` para `dim == "temp"` (não há
  conversão afim °C↔°F). Sem SI, não há comparação. O buraco é declarado aqui e
  no contrato, não descoberto depois;
- **`ratio` (`%`)** — porcentagem não é dimensão física. `50%` numa página e
  `80%` noutra podem ser percentuais **de coisas diferentes**; comparar seria
  inventar sujeito;
- **`date`** — datas só carregam `{"iso": ...}`: não há dimensão nem tolerância
  definível sem decidir o que "datas divergentes" significa (edição diferente?
  acesso diferente?). Fica para quando houver caso medido.

## 5. F4-PR3a — o instrumento (entregue neste PR)

Mesmo padrão do PR-0 e do F3-PR0: **o instrumento antes da obra**. O que entra
agora é puro, aditivo e não muda comportamento de nenhum caminho de escrita.

### 5.1 `kernel/factual.py` — a regra, sem I/O

Recebe `{rel_path: [{"dim", "si", "unit", "surface", "span"}]}` e devolve as
divergências. Não importa `normalize` (seria camada externa para o núcleo puro);
recebe a forma mínima e é testável sem disco.

**A guarda de precisão que não estava no plano.** Uma dimensão só vira conflito
se **cada página envolvida afirmar UM valor** para ela. Uma página que menciona
`12 km` *e* `20 km` está descrevendo faixa ou comparação — não está afirmando um
valor, e comparar o extremo dela com o de outra página seria ler mal o texto.

### 5.2 A tolerância — a primeira constante calibrável do Harness

`TOLERANCIA_RELATIVA = 0.01` (1% sobre o valor SI de maior magnitude).

**Como o número foi escolhido, e o que ele não é.** Abaixo de 1% ficam
arredondamento de exibição e transcrição (`1.5 GB` vs `1500 MB` são idênticos em
SI; `12.5 km` vs `12.51 km` é digitação). Acima, a divergência sobrevive a
qualquer formatação razoável.

Este é o **primeiro limiar numérico do Harness** — hoje as regras usam só
cardinalidades (`< 2`) e truncamentos. Não há precedente interno de calibração
para copiar, e **não há golden set de conflitos factuais neste repositório**.
Portanto, com a mesma honestidade que `epistemics.toml` já aplica ao HI/LO da
reconciliação: **o valor é um ponto de partida declarado, não calibrado**. O
contrato epistêmico (§6) dirá isso em `assumptions`, e a calibração é condição
de reentrada, não promessa.

### 5.3 `contested` ganha leitura — e marcar não é assentar

`kernel/ontology.classificar(meta, *, em_conflito=False)` passa a devolver
`resolution_status = "contested"`.

`ontology.toml` diz do eixo: *"só um ato posterior desata; nenhuma fusão,
recompilação ou reindexação pode assentar sozinha o que ninguém assentou"*. Um
detector que marca `contested` **não viola** essa restrição, e vale dizer por
quê: `contested` é precisamente o estado **não assentado**. Marcar é registrar
que o nó existe; assentar seria escolher um lado. A restrição proíbe a segunda
coisa, e o detector faz só a primeira.

## 6. F4-PR3b — a obra (NÃO entregue neste PR)

1. `check_corpus` emite `policy.factual_conflict` dentro dos grupos que já
   produzem `contradiction_candidate` — **warn**, na mesma camada (a resolução
   nunca é automática, e `check_corpus` nunca é `error` por decisão declarada);
2. a fila distingue os dois: conflito factual vale mais que coexistência
   genérica, porque é acionável (há um número para conferir);
3. `[mechanisms.factual_conflict]` em `epistemics.toml`, com o limiar em
   `parameters` cruzado com a constante real, e o nome **movido** de
   `PROMISED_MECHANISMS` para `EXPECTED_MECHANISMS` no mesmo commit — o gesto de
   mover é o registro da dívida paga;
4. o código novo entra em `docs/06-referencia.md` §1 (a tabela de códigos não é
   travada por teste; a obrigação é processual).

**Por que separado.** A §5 é aditiva e não muda nada; a §6 muda o que o painel
Qualidade mostra, o que a fila propõe e o que o registro epistêmico afirma. São
riscos diferentes e merecem revisões diferentes.

## 7. Achado colateral: o renomeio de ADR-52 está incompleto

O levantamento encontrou duas saídas **user-facing** que o rename não alcançou,
e nenhuma quebra o gate:

| Onde | O que ainda diz |
|---|---|
| `usecases/cognitive_journey.py:537` | emite o sinal literal `("contested", 0.8)` em `GET /cognitive/curation` — derivado de `page_overlay.status = 'low_yield'` |
| `cognitive/scoring.py:66` | escreve na UI *"⚔ contestada no canônico — há disputa aberta"* a partir de `view.low_yield` |

`docs/18` diz "rename entregue". **Está incompleto**, e agora é perigoso: a
palavra passou a ter dois donos — o valor legado do overlay e o valor de
primeira classe do eixo `resolution_status`. Um `grep` cego de `contested`
destruiria o vocabulário novo.

O conserto é **pré-requisito do F4-PR3b**, não parte dele: enquanto a API emitir
`contested` significando "deu beco", nenhum consumidor pode confiar no
`contested` que significa "há divergência factual". Registrado em `docs/18` como
item próprio.

## 8. Invariantes

- **I-1** — o detector nunca produz mais grupos que `contradiction_candidate`
  (limitação por construção, testável);
- **I-2** — página que afirma dois valores da mesma dimensão não entra em
  conflito (guarda de faixa);
- **I-3** — `temp` e `ratio` nunca produzem conflito, e a exclusão é declarada;
- **I-4** — comparação em SI: `12 km` vs `12000 m` **não** é conflito;
- **I-5** — `contested` só aparece com `em_conflito=True`; nenhum caminho o
  produz sozinho.

## 9. Modos de falha

| Falha | Sintoma | Contenção |
|---|---|---|
| tolerância baixa demais | fila inunda dentro dos grupos | limitado por I-1; supressão por `pattern_key` já existe |
| tolerância alta demais | conflito real passa | declarado como não-calibrado; condição de reentrada é golden set |
| unidade composta (`km/h`) | não detectada | `RE_QTY` casa uma chave de `UNITS` só — limite declarado |
| °F mapeado para SI `°C` com fator 1.0 (`quantities.py:27`) | valor errado | hoje **inerte** (`temp` suprime `si`); vira defeito se alguém habilitar temperatura sem corrigir — anotado |

## 10. Risco de overengineering

O detector é ~60 linhas puras. O risco real não é o tamanho: é **introduzir o
primeiro limiar numérico do Harness sem instrumento de medida**. A contenção é
não fingir calibração — o número entra declarado como ponto de partida, o
contrato epistêmico dirá isso, e a §6 não move a promessa para "pago" sem o
contrato que admite o limite.
