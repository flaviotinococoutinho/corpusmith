"""DetectCommunities (v0.8 §7 como use case, v0.9 + topologia).

Além das comunidades (Leiden ou componentes ponderados) e das páginas
community_summary (via o MESMO Template Method de página de máquina),
computa as PONTES FRÁGEIS do grafo por persistência 0-dimensional
(kernel.topology): pares de blocos de conhecimento unidos por um único fio
fraco — o diagnóstico topológico que a curadoria usa para linkar temas.

**F2-PR1 (ADR-43) — o mapa passa a ser repetível e datado.** Três coisas
que faltavam, e a ordem entre elas não é arbitrária:

1. **repetibilidade**, em duas pernas, e qual perna faz o quê foi
   estabelecido por execução. Num ANEL de 24 nós (muitos cortes
   quase-empatados), 8 execuções:

   | ordem de inserção das arestas | seed | partições distintas |
   |---|---|---|
   | variável | não | 8 |
   | variável | sim | 6 |
   | canônica | não | 1 |
   | canônica | sim | 1 |

   - **ordem canônica** (os `sorted()` do `_partition` e do
     `_leiden_or_components`) é o que mata a variação — a numeração de
     vértice do `igraph` vem da ordem de inserção. `seed` SOZINHO não
     resolve: 6 partições em 8 execuções;
   - **`seed`** é o que sobrevive a `PYTHONHASHSEED=random`, a condição real
     (o daemon não fixa hash): em 4 processos, sem seed o de hash aleatório
     divergiu dos outros três; com seed, os quatro idênticos.

   E a **numeração da comunidade** vem do menor membro: medido, em três
   execuções sobre o mesmo bundle o agrupamento se manteve e o rótulo trocou
   nas três — `communities` mudava sem o conhecimento ter mudado, e a F2-PR2,
   que casa partições entre execuções, compararia ruído com ruído;
2. **datação** (`graph_snapshot`): o mapa diz de quando é, de qual `HEAD`, e
   **por qual backend**. Esse último campo não é decoração — numa máquina em
   que o extra `[ml]` não compilou, o produto cai no fallback de componentes
   conexos EM SILÊNCIO e chama o resultado de "comunidade". Sem registrar
   quem produziu, o doctor não tem como dizer isso em voz alta;
3. **poda**: ponte cujo endpoint saiu do índice ou foi supersedida é ponte
   para lugar nenhum — e é o item que a fila do cockpit põe entre os de
   maior densidade valor/custo.

Uma medição que NÃO virou mudança, e fica registrada para ninguém repetir o
caminho: o laço de co-menção parecia um N+1 (uma query por entidade) e num
banco sintético levou 76 s para 10 000 entidades. Com o índice
`idx_pe_entity`, que o schema real tem, o N+1 empata com uma varredura
única (1,0×) — os 76 s eram artefato da tabela sem índice. Trocar por
varredura seria refactor sem ganho medido, o que o `AGENTS.md` proíbe.
"""
from __future__ import annotations
import hashlib
import itertools
import json
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from .base import DraftPage, MachinePageUseCase, UseCase
from ..kernel.topology import fragile_bridges
from ..models.router import ModelRouter, ModelUnavailable
from ..okf.git_store import GitStore
from ..runtime.db import connect
from ..settings import Settings

W = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}
# Seed fixo do particionamento. É CONSTANTE do produto, não configuração: um
# seed que o usuário pudesse mudar tornaria "mesmo bundle ⇒ mesma partição"
# uma promessa condicional, e o valor do carimbo é justamente ser comparável
# entre execuções. Fica gravado no snapshot para a comparação ser auditável.
LEIDEN_SEED = 20260726
# `communities/` é PRODUTO do particionamento (D-E do docs/15). Deixá-lo no
# grafo faz cada rodada alterar o grafo da seguinte: épocas falsas de tema e
# sumários entrando no p99 de grau. Hoje não morde porque o job não reindexa,
# mas o DoD da F2-PR2 diz que passará a reindexar.
_DERIVED_PREFIX = "communities/"


def _slug(name: str) -> str:
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "comunidade"


