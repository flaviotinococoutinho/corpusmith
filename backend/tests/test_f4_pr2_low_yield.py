"""F4-PR2 (ADR-52, P-5) — o produto para de chamar beco de disputa.

`page_overlay.status = 'contested'` deriva de DESFECHO DE USO (dead_end
repetido) e cinco superfícies o exibiam como conflito factual. O valor,
as chaves e os rótulos viram `low_yield`; o conflito REAL chega na
F4-PR3 (`policy.factual_conflict`).

**O-6 (medido depois do RFC-004)**: o renomeio ficou INCOMPLETO em três
superfícies, e o guarda desta suíte não pegou porque só cobria UMA
(`gap_items`). As que faltavam:

    usecases/cognitive_journey.py:537   sinal literal "contested" na API
    cognitive/scoring.py:66             "⚔ contestada … há disputa aberta"
    epistemics.toml:382                 prosa "contestada 0.8" no contrato

Ficou perigoso quando o ADR-54 deu à palavra um SEGUNDO dono:
`resolution_status = contested` significa divergência factual aberta.
Enquanto a API emitisse os dois sentidos sob o mesmo nome, nenhum
consumidor podia distingui-los — e um `grep` cego destruiria o
vocabulário novo. Os testes abaixo travam as três saídas, uma a uma."""
from __future__ import annotations
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _write(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def test_overlay_aceita_low_yield_e_recusa_contested(settings):
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO page_overlay(page, status) "
                "VALUES ('concepts/a.md', 'low_yield')")
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        idx.execute("INSERT INTO page_overlay(page, status) "
                    "VALUES ('concepts/b.md', 'contested')")
    idx.close()


def test_migracao_converte_contested_legado(settings, tmp_path):
    """Banco antigo com 'contested' abre no produto novo com o valor
    migrado — sem isso, todo index.db existente quebraria no CHECK."""
    import sqlite3
    from corpusmith.runtime.db import SCHEMA_VERSIONS, reset_initialized
    db = settings.app_support / "index.db"
    connect(db).close()                    # inicializa o banco do produto
    # simula o banco da versão anterior: sem CHECK novo, valor antigo
    raw = sqlite3.connect(db)
    raw.executescript(
        "DROP TABLE IF EXISTS page_overlay;"
        "CREATE TABLE page_overlay("
        "  page TEXT PRIMARY KEY,"
        "  status TEXT CHECK(status IN ('preferred','tentative','contested')),"
        "  useful INTEGER DEFAULT 0, dead INTEGER DEFAULT 0, updated REAL);"
        "INSERT INTO page_overlay(page, status) "
        "  VALUES ('concepts/velha.md', 'contested');")
    raw.execute("UPDATE _meta SET value=? WHERE key='schema_version'",
                (str(SCHEMA_VERSIONS["index.db"] - 1),))
    raw.commit(); raw.close()
    reset_initialized()
    idx = connect(db)
    row = idx.execute("SELECT status FROM page_overlay "
                      "WHERE page='concepts/velha.md'").fetchone()
    idx.close()
    assert row["status"] == "low_yield"


def test_fila_oferece_low_yield_com_rotulo_honesto(settings, kb):
    from corpusmith.usecases.plan_attention import gap_items
    _write(settings, kb,
           _doc("concepts/beco.md", "Beco", "# Beco\n\nsempre dá em nada."))
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO page_overlay(page, status) "
                "VALUES ('concepts/beco.md', 'low_yield')")
    idx.commit(); idx.close()
    items = [i for i in gap_items(settings)
             if i["target"] == "concepts/beco.md"]
    assert items and items[0]["kind"] == "low_yield"
    razao = items[0]["reason"].lower()
    assert "disputa" not in razao and "contestada" not in razao
    assert "beco" in razao or "rendimento" in razao


