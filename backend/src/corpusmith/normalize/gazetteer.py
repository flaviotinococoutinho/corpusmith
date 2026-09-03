"""Gazetteer: alias → identidade curada — PURO.

**RFC-006 V2 (identidade-com-sentido).** Até aqui um alias resolvia para
EXATAMENTE um canônico, e a colisão era decidida por ordem de inserção:
`self.map[f] = (...)` — o último a escrever vencia, em silêncio. Num corpus
de estudo isso é o defeito central: "entropia" da física e "entropia" da
informação colapsavam na MESMA entidade, e quem lia não tinha como saber
que dois sentidos tinham sido fundidos.

A correção não inventa mecanismo: usa o que o produto já tem para *não
decidir*. Um alias disputado produz `Match(confidence="ambiguous")`, e
`ambiguous` já significa "não resolvido" em toda a cadeia — `_rewritable`
não reescreve (o texto não ganha um lado escolhido), `fts.py` não indexa
como entidade e `entities_frontmatter` não lista — e, como aresta de
grafo nasce de LINK e não de entidade, o termo simplesmente deixa de
ligar páginas. O que faltava era PRODUZIR a ambiguidade em vez de
resolvê-la sozinho.

**Precedência entre camadas ≠ ambiguidade dentro de uma.** Seeds embutidos
e `reference.db` são DEFAULTS; `authority_record` no bundle é CURADORIA. A
curadoria vence por precedência, e isso não é conflito — é a regra
declarada de sempre (v0.22). Conflito é quando DOIS registros da mesma
camada disputam o alias: aí ninguém tem autoridade sobre o outro, e
escolher seria inventar.

**O sentido mora no CANÔNICO, não num campo novo.** `Entropia (física)` e
`Entropia (informação)` são identidades diferentes, e o qualificador é
parte da identidade — um campo `sense` paralelo criaria dois donos do
mesmo fato (a patologia que o RFC-004 pagou caro para desfazer) e ainda
convidaria a enfiar "disciplina" no campo `authority`, que já carrega
cinco sentidos (`[drift.authority]`, ABERTA). Sem schema novo: o canônico
é string curada, e `sentido()` só LÊ o que o curador escreveu.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from .model import Match

#: Camadas de origem, da menos para a mais autoritativa. A precedência é a
#: regra de sempre (v0.22: authority_record > reference.db > seeds); o que
#: muda na V2 é que a colisão DENTRO da camada deixa de ser silenciosa.
TIER_SEED, TIER_REFERENCIA, TIER_BUNDLE = 0, 1, 2

#: Qualificador de sentido no fim do canônico, à moda das desambiguações de
#: enciclopédia: `Entropia (física)`. Conservador de propósito — só um
#: parêntese FINAL, sem aninhamento. Ele NÃO decide identidade (identidade
#: é o canônico inteiro, comparado por igualdade): serve para explicar o
#: conflito a quem lê. Um canônico que termine em parêntese sem ser sentido
#: custa um rótulo errado, nunca uma entidade errada.
_RE_SENTIDO = re.compile(r"^(?P<base>.+?)\s+\((?P<sentido>[^()]+)\)$")


def sentido(canonical: str) -> str | None:
    """`Entropia (física)` → `física`; `PostgreSQL` → None."""
    m = _RE_SENTIDO.match(canonical.strip())
    return m.group("sentido").strip() if m else None


def base(canonical: str) -> str:
    """O termo sem o qualificador: `Entropia (física)` → `Entropia`."""
    m = _RE_SENTIDO.match(canonical.strip())
    return m.group("base").strip() if m else canonical.strip()


@dataclass(frozen=True)
class Candidato:
    """Uma identidade que reivindica um alias, e de onde ela veio.

    `page` só existe para a camada do bundle — é o `authority_record` que
    o curador edita para resolver um conflito, e é o alvo do finding."""
    canonical: str
    authority: str
    qid: str | None = None
    tier: int = TIER_SEED
    page: str | None = None

    @property
    def sentido(self) -> str | None:
        return sentido(self.canonical)

# ---------- seeds embutidos (subconjunto; a curadoria REAL vive no bundle, §4) ----------
# (canônico, [aliases], authority, qid)
SEEDS: list[tuple[str, list[str], str, str | None]] = [
    # stacks — grafia oficial correta é o produto aqui
    ("PostgreSQL", ["postgres", "postgresql", "pgsql", "postgre"], "stack", "Q192490"),
    ("SQLite", ["sqlite", "sqlite3"], "stack", "Q319417"),
    ("JavaScript", ["javascript", "java script"], "stack", "Q2005"),
    ("TypeScript", ["typescript"], "stack", "Q978185"),
    ("Node.js", ["nodejs", "node.js", "node js"], "stack", "Q756100"),
    ("Kubernetes", ["kubernetes", "k8s"], "stack", "Q22661306"),
    ("Elasticsearch", ["elasticsearch", "elastic search"], "stack", "Q3050461"),
    ("MongoDB", ["mongodb", "mongo db"], "stack", "Q1165204"),
    ("RabbitMQ", ["rabbitmq"], "stack", "Q1481819"),
    ("gRPC", ["grpc"], "stack", "Q24074746"),
    ("GraphQL", ["graphql"], "stack", "Q25104949"),
    ("Wi-Fi", ["wifi", "wi-fi", "wi fi"], "stack", "Q29643"),
    ("macOS", ["macos", "mac os x", "osx", "os x"], "stack", "Q14116"),
    ("PyTorch", ["pytorch"], "stack", "Q47509047"),
    ("scikit-learn", ["scikit-learn", "sklearn", "scikit learn"], "stack", "Q1026367"),
    ("LaTeX", ["latex"], "stack", "Q5310"),
    ("GitHub", ["github"], "stack", "Q364"),
    ("GitLab", ["gitlab"], "stack", "Q16639197"),
    ("VS Code", ["vscode", "vs code", "visual studio code"], "stack", "Q19841877"),
    ("IntelliJ IDEA", ["intellij", "intellij idea"], "stack", "Q1131183"),
    ("Spring Boot", ["spring boot", "springboot"], "stack", "Q98731994"),
    ("OAuth 2.0", ["oauth2", "oauth 2", "oauth 2.0"], "stack", "Q7078461"),
    ("JSON", ["json"], "stack", "Q2063"), ("YAML", ["yaml", "yml"], "stack", "Q281876"),
    ("JWT", ["jwt"], "stack", None), ("CI/CD", ["ci/cd", "cicd"], "stack", None),
    ("FastAPI", ["fastapi", "fast api"], "stack", "Q97302003"),
    ("Electron", ["electron"], "stack", "Q21005674"),
    ("llama.cpp", ["llama.cpp", "llamacpp", "llama cpp"], "stack", None),
    # editoras / publicações — inclui a armadilha do apóstrofo tipográfico
    ("O'Reilly", ["oreilly", "o'reilly", "o’reilly", "o reilly"], "publisher", "Q1668540"),
    ("Springer", ["springer", "springer-verlag", "springer verlag"], "publisher", "Q1667701"),
    ("Springer Nature", ["springer nature"], "publisher", "Q21096327"),
    ("Elsevier", ["elsevier"], "publisher", "Q746413"),
    ("Addison-Wesley", ["addison-wesley", "addison wesley"], "publisher", "Q622281"),
    ("Manning", ["manning", "manning publications"], "publisher", "Q15709347"),
    ("MIT Press", ["mit press"], "publisher", "Q1341102"),
    ("Packt", ["packt", "packtpub"], "publisher", "Q3357087"),
    ("Casa do Código", ["casa do codigo", "casa do código"], "publisher", None),
    ("Novatec", ["novatec"], "publisher", None),
    ("NeurIPS", ["nips", "neurips"], "publication", "Q5726293"),  # renomeio clássico
    ("ICML", ["icml"], "publication", "Q969707"),
    ("arXiv", ["arxiv"], "publication", "Q118398"),
    ("Communications of the ACM", ["cacm", "communications of the acm"],
     "publication", "Q1119032"),
    ("Nature", ["nature"], "publication", "Q180445"),
    # organizações reguladoras/técnicas
    ("W3C", ["w3c"], "org", "Q37033"), ("IETF", ["ietf"], "org", "Q217082"),
    ("ISO", ["iso"], "org", "Q15028"), ("ABNT", ["abnt"], "org", "Q4651530"),
    ("IEEE", ["ieee"], "org", "Q131566"), ("ACM", ["acm"], "org", "Q127992"),
    ("NIST", ["nist"], "org", "Q176691"), ("ANPD", ["anpd"], "org", None),
]
# jamais case bare por FP: exigem alias explícito ou casamento case-sensitive (§1.6)
UNSAFE_BARE = {"Go", "R", "C", "Rust", "Swift", "Nature"}

class Gazetteer:
    """Compila (seeds ∪ reference.db ∪ authority_records) num autômato regex.

    Aliases mais longos vencem; 'node.js' casa antes de qualquer subparte.
    Cada alias guarda a LISTA de candidatos da camada mais alta que o
    reivindica: um só ⇒ resolvido; dois ou mais ⇒ ambíguo, e o produto
    recusa escolher (V2)."""

    def __init__(self, entries: list[tuple[str, list[str], str, str | None]],
                 *, curados: list[dict] | None = None):
        por_alias: dict[str, list[Candidato]] = {}

        def reivindicar(cand: Candidato, aliases) -> None:
            # `aliases` vem de frontmatter com `extra="allow"`: NADA valida o
            # tipo. `aliases: entropia` (escalar) chega como str, e iterar
            # str produz um alias por CARACTERE — medido: 8 aliases de uma
            # letra, cada vogal do corpus virando ocorrência da entidade, e
            # com dois registros assim a V2 amplificava para findings de
            # conflito sobre letras soltas. Alias vazio é igualmente tóxico:
            # entra no `alts` como alternativa vazia e casa em toda fronteira
            # de pontuação (spans de comprimento zero).
            if isinstance(aliases, str):
                aliases = [aliases]
            forms = {a.lower() for a in aliases or ()
                     if isinstance(a, str) and a.strip()}
            if cand.canonical not in UNSAFE_BARE:
                forms.add(cand.canonical.lower())   # idempotência: casa a si mesmo
            for f in forms:
                por_alias.setdefault(f, []).append(cand)

        for canonical, aliases, authority, qid in entries:
            reivindicar(Candidato(canonical, authority, qid, TIER_SEED),
                        aliases)
        for e in curados or []:
            reivindicar(Candidato(e["canonical"], e.get("authority", "term"),
                                  e.get("qid"), int(e.get("tier", TIER_BUNDLE)),
                                  e.get("page")),
                        e.get("aliases", []))

        self.map: dict[str, list[Candidato]] = {}
        for alias, cands in por_alias.items():
            teto = max(c.tier for c in cands)
            vistos: dict[tuple, Candidato] = {}
            for c in cands:
                # precedência resolve ENTRE camadas; dentro da camada,
                # IDENTIDADE repetida é o mesmo fato dito duas vezes
                # (dedup), e identidade diferente é conflito de verdade.
                #
                # A chave é (canônico, autoridade, qid), não só o canônico:
                # dedupar só por canônico deixava `qid` ser decidido pela
                # ORDEM DO ARQUIVO — o mesmo "último a escrever vence" que
                # este pacote existe para eliminar, sobrevivendo nos outros
                # campos da identidade.
                if c.tier == teto:
                    vistos.setdefault((c.canonical, c.authority, c.qid), c)
            self.map[alias] = sorted(
                vistos.values(),
                key=lambda c: (c.canonical, c.authority, c.qid or ""))

        alts = "|".join(sorted((re.escape(k) for k in self.map),
                               key=len, reverse=True))
        # lookahead permite pontuação final ("…nodejs."), protege nomes com ponto
        # ("node.js") e esquemas de URL ("postgres://")
        self.rx = re.compile(rf"(?<![\w./])({alts})(?!\w|\.\w|://)", re.I)

    @classmethod
    def load(cls, extra: list[dict] | None = None) -> "Gazetteer":
        return cls(list(SEEDS), curados=list(extra or []))

    # ------------------------------------------------------------ leitura
    def candidatos(self, alias: str) -> list[Candidato]:
        return self.map.get(alias.lower(), [])

    def termos(self) -> set[tuple[str, str, str | None]]:
        """Identidades distintas conhecidas — o que o painel conta."""
        return {(c.canonical, c.authority, c.qid)
                for cands in self.map.values() for c in cands}

    def conflitos(self) -> dict[str, list[Candidato]]:
        """Aliases reivindicados por 2+ identidades da MESMA camada.

        É o sinal da V2, e ele é DETERMINÍSTICO: igualdade de alias entre
        registros curados, sem limiar e sem nada a calibrar. O que ele NÃO
        vê está declarado no contrato — ambiguidade que ninguém curou é
        invisível aqui (um corpus sem `authority_record` tem zero
        conflitos e vocabulário inteiramente por resolver)."""
        return {alias: cands for alias, cands in sorted(self.map.items())
                if len(cands) > 1}

    def detect(self, text: str) -> list[Match]:
        out = []
        for m in self.rx.finditer(text):
            cands = self.map[m.group(1).lower()]
            if len(cands) == 1:
                c = cands[0]
                out.append(Match(m.start(), m.end(), "entity", c.authority,
                                 m.group(0), c.canonical,
                                 data={"qid": c.qid} if c.qid else {}))
                continue
            # ALIAS DISPUTADO: o canônico continua sendo a superfície — o
            # produto não escolhe um lado no texto de ninguém —, e o
            # `ambiguous` propaga o "não resolvido" por toda a cadeia que
            # já o respeita. `authority` só sobrevive quando os candidatos
            # concordam; discordando, cai no genérico em vez de fingir.
            autoridades = {c.authority for c in cands}
            out.append(Match(
                m.start(), m.end(), "entity",
                autoridades.pop() if len(autoridades) == 1 else "term",
                m.group(0), m.group(0), confidence="ambiguous",
                data={"candidates": [c.canonical for c in cands],
                      "senses": [c.sentido for c in cands]}))
        return out
