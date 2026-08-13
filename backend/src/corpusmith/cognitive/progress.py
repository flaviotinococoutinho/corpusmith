"""Profundidade multidimensional: declarada × validada (ADR-20, porta
fechada na v0.20) + vocabulários de experiência metacognitiva (Efklides)
e contrato de analogia (§10) + prompts determinísticos de exercício.

Validação vem de PRÁTICA: cada exercício mapeia para uma dimensão; o
nível validado da dimensão é o maior nível da escada atingido com
sucesso em itens do objetivo. Dimensões sem exercício mapeado são
reportadas como não-mensuráveis — nunca um número inventado.
"""
from __future__ import annotations
from .model import ACCESS_LEVELS, DEPTH_DIMENSIONS, level_index

# exercício → dimensão que ele evidencia (1:1 honesto; mathematical e
# historical não têm exercício ⇒ "sem instrumento")
EXERCISE_DIMENSION = {"recall": "conceptual", "explain": "conceptual",
                      "apply": "practical", "compare": "critical",
                      "critique": "critical", "transfer": "transfer"}

# escada (7 níveis) → escala de profundidade 0..3 usada nos objetivos
_LEVEL_DEPTH = {"none": 0, "recognition": 1, "recall": 1,
                "explanation": 2, "application": 2,
                "transfer": 3, "critique": 3}

# experiências metacognitivas DECLARADAS (Efklides 2006) — eventos
# revisáveis, jamais diagnósticos
EXPERIENCE_TYPES = ("familiarity", "difficulty", "surprise", "conflict",
                    "fluency", "insecurity", "confidence", "progress",
                    "familiar_cannot_explain", "intuition_no_formalism",
                    "formalism_no_intuition")

_PROMPTS = {
    "recall": "Sem consultar: enumere os pontos centrais de «{title}».",
    "explain": "Explique «{title}» com as suas palavras, como para um "
               "colega que nunca viu o tema.",
    "apply": "Descreva um cenário concreto seu onde «{title}» se aplica: "
             "restrições, decisão e trade-offs aceitos.",
    "compare": "Compare «{title}» com o conceito vizinho mais próximo: o "
               "que muda, o que se preserva, quando escolher cada um?",
    # Toulmin (v0.21): a crítica decompõe o argumento — claim, dado,
    # garantia, qualificador e réplica — em vez de "opinar sobre"
    "critique": "Critique «{title}» decompondo o argumento (Toulmin): "
                "qual é a AFIRMAÇÃO central? que EVIDÊNCIA a sustenta? "
                "qual GARANTIA liga evidência a afirmação? em que "
                "CONDIÇÕES vale (qualificador)? qual a melhor RÉPLICA?",
    "transfer": "Aplique a ESTRUTURA de «{title}» em outra disciplina: "
                "correspondências e o ponto exato onde a transferência "
                "quebra.",
}


def exercise_prompt(exercise: str, title: str) -> str:
    """Prompt determinístico (LLM nenhum): a pergunta vem de template,
    a resposta vem da pessoa — retrieval practice de verdade."""
    if exercise not in _PROMPTS:
        raise ValueError(f"exercise ∈ {sorted(_PROMPTS)}")
    return _PROMPTS[exercise].format(title=title)


def depth_progress(desired: dict, successes: list[dict]) -> dict:
    """desired: {dimensão: 0..3}; successes: [{exercise, level}] de
    tentativas BEM-SUCEDIDAS em itens do objetivo. Devolve, por dimensão
    desejada: declarada × validada × progresso — e `measurable=False`
    onde não existe instrumento (honestidade > número)."""
    validated: dict[str, int] = {}
    for s in successes:
        dim = EXERCISE_DIMENSION.get(s.get("exercise", ""))
        if dim is None:
            continue
        depth = _LEVEL_DEPTH.get(s.get("level", "none"), 0)
        validated[dim] = max(validated.get(dim, 0), depth)
    out = {}
    for dim in DEPTH_DIMENSIONS:
        want = int(desired.get(dim, 0))
        if want == 0:
            continue
        measurable = dim in set(EXERCISE_DIMENSION.values())
        have = validated.get(dim, 0)
        out[dim] = {"desired": want, "validated": have if measurable else None,
                    "measurable": measurable,
                    "progress": round(min(1.0, have / want), 2)
                    if measurable else None}
    return out


def support_level(streak: int) -> dict:
    """Scaffolding com FADING (design instrucional, v0.21): quem nunca
    recuperou recebe exemplo resolvido primeiro; uma recuperação dá
    direito a dica; duas ou mais, suporte zero — a retirada do apoio é
    parte do método (worked examples → fading), não economia."""
    if streak <= 0:
        return {"level": "worked_example",
                "hint": "Leia um exemplo resolvido ANTES de tentar — "
                        "depois tente sem olhar."}
    if streak == 1:
        return {"level": "hint",
                "hint": "Tente primeiro; se travar, releia só a abertura "
                        "da página."}
    return {"level": "none",
            "hint": "Sem apoio: recuperação limpa (o esforço é o método)."}


def interleave(items: list[dict], key: str) -> list[dict]:
    """Intercalação (v0.21, Rohrer/Taylor): alterna itens de grupos
    diferentes em round-robin, preservando a ordem interna de cada
    grupo — variar o contexto de recuperação fortalece a discriminação
    entre conceitos vizinhos. Puro e estável."""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for item in items:
        bucket = str(item.get(key, "")).split("/")[0]
        if bucket not in groups:
            groups[bucket] = []
            order.append(bucket)
        groups[bucket].append(item)
    out, index = [], 0
    while any(groups[b] for b in order):
        bucket = order[index % len(order)]
        if groups[bucket]:
            out.append(groups[bucket].pop(0))
        index += 1
    return out


def new_analogy(*, analogy_id: str, source: str, target: str,
                mappings: list, preserved: list | None = None,
                breaks: list | None = None, didactic_goal: str = "",
                origin: str = "human") -> dict:
    """Contrato de analogia (§10): correspondências + limites SEMPRE
    juntos — analogia sem ponto de ruptura declarado é recusada (nunca
    apresentar analogia como equivalência exata)."""
    if not source or not target:
        raise ValueError("analogia exige source e target")
    if not mappings:
        raise ValueError("analogia exige ao menos uma correspondência")
    if not breaks:
        raise ValueError("analogia exige onde ELA QUEBRA (limites "
                         "explícitos — nunca equivalência exata)")
    if origin not in ("human", "llm"):
        raise ValueError("origin ∈ human|llm")
    return {"id": analogy_id, "source": source, "target": target,
            "mappings": list(mappings), "preserved": list(preserved or []),
            "breaks": list(breaks), "didactic_goal": didactic_goal,
            "origin": origin, "status": "draft"}
