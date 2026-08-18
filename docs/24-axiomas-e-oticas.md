# 24 · Axiomas e óticas — o que o produto assume, e por quantos ângulos ele olha

> **Axioma**, aqui, não é frase de efeito: é uma proposição que o produto assume
> **e paga** — cada uma tem uma asserção executável que quebra a suíte se a
> proposição for violada. Uma proposição sem asserção não é axioma; é slogan, e
> não entra nesta lista.
>
> A **ótica** é o outro lado: o mesmo corpus visto por ângulos diferentes, cada
> um com sua unidade, seu artefato e seu frescor próprio. Confundir óticas é o
> que produz alarme desconexo e resposta que não sabe do que está falando.
>
> Vocabulário: [`23`](23-ontologia-e-etimologia.md) · Por que as técnicas
> funcionam: [`03`](03-teoria.md) · Como se constrói: [`10`](10-engenharia-ai-friendly.md)

---

## 1. Os axiomas

### A-1 · O canônico é um só, e nenhuma projeção decide sobre ele

O bundle (Markdown OKF + Git) é a autoridade. `index.db`, grafo, comunidades,
temas e centralidade são **projeções**: apagáveis, reconstruíveis, sem voto.

**Como é pago.** `architecture.toml` declara `source_of_truth` e
`derived_stores`, e `test_architecture_toml.py` cruza a declaração com o código.
`kernel/checkpoints.py:DERIVATIONS` declara a cadeia inteira —
`bundle → index → graph_map → themes`, `index → centrality` — com `None`
significando *autoridade*. INV-001 (página no índice existe no bundle), INV-002
(índice corresponde ao HEAD) e INV-006 (cadeia coerente) verificam em runtime, e
os três primeiros são reparáveis por `rebuild_index`.

**Onde já foi violado.** A escada de reconciliação usava `index.db` como
autoridade para decidir escrita canônica. Não foi uma opinião de arquitetura: a
projeção desatualizada mudava a decisão. Corrigido em
[RFC-002](19-rfc-escada-reconciliacao.md), que passou a exigir projeção fresca e
a **carregar a staleness residual na decisão** em vez de escondê-la.

### A-2 · Aposentar não é apagar; toda escrita é para a frente

Suceder, invalidar, depreciar e desfazer **escrevem**. Nada é removido.

**Como é pago.** `undo` desfaz escrevendo um ato inverso, nunca apagando
(`usecases/curate/undo.py`); `kernel/curation.py:NOT_MERGEABLE` protege as
chaves de ciclo de vida numa fusão; `kernel/vitality.py:APOSENTAM` define
"aposentada" como *deixa de ser endereço de trabalho novo*, com a página seguindo
no bundle, no Git e no índice.

**Consequência que a maioria dos produtos não paga.** Errar não perde. É o que
permite que o gesto destrutivo tenha preview e volta — e é por isso que
"cuidado" (*cura*) e "controle" são coisas diferentes aqui.

### A-3 · Determinismo antes de modelo

O que regex, checksum, grafo ou aritmética resolvem não passa por LLM. O modelo
é um **estágio cercado** por passadas determinísticas — o sanduíche — nunca a
autoridade final.

**Como é pago.** O árbitro LLM da escada de reconciliação existe, está
implementado, e vive atrás de `reconcile.llm_arbiter`, cujo default é `False`
em `settings.py` e nos dois presets de `configure_system.py`. Um caminho
opcional cujo default é ligado não é opcional.

### A-4 · Há UM caminho de escrita, e ele é inescapável

Todo ato que muda o canônico atravessa o mesmo esqueleto —
`produce → normalize → reconcile → write → done` — e o mesmo gate.

**Como é pago.** `MachinePageUseCase.execute()` é Template Method **fechado**:
`architecture.toml` declara `machine_page_template_closed = true` e o teste
proíbe subclasse que sobrescreva `execute`. `single_public_method = "execute"`
impede que um use case ganhe uma segunda porta. O Harness roda duas camadas
separadas (conformidade OKF e política local), para que o produto **nunca**
invente exigência do SPEC.

### A-5 · Nenhuma garantia é universal

Todo mecanismo heurístico declara **a que** sua garantia é relativa, com vieses,
pressupostos, modos de falha e fallback.

**Como é pago.** `epistemics.toml` + `corpusmith epistemics lint`:
`universal_guarantee = true` é proibido, evidência composta só por
`self_reported` é proibida (não-autocertificação), e
`test_epistemics_toml.py` cruza os parâmetros declarados com as constantes
reais — contrato que mente sobre o código quebra a suíte.

### A-6 · Um teste que passa com e sem a correção é teatro

Toda correção precisa de uma asserção que **saiba reprovar** quando a correção
é revertida.

**Como é pago.** Por disciplina de mutação registrada no próprio código: os
docstrings dos testes trazem o valor medido *antes*, e a reversão é executada
antes do commit. Quatro testes deste repositório passaram na primeira redação
com a correção revertida e tiveram de ser reescritos — o registro disso fica
nos docstrings, não numa lista de boas intenções.

