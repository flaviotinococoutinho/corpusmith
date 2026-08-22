"""Estabilidade editorial: o que menos muda — PURO (RFC-006, V3).

**A palavra "estabilidade" carrega quatro sentidos, e este módulo mede UM.**
A lição é a mesma do `[drift.time]` (quatro tempos exigiram quatro nomes):
um score único somando sentidos diferentes seria o novo
`confidence`-com-seis-perguntas. Os quatro, com seus donos:

1. **edição de texto** — quantas vezes a página foi ESCRITA no Git. É o que
   este módulo consolida, e só isto;
2. **ciclo de vida** — sucessão/invalidação declaradas no frontmatter. Dono:
   `kernel/vitality.py`. Este módulo LÊ o veredito de lá (campo `ciclo`) e
   não o recalcula;
3. **decaimento de uso** — `page_heat` mede USO, não mudança. Fica fora;
4. **churn de tema** — `theme_epochs` (RFC-001) mede a partição, não a
   página. Fica fora.

**O que "estável" NÃO significa** (capta ≠ data, `docs/26`): edição rara
mede QUIETUDE EDITORIAL — ninguém mexeu — e não correção, aprovação nem
importância. Uma página errada que ninguém revisita é perfeitamente
"estável" neste sentido. A projeção responde "o que menos muda", que é a
pergunta de quem estuda (RFC-006 §1); "o que está certo" é outra pergunta,
com outros donos (Harness, curadoria).

**Exclusões, e por que são obrigatórias.** `BundleWriter.write` regenera o
`index.md` de cada diretório tocado e apensa em `log.md` a CADA escrita —
contá-los faria toda página parecer volátil, e o erro de medição estaria
pré-armado. `reviews/` é ritual de máquina: sua cadência mede o scheduler,
não o conceito. A lista é fechada e o contrato epistêmico a declara
(cross-check em `test_epistemics_toml`).
"""
from __future__ import annotations
from dataclasses import dataclass
from .vitality import aposentada

#: Basenames regenerados pelo caminho de escrita (writer.py): todo `write`
#: reescreve o `index.md` do diretório e apensa no `log.md`.
BASENAMES_REGENERADOS = ("index.md", "log.md")

#: Prefixos de ritual de máquina: a cadência deles mede o agendador.
PREFIXOS_DE_RITUAL = ("reviews/",)


def conta_para_estabilidade(rel_path: str) -> bool:
    """Este caminho entra na medição de edição?

    Regra por CAMINHO, não por conteúdo: é o que dá para decidir puro, e o
    modo de falha (página de máquina nova fora da lista contando como
    conteúdo) está declarado no contrato em vez de escondido aqui."""
    base = rel_path.rsplit("/", 1)[-1]
    if base in BASENAMES_REGENERADOS:
        return False
    return not any(rel_path.startswith(p) for p in PREFIXOS_DE_RITUAL)


@dataclass(frozen=True)
class Estabilidade:
    """O veredito de UMA página, nos dois sentidos que este módulo cobre.

    `ciclo` é o motivo de aposentadoria de `vitality.aposentada` ("viva"
    quando nenhum) — sentido 2, lido e não recalculado. `edicoes` é o
    sentido 1. Os outros dois sentidos não têm campo aqui DE PROPÓSITO."""
    rel_path: str
    edicoes: int
    primeira_em: float | None
    ultima_em: float | None
    ciclo: str


def consolidar(historico: dict[str, dict],
               frontmatter: dict[str, dict]) -> list[Estabilidade]:
    """Consolida história de edições + frontmatter num ranking estável.

    - Só páginas presentes em `frontmatter` entram: história de página que
      não está mais no bundle não é estabilidade de coisa nenhuma;
    - página sem entrada no histórico (repo recém-inicializado, import por
      fora do Git) sai com `edicoes=0` — o dado diz "nunca vi esta página
      ser escrita", e inventar 1 seria fabricar história;
    - ordem: da mais QUIETA para a mais volátil (`edicoes` asc), empate por
      `rel_path` — determinística, sem limiar. Onde cortar "núcleo" de
      "volátil" é decisão de leitura, não deste módulo: qualquer corte fixo
      seria uma calibração que ninguém fez (a mesma razão do 1% do
      `factual_conflict` ser declarado NÃO calibrado).
    """
    out: list[Estabilidade] = []
    for rel_path, meta in frontmatter.items():
        if not conta_para_estabilidade(rel_path):
            continue
        h = historico.get(rel_path) or {}
        out.append(Estabilidade(
            rel_path=rel_path,
            edicoes=int(h.get("edicoes", 0)),
            primeira_em=h.get("primeira_em"),
            ultima_em=h.get("ultima_em"),
            ciclo=aposentada(meta) or "viva"))
    return sorted(out, key=lambda e: (e.edicoes, e.rel_path))
