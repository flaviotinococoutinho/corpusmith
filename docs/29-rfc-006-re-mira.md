# 29 · RFC-006 — A re-mira: do compilador de corpus ao instrumento de estudo

> Este documento fixa uma **direção de produto**, e direção não costuma exigir
> RFC — mas esta exige, por três gatilhos do `AGENTS.md` §8 que as capacidades
> abaixo vão tocar: **mudar o domínio de sujeito de uma heurística** (V1 amplia
> o sujeito do conflito factual — `usecases/curate/merge.py:86-87` registra que
> isso pede RFC), **heurística nova** (V4 compõe um índice; V2 propõe sentido
> por modelo sob gate) e **vocabulário de identidade** (V2 muda o que "mesmo
> conceito" significa). O RFC é o guarda-chuva que fixa fronteiras UMA vez;
> cada capacidade que dispara um gatilho próprio ainda paga o próprio gate
> quando chegar a vez dela.
>
> A base factual foi levantada por cinco leituras independentes do código e
> validada adversarialmente contra os axiomas (2026-08-22); toda alegação
> "já existe" abaixo carrega `arquivo:linha`.

| | |
|---|---|
| **Status** | Aceito como direção (pedido do dono, 2026-08-22); capacidades entram uma a uma, cada qual pelo seu gate |
| **Sucede** | RFC-004 (eixos da asserção) · RFC-005 (conflito factual) · ADR-53 (categoria e fronteira de honestidade) |
| **Origem** | pedido do dono · `docs/18` §9 (fila corrente) · mapeamento V1–V6 desta data |
| **Efeito imediato** | reordena a fila (`docs/18` §10); **nenhum** schema, autoridade ou default muda por este documento |

---

## 1. A demanda, nas palavras de quem usa

O público é **quem estuda e acumula conteúdo** — conceitos, axiomas, normas
(ISO, RFC, ABNT, circulares), metodologias — e tromba nos mesmos quatro muros:

1. **conceitos muito próximos sob óticas diferentes**: a mesma palavra em
   física, matemática ou direito carrega sentidos vizinhos que se contaminam
   (ambiguidade, viés) — e nenhuma ferramenta de nota separa os sentidos;
2. **ideias abstratas sem enquadramento**: entender como uma ideia funciona
   *na prática*, ou se ela se enquadra diretamente num caso;
3. **não saber o que permanece**: quem acumula muito não distingue o que
   menos muda (o núcleo durável) do que é volátil — nem o que é mais
   difícil de explicar, que é onde o estudo trava;
4. **falta de linguagem prática/ubíqua para vender**: apresentar uma ideia
   com custo, tempo, complexidade, trade-offs e ganhos, em vez de jargão.

O pitch que esta re-mira persegue:

> **O Corpusmith compila conteúdo disperso em conceitos comparáveis,
> rastreáveis, explicáveis e acionáveis: mostra não apenas o que uma ideia
> significa, mas sob qual lente, o que permanece, onde diverge, como se
> aplica e quanto custa adotá-la.**

Cada verbo do pitch mapeia numa capacidade da §3 — e a fronteira de
honestidade do ADR-53 vale para o próprio pitch: **nenhum verbo entra na
superfície pública (README, material de venda) antes de a capacidade que o
paga existir e estar medida**. Vender governança exagerando a própria seria
a autocertificação que `epistemics.toml` proíbe para os mecanismos.

## 2. Por que isto é re-mira, e não pivô

A categoria não muda: *governar o que humanos e agentes podem tratar como
conhecimento* (`AGENTS.md` §1). O que muda é o **beneficiário primário** do
diferencial epistêmico — de "auditoria do corpus" para "compreensão de quem
estuda". As perguntas do estudante já são as perguntas que a maquinaria
responde ou quase responde:

| Pergunta de quem estuda | Mecanismo que a serve (ou quase) |
|---|---|
| "esses dois textos divergem sobre a mesma coisa?" | `policy.contradiction_candidate` + `policy.factual_conflict` (RFC-005) |
| "essa palavra tem o mesmo sentido aqui e ali?" | **quase**: gazetteer resolve alias → UM canônico e colapsa sentidos (V2) |
| "o que desse assunto é estável?" | **quase**: Git + sucessão + `theme_epochs` têm os insumos, falta o cálculo (V3) |
| "onde estou travado?" | **quase**: contradições, perguntas abertas, falhas de prática existem soltas (V4) |
| "onde isso se aplica na prática?" | **quase**: regiões de evidência existem; o nível da afirmação não (V5) |
| "quanto custa adotar essa ideia?" | **metade**: custo em minutos existe na fila; valor segue não calibrado (V6) |

Governar contradição, proveniência e validade temporal *já é* o instrumento
de estudo — faltava apontá-lo para o estudante em vez de para o auditor.

## 3. As seis capacidades

Formato fixo: **já existe** (com evidência) · **a menor construção** (e a
camada) · **gate** · **armadilha nomeada** — a armadilha é sempre uma
patologia que este repositório já cometeu e catalogou, porque é nelas que se
tropeça de novo.

### V1 · Catálogo por natureza epistêmica (normas como sujeitos fortes)

> **Estado: mínimo ENTREGUE** — normas em `CONTRADICTION_IDS` com
> `regulator` fora e a reconciliação intocada (`docs/18` §10). O
> "catálogo" como projeção segue aberto.

**Já existe.** `normalize/detectors/standards.py` detecta ISO/NBR/RFC/NIST/
IEEE/Regulamento UE com canônicos estáveis (`RFC 793` normalizado por
`int()`, `ABNT NBR ISO…`, `:2022` como parte do canônico) e reguladores
nomeados (LGPD, GDPR…, `standards.py:17-27`). A maquinaria de sujeito forte
— grupo por identificador → contradição/conflito — opera em
`harness/local_policy.py`, mas só para `CONTRADICTION_IDS = ("doi", "isbn",
"issn", "arxiv")` (`local_policy.py:152`); `kind="standard"` fica de fora do
filtro `m.kind == "identifier"` (`local_policy.py:255`).

**A menor construção.** (i) Promover normas a sujeitos fortes: subkinds de
standard em `CONTRADICTION_IDS`, filtro de kind relaxado, contrato
atualizado (o cross-check `test_epistemics_toml` quebra primeiro, como deve);
detector de circulares (entrada em `NAMED` ou regex novo). Camadas:
normalize (puro) + harness. (ii) O "catálogo" como **projeção**: página de
regime normativo = derivada da presença de sujeito-standard — nunca campo
escrito no canônico.

**Gate.** Mudar o domínio de sujeito da heurística exige RFC — é este.
Modos de falha a declarar no contrato: `ISO 9001` e `ISO 9001:2015` não
agrupam (canônicos distintos; no regime normativo versão ≠ mesma norma, mas
precisa estar dito); RFC 2119 citada pervasivamente forma grupo gigante.

**Armadilha.** Definir "abstrato/metodológico" como classe **negativa**
("não tem identificador forte") — colapsa "não detectado" com "não
normativo". O lado abstrato não tem detector por regex; se for classificado,
será por heurística declarada, nunca por omissão.

### V2 · Ótica/domínio na identidade do conceito

> **Estado: ENTREGUE** — alias → lista de candidatos com precedência por
> camada, sentido no canônico, `ambiguous` propagando o "não resolvido",
> `policy.alias_conflict` e contrato próprio (`docs/18` §10). A rota
> confirmou o desenho: **nenhum eixo novo, nenhum schema novo** — o
> `authority_record` já tolera campos extras e o sentido é parte do
> canônico. A escolha do sentido em contexto segue humana.

**O que existia antes deste pacote** (mapa original, preservado porque é o
diagnóstico): quase nada. A identidade de entidade é
`UNIQUE(kind, canonical)` (`backend/db/schema_index.sql:49`); um alias
resolvia para exatamente **um** canônico, e a colisão era decidida por
ordem de inserção — "entropia" da física e da informação eram **a mesma
entidade**. Temas não são disciplinas (partição emergente, rótulo sem
semântica) e seguem não sendo.

**O que existe agora**: alias → LISTA de candidatos com precedência por
camada; alias disputado vira `ambiguous` (não reescreve, não indexa, não
liga páginas); `policy.alias_conflict` nomeia a edição que resolve; o
sentido mora no canônico. A identidade de entidade continua sendo
`UNIQUE(kind, canonical)` — o qualificador é parte dela, e por isso não
houve migração.

**A menor construção.** (i) O `authority_record` (canônico, no bundle) ganha
qualificador de sentido, e o canônico desambiguado o carrega — estilo
`massa (física)` — preservando `UNIQUE(kind, canonical)` sem migração;
(ii) o gazetteer compila alias → **lista** de candidatos, e alias com 2+
canônicos emite `policy.alias_conflict` — que `docs/14` §P-10 já propunha;
(iii) a colisão silenciosa de autoridade vira finding. A **escolha** do
sentido em contexto não é determinística: fica com ato humano de curadoria,
ou proposta de modelo sob gate — nunca decisão automática. Camadas: okf +
normalize + harness + projeção.

**Gate.** Domínio é atributo de **entidade**, não eixo de asserção — criar
`[axes.domain]` em `ontology.toml` seria erro de nível (os eixos declaram
`applies_to = "assertion"`). A rota pela identidade da entidade não abre o
gate de eixo novo; a proposta de sentido por modelo, quando vier, abre o de
heurística.

**Armadilha.** `[drift.authority]` está **aberta** com cinco sentidos para a
palavra `authority` — e o campo `authority` da entrada do gazetteer é o
lugar exato onde "disciplina" seria enfiada por conveniência, virando o
sexto. Segunda: `entities.kind` já armazena o subkind — campo cujo nome diz
uma coisa e guarda outra. Disciplina exige campo próprio com pergunta
própria (INV-ONT-001).

### V3 · "O que menos muda" — estabilidade medida

> **Estado: ENTREGUE** — `kernel/stability.py`, `page_stability`,
> derivação `stability`, `corpusmith stability`, contrato
> `editorial_stability` (`docs/18` §10). Os quatro sentidos ficaram
> SEPARADOS, como a armadilha abaixo exigia; o dicionário (`docs/30`)
> fixa o vocabulário.

**Já existe.** Todos os insumos, nenhum cálculo: Git como autoridade com
commit por escrita; leitura histórica read-only pronta (`parent_of`/
`read_at`/`changed_since` em `okf/git_store.py`); sucessão/invalidação como
funções puras de frontmatter (`kernel/curation.py:33-53`); "aposentada"
definida (`kernel/vitality.py`); churn por tema já persistido
(`theme_epochs`, `backend/db/schema_index.sql:153`); retrabalho humano
declarado (`curation_acts.undoes/undone_by`). Nenhuma ocorrência de
"estabilidade"/"churn" no código de produção.

**A menor construção.** Um use case que leia história + frontmatter e
persista estabilidade por página em `index.db`, registrado em `DERIVATIONS`
(`kernel/checkpoints.py`; o registro dinâmico é recusado em
`runtime/checkpoints.py:33-36`) — ganhando doctor e cadeia de frescor de
graça. Regra de ranking pura no kernel; leitura de Git fica em okf
(precedente: `git_store.py`). Exclusão **obrigatória** de `index.md`/
`log.md`/`reviews/` do churn: toda escrita os regenera, e contá-los faria
toda página parecer volátil.

**Gate.** Nenhum — é projeção pura (A-1), determinística, sem LLM. Duas
declarações obrigatórias no contrato: churn baixo mede **quietude
editorial**, não correção (capta ≠ data, `docs/26`); e a fonte é
só-Git+frontmatter (100% re-derivável) — misturar `runtime.db` tornaria a
métrica não-reconstruível do bundle.

**Armadilha.** A lição de `[drift.time]` (quatro tempos exigiram quatro
nomes): "estabilidade" tem pelo menos quatro sentidos — edição de texto
(Git), ato de ciclo de vida (sucessão/invalidação), decaimento de uso
(`page_heat` mede USO, não mudança) e churn de tema (épocas). Um score único
somando os quatro seria o novo `confidence`-com-seis-perguntas.

### V4 · "O que é mais difícil de explicar" — índice declarado

> **Estado: ENTREGUE** (`docs/18` §10 item 5). Cinco componentes de cinco
> donos com pesos e tetos declarados no contrato
> `explanation_difficulty`; `corpusmith difficulty` + bloco no painel
> Indicadores. As três recusas do desenho estão presas por teste:
> `low_yield` fica FORA (a armadilha nomeada abaixo), silêncio sai como
> `medida=false` em vez de "fácil", e cada componente satura no seu teto.
> O que NÃO entrou: calibração dos pesos (não há ground truth de
> dificuldade — porta de reentrada é medir contra desfechos de prática) e
> derivação declarada na cadeia (dois sinais são de uso e não movem o
> HEAD; um carimbo prometeria frescor que a cadeia não entrega).

**Já existe.** Cada componente com dono: contradição/conflito factual
(harness), perguntas sem `answered_by`, `low_yield` por desfecho agregado,
falha de recuperação com sobreconfiança (o "sinal de calibração mais caro",
`cognitive/practice.py`), `misinterpretations` por mecanismo. E o **molde**
para heurística composta existe e é fiscalizado: `attention_queue` declara
pesos fixos, `guarantee_kind="heuristic"`, `guarantee_relative_to` e
fallback, com constantes amarradas por `test_epistemics_toml`.

**A menor construção.** Só a composição: função pura no kernel (à la
`vitality.py`) com pesos fixos **declarados** + bloco novo em
`epistemics.toml` + projeção. Nenhum detector novo.

**Gate.** INV-EPI-001 é a especificação, não o obstáculo — com uma tensão
real: vários componentes são auto-observação do produto, e evidência só
`self_reported` é proibada pelo contrato-mestre. O bloco precisa ancorar em
`human_feedback` (desfechos de prática SÃO resultado humano) e/ou
`deterministic_check`. A-6 exige fixture onde os componentes divergem.

**Armadilha.** Somar ingenuamente `low_yield` + contradição **re-fundiria**
o que o F4-PR2 acabou de separar: "difícil de explicar" e "ninguém achou
útil" são perguntas diferentes. Segunda: o índice é por página e fala de
compreensão de afirmações — declarar a granularidade no contrato em vez de
fingir a precisão que o nível não tem (`docs/28` §2).

### V5 · Ponte abstrato→prático

> **Estado: ENTREGUE em versão página-tipada** (`docs/18` §10 item 6) —
> exatamente o que o gate desta capacidade autorizava: "V5 em versão
> página-tipada é compatível hoje; V5 em versão afirmação, só depois de
> medir". O vocabulário fechado, o ato humano, a projeção e a consulta
> estão de pé; a **medição** que a RFC-004 §6 exige passa a existir
> (`ambiguous_fraction`). O nível da AFIRMAÇÃO segue vazio, e a
> reentrada continua condicionada — agora com um número em vez de uma
> intuição.

**Já existe.** O mapa e o buraco: o nível 3 da escada — a afirmação — "não
existe ainda" (`docs/28`, tabela do §1). Regiões de evidência existem
(nível 2, `okf/regions.py`); `/ask` cita página+span como aproximação. O que
**não** serve apesar do nome: os itens "bridge" da fila são pontes
topológicas entre temas — grafo, não epistemologia.

**A menor construção.** (i) Aresta **tipada** "aplica-se-a/exemplifica" como
ato de curadoria humano (caminho único de escrita) + projeção — vizinha de
P-6; (ii) usar V5 como a **fonte da medição** que RFC-004 §6 exige: "que
caso prático sustenta o conceito X?" é exatamente a consulta que a
granularidade de página responde errado. O enquadramento em prosa é borda
LLM, default desligado, **propondo**.

**Gate.** O mais forte dos seis: fazer V5 no nível da afirmação exige
reabrir RFC-004 §6, que exige a medição primeiro. V5 em versão
página-tipada é compatível hoje; V5 em versão afirmação, só depois de
medir. Fingir que não há gate É o conflito.

**Armadilha.** O erro de nível em pessoa: carimbar "aplica-se na prática a
Y" numa **página** afirma que todas as asserções dela se aplicam — os três
sintomas do mesmo buraco que `docs/28` §2 cataloga. Segunda: dois sentidos
de "ponte" no mesmo nome (topológica × epistêmica) — se a nova entrar na
fila com o mesmo kind, é deriva nova no dia um.

### V6 · Linguagem ubíqua — custo, tempo, trade-offs e ganhos como projeção

**Já existe.** Metade do trade-off já é legível: custo em **minutos** em
toda parte (150 wpm, piso de 2 min, mochila com `budget_min`), `reason`
textual obrigatória ("recomendação sem porquê não entra na interface"). A
outra metade não: `value` é constante interna não calibrada, e o código
admite — *"o detector não mede importância"*
(`usecases/next_actions.py:44-47`). Gerador de linguagem de venda:
inexistente.

**A menor construção.** Uma projeção de borda: facade read-only que monta um
**fact sheet determinístico** (estabilidade V3, dificuldade V4, custos da
fila, garantias declaradas dos contratos, `misinterpretations`) + estágio
LLM com default **desligado** produzindo prosa FORA do bundle (artefato de
export). Se persistir, página de máquina com `generated_via`, pelo caminho
único. As ressalvas do fact sheet são **re-anexadas deterministicamente**
após a geração — fora da região que o modelo pode editar.

**Gate.** A-3/A-4 são satisfeitos por construção ("LLM lê projeções; nunca
escreve no canône" é o enunciado da própria demanda). Restrições de
conteúdo herdadas: sem "zero alucinação", sem "fonte da verdade", arte
prévia citada como arte prévia (ADR-53 §3, `docs/26`).

**Armadilha.** Autocertificação: citar as constantes internas não
calibradas (0.9, 0.85) como "ganhos medidos" — o repositório recusou esse
gesto para si mesmo (a densidade do conflito factual subiu pelo CUSTO
porque o valor não foi medido); material de venda que faça isso comete o
`self_reported`-só que o contrato-mestre proíbe.

## 4. A LLM-wiki e a memória de IA

Parte da demanda é explícita: *uma LLM-wiki e memória de IA para facilitar
progresso de estudo, com o app dirigindo e refinando ideias*. Isso não é
capacidade nova — é o **nome de uso** do que o produto já é, e a fronteira
já está paga:

- **o bundle É a wiki**: páginas OKF legíveis por humanos, versionadas,
  com evidência e proveniência — e É a memória que agentes consomem, pelas
  projeções e pelo `/ask` com citação e abstenção;
- **dirigir ideias** = a fila de atenção: VoI por custo, com razão textual
  obrigatória. As capacidades V1–V5 alimentam a fila com os itens que
  interessam a quem estuda (conflito entre normas, alias ambíguo, conceito
  instável, conceito difícil);
- **refinar ideias** = os atos de curadoria com preview: o humano assenta
  sentido (V2), fecha divergência (`edit` antes de `merge`, RFC-005),
  liga abstrato a prático (V5);
- **o modelo propõe, nunca assenta** (A-3, A-4): prosa gerada que
  reentrar pelo inbox carrega `generated_via` — a wiki não se
  auto-alimenta em silêncio.

## 5. A experiência-alvo no app: a ficha do conceito

O norte da UI — **não** um pacote de implementação — é uma superfície por
conceito com cinco linhas, uma por verbo do pitch:

| Linha | Responde | Capacidade |
|---|---|---|
| **sob qual lente** | em que disciplina(s) este termo tem sentido próprio, e quais páginas usam qual | V2 |
| **o que permanece** | o núcleo durável × a camada volátil deste conceito | V3 |
| **onde diverge** | conflitos factuais e coexistências abertas que o tocam | V1 + RFC-005 |
| **como se aplica** | os casos práticos ligados por aresta tipada, com evidência | V5 |
| **quanto custa adotar** | o fact sheet: custo em minutos, dificuldade, garantias e limites declarados | V6 (com V4) |

A ficha entra **por linha, conforme cada capacidade é paga** — nunca
big-bang. O pré-requisito de UI (smoke de teste, X4) já está pago; a regra
de sempre vale: dado na tela carrega frescor e origem (X1/X2), e nenhuma
linha aparece antes de o mecanismo que a alimenta ter contrato.

## 6. Ordem de ataque e o efeito na fila

Por dependência real (a fila reordenada vive em `docs/18` §10):

1. **V3** — dependência zero, conflito zero; produz o dado que V4 compõe e
   V6 projeta;
2. **V1 mínimo** — pequeno e localizado; dá sujeitos fortes ao regime
   normativo (alimenta V3 com sucessão `:2015`→`:2022` e V5 com sujeitos);
3. **V2** — a fase F5 da fila (P-10) **ressignificada**: de "preservar o
   vínculo entidade↔página" para portadora da identidade-com-sentido
   (alias multi-candidato, `policy.alias_conflict`, colisão de autoridade
   como finding). Promovida a fase mais estratégica;
4. **F6 promovida** ✅ **entregue** — o rastro de abstenção (P-8) deixou
   de ser "deliberadamente depois": `ask_misses` com chave determinística
   por entidades, fechamento verificado por re-ask, superfície nos
   Indicadores e contrato `abstention_trace` (docs/18 §10 item 4). O
   sinal que V4 consome existe;
5. **V4** — composição pura + contrato, depois de F6;
6. **V5 como medição** — arestas tipadas por ato humano + a consulta medida
   que financia as condições de reentrada de RFC-004 §6. **O-2 fica
   ressignificada, não resolvida**: a marca persistente continua esperando
   o nível 3, e V5 é o caminho legítimo até lá;
7. **V6 por último** — projeta o que os anteriores produzem; **C6**
   (campo de efeito colateral no contrato) levemente promovida como
   pré-requisito barato do fact sheet;
8. **F7 rebaixada** — `temporal_partition` e o resíduo de custo (P-11) não
   bloqueiam nenhuma capacidade. É performance, não visão.

## 7. O que este RFC NÃO decide

- **nenhum** schema, autoridade, default de privacidade ou eixo muda por
  este documento — cada gatilho técnico paga o próprio RFC/ADR na vez dele;
- as alegações proibidas do ADR-53 §3 continuam proibidas — o pitch da §1
  avança na superfície pública **atrás** das entregas, verbo a verbo;
- a fronteira de `docs/25` não se move: o produto segue não sendo coletor,
  publicador nem agente. A re-mira muda para quem o diferencial aponta,
  não o que o produto recusa fazer.

## 8. As duas armadilhas transversais (registro para revisores)

Todas as armadilhas da §3 são instâncias de duas patologias que este
repositório já catalogou e pagou para desfazer:

1. **um nome carregando várias perguntas** — `confidence` respondia a seis
   (RFC-004); "estabilidade" tem quatro sentidos; "disciplina" caberia no
   campo `authority` por conveniência. A resposta é sempre a mesma: campo
   próprio, pergunta própria, vocabulário fechado (INV-ONT-001);
2. **atributo afirmado no nível errado** — aplicabilidade e dificuldade
   falam de afirmações; carimbá-las na página é o erro de nível de
   `docs/28` §2, o mesmo que fez `confidence` de página doer. A resposta:
   declarar a granularidade no contrato, e só descer de nível com a
   medição que RFC-004 §6 exige.

Quem revisar um PR desta trilha deve procurar essas duas primeiro.