**Exemplo desta entrega.** `test_fusao_e_simetrica` verifica simetria por
`merge_meta`, não pela função nova: verificar só a função daria verde com o
defeito intacto no chamador.

### A-7 · Todo eixo epistêmico tem vocabulário fechado

Valor fora do vocabulário é **erro**, não "extensão privada".

**Como é pago.** `kernel/ontology.py` + `corpusmith ontology lint`
([RFC-004](22-rfc-ontologia-da-assercao.md)). Este é o axioma mais novo, e
entrou pagando uma dívida: `confidence` era o único campo epistêmico do
frontmatter **sem nenhuma validação no Harness** — `grep -rn "confidence"
harness/` não devolvia nenhuma linha.

### A-8 · Um campo, um eixo

Nenhum valor responde a duas perguntas. Conflação é classe de defeito, não
questão de estilo.

**Como é pago.** `test_nenhum_valor_responde_a_duas_perguntas` e o finding
`ontology.term_off_axis`. O registro de deriva
([`23`](23-ontologia-e-etimologia.md) §4) mantém as conflações remanescentes
visíveis, com marcadores que o lint confere nos dois sentidos — para que nem
apodreçam nem regridam.

### O que NÃO é axioma

Vale dizer o que ficou de fora, porque a tentação é inflar a lista:

- *"o humano sempre decide"* — falso hoje: o caminho de máquina cria, atualiza e
  sucede páginas depois de passar pelo gate ([`00`](00-o-que-e-corpusmith.md) §5);
- *"zero alucinação"* — o produto abstém quando o suporte é fraco e cita a
  evidência quando responde. Reduz e torna auditável; não elimina;
- *"o conhecimento é verdadeiro"* — canônico é o que foi **aceito**. A raiz de
  *canon* é régua, não verdade.

## 2. As óticas

O mesmo corpus, oito ângulos. Cada um responde a uma pergunta que os outros não
respondem, tem **unidade** própria e **frescor** próprio. Misturar óticas é o
que faz um painel acender alarme sobre uma coisa apontando para outra.

| # | Ótica | Pergunta | Unidade | Artefato | Frescor deriva de |
|---|---|---|---|---|---|
| 1 | **editorial** | o que se lê? | página | Markdown OKF no bundle | — (é a autoridade) |
| 2 | **epistêmica** | o que se afirma, com que força? | *asserção* | eixos de `kernel/ontology.py` | bundle |
| 3 | **de proveniência** | de onde veio cada parte? | região | sentinelas em `okf/regions.py` | bundle |
| 4 | **temporal** | quando valia, quando soubemos? | fato | `valid_at`/`invalid_at` × `timestamp`/`stale_as_of` | bundle |
| 5 | **de governança** | quem decidiu, e dá para voltar? | ato | `curation_acts` + commit | bundle |
| 6 | **topológica** | como isto se relaciona? | comunidade / tema | grafo, Leiden, centralidade | `index` → `graph_map` → `themes` |
| 7 | **de atenção** | o que merece trabalho agora? | item de fila | calor, revisão espaçada, lacunas | `index` |
| 8 | **de avaliação** | o quanto isto foi medido? | mecanismo | envelopes em `runtime.db` | execução do eval |

### O que se ganha em separá-las

**O doctor sabe qual elo está atrás.** Porque a ótica topológica declara sua
cadeia (`bundle → index → graph_map → themes`), INV-006 diz *qual* derivação
está obsoleta, em vez de acender cinco alarmes desconexos sobre o mesmo atraso.

**A fila para de propor trabalho morto.** A ótica de atenção lia `page_heat` cru
— histórico de uso por caminho — e propunha revisar páginas sucedidas e páginas
que nunca existiram. A correção não foi filtrar em cada fonte: foi reconhecer
que a ótica de atenção precisa consultar a ótica editorial
(`kernel/vitality.py`), porque "esta página conta?" não é pergunta dela.

**A ótica epistêmica é a que ainda não tem unidade própria.** É o vão registrado
em ADR-53 §5 e em [`00`](00-o-que-e-corpusmith.md) §7: hoje ela pega carona na
unidade editorial, e uma página com três afirmações de fontes e validades
diferentes recebe um rótulo só. RFC-004 §6 descreve a forma proposta e as três
condições de reentrada — a primeira delas sendo **medir** uma consulta que a
granularidade de página responde errado, em vez de imaginá-la.

## 3. Como usar esta página

- vai **mudar código**? cheque contra A-1..A-8 antes de desenhar. Um PR que
  precise violar um deles não é um PR: é um RFC (`AGENTS.md` §8);
- vai **explicar o produto**? as óticas são a estrutura da explicação; a maior
  parte da confusão de quem chega vem de estar olhando por uma ótica e ouvindo
  resposta de outra;
- achou um axioma **sem asserção executável** listada? é defeito desta página,
  e a correção é acrescentar a asserção ou remover o axioma — nunca deixar a
  proposição solta.
