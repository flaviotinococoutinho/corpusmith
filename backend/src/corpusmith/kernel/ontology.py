"""Ontologia: os EIXOS de uma afirmação — PURO (RFC-004).

**O problema que este módulo nomeia.** Um campo, `confidence`, carrega hoje
sentidos de eixos diferentes. Medido nesta árvore:

    usecases/promote_memory.py:173   "confidence": "human_approved"
    compute/python_kernel.py:17      {"extracted", "inferred", "ambiguous"}
    kernel/curation.py:87            fraqueza = {extracted, inferred, ambiguous}

`extracted`/`inferred` respondem *como a afirmação foi derivada*.
`ambiguous` responde *se a leitura foi resolvida*. `human_approved` responde
*quem autorizou* — três perguntas ortogonais no mesmo campo. E o Harness, que
valida `privacy`, checksum, PII e sucessão, **não valida `confidence`**: não há
vocabulário fechado, qualquer string passa.

**A consequência era medível, não teórica.** `merge_meta` ordenava por
`fraqueza.get(c, 0)`; `human_approved` não está no dicionário, então caía no
default `0` — o mesmo peso de `extracted`. Resultado antes da correção:

    merge("human_approved", "extracted") -> "human_approved"   (ratificação fica)
    merge("human_approved", "inferred")  -> "inferred"         (ratificação some)

A MESMA situação de governança com dois desfechos, decidida por um `default=0`
que ninguém escolheu. Não é que um dos dois estivesse errado — é que a regra
não existia, e um acidente de dicionário estava respondendo por ela.

**O que este módulo faz.** Separa os eixos, dá a cada um vocabulário FECHADO,
e escreve a regra de fusão *por eixo*. Não muda schema, não muda frontmatter:
`classificar()` LÊ o campo legado e devolve os eixos; `merge_confidence()`
reescreve no mesmo vocabulário legado. A migração para `Assertion` como
entidade de primeira classe é RFC-004 §6, e não acontece aqui.

**Por que os eixos são quatro e só três moram aqui.** `evaluation_status` já
existe, fechado e validado, em `epistemic/model.py` — mas aplicado a
*mecanismo*, não a afirmação. Duplicá-lo aqui criaria a segunda definição do
mesmo termo, que é exatamente o defeito que este módulo combate.
"""
from __future__ import annotations

# ---------------------------------------------------------------- eixos
# Cada eixo responde UMA pergunta. O teste de que um valor está no eixo
# certo é conseguir responder a pergunta do eixo com ele — e não a de outro.

#: COMO a afirmação passou a existir.
DERIVATION = ("extracted", "inferred", "asserted", "imported")

#: SE as leituras concorrentes foram assentadas.
RESOLUTION = ("resolved", "ambiguous", "contested")

#: QUEM autorizou a afirmação a contar como conhecimento.
GOVERNANCE = ("proposed", "ratified", "retired")

AXES: dict[str, tuple[str, ...]] = {
    "derivation_method": DERIVATION,
    "resolution_status": RESOLUTION,
    "governance_status": GOVERNANCE,
}

#: A pergunta de cada eixo — parte do contrato, não comentário. Um valor
#: que não responda a ESTA pergunta está no eixo errado.
QUESTIONS: dict[str, str] = {
    "derivation_method": "COMO esta afirmação passou a existir?",
    "resolution_status": "as leituras concorrentes foram assentadas?",
    "governance_status": "quem autorizou isto a contar como conhecimento?",
}

#: Vocabulário LEGADO do campo `confidence` — os quatro valores que o
#: produto de fato escreve hoje. Fechado a partir de agora: valor fora
#: daqui é `ontology.value_off_axis` no lint, não "extensão privada".
LEGACY_CONFIDENCE = ("extracted", "inferred", "ambiguous", "human_approved")

#: Ordem de FRAQUEZA da derivação: fundir não pode promover a qualidade do
#: que se afirma, então a fusão fica com a mais fraca. A ordem é por
#: DISTÂNCIA até a fonte, não por prestígio de quem produziu: `extracted`
#: é literal na fonte; `imported` é literal em outro registro, cuja
#: extração não presenciamos; `asserted` é afirmado sem fonte externa;
#: `inferred` é derivado por regra ou modelo — o único que pode estar
#: errado sem que ninguém tenha errado. `asserted` e `imported` ainda não
#: aparecem no campo legado; entram já ordenados para quando RFC-004 §6 os
#: tornar escrevíveis.
_WEAKNESS = {"extracted": 0, "imported": 1, "asserted": 2, "inferred": 3}


