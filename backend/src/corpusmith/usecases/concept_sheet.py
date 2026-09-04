"""ConceptSheet — a ficha do conceito (RFC-006, V6).

**A pergunta do pitch**: "quanto custa adotar essa ideia?" — e é a
capacidade mais fácil de entregar desonesta. A RFC nomeou a armadilha:
**autocertificação**. O produto tem constantes internas de "valor" (0.9
para pergunta aberta, 0.85 para contradição) que ele mesmo declara não
calibradas — *"o detector não mede importância"*
(`usecases/next_actions.py`). Apresentá-las como "ganho medido" numa
ficha de venda seria cometer, na superfície pública, exatamente o
`self_reported`-só que o contrato-mestre proíbe aos mecanismos.

Então esta ficha:

- **compõe o que foi medido** — tempo de leitura (mesma constante da
  fila, nunca uma segunda definição de custo), estabilidade editorial
  (V3), dificuldade de explicar (V4), casos práticos declarados por
  humano + a medição do nível (V5), sob qual LENTE a página fala (V2) e
  ONDE ela diverge (o lint de corpus);
- **carrega as ressalvas junto dos números** — as `misinterpretations`
  de cada contrato viajam ao lado do valor que elas qualificam, não numa
  página separada que ninguém abre;
- **declara o que NÃO mediu** — ganho, valor e importância não têm campo
  nesta estrutura. A ausência é ESTRUTURAL: não há onde alguém escrever
  um número inventado depois, e o teste prende isso.

**A ficha LÊ; ela não recomputa (Q-1).** Até aqui `_estabilidade` e
`_dificuldade` chamavam `Compute*` ao montar — `git log` da história
inteira + lint do corpus inteiro, por abertura de ficha, e um TERCEIRO
caminho para números que o CLI já persistia e o painel já lia. Agora as
três leituras passam por `retrieval/projections.py` e o refresh tem um
dono só (o comando/job que persiste). O preço honesto dessa escolha é
que a ficha pode mostrar projeção VELHA — então ela mostra o frescor
junto (`freshness`, `computed_from`) e diz qual comando a atualiza, em
vez de esconder a idade recomputando na cara do usuário.

**"Nunca computado" não é "vazio", e a ficha não pode empatá-los.** Uma
página sem linha na projeção CALCULADA é "nada observado" (que a V4 já
distinguia de "fácil"); uma projeção que nunca rodou não diz nada sobre
página nenhuma. Ler o segundo caso como o primeiro é vender silêncio
como resultado — o avesso da autocertificação, e igualmente falso.

**A borda LLM é enfeite, não produto.** `prose` sai `None` por default;
ligada, o modelo recebe a ficha determinística e devolve prosa que vive
FORA do bundle. As ressalvas são **re-anexadas depois** da geração, fora
da região que o modelo pode editar — um modelo que "esqueça" de dizer o
que não foi medido não consegue publicar isso, porque essa parte não
passa por ele. Sem modelo, a ficha seca continua inteira.
"""
from __future__ import annotations

from .base import UseCase
from .plan_attention import _cost
from .practical_cases import PracticalCases
from ..okf.bundle import BundleReader
from ..retrieval import projections
from ..settings import Settings

#: Os mecanismos cujas ressalvas a ficha carrega — um por número
#: apresentado. Lista FECHADA: acrescentar um número à ficha sem
#: acrescentar o contrato dele aqui deixaria um valor sem qualificação,
#: que é o gesto que esta capacidade existe para não fazer.
#: `alias_conflict` entra com a linha "sob qual lente" (a identidade
#: com sentido da V2) e `factual_conflict` com "onde diverge" — as duas
#: linhas que a Q-1 acrescentou. A ordem é a de apresentação.
_CONTRATOS = ("editorial_stability", "explanation_difficulty",
              "typed_application_edges", "alias_conflict",
              "factual_conflict")

#: O que a ficha NÃO mede, dito na própria ficha. Não é rodapé: é
#: conteúdo, porque a pergunta "quanto ganho?" é a que o leitor traz.
_NAO_MEDIDO = (
    "GANHO de adotar a ideia — o produto não tem instrumento de desfecho "
    "de negócio, e as constantes internas de 'valor' da fila são de "
    "projeto, explicitamente não calibradas",
    "IMPORTÂNCIA do conceito: nem estabilidade nem dificuldade dizem que "
    "algo vale a pena — dizem quanto mudou e onde travou",
    "esforço de IMPLEMENTAÇÃO: o custo aqui é de LEITURA (minutos de "
    "texto), não de adoção, migração ou operação",
    "QUEM TEM RAZÃO numa divergência: a ficha diz que duas páginas "
    "desacordam sob o mesmo identificador, nunca qual delas está certa "
    "— isso é ato humano (supersede/invalidate/merge)",
)

_PROSA_INSTRUCAO = (
    "Escreva em português, em no máximo 6 linhas, um resumo prático "
    "deste conceito para alguém decidir se vale estudá-lo agora. Use "
    "SOMENTE os números abaixo. NÃO invente benefícios, ganhos ou "
    "porcentagens.\n\n"
)


