from __future__ import annotations
import re
from .model import Match

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
    """Compila (seeds ∪ authority_records do bundle) num único autômato regex.
    Aliases mais longos vencem; 'node.js' casa antes de qualquer subparte."""

    def __init__(self, entries: list[tuple[str, list[str], str, str | None]]):
        self.map: dict[str, tuple[str, str, str | None]] = {}
        for canonical, aliases, authority, qid in entries:
            forms = set(a.lower() for a in aliases)
            if canonical not in UNSAFE_BARE:
                forms.add(canonical.lower())    # idempotência: canônico casa a si mesmo
            for f in forms:
                self.map[f] = (canonical, authority, qid)
        alts = "|".join(sorted((re.escape(k) for k in self.map),
                               key=len, reverse=True))
        # lookahead permite pontuação final ("…nodejs."), protege nomes com ponto
        # ("node.js") e esquemas de URL ("postgres://")
        self.rx = re.compile(rf"(?<![\w./])({alts})(?!\w|\.\w|://)", re.I)

    @classmethod
    def load(cls, extra: list[dict] | None = None) -> "Gazetteer":
        entries = list(SEEDS)
        for e in extra or []:                   # authority_records vindos do bundle
            entries.append((e["canonical"], list(e.get("aliases", [])),
                            e.get("authority", "term"), e.get("qid")))
        return cls(entries)

    def detect(self, text: str) -> list[Match]:
        out = []
        for m in self.rx.finditer(text):
            canonical, authority, qid = self.map[m.group(1).lower()]
            out.append(Match(m.start(), m.end(), "entity", authority,
                             m.group(0), canonical,
                             data={"qid": qid} if qid else {}))
        return out
