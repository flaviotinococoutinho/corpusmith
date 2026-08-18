"""Transformações de curadoria — núcleo PURO (F1-PR1, v1.8.1).

Aqui moram as regras de "invalidar-nunca-apagar" como FUNÇÕES sobre
metadados: nenhuma I/O, nenhum writer, nenhum banco. Os DOIS eixos de
escrita importam daqui — o de máquina (`usecases/base.py`, quando a
reconciliação decide SUPERSEDE) e o humano (`usecases/curate/`, quando o
curador decide) — de modo que sucessão e invalidação tenham UMA definição
só, e o eixo máquina não precise conhecer o eixo humano (o contrário
inverteria o gradiente de mutabilidade e criaria ciclo).

Também vive aqui o diff unificado do PREVIEW: mostrar o que vai mudar
antes de escrever é o que torna um ato destrutivo em ato revisável, e
calcular diff é operação pura por natureza.
"""
from __future__ import annotations
import difflib
from datetime import datetime, timezone
from .ontology import merge_confidence


class UndoNotExpressible(RuntimeError):
    """O estado anterior existe no histórico mas NÃO é alcançável por
    escrita para a frente (F1-PR2).

    Mora no kernel, e não no use case, por uma razão de camada: a API
    precisa traduzi-la em 409 e não pode importar `usecases/`
    (INV-ARCH-004). Como é um conceito puro de curadoria — "este estado
    não é expressável pelo caminho de escrita" — o kernel é o lugar em que
    todas as camadas podem vê-la sem ninguém pular a facade.
    """


def superseded_meta(meta: dict, successor: str,
                    when: datetime | None = None) -> dict:
    """Metadados da página ANTIGA numa sucessão: aponta para a sucessora e
    fecha a validade. Nunca remove nada — a página segue legível e
    recuperável (a autoridade é o Git)."""
    out = dict(meta)
    out["superseded_by"] = successor
    out["invalid_at"] = when or datetime.now(timezone.utc)
    return out


def invalidated_meta(meta: dict, when: datetime,
                     reason: str | None = None) -> dict:
    """Metadados de uma página cujo fato DEIXOU DE VALER em `when` — tempo
    de MUNDO, não de escrita. Sem sucessora: a afirmação simplesmente
    expirou. `reason` entra como descrição curta quando informada."""
    out = dict(meta)
    out["invalid_at"] = when
    if reason:
        out["description"] = reason[:200]
    return out


# Chaves que NÃO entram na união de uma fusão (F1-PR5). Todas dizem algo
# sobre o CICLO DE VIDA ou a IDENTIDADE da página de origem, não sobre o
# fato que ela afirma — e herdá-las faria a vencedora afirmar o que não se
# pode verificar:
#   superseded_by / supersedes  → a vencedora herdaria a sucessão da outra;
#   invalid_at                  → a vencedora nasceria EXPIRADA (a origem
#                                 pode estar stale sem estar supersedida);
#   stale_as_of                 → âncora de commit da origem;
#   source_sha256 / source / resource → checksum e URI canônica da FONTE da
#                                 origem. A proveniência do texto absorvido
#                                 fica na página de origem, que segue no
#                                 bundle (invalidar-nunca-apagar) e é
#                                 linkada da região — por REFERÊNCIA, não
#                                 por cópia. Dois checksums de fontes
#                                 diferentes num campo escalar seria
#                                 escolher um em silêncio;
#   generated_via               → herdar `api:*` sujeitaria a vencedora à
#                                 política de citação de outra página.
NOT_MERGEABLE = ("superseded_by", "supersedes", "invalid_at", "stale_as_of",
                 "source_sha256", "source", "resource", "generated_via")


def mergeable_source_meta(source: dict) -> dict:
    """Frontmatter da origem SEM as chaves de ciclo de vida/identidade."""
    return {k: v for k, v in source.items() if k not in NOT_MERGEABLE}


def merge_meta(target: dict, source: dict) -> dict:
    """União DECLARADA de frontmatter numa fusão (usado pelo MergePages e
    pela fusão de UPDATE): o alvo manda, o que falta vem da fonte, listas
    se unem sem duplicar e a confiança cai para a MAIS FRACA — fundir não
    pode promover a qualidade do que se afirma.

    RFC-004: `confidence` deixa de ser decidido por uma tabela local de
    fraqueza. A tabela tinha três valores e o produto escreve quatro, de
    modo que `human_approved` caía no `default=0` e a mesma situação de
    governança saía ratificada ou não conforme o OUTRO lado da fusão. A
    regra passa a morar em `kernel/ontology.py`, decidida eixo a eixo."""
    out = dict(target)
    for chave, valor in source.items():
        if chave not in out or out[chave] in (None, [], ""):
            out[chave] = valor
            continue
        atual = out[chave]
        if isinstance(atual, list) and isinstance(valor, list):
            visto: list = []
            for item in [*atual, *valor]:
                if item not in visto:
                    visto.append(item)
            out[chave] = visto
        elif chave == "confidence":
            out[chave] = merge_confidence(str(atual), str(valor))
        elif chave == "valid_at":
            out[chave] = min(atual, valor)      # o fato vale desde o + antigo
    return out


def unified_diff(before: str, after: str, path: str) -> str:
    """Diff unificado do corpo COMPLETO da página (frontmatter incluso, já
    que é ele que a maioria dos atos muda). Vazio quando nada muda — e
    preview sem diff é sinal de NOOP, não de sucesso silencioso."""
    linhas = difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}", n=3)
    return "".join(linhas)