class ConceptSheet(UseCase):
    """Ficha determinística de UM conceito; `prose` liga a borda LLM."""

    def __init__(self, settings: Settings, page: str, *,
                 prose: bool = False, _router=None):
        self._settings = settings
        self._page = page
        self._prose = prose
        self._router = _router

    def execute(self) -> dict:
        doc = self._carregar()
        palavras = len(doc.body.split())
        ficha = {
            "page": self._page,
            "title": doc.meta.title or self._page,
            "cost": {
                "read_minutes": _cost(palavras),
                "words": palavras,
                # o método viaja com o número: "12 min" sem "a 150
                # palavras/min" convida a ler como esforço de adoção
                "how": "leitura estimada a 150 palavras/min, piso de 2 min "
                       "— é custo de LER, não de adotar",
            },
            "stability": self._estabilidade(),
            "difficulty": self._dificuldade(),
            "applications": PracticalCases(self._settings,
                                           self._page).execute(),
            # Q-1: as duas linhas que faltavam ao pitch de cinco linhas
            "lens": projections.lens(self._settings, self._page),
            "divergence": projections.divergence(self._settings, self._page),
            "guarantees": self._ressalvas(),
            "not_measured": list(_NAO_MEDIDO),
            "prose_enabled": bool(self._prose),
            "prose": None,
        }
        if self._prose:
            self._acrescentar_prosa(ficha)
        return ficha

    # ------------------------------------------------------------ partes
    def _carregar(self):
        reader = BundleReader(self._settings.path("knowledge") / "bundle")
        if not reader.exists(self._page):
            raise KeyError(f"página não existe no bundle: {self._page}")
        return reader.load(self._page)

    def _estabilidade(self) -> dict:
        """LEITURA de `page_stability` — a ficha não recomputa (Q-1).

        `edits: None` com `computed: False` é o estado "ainda não
        calculado"; `0` só aparece quando a projeção rodou e a página de
        fato nunca foi editada depois de nascer."""
        p = projections.stability(self._settings, page=self._page)
        linha = p["row"] or {}
        return {"computed": p["computed"],
                "edits": linha.get("edits") if p["computed"] else None,
                "lifecycle": linha.get("lifecycle") if p["computed"] else None,
                "last_edit_at": linha.get("last_edit_at"),
                "computed_from": p["computed_from"],
                "freshness": p["freshness"],
                "refresh": p["refresh"],
                "means": p["means"]}

    def _dificuldade(self) -> dict:
        """LEITURA de `page_difficulty` — três estados, não dois.

        `computed=False` (nunca rodou) ≠ `measured=False` (rodou, e nada
        foi observado sobre esta página) ≠ score com sinal."""
        p = projections.difficulty(self._settings, page=self._page)
        linha = p["row"] or {}
        return {"computed": p["computed"],
                "score": linha.get("score") if p["computed"] else None,
                "measured": bool(linha.get("measured", False)),
                "reason": linha.get("reason", ""),
                "components": linha.get("components", {}),
                "refresh": p["refresh"],
                "means": p["means"]}

    def _ressalvas(self) -> list[dict]:
        """As `misinterpretations` de cada contrato, ao lado do número que
        elas qualificam. Contrato ausente do registro não é silêncio: a
        lista é fechada e o `EXPECTED_MECHANISMS` já quebra o lint."""
        from ..harness.epistemics import load_registry
        registry, _ = load_registry()
        out = []
        for mid in _CONTRATOS:
            c = registry.get(mid)
            if c is None:
                continue
            out.append({"mechanism_id": mid,
                        "guarantee": c.guarantee.kind.value,
                        "relative_to": c.guarantee.relative_to,
                        "misinterpretations": list(c.misinterpretations)})
        return out

    # -------------------------------------------------------- borda LLM
    def _acrescentar_prosa(self, ficha: dict) -> None:
        from ..models.router import ModelRouter, ModelUnavailable
        router = self._router or ModelRouter(self._settings)
        try:
            texto = router.complete(_PROSA_INSTRUCAO + _resumo(ficha),
                                    privacy="local_only")
        except ModelUnavailable as e:
            ficha["prose_error"] = str(e)
            return
        if not (texto or "").strip():
            ficha["prose_error"] = "modelo devolveu vazio"
            return
        # RE-ANEXAR DETERMINISTICAMENTE: as ressalvas não passam pelo
        # modelo, então ele não tem como esquecê-las nem reescrevê-las.
        ficha["prose"] = texto.strip() + "\n\n" + _rodape(ficha)


def _resumo(ficha: dict) -> str:
    """O que o modelo VÊ — só números medidos, nunca a promessa.

    Projeção não calculada entra como a FRASE "ainda não calculado", não
    como número ausente: dar `None` a um modelo é convidá-lo a preencher."""
    a, e, d = ficha["applications"], ficha["stability"], ficha["difficulty"]
    lente = ficha["lens"]
    edits = (f"{e['edits']}" if e["computed"]
             else "ainda não calculado nesta máquina")
    dific = (f"{d['score']} (medida={d['measured']}; {d['reason']})"
             if d["computed"] else "ainda não calculado nesta máquina")
    return (f"Conceito: {ficha['title']}\n"
            f"Custo de leitura: {ficha['cost']['read_minutes']} min "
            f"({ficha['cost']['how']})\n"
            f"Edições no histórico: {edits} ({e['means']})\n"
            f"Dificuldade: {dific}\n"
            f"Casos práticos declarados: {len(a['cases'])}\n"
            f"Lentes (menções): "
            f"{', '.join(x['canonical'] for x in lente['entities']) or '—'} "
            f"({lente['means']})\n"
            f"Divergências registradas: "
            f"{len(ficha['divergence']['conflicts'])}\n")


def _rodape(ficha: dict) -> str:
    return ("— o que NÃO medimos: "
            + "; ".join(ficha["not_measured"])
            + ".\nRessalvas dos mecanismos usados: "
            + " | ".join(f"{g['mechanism_id']}: {g['misinterpretations'][0]}"
                         for g in ficha["guarantees"]
                         if g["misinterpretations"]))