class TermoForaDoEixo(ValueError):
    """Valor que não pertence ao eixo pedido — erro CONTROLADO, virado em
    Finding pelo lint (nunca stacktrace no caminho de escrita)."""


def valido(eixo: str, valor: str) -> bool:
    """O valor pertence ao vocabulário fechado do eixo?"""
    return valor in AXES.get(eixo, ())


def eixos_de(valor: str) -> tuple[str, ...]:
    """Eixos em que este valor aparece.

    Devolver mais de um é o SINAL de deriva semântica: o mesmo termo
    respondendo a duas perguntas. Hoje devolve no máximo um — e é essa
    propriedade que o teste guarda, para que a próxima adição de
    vocabulário não reintroduza a conflação em silêncio."""
    return tuple(eixo for eixo, vocab in AXES.items() if valor in vocab)


# ------------------------------------------------- leitura do campo legado
# Mapa EXPLÍCITO em vez de heurística: cada valor legado diz o que de fato
# afirma em cada eixo, e o que ele NÃO afirma fica `None` — silêncio é
# diferente de "proposto". `ambiguous` é o caso que prova a separação: ele
# não diz nada sobre derivação, só que a leitura não foi assentada.
_LEGACY_AXES: dict[str, dict[str, str | None]] = {
    "extracted": {"derivation_method": "extracted",
                  "resolution_status": "resolved",
                  "governance_status": None},
    "inferred": {"derivation_method": "inferred",
                 "resolution_status": "resolved",
                 "governance_status": None},
    "ambiguous": {"derivation_method": None,
                  "resolution_status": "ambiguous",
                  "governance_status": None},
    "human_approved": {"derivation_method": "asserted",
                       "resolution_status": "resolved",
                       "governance_status": "ratified"},
}


def classificar(meta: dict, *, em_conflito: bool = False) -> dict[str, str]:
    """Eixos de uma página, lidos do frontmatter que já existe.

    `em_conflito` é o PRIMEIRO produtor de `contested` (RFC-005 §5.3): o
    detector de conflito factual passa `True` quando a página diverge
    numericamente de outra do mesmo grupo de identificador forte. Isso não
    viola a restrição declarada do eixo em `ontology.toml` — *"só um ato
    posterior desata"* — porque `contested` é exatamente o estado NÃO
    assentado. Marcar registra que o nó existe; assentar seria escolher um
    lado, e o detector não escolhe.

    Função de LEITURA: não escreve, não exige campo novo e não inventa
    eixo que a página não sustenta. Onde o campo legado cala, a resposta
    vem de outra chave que já carrega o mesmo sentido — `generated_via`
    diz quem produziu, `superseded_by`/`invalid_at` dizem que a página foi
    aposentada. Só quando TODAS calam entra o default que o código já
    aplica hoje (`COALESCE(confidence,'extracted')` em
    `compute/python_kernel.py`), e ele entra por ser o comportamento
    vigente, não por ser a leitura mais generosa.

    Ausência é resposta: uma página de máquina sem ato humano registrado é
    `proposed`, e chamá-la de ratificada seria a alegação que ADR-53 §3
    proíbe."""
    out: dict[str, str] = {}
    bruto = meta.get("confidence")
    if isinstance(bruto, str):
        for eixo, valor in _LEGACY_AXES.get(bruto, {}).items():
            if valor is not None:
                out[eixo] = valor

    via = str(meta.get("generated_via") or "")
    out.setdefault("derivation_method",
                   "asserted" if via.startswith("human:") else "extracted")
    # Conflito factual VENCE a leitura do campo legado: `ambiguous` diz que
    # ESTA leitura não foi assentada, `contested` diz que duas páginas se
    # contradizem. A segunda é a informação mais cara de perder, e é a que
    # tem destino na fila.
    if em_conflito:
        out["resolution_status"] = "contested"
    out.setdefault("resolution_status", "resolved")

    # Governança tem precedência de ciclo de vida: aposentar é o gesto mais
    # recente e vence a ratificação anterior — a página segue no bundle, só
    # deixa de valer como afirmação corrente (kernel/vitality.py).
    if meta.get("superseded_by") or meta.get("invalid_at"):
        out["governance_status"] = "retired"
    else:
        out.setdefault("governance_status",
                       "ratified" if via.startswith("human:") else "proposed")
    return out


