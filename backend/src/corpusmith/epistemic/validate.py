"""Regras obrigatórias sobre contratos epistêmicos → findings (PURO).

Cada regra tem CÓDIGO ESTÁVEL. A existência de arquivos NÃO é checada
aqui (puro): o shell passa `existing_refs` como dado. Determinístico:
mesma entrada (em qualquer ordem) ⇒ mesmos findings, ordenados.
"""
from __future__ import annotations
from .model import (SideEffect,
                    EMPIRICAL_GUARANTEES, HEURISTIC_GUARANTEES,
                    SELF_CONTAINED_GUARANTEES, EpistemicContract,
                    EvidenceKind, Finding, Registry)

# Gödel motiva a POSTURA de não-autocertificação total; NÃO fornece
# bounds de generalização para ML. NFL motiva declarar escopo; NÃO prova
# que aprender é impossível nem que "qualquer heurística serve". Nenhum
# dos dois pode aparecer como justificativa DENTRO de um contrato.
_FORBIDDEN_JUSTIFICATIONS = ("gödel", "godel", "no free lunch",
                             "incompletude de g")


def _texts(contract: EpistemicContract) -> str:
    parts = [contract.title, contract.decision, contract.feedback_signal,
             contract.guarantee.relative_to]
    parts += [b.text for b in contract.inductive_biases]
    parts += [a.text for a in contract.assumptions]
    parts += [s.text for s in contract.validity_scope]
    parts += [m.text for m in contract.known_failure_modes]
    parts += list(contract.misinterpretations)
    return " \n ".join(parts).lower()


def _validate_contract(c: EpistemicContract,
                       existing_refs: frozenset[str] | None,
                       out: list[Finding]) -> None:
    def finding(code: str, message: str, severity: str = "error") -> None:
        out.append(Finding(code, severity, c.mechanism_id, message))

    if not c.inductive_biases:
        finding("epistemic.contract_missing_bias",
                "nenhum viés indutivo declarado — toda decisão heurística "
                "só é possível por um viés; nomeie-o")
    if not c.validity_scope:
        finding("epistemic.contract_missing_scope",
                "escopo de validade ausente — onde este mecanismo foi "
                "pensado para operar?")
    if c.guarantee.universal:
        finding("epistemic.guarantee_unbounded",
                "universal_guarantee=true é PROIBIDO — nenhuma garantia "
                "do produto é universal; declare a referência relativa")
    if (c.guarantee.kind not in SELF_CONTAINED_GUARANTEES
            and not c.guarantee.relative_to):
        finding("epistemic.guarantee_unbounded",
                f"garantia '{c.guarantee.kind.value}' sem "
                "guarantee_relative_to — relativa a quê?")
    if c.guarantee.kind in HEURISTIC_GUARANTEES and \
            not c.known_failure_modes:
        finding("epistemic.failure_modes_missing",
                "mecanismo heurístico sem failure modes declarados")
    # C6: efeito colateral declarado (`docs/17`). Escrever no CANÔNICO é
    # alto impacto por construção neste produto — o bundle é a autoridade
    # e o commit é para sempre. Declarar a escrita e negar o impacto seria
    # o contrato dizendo duas coisas opostas sobre o mesmo mecanismo.
    if SideEffect.CANONICAL_WRITE in c.side_effects and not c.high_impact:
        finding("epistemic.canonical_write_without_impact",
                "declara escrita no CANÔNICO e high_impact=false — o "
                "bundle é a autoridade e o commit é definitivo; escrita "
                "no canônico é alto impacto por construção")
    if SideEffect.NONE in c.side_effects and len(c.side_effects) > 1:
        finding("epistemic.side_effect_contradiction",
                "declara `none` ao lado de outro efeito — quem ler `none` "
                "primeiro lê o contrário do que o mecanismo faz")
    if c.guarantee.kind in EMPIRICAL_GUARANTEES and not c.evaluated_by:
        finding("epistemic.evaluation_missing",
                "garantia empírica sem vínculo com envelope de avaliação "
                "(evaluated_by vazio)")
    if c.high_impact and not c.fallback:
        finding("epistemic.fallback_missing",
                "erro de alto impacto sem fallback declarado "
                "(abster/degradar/revisão humana?)")
    if c.adaptive and not c.feedback_signal:
        finding("epistemic.feedback_signal_missing",
                "mecanismo adaptativo sem loss/feedback signal declarado")
    if c.composite and not c.composite_components:
        finding("epistemic.components_missing",
                "score composto sem componentes declarados")
    if not c.implementation_refs:
        finding("epistemic.implementation_ref_missing",
                "contrato sem referência de implementação")
    elif existing_refs is not None:
        for ref in c.implementation_refs:
            if ref not in existing_refs:
                finding("epistemic.implementation_ref_missing",
                        f"implementação referenciada não existe: {ref}")
    if c.evidence and all(e is EvidenceKind.SELF_REPORTED
                          for e in c.evidence):
        finding("epistemic.self_certification_only",
                "única evidência de qualidade é produzida pelo próprio "
                "mecanismo — exija golden set, feedback humano, regra "
                "determinística ou validador independente")
    text = _texts(c)
    for term in _FORBIDDEN_JUSTIFICATIONS:
        if term in text:
            finding("epistemic.forbidden_justification",
                    f"'{term}' não pode justificar desempenho/limite de "
                    "ML em contrato (ver docs/11 §não-autocertificação)")


def validate_registry(registry: Registry,
                      existing_refs: frozenset[str] | None = None
                      ) -> tuple[Finding, ...]:
    """`existing_refs=None` pula a checagem de existência (parsing puro
    em testes); um frozenset (mesmo vazio) a liga."""
    out: list[Finding] = []
    for contract in registry.contracts:
        _validate_contract(contract, existing_refs, out)
    out.sort(key=lambda f: (f.mechanism_id, f.code, f.message))
    return tuple(out)