def test_politica_cognitiva_aceita_chave_legada(settings):
    """`allow_contested` vive em snapshots PERSISTIDOS (cognitive.db).
    A chave nova governa; a legada é traduzida, nunca recusada."""
    from corpusmith.cognitive.policy import validate_policy
    p = validate_policy({"gates": {"allow_contested": False}})
    assert p["gates"]["allow_low_yield"] is False
    p2 = validate_policy({"gates": {"allow_low_yield": True}})
    assert p2["gates"]["allow_low_yield"] is True


# =================================================== O-6: as três que faltavam
def test_projecao_de_curadoria_emite_low_yield_e_nunca_contested(settings, kb):
    """O-6, sítio 1 — `GET /cognitive/curation`.

    Medido ANTES: `signals == ["contested"]`. A coluna já era `low_yield`
    (F4-PR2 migrou o índice), mas o SINAL publicado ainda era `contested`,
    que a partir do ADR-54 significa outra coisa.

    Falsificável: devolvendo `("contested", 0.8)` a `cognitive_journey.py`,
    as duas asserções reprovam."""
    from corpusmith.usecases.cognitive_journey import curation_projection
    _write(settings, kb,
           _doc("concepts/beco.md", "Beco", "# Beco\n\nsempre dá em nada."))
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO page_overlay(page, status) "
                "VALUES ('concepts/beco.md', 'low_yield')")
    idx.commit(); idx.close()
    item = next(i for i in curation_projection(settings)["items"]
                if i["page"] == "concepts/beco.md")
    assert "low_yield" in item["signals"]
    # `contested` é do eixo resolution_status (ADR-54) e NÃO tem nada a ver
    # com desfecho de uso — a API não pode publicar os dois sob um nome só
    assert "contested" not in item["signals"]
    assert "contested" not in item["reason"]


def test_razao_cognitiva_de_low_yield_nao_alega_disputa():
    """O-6, sítio 2 — a linha de UI de `cognitive/scoring.py`.

    Medido ANTES: "⚔ contestada no canônico — há disputa aberta". O campo
    já era `view.low_yield`; o TEXTO seguia alegando disputa factual sobre
    o que é apenas desfecho de uso (ADR-52 §P-5).

    Falsificável: restaurando aquela frase, `"disputa" not in razao` reprova.
    A asserção é sobre a SAÍDA (a razão que o curador lê), não sobre o
    fonte — verificar o fonte deixaria passar um rótulo montado noutro
    lugar."""
    from corpusmith.cognitive import KnowledgeItemView, validate_policy
    from corpusmith.cognitive.model import new_focus_goal
    from corpusmith.cognitive.scoring import cognitive_priority
    goal = new_focus_goal(goal_id="g", title="t", root="concepts/r.md",
                          depth_desired={"conceptual": 2})
    item = cognitive_priority(
        KnowledgeItemView(page="concepts/beco.md", distance=1,
                          low_yield=True),
        goal, validate_policy({}))
    razao = " ".join(item.reasons).lower()
    assert "disputa" not in razao and "contestada" not in razao, \
        "a razão de low_yield voltou a alegar disputa factual"
    assert "beco" in razao or "rendimento" in razao


def test_contrato_da_fila_nao_chama_baixo_rendimento_de_contestada():
    """O-6, sítio 3 — a PROSA de `epistemics.toml` (contrato legível por
    máquina) ainda dizia "contestada 0.8" enquanto o parâmetro logo abaixo
    já se chamava `value_low_yield`.

    Falsificável: devolvendo a palavra à linha de inductive_biases, reprova.
    Cobre TODO o contrato, não só aquela linha — o vocabulário do eixo
    `resolution_status` mora em `ontology.toml`, nunca aqui."""
    from corpusmith.harness.epistemics import load_registry
    registry, _ = load_registry()
    fila = registry.get("attention_queue")
    prosa = " ".join([*(b.text for b in fila.inductive_biases),
                      *(a.text for a in fila.assumptions),
                      *(m.text for m in fila.known_failure_modes),
                      *fila.misinterpretations]).lower()
    assert "contestada" not in prosa and "contested" not in prosa
    # e o valor continua declarado, só que pelo nome certo
    assert float(dict(fila.parameters)["value_low_yield"]) == 0.8