def _legado(eixos: dict[str, str]) -> str:
    """Reescreve os eixos no vocabulário legado. Ordem de precedência =
    ordem de custo: uma ambiguidade não assentada é o que mais importa
    saber, e por isso ela vem antes de tudo.

    **Onde a reescrita perde, e por que perde para BAIXO.** O vocabulário
    legado não tem casa para "afirmado por pessoa, ainda não ratificado" —
    o par (`asserted`, `proposed`), que é justamente o que sobra quando uma
    fusão desfaz a cobertura de uma ratificação. Chamar isso de `extracted`
    seria alegar leitura literal da fonte, que é falso e é a alegação mais
    forte do vocabulário. A reescrita desce para `inferred`: também não é
    exato, mas erra para o lado que reduz influência (peso 0.5 contra 1.0
    em `compute/python_kernel.py`) em vez de para o lado que inventa
    proveniência. Esta perda é o argumento concreto de RFC-004 §6 — não se
    conserta reescrevendo melhor, só com eixos escrevíveis."""
    if eixos.get("resolution_status") == "ambiguous":
        return "ambiguous"
    derivacao = eixos.get("derivation_method", "extracted")
    if derivacao == "asserted":
        return ("human_approved"
                if eixos.get("governance_status") == "ratified"
                else "inferred")
    return derivacao if derivacao in LEGACY_CONFIDENCE else "inferred"


def merge_confidence(alvo: str, fonte: str) -> str:
    """`confidence` de uma fusão, decidido EIXO A EIXO.

    Três regras, uma por eixo, e cada uma é conservadora na direção do que
    a fusão não pode inventar:

    - **derivação** fica com a mais fraca — fundir não melhora a qualidade
      do que se afirma (era a única regra que existia, e estava certa);
    - **resolução** fica ambígua se qualquer lado for ambíguo — fundir não
      assenta uma leitura que ninguém assentou;
    - **governança** só permanece `ratified` se AMBOS os lados forem: a
      ratificação é um ato sobre um conteúdo, e o conteúdo mudou.

    A terceira regra é a que muda comportamento. Antes,
    `merge("human_approved", "extracted")` devolvia `human_approved` — a
    página fundida saía carimbada como ratificada sem que ninguém tivesse
    ratificado a fusão. Agora devolve `extracted`, e a ratificação, se for o
    caso, volta por um ato humano registrado em `curation_acts`."""
    a, b = classificar({"confidence": alvo}), classificar({"confidence": fonte})
    derivacao = max(a["derivation_method"], b["derivation_method"],
                    key=lambda v: _WEAKNESS.get(v, 0))
    ambos_ratificados = (a["governance_status"] == "ratified"
                         and b["governance_status"] == "ratified")
    return _legado({
        "derivation_method": derivacao,
        "resolution_status": (
            "ambiguous" if "ambiguous" in (a["resolution_status"],
                                           b["resolution_status"])
            else "resolved"),
        "governance_status": "ratified" if ambos_ratificados else "proposed",
    })


def ratificacao_perdida(alvo: str, fonte: str) -> dict | None:
    """A fusão desfaz uma ratificação? Se sim, QUAL lado a tinha.

    A regra de `merge_confidence` está certa em derrubar a ratificação
    quando só um lado a tem — mas derrubar em SILÊNCIO é a falha que a
    literatura chama de *audit erasure* (docs/26 §3): o produto sempre
    protegeu o CONTEÚDO contra apagamento (axioma A-2), e não protegia o
    atributo de governança. Esta função existe para que todo chamador da
    fusão possa DECLARAR a perda — no preview, antes do efeito, no eixo
    humano; no evento e no resultado, no eixo de máquina.

    Devolve `None` quando não há perda (nenhum lado ratificado, ou ambos)
    e, quando há, um dict estável para preview/evento/log:
    `{"axis", "before", "after", "ratified_side", "merged_confidence"}` —
    `ratified_side` ∈ {"alvo", "fonte"} diz qual página carregava o ato
    que a fusão deixa de cobrir."""
    a, b = classificar({"confidence": alvo}), classificar({"confidence": fonte})
    resultado = merge_confidence(alvo, fonte)
    depois = classificar({"confidence": resultado})["governance_status"]
    if depois == "ratified":
        return None
    lados = [nome for nome, eixos in (("alvo", a), ("fonte", b))
             if eixos["governance_status"] == "ratified"]
    if not lados:
        return None
    return {"axis": "governance_status", "before": "ratified",
            "after": depois, "ratified_side": lados[0],
            "merged_confidence": resultado}