class _CommunitySummaryPage(MachinePageUseCase):
    LOG_KIND = "Update"
    MODULE = "communities"

    def __init__(self, settings: Settings, label: str, summary: str,
                 members: list[tuple[str, str]], fingerprint: str,
                 theme: str):
        super().__init__(settings)
        self._label = label
        self._summary = summary
        self._members = members
        self._fingerprint = fingerprint
        self._theme = theme

    def _produce(self) -> DraftPage:
        body = (f"# {self._label}\n\n{self._summary}\n\n## Membros centrais\n"
                + "\n".join(f"- [{title}](/{page})"
                            for page, title in self._members) + "\n")
        # F2-PR2 (RFC-001 §4.3): o caminho vem do `theme_id`, NÃO do rótulo.
        # Medido antes: um tema de 5 páginas cuja página mais conectada troca
        # produzia DUAS páginas canônicas vivas (`ana.md` e `elo.md`) para o
        # mesmo tema, nenhuma supersedida. O rótulo legível vai para o
        # frontmatter e para o corpo — onde mudar não cria arquivo.
        return DraftPage(
            rel_path=f"communities/{self._theme}.md",
            title=self._label, body=body,
            meta={"type": "community_summary",
                  "description": self._summary[:200],
                  "privacy": "local_only",
                  "generated_via": "local:leiden",
                  "theme_id": self._theme,
                  "source_sha256": self._fingerprint},
            log_message=f"comunidade: {self._label}",
            commit_message=f"leiden: {_slug(self._label)}")


