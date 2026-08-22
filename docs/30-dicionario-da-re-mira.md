# 30 · Dicionário da re-mira e a disciplina que a sustenta

> **Para que serve.** A RFC-006 nomeou as duas patologias mais caras deste
> repositório: *um nome carregando várias perguntas* e *atributo afirmado
> no nível errado*. Este documento é a vacina de vocabulário: onde uma
> palavra da re-mira poderia significar duas coisas, aqui está fixado qual
> ela significa, qual ela NÃO significa, quem é o dono e **qual teste
> prende** — porque definição sem guarda é opinião.
>
> Complementa, não substitui: o léxico geral é [`23`](23-ontologia-e-etimologia.md)
> + [`ontology.toml`](../ontology.toml); os contratos de mecanismo,
> [`epistemics.toml`](../epistemics.toml); a direção, [`29`](29-rfc-006-re-mira.md).

---

## 1. Os termos da re-mira

### estabilidade — QUATRO sentidos, quatro donos

A palavra mais perigosa da V3. Um score único somando os quatro seria o
novo `confidence`-com-seis-perguntas (a lição do `[drift.time]`).

| Sentido | Pergunta | Dono | Onde mora |
|---|---|---|---|
| **edição** | quantas vezes a página foi ESCRITA? | `kernel/stability.py` | `page_stability.edits` |
| **ciclo de vida** | foi sucedida/invalidada por ato declarado? | `kernel/vitality.py` (stability LÊ, nunca recalcula) | `page_stability.lifecycle` |
| **uso** | ainda é consultada? | `page_heat` | cognitivo/retrieval |
| **tema** | a partição em volta dela se moveu? | `theme_epochs` (RFC-001) | index.db |

O que "estável" **não** significa: correto, revisado, aprovado, importante.
Página errada que ninguém revisita é perfeitamente quieta. Guarda:
contrato `editorial_stability` (misinterpretations) + cross-check das
exclusões em `test_epistemics_toml`.

### núcleo × volátil — decisão de LEITURA, não de máquina

O ranking é determinístico e **sem limiar**: onde cortar "núcleo durável"
é escolha de quem lê. Qualquer corte fixo seria uma calibração que ninguém
fez — a mesma razão de o 1% do `factual_conflict` ser declarado NÃO
calibrado. Guarda: `test_consolidar_ordena_da_mais_quieta_para_a_mais_volatil`.

### lente/ótica ≠ tema ≠ goal ≠ eixo

Quatro palavras que a conversa cotidiana mistura e o produto separa:

- **lente/ótica (sentido)** — em que disciplina o termo tem este sentido
  ("entropia" em física ≠ em informação). **Existe desde a V2**, e mora no
  CANÔNICO da entidade (`Entropia (física)`), não num eixo de asserção
  (`ontology.toml` declara `applies_to = "assertion"` para eixos; sentido
  fala da entidade) nem num campo `sense` paralelo (dois donos do mesmo
  fato). Lido por `normalize.gazetteer.sentido()`; guarda:
  `test_sentido_e_base_leem_o_qualificador_do_canonico`;
- **tema** — partição EMERGENTE do grafo (RFC-001): rótulo sem semântica,
  diz "estas páginas andam juntas", não "são sobre o mesmo assunto";
- **goal** — recorte de SESSÃO do domínio cognitivo (`cognitive/gates.py`):
  o que o usuário quer agora, não o que o conceito é;
- **eixo** — pergunta epistêmica de vocabulário fechado sobre uma
  asserção (`kernel/ontology.py`). INV-ONT-001: nenhum termo em dois eixos.

Armadilha registrada na RFC-006 §3-V2: enfiar "disciplina" no campo
`authority` do gazetteer criaria o 6º sentido do nome mais derivado do
repositório (`[drift.authority]` está aberta com 5).

### sujeito forte — e os DOIS conjuntos que a palavra esconde

"Identificador forte" responde a duas perguntas diferentes, em dois
lugares, de propósito:

| Conjunto | Pergunta | Conteúdo | Dono |
|---|---|---|---|
| `STRONG_IDS` | "é o MESMO documento?" (escada de escrita) | doi, isbn, issn, arxiv, git_sha | `reconcile_candidate.py` |
| `CONTRADICTION_IDS` | "falam DA MESMA coisa?" (sujeito de conflito) | os acadêmicos + normas: iso, nbr, rfc, nist, ieee, eu_reg, circular | `harness/local_policy.py` |

Duas notas que citam a mesma ISO **falam da mesma norma** (podem
conflitar) e **não são o mesmo documento** (não podem fundir por carona).
Guarda: `test_reconciliacao_nao_ganha_normas_por_efeito_colateral`.

`regulator` (LGPD, GDPR, OWASP) fica fora dos DOIS: nomeia um REFERENTE
(lei, organização), não um texto — incluí-lo compraria o sujeito inventado
que a RFC-005 §3 recusou. Guarda: `test_regulator_nao_forma_sujeito`.

### precedência ≠ ambiguidade (a distinção que a V2 vive de manter)

Duas identidades reivindicando o mesmo alias significam coisas opostas
conforme a CAMADA:

| Situação | Leitura | Por quê |
|---|---|---|
| camadas diferentes (bundle × reference × seed) | **precedência** — a mais alta vence, em silêncio e corretamente | é a regra de sempre (v0.22): a curadoria humana é a última palavra, e avisar seria ruído em todo bundle que corrige uma grafia |
| mesma camada | **ambiguidade** — ninguém tem autoridade sobre o outro | escolher seria inventar; o produto marca `ambiguous` e devolve a decisão ao humano |

Guarda: `test_registro_curado_vence_o_seed_sem_virar_conflito` e
`test_camadas_diferentes_resolvem_por_precedencia`.

### ambíguo — o estado honesto, com preço declarado

`confidence = "ambiguous"` já significava "não resolvido" em toda a
cadeia; a V2 apenas passou a **produzi-lo** em vez de resolver sozinha. O
que ele desliga, de propósito: reescrita do texto (`_rewritable` exige
`extracted`), índice de entidades (`fts`), lista do frontmatter
(`entities_frontmatter`), peso de aresta (0.15). O preço: enquanto o
conflito durar, o termo **não liga páginas** — recall trocado por não
mentir, e a troca é declarada no contrato.

### conflito factual ≠ coexistência ≠ low_yield ≠ alias em conflito

- **coexistência** (`policy.contradiction_candidate`) — o mesmo sujeito em
  2+ páginas sem sucessão. Não diz que discordam;
- **conflito factual** (`policy.factual_conflict`) — dentro da
  coexistência, número divergente na mesma dimensão SI. Não diz quem erra;
- **low_yield** — desfecho de USO ("não rendeu"), sem relação com
  divergência. A palavra antiga (`contested`) foi devolvida ao eixo
  `resolution_status` (ADR-52/O-6), que segue **sem escritor persistente**
  (O-2 aberta);
- **alias em conflito** (`policy.alias_conflict`) — nada disso: é sobre
  o VOCABULÁRIO, não sobre o conteúdo. Duas identidades disputam uma
  palavra; nenhuma página precisa estar errada.

### LLM-wiki e memória de IA — dois nomes de USO do mesmo bundle

Não são componentes novos. O bundle **é** a wiki (páginas OKF legíveis,
versionadas, com evidência) e **é** a memória que agentes consomem (via
projeções e `/ask` com citação e abstenção). O modelo **propõe, nunca
assenta** (A-3/A-4): prosa gerada que reentrar carrega `generated_via`.
"Dirigir ideias" = fila de atenção; "refinar" = atos de curadoria com
preview.

---

## 2. A natureza da memória, por nível de acesso

A pergunta que organiza os cinco bancos não é "onde está o dado" — é
**"quem pode escrever, por qual porta, e o que sobrevive a quê"**. O
gradiente vai do mais governado ao mais descartável:

| Fonte | Natureza | Escreve | Porta de escrita | Sobrevive a | Guarda |
|---|---|---|---|---|---|
| `knowledge/bundle` + Git | **canônica** — a autoridade | humano (atos com preview) e máquina (sob política) | ÚNICA: Harness + `BundleWriter` | tudo — é o que os outros seguem | INV-DATA-001 |
| `index.db` | **derivada** — projeção consultável | só o produto (rebuild/projeções) | `rebuild_index` + use cases de projeção | nada — apague e reconstrua | INV-DATA-003 |
| `runtime.db` | **operacional** — jobs, trilhas, checkpoints | só o produto | módulos de runtime | rebuild do índice (por isso os checkpoints moram AQUI) | INV-OPS-002 |
| `cognitive.db` | **experiência** — desfechos, prática, calibração | só o produto, a partir de gesto humano | domínio cognitivo | falha cognitiva NÃO altera o canônico | INV-DATA-004 |
| `reference.db` | **cache do mundo** — gazetteer, normas, citações | só o produto | manage_reference | é re-obtenível; nunca vira autoridade | AGENTS §6 |

Três consequências práticas desse ordenamento:

1. **projeção nunca decide sobre o canônico** — quando decidiu, foi
   tratado como defeito (B2, RFC-002);
2. **derivada nova declara-se na cadeia** — `DERIVATIONS` em
   `kernel/checkpoints.py` é registro FECHADO: derivação não declarada nem
   grava checkpoint (`record()` recusa), e declarar é ganhar doctor, CLI e
   obsolescência transitiva de graça. `stability` (V3) entrou assim;
3. **o que precisa sobreviver ao rebuild mora em runtime.db** — carimbo
   dentro do índice morre com o índice e não consegue dizer "sumi".

---

## 3. Os conceitos de engenharia que pagam manutenção e expansão

Cada um com a asserção executável que o prende — conceito sem teste é
estilo, e estilo não sobrevive a refactor.

| # | Conceito | O que compra | Preso por |
|---|---|---|---|
| 1 | **Núcleo funcional, casca imperativa** — regra pura em `kernel/`; I/O nas bordas | testável sem disco/rede; a regra tem UM lugar | `test_architecture.py::test_kernel_and_normalize_are_pure` |
| 2 | **Gradiente de mutabilidade** — quanto mais interna a camada, menos volátil | mudança cara fica rara; mudança barata fica barata | `architecture.toml` + INV-ARCH-001..006 |
| 3 | **Um nome, uma pergunta** — vocabulário fechado; deriva REGISTRADA quando existe | a conversa não degrada; `grep` volta a ser confiável | INV-ONT-001, `ontology lint`, varredura por SENTIDO no fonte |
| 4 | **Nível certo da escada** — atributo afirmado onde é verdade para o objeto inteiro | evita a classe de defeito mais cara (docs/28 §2) | revisão obrigatória da RFC-006 §8 |
| 5 | **Autoridade única + projeções recomputáveis** — Git é o juiz; o resto deriva | experimento seguro: o pior caso é reindexar | INV-DATA-003, `DERIVATIONS` |
| 6 | **Um caminho de escrita** — todo byte canônico passa pelo gate | política impossível de pular por construção | INV-DATA-001, Template Method fechado (INV-ARCH-006) |
| 7 | **1 use case = 1 `execute()`; facades onde 2+ domínios se encontram** — API só fala com facades | a intenção cabe no nome; orquestração tem endereço | INV-ARCH-004/005 |
| 8 | **Contratos executáveis** — architecture/epistemics/ontology.toml presos a testes | doc que mente QUEBRA a suíte, em vez de envelhecer | `test_pr0_gate`, `test_epistemics_toml`, `test_ontology` |
| 9 | **Falsificabilidade por mutação (A-6)** — teste que passa com e sem a mudança é teatro | a suíte prova que vigia, não só que passa | mutações executadas e registradas por PR |
| 10 | **Complexidade isolada atrás de porta** — otimização (Rust, caches) NUNCA decide domínio; fallback declarado | o difícil fica documentado num lugar só e removível | ADR-39, `compute/` como porta, `bench compare` fora do gate |
| 11 | **Resiliência declarada** — erro com código estável; retry só idempotente; job termina ou é recuperável; preview antes do efeito; lote com teto | falha vira estado nomeado, não surpresa | INV-OPS-001/002, `LOTE_MAXIMO` guardado, 409 nomeado |

**O ritual de extensão** (como a V3 entrou, e como as próximas entram):
teste que falha antes → regra pura no kernel → leitura/escrita na camada
que pode → derivação declarada → contrato com garantias E limites → docs
+ dicionário → mutações executadas → gate. Pular etapa não é atalho; é
onde as duas patologias da §1 entram.