class DetectCommunities(UseCase):
    def __init__(self, settings: Settings, notify=None, *, gov=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)
        # REL-1: rota de modelo carrega o Governor — orçamento e ledger
        self._router = ModelRouter(settings, gov)

    def execute(self) -> dict:
        idx = connect(self._settings.app_support / "index.db")
        adjacency = self._weighted_graph(idx)
        bridges = self._store_bridges(idx, adjacency)
        centrality_backend = self._store_centrality(idx, adjacency)
        communities, backend, hubs = self._partition(adjacency)
        idx.execute("DELETE FROM communities")
        idx.executemany("INSERT INTO communities(page,community) VALUES (?,?)",
                        sorted(communities.items()))
        idx.commit()
        distinct = {c for c in communities.values() if c >= 0}
        edges = sum(len(nb) for nb in adjacency.values()) // 2
        eventos = self._match_themes(idx, communities, backend)
        summaries = self._write_summaries(adjacency, communities, idx)
        # O CARIMBO VEM DEPOIS DOS SUMÁRIOS, e a ordem é a correção de um
        # defeito medido: `_write_summaries` escreve páginas
        # `communities/` pelo writer, e cada escrita é um COMMIT. Carimbar
        # antes gravava o HEAD anterior aos próprios sumários, então o mapa
        # nascia "velho" e o INV-004 disparava para sempre — um alarme sem
        # saída, porque recomputar reproduzia a divergência.
        adotadas = self._adopt_legacy(idx)
        self._stamp(idx, backend=backend, nodes=len(adjacency), edges=edges,
                    communities=len(distinct), bridges=bridges, hubs=hubs,
                    centrality_backend=centrality_backend)
        idx.close()
        return {"communities": len(distinct), "pages": len(communities),
                "summaries": summaries, "backend": backend,
                "bridges": bridges, "centrality_backend": centrality_backend,
                "theme_events": [e.event for e in eventos],
                "themes_adopted": adotadas}

    def _adopt_legacy(self, idx) -> int:
        """Páginas `communities/` escritas ANTES do `theme_id` (RFC-001 §4.5).

        Sem isto, o PR entrega o INV-005 violado no primeiro upgrade: a página
        no caminho antigo (`communities/ana.md`) continua VIVA ao lado da nova
        (`communities/thm_....md`), as duas descrevendo o mesmo tema — que é
        exatamente o defeito medido que este PR existe para fechar, agora com
        um arquivo a mais.

        Não apaga (invalidar-nunca-apagar): a página antiga é SUPERSEDIDA
        apontando para o caminho novo do tema que ela descreve, casado pelos
        membros que ela mesma lista. Se não casa com tema nenhum, é supersedida
        sem sucessora — o corpo segue legível e no histórico.

        A escrita passa pelo `BundleWriter`, logo pelo gate, como toda escrita.
        """
        from ..kernel.curation import superseded_meta
        from ..kernel.themes import TAU, jaccard
        from ..okf.document import OKFDocument, OKFFrontMatter
        from ..okf.links import MD_LINK
        from ..okf.writer import BundleWriter
        writer = BundleWriter(self._settings.path("knowledge"))
        reader = writer.reader
        vivos = {r["theme_id"]: set(json.loads(r["members"]))
                 for r in idx.execute("SELECT theme_id, members FROM themes "
                                      "WHERE died_at IS NULL")}
        pendentes = []
        for rel in reader.raw_md_files():
            if not rel.startswith(_DERIVED_PREFIX) or rel.endswith("/index.md"):
                continue
            nome = rel.rsplit("/", 1)[-1]
            if nome.startswith("thm_"):
                continue                     # já está no formato novo
            try:
                doc = reader.load(rel)
            except Exception:
                continue
            meta = doc.meta.model_dump(exclude_none=True)
            if meta.get("theme_id") or meta.get("superseded_by") \
                    or meta.get("invalid_at"):
                continue                     # já adotada ou já aposentada
            # os membros que a PRÓPRIA página declara
            membros = {m.group("target").lstrip("/")
                       for m in MD_LINK.finditer(doc.body)}
            melhor, melhor_j = None, 0.0
            for tid, atuais in sorted(vivos.items()):
                j = jaccard(membros, atuais)
                if j > melhor_j:
                    melhor, melhor_j = tid, j
            novo = superseded_meta(meta, f"{_DERIVED_PREFIX}{melhor}.md") \
                if melhor and melhor_j >= TAU else \
                {**meta, "invalid_at": datetime.now(timezone.utc)}
            pendentes.append(OKFDocument(rel_path=rel, body=doc.body,
                                         meta=OKFFrontMatter(**novo)))
        # UMA escrita por página, e não uma só com todas: uma página antiga
        # MALFORMADA (editada à mão, sem `source_sha256`) faz o Harness recusar
        # — corretamente. Numa escrita única, essa recusa bloquearia a adoção
        # de todas as outras e o INV-005 seguiria violado no bundle inteiro por
        # causa de um arquivo. O gate não é enfraquecido: a recusa é isolada e
        # a página problemática simplesmente continua como estava, visível ao
        # `okf lint`.
        adotadas = 0
        for doc in pendentes:
            try:
                writer.write([doc], log_kind="Deprecation",
                             log_message=(f"tema no formato antigo "
                                          f"supersedido: {doc.rel_path}"),
                             commit_message=f"themes: adota {doc.rel_path}")
                adotadas += 1
            except Exception:                # noqa: BLE001
                self._notify("themes.adopt_refused", {"page": doc.rel_path})
        return adotadas

    # ------------------------------------------------ identidade de tema (PR2)
    def _match_themes(self, idx, communities, backend) -> list:
        """Casa a época anterior com a nova e registra as épocas (RFC-001).

        Roda ANTES dos sumários porque é ele que decide o `rel_path` de cada
        página de tema — e depois do particionamento porque precisa da
        partição nova.

        **Recusa casar partições de backends diferentes** (RFC §8): `leiden` e
        `components` produzem mapas incomparáveis por construção, e casá-los
        registraria épocas falsas em massa. Nesse caso o tema mantém a
        identidade que tinha e nenhuma época é escrita.
        """
        from ..kernel.themes import match, theme_id as _tid
        novas: dict[int, set[str]] = defaultdict(set)
        for page, cid in communities.items():
            if cid >= 0 and not page.startswith(_DERIVED_PREFIX):
                novas[cid].add(page)
        # comunidade de 1 membro não recebe sumário, logo não é tema
        particao = [m for _, m in sorted(novas.items()) if len(m) >= 2]

        anterior = {r["theme_id"]: set(json.loads(r["members"]))
                    for r in idx.execute(
                        "SELECT theme_id, members FROM themes "
                        "WHERE died_at IS NULL")}
        carimbo = idx.execute("SELECT backend FROM graph_snapshot WHERE id=1"
                              ).fetchone()
        if anterior and carimbo and carimbo["backend"] != backend:
            self._temas = {}                 # sem casamento: mantém o que há
            for tid, membros in anterior.items():
                self._temas[frozenset(membros)] = tid
            return []
        if not particao and not anterior:
            self._temas = {}
            return []

        eventos = match(anterior, particao)
        agora = time.time()
        head = ""
        try:
            head = GitStore(self._settings.path("knowledge")).head()
        except Exception:
            pass
        # mapa membros -> theme_id que o `_write_summaries` consulta
        self._temas = {frozenset(m): tid for tid, m in anterior.items()}
        for ev in eventos:
            chave = frozenset(ev.members)
            if ev.event == "died":
                idx.execute("UPDATE themes SET died_at=? WHERE theme_id=?",
                            (agora, ev.theme_id))
                self._temas.pop(chave, None)
            elif ev.event == "split":
                idx.execute("UPDATE themes SET died_at=? WHERE theme_id=?",
                            (agora, ev.theme_id))
                self._temas.pop(chave, None)
            else:
                idx.execute(
                    "INSERT INTO themes(theme_id, community, rel_path, "
                    "born_at, members) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(theme_id) DO UPDATE SET members=excluded.members",
                    (ev.theme_id, None,
                     f"communities/{ev.theme_id}.md", agora,
                     json.dumps(sorted(ev.members))))
                self._temas[chave] = ev.theme_id
            idx.execute(
                "INSERT INTO theme_epochs(theme_id, event, at, bundle_head, "
                "jaccard, members, related) VALUES (?,?,?,?,?,?,?)",
                (ev.theme_id, ev.event, agora, head, ev.jaccard,
                 json.dumps(sorted(ev.members)), json.dumps(ev.related)))
        # temas que continuaram sem evento precisam seguir no mapa
        for membros in particao:
            chave = frozenset(membros)
            if chave not in self._temas:
                self._temas[chave] = _tid(membros)
                idx.execute(
                    "INSERT OR IGNORE INTO themes(theme_id, community, "
                    "rel_path, born_at, members) VALUES (?,?,?,?,?)",
                    (self._temas[chave], None,
                     f"communities/{self._temas[chave]}.md", agora,
                     json.dumps(sorted(membros))))
        idx.commit()
        return eventos

    # -------------------------------------------------- centralidade (PR3+4)
    def _store_centrality(self, idx, adjacency) -> str:
        """Brandes FORA do request, pelo `ComputeKernel`.

        Duas correções num gesto, as duas medidas:

        1. **fora do request**. Brandes era 95% do custo de `/cockpit/graph` a
           1200 páginas (2571 ms de 2571; a 100 páginas era 52%), cresce
           ~O(n²) e o baseline registra 88 s a 5000 nós. E `structural_gaps`
           chamava `graph_data`, então abrir Grafo e Insights pagava DUAS
           vezes. Agora o request lê uma tabela;
        2. **pelo kernel**. O `ComputeKernel` seleciona `rust` quando existe —
           e o `observatory` chamava o `betweenness_centrality` PURO em Python
           direto, ignorando o kernel selecionado. O baseline mede 88 058 ms
           (python) contra 1 944 ms (rust) a 5000 nós: 45×. A camada nativa
           estava paga e não estava sendo usada no caminho quente.

        Devolve o nome do backend que mediu, para o carimbo declarar. Falha do
        kernel NÃO derruba o job: a centralidade é um enfeite do mapa, não o
        mapa — devolve `none` e a interface serve grau (ADR-39 §22: ausência
        de camada nativa é comportamento suportado, não erro).
        """
        idx.execute("DELETE FROM graph_centrality")
        if not adjacency:
            idx.commit()
            return "none"
        try:
            from ..compute import get_kernel
            kernel = get_kernel(self._settings)
            nome = kernel.backend_info().name
            # O kernel lê `graph_edges` da MESMA conexão e aplica o MESMO
            # `EDGE_WEIGHT` que o `observatory` aplicava — então os valores
            # persistidos são idênticos aos que o request calculava, e este PR
            # é mudança de ONDE e de QUAL kernel, não de QUANTO. Alimentar o
            # `adjacency` do leiden aqui seria tentador e estaria errado por
            # duas razões: ele carrega arestas de co-menção que a
            # centralidade nunca teve, e `load_edges` mapeia o terceiro campo
            # por `EDGE_WEIGHT`, então peso já acumulado viraria 0.5 para tudo.
            grafo = kernel.load_graph(index_path="", connection=idx)
            centralidade = kernel.betweenness(grafo)
        except Exception:                            # noqa: BLE001
            idx.commit()
            return "none"
        idx.executemany(
            "INSERT INTO graph_centrality(page, betweenness) VALUES (?,?)",
            sorted((p, float(v)) for p, v in centralidade.items()))
        idx.commit()
        return nome if nome in ("python", "rust") else "none"

    # -------------------------------------------------------------- carimbo
    def _stamp(self, idx, *, backend: str, nodes: int, edges: int,
               communities: int, bridges: int, hubs: int,
               centrality_backend: str = "none") -> None:
        """`graph_snapshot`: de quando é o mapa, e quem o produziu.

        Uma linha só, sobrescrita — o histórico do tema é entrega da F2-PR2,
        e guardar série aqui seria inventar autoridade que a fase seguinte
        vai definir."""
        try:
            head = GitStore(self._settings.path("knowledge")).head()
        except Exception:
            head = ""            # kb sem commit ainda: carimba vazio, não mente
        idx.execute("DELETE FROM graph_snapshot")
        idx.execute(
            "INSERT INTO graph_snapshot(id, bundle_head, computed_at, backend,"
            " seed, nodes, edges, communities, bridges, hubs_excluded,"
            " centrality_backend) VALUES (1,?,?,?,?,?,?,?,?,?,?)",
            (head, time.time(), backend,
             LEIDEN_SEED if backend == "leiden" else None,
             nodes, edges, communities, bridges, hubs, centrality_backend))
        idx.commit()

    # -------------------------------------------------------------- grafo
    def _weighted_graph(self, idx) -> dict[str, dict[str, float]]:
        adjacency: dict[str, dict[str, float]] = defaultdict(dict)

        def add_edge(a: str, b: str, weight: float) -> None:
            # D-E: página derivada não entra no grafo que a gerou
            if a == b or a.startswith(_DERIVED_PREFIX) \
                    or b.startswith(_DERIVED_PREFIX):
                return
            adjacency[a][b] = adjacency[a].get(b, 0.0) + weight
            adjacency[b][a] = adjacency[b].get(a, 0.0) + weight

        # Sem ORDER BY nas duas queries, e a ausência é DELIBERADA — cheguei
        # a acrescentá-lo e o removi, porque não se justifica. O raciocínio,
        # para ninguém repetir o caminho: a ordem da query poderia importar
        # pela SOMA (`add_edge` acumula com `+=`, e float não é associativo —
        # medido, `1.0 + 0.15 + 0.15` dá 1.3 ou 1.2999999999999998 conforme a
        # ordem). Mas a PK de `graph_edges` é `(src, dst, kind)` com dois
        # `kind` possíveis, então um par recebe no MÁXIMO duas contribuições
        # deste laço — e soma de dois floats é comutativa. As do laço de
        # co-menção são todas iguais (0.25), e ordem de parcelas iguais não
        # muda soma. Quem canoniza a numeração de vértice são os `sorted()` do
        # `_partition`/`_leiden_or_components`, e isso é falsificável por
        # teste; um ORDER BY infalsificável seria custo sem ganho medido.
        for src, dst, conf in idx.execute(
                "SELECT src, dst, COALESCE(confidence,'extracted') "
                "FROM graph_edges"):
            add_edge(src, dst, W.get(conf, 0.5))
        # arestas inferred por co-menção de entidade (teto anti-hub na origem)
        for (eid,) in idx.execute(
                "SELECT entity_id FROM page_entities GROUP BY entity_id "
                "HAVING COUNT(DISTINCT page) BETWEEN 2 AND 30"):
            pages = [r[0] for r in idx.execute(
                "SELECT DISTINCT page FROM page_entities WHERE entity_id=?",
                (eid,))]
            for a, b in itertools.combinations(pages, 2):
                add_edge(a, b, W["inferred"] * 0.5)
        return adjacency

    def _store_bridges(self, idx, adjacency) -> int:
        """Persistência 0-dim: as pontes mais frágeis entre blocos reais.

        Poda embutida: `adjacency` já não contém página fora do índice nem
        `communities/`, então uma ponte só sobrevive se os DOIS endpoints
        ainda existem no grafo. A poda explícita de endpoint supersedido
        fica no `_prune_bridges`, porque supersedida CONTINUA no índice."""
        edges = [(a, b, w) for a, neighbors in adjacency.items()
                 for b, w in neighbors.items() if a < b]
        idx.execute("DELETE FROM graph_bridges")
        gravadas = 0
        for event in fragile_bridges(edges, limit=10):
            # D-I: colunas NOMEADAS — `VALUES (?,?,?,?,?)` posicional quebra
            # no instante em que o carimbo acrescenta coluna
            idx.execute(
                "INSERT OR REPLACE INTO graph_bridges"
                "(src, dst, weight, small_side, large_side) VALUES (?,?,?,?,?)",
                (event.src, event.dst, event.weight,
                 event.small_side, event.large_side))
            gravadas += 1
        gravadas -= self._prune_bridges(idx)
        idx.commit()
        return gravadas

    @staticmethod
    def _prune_bridges(idx) -> int:
        """Ponte com endpoint SUPERSEDIDO é ponte para lugar nenhum.

        Supersedida continua no índice (invalidar-nunca-apagar), então não
        cai pela construção do grafo — e a fila do cockpit põe ponte frágil
        entre os itens de maior densidade valor/custo. Oferecer "reforce
        este fio" apontando para página aposentada gasta a atenção que a
        fila existe para economizar."""
        # a autoridade de "supersedida" no índice é `chunks.superseded`
        # (INV-003) — não existe tabela de páginas
        cur = idx.execute(
            "DELETE FROM graph_bridges WHERE src IN "
            "(SELECT DISTINCT page FROM chunks WHERE superseded=1) "
            "OR dst IN "
            "(SELECT DISTINCT page FROM chunks WHERE superseded=1)")
        return max(cur.rowcount, 0)

    def _partition(self, adjacency) -> tuple[dict[str, int], str, int]:
        # exclusão de super-hubs (p99 de grau) antes do particionamento
        degrees = sorted(len(nb) for nb in adjacency.values())
        hubs: set[str] = set()
        if degrees:
            p99 = degrees[int(0.99 * (len(degrees) - 1))]
            hubs = {n for n, nb in adjacency.items() if len(nb) > max(p99, 8)}
        core = {n: {m: w for m, w in nb.items() if m not in hubs}
                for n, nb in sorted(adjacency.items()) if n not in hubs}
        communities, backend = self._leiden_or_components(core)
        for hub in sorted(hubs):                       # atribuição pós-hoc
            neighborhood = sorted(communities[x] for x in adjacency[hub]
                                  if communities.get(x) is not None)
            # empate resolvido pelo MENOR rótulo (`max` por contagem sozinho
            # depende da ordem de `set`, que varia entre processos)
            communities[hub] = (max(set(neighborhood),
                                    key=lambda c: (neighborhood.count(c), -c))
                                if neighborhood else -1)
        return self._canonical(communities), backend, len(hubs)

    @staticmethod
    def _canonical(communities: dict[str, int]) -> dict[str, int]:
        """Renumera as comunidades pelo MENOR membro, em ordem.

        Medido antes desta mudança: em três execuções sobre o mesmo bundle o
        AGRUPAMENTO se manteve e o rótulo inteiro trocou nas três — então
        `communities` mudava sem o conhecimento ter mudado, e qualquer
        comparação entre execuções (a F2-PR2 vive disso) comparava ruído.
        O rótulo não tem semântica: quem a dará é o `theme_id` (D-K)."""
        membros: dict[int, list[str]] = defaultdict(list)
        for page, cid in communities.items():
            membros[cid].append(page)
        ordem = sorted((min(paginas), cid)
                       for cid, paginas in membros.items() if cid >= 0)
        novo = {cid: i for i, (_, cid) in enumerate(ordem)}
        return {page: (novo[cid] if cid >= 0 else -1)
                for page, cid in sorted(communities.items())}

    @staticmethod
    def _leiden_or_components(core) -> tuple[dict[str, int], str]:
        try:
            import igraph, leidenalg                   # noqa: F401  extra [ml]
            edges, weights = [], []
            for a in core:
                for b, w in sorted(core[a].items()):
                    if a < b:
                        edges.append((a, b))
                        weights.append(w)
            g = igraph.Graph.TupleList(edges)
            # `seed` e ordem canônica pagam por coisas DIFERENTES, medido:
            # com ordem variável, `seed` sozinho ainda deu 6 partições
            # distintas em 8 execuções; com ordem canônica e sem `seed`, deu 1
            # — mas só dentro do mesmo `PYTHONHASHSEED`. Em 4 processos com
            # hash aleatório, o sem-seed divergiu. Precisa dos dois.
            part = leidenalg.find_partition(
                g, leidenalg.ModularityVertexPartition, weights=weights,
                seed=LEIDEN_SEED)
            return ({g.vs[v]["name"]: i
                     for i, c in enumerate(part) for v in c}, "leiden")
        except ImportError:
            communities: dict[str, int] = {}
            next_id = 0
            for start in core:
                if start in communities:
                    continue
                stack = [start]
                while stack:
                    node = stack.pop()
                    if node in communities:
                        continue
                    communities[node] = next_id
                    stack.extend(sorted((x for x in core[node]
                                         if x not in communities),
                                        reverse=True))
                next_id += 1
            return communities, "components"

    # ----------------------------------------------------------- sumários
    def _write_summaries(self, adjacency, communities, idx=None) -> int:
        members_by_community: dict[int, list[str]] = defaultdict(list)
        for page, community in communities.items():
            if community >= 0 and not page.startswith("communities/"):
                members_by_community[community].append(page)
        written = 0
        for community, members in members_by_community.items():
            if len(members) < 2:
                continue
            top = sorted(members, key=lambda p: -sum(
                adjacency[p].values()) if p in adjacency else 0)[:8]
            titles = [(p, p.rsplit("/", 1)[-1][:-3].replace("-", " "))
                      for p in top]
            label, summary = self._label(titles)
            fingerprint = hashlib.sha256(
                "\n".join(sorted(members)).encode()).hexdigest()
            tema = getattr(self, "_temas", {}).get(frozenset(members))
            if tema is None:            # sem casamento (backend trocou): id novo
                from ..kernel.themes import theme_id as _tid
                tema = _tid(set(members))
            _CommunitySummaryPage(self._settings, label, summary,
                                  titles, fingerprint, tema).execute()
            written += 1
        return written

    def _label(self, titles: list[tuple[str, str]]) -> tuple[str, str]:
        label = titles[0][1]
        summary = "Tema comum: " + ", ".join(t for _, t in titles[:4]) + "."
        try:
            r = self._router.complete(
                "Nomeie em 2-4 palavras e resuma em 3 frases o tema comum "
                "destas páginas (responda 'ROTULO: ...\nRESUMO: ...'):\n"
                + "\n".join(f"- {t}" for _, t in titles),
                privacy="local_only", max_tokens=160)
            found = re.search(r"ROTULO:\s*(.+)", r["text"])
            found_summary = re.search(r"RESUMO:\s*(.+)", r["text"], re.S)
            if found:
                label = found.group(1).strip()[:60]
            if found_summary:
                summary = found_summary.group(1).strip()[:800]
        except (ModelUnavailable, Exception):
            pass
        return label, summary
