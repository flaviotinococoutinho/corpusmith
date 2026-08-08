"""Veredito e vitalidade — F3-PR2 / P-3.

*"Nada fecha e nada aposenta"* é como `docs/14` nomeia o problema, e cada
palavra é literal. Reproduzido nesta árvore antes da correção:

    review_items -> ['concepts/apagada.md', 'concepts/morta.md',
                     'concepts/viva.md']

`morta.md` tinha `superseded_by` — aposentada por um ato humano explícito — e
`apagada.md` **nunca existiu no bundle**: `page_heat` guarda uso por caminho e
nenhuma fonte o confrontava com a autoridade. Uma pergunta respondida também
não tinha como sair: `type: question` valia 0.9 na fila e voltava ao topo
todo dia, para sempre.

Os testes abaixo cobrem os três níveis do P-3: veredito sobre objeto canônico
(A), veredito sobre padrão computado (B) e o filtro de vitalidade (C).
"""
from __future__ import annotations
import time
import pytest
from llmwiki.harness.local_policy import check_corpus
from llmwiki.harness.runner import HarnessRejection
from llmwiki.kernel.vitality import aposentada, vivas
from llmwiki.kernel.verdicts import pattern_key, suprime, Verdict
from llmwiki.okf.bundle import BundleReader
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.verdicts import load, record, suppressed_keys
from llmwiki.usecases.curate import CloseQuestion
from llmwiki.usecases.next_actions import bridge_items, contradiction_items
from llmwiki.usecases.plan_attention import gap_items, review_items


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _write(settings, kb, *docs, kind="Creation"):
    BundleWriter(kb).write(list(docs), log_kind=kind, log_message="m",
                           commit_message="c")
    rebuild_index(settings)


def _aquece(settings, *paths, uses=5):
    """Histórico de uso, como o produto acumula ao ler páginas."""
    rt = connect(settings.app_support / "runtime.db")
    agora = time.time()
    for p in paths:
        rt.execute("INSERT OR REPLACE INTO page_heat"
                   "(path, reads, cites, last_seen, first_seen) "
                   "VALUES (?,?,?,?,?)",
                   (p, uses, 2, agora, agora - 86400 * 30))
    rt.commit()
    rt.close()


# ======================================================== (C) vitalidade
def test_kernel_nomeia_o_motivo_em_vez_de_devolver_booleano():
    """A fila precisa DIZER por que não propôs — "sumiu da lista" sem
    explicação é indistinguível de defeito, e foi assim que a ausência do
    filtro passou despercebida por versões."""
    assert aposentada({"superseded_by": "concepts/nova.md"}) == "superseded_by"
    assert aposentada({"invalid_at": "2020-01-01"}) == "invalid_at"
    assert aposentada({"title": "viva"}) is None
    assert vivas({"a.md": {}, "b.md": {"superseded_by": "a.md"}}) == {"a.md"}


def test_a_fila_para_de_propor_pagina_aposentada_e_inexistente(settings, kb):
    """A reprodução exata do defeito, agora com o desfecho novo.

    Falsificável — sem `filtrar(...)` em `review_items`, os três voltam."""
    _write(settings, kb,
           _doc("concepts/viva.md", "Viva", "# Viva\n\ntexto sobre docker."),
           _doc("concepts/morta.md", "Morta", "# Morta\n\noutro texto.",
                superseded_by="concepts/viva.md"))
    _aquece(settings, "concepts/viva.md", "concepts/morta.md",
            "concepts/apagada.md")
    alvos = {i["target"] for i in review_items(settings)}
    assert alvos == {"concepts/viva.md"}, alvos


def test_pergunta_fechada_sai_da_fila(settings, kb):
    """`type: question` valia 0.9 — o item de maior valor depois da
    contradição — e não havia gesto que a tirasse de lá."""
    _write(settings, kb,
           _doc("concepts/resposta.md", "Resposta",
                "# Resposta\n\nRust calcula, Python decide."),
           _doc("questions/q1.md", "Como dividir Rust e Python?",
                "# Pergunta\n\nQual camada faz o quê?", type="question"))
    assert {i["target"] for i in gap_items(settings)} == {"questions/q1.md"}
    _write(settings, kb,
           _doc("questions/q1.md", "Como dividir Rust e Python?",
                "# Pergunta\n\nQual camada faz o quê?", type="question",
                answered_by="concepts/resposta.md"), kind="Update")
    assert gap_items(settings) == []


def test_ponte_com_ponta_morta_nao_e_proposta(settings, kb):
    """A ponte liga DUAS páginas: com uma ponta aposentada, o item pede
    para linkar um endereço que já não aceita trabalho."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\ntexto."),
           _doc("concepts/b.md", "B", "# B\n\ntexto."),
           _doc("concepts/c.md", "C", "# C\n\ntexto.",
                superseded_by="concepts/a.md"))
    idx = connect(settings.app_support / "index.db")
    for src, dst in (("concepts/a.md", "concepts/b.md"),
                     ("concepts/a.md", "concepts/c.md")):
        idx.execute("INSERT OR REPLACE INTO graph_bridges VALUES (?,?,?,?,?)",
                    (src, dst, 0.15, 4, 9))
    idx.commit()
    idx.close()
    alvos = {(i["action"]["src"], i["action"]["dst"])
             for i in bridge_items(settings)}
    assert alvos == {("concepts/a.md", "concepts/b.md")}


# =================================================== (B) padrão computado
def test_a_chave_sai_da_evidencia_canonica_nao_da_epoca():
    """`community` é um inteiro de ÉPOCA — muda a cada Leiden, e um veredito
    chaveado por ele suprimiria um padrão diferente na semana seguinte. A
    chave sai dos rel_paths, ordenados: A↔B é o mesmo padrão que B↔A."""
    assert pattern_key(["b.md", "a.md"]) == pattern_key(["a.md", "b.md"])
    assert pattern_key(["a.md", "a.md"]) == pattern_key(["a.md"])
    assert pattern_key(["a.md", "b.md"]) != pattern_key(["a.md", "c.md"])


def test_rejeitar_suprime_e_aceitar_nao():
    """Aceitar uma ponte é motivo para AGIR sobre ela, não para escondê-la —
    quem a tira da fila é o ato de link, não o juízo."""
    agora = 1_000.0
    def v(status, until=None):
        return Verdict("bridge", "k", status, until, ("a.md",))
    assert suprime(v("rejected"), agora) is True
    assert suprime(v("deferred", until=agora + 10), agora) is True
    assert suprime(v("deferred", until=agora - 10), agora) is False  # venceu
    assert suprime(v("accepted"), agora) is False


def test_veredito_sobrevive_a_recomputacao_do_padrao(settings, kb):
    """O motivo de morar em `runtime.db` e não em `index.db`: o job recria
    `graph_bridges` do zero, e um veredito guardado lá seria apagado pela
    própria recomputação que ele existe para calar.

    Falsificável — mover a tabela para `index.db` faz esta asserção cair."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\ntexto."),
           _doc("concepts/b.md", "B", "# B\n\ntexto."))
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT OR REPLACE INTO graph_bridges VALUES (?,?,?,?,?)",
                ("concepts/a.md", "concepts/b.md", 0.15, 4, 9))
    idx.commit()
    idx.close()
    assert len(bridge_items(settings)) == 1
    record(settings, "bridge", ["concepts/a.md", "concepts/b.md"], "rejected",
           note="não vale a pena")
    assert bridge_items(settings) == []
    # a recomputação que apagaria um veredito guardado na projeção
    (settings.app_support / "index.db").unlink()
    rebuild_index(settings)
    assert suppressed_keys(settings, "bridge"), (
        "o juízo humano morreu junto com a projeção")


def test_until_devolve_o_item_quando_vence(settings, kb):
    """Adiar não é rejeitar para sempre: o `until` é a supressão com prazo
    declarado, e o item VOLTA — senão "vejo depois" viraria "nunca mais"."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\ntexto."),
           _doc("concepts/b.md", "B", "# B\n\ntexto."))
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT OR REPLACE INTO graph_bridges VALUES (?,?,?,?,?)",
                ("concepts/a.md", "concepts/b.md", 0.15, 4, 9))
    idx.commit()
    idx.close()
    record(settings, "bridge", ["concepts/a.md", "concepts/b.md"], "deferred",
           until=time.time() - 1)
    assert len(bridge_items(settings)) == 1, "o prazo venceu — deve voltar"
    record(settings, "bridge", ["concepts/a.md", "concepts/b.md"], "deferred",
           until=time.time() + 3600)
    assert bridge_items(settings) == []


def test_status_fora_do_vocabulario_e_recusado(settings):
    with pytest.raises(ValueError, match="status inválido"):
        record(settings, "bridge", ["a.md"], "talvez")


def test_veredito_e_idempotente_por_chave(settings):
    record(settings, "bridge", ["a.md", "b.md"], "deferred", until=1.0)
    record(settings, "bridge", ["b.md", "a.md"], "rejected")
    guardados = load(settings, "bridge")
    assert len(guardados) == 1
    assert guardados[0].status == "rejected" and guardados[0].until is None


def test_contradicao_rejeitada_para_de_voltar(settings, kb):
    """A contradição é o item de maior VoI (0.85): sem poder dizer "já
    olhei, é falso positivo", ela volta ao topo toda vez e ensina o usuário
    a ignorar a fila inteira."""
    doi = "10.1000/xyz123"
    _write(settings, kb,
           _doc("concepts/p1.md", "P1", f"# P1\n\nEstudo com DOI {doi}."),
           _doc("concepts/p2.md", "P2", f"# P2\n\nOutra com o DOI {doi}."))
    itens = contradiction_items(settings)
    assert itens, "fixture inútil: nenhuma contradição detectada"
    record(settings, "contradiction", itens[0]["action"]["pages"], "rejected")
    assert contradiction_items(settings) == []


# ============================ (A) veredito sobre o canônico + sucessor
def test_fechar_pergunta_escreve_no_canonico(settings, kb):
    """O veredito é CONTEÚDO: vai ao frontmatter, versionado em Git e
    sujeito ao Harness — não a uma tabela que o rebuild apagaria."""
    _write(settings, kb,
           _doc("concepts/resposta.md", "Rust e Python",
                "# Resposta\n\nRust calcula sinais; Python decide."),
           _doc("questions/q1.md", "Rust e Python",
                "# Pergunta\n\nQual camada faz o quê?", type="question"))
    ato = CloseQuestion(settings, page="questions/q1.md",
                        answered_by="concepts/resposta.md", force=True)
    resultado = ato.execute()
    assert resultado["pages"] == ["questions/q1.md"]
    meta = BundleReader(kb / "bundle").load("questions/q1.md").meta
    assert meta.answered_by == "concepts/resposta.md"
    assert meta.resolved_at is not None


def test_fechar_passa_sem_force_quando_o_vinculo_se_sustenta(settings, kb):
    """O outro lado da guarda, e o que a impede de ser um bloqueio universal:
    quando o produto DE FATO chega à resposta, fechar não pede força.

    Sem este teste, uma guarda que recusasse tudo passaria despercebida —
    todos os outros testes usam `force=True`."""
    _write(settings, kb,
           _doc("concepts/homologia.md", "Homologia persistente em grafos",
                "# Homologia persistente\n\nA homologia persistente em "
                "grafos densos mede quantos buracos sobrevivem à filtração."),
           _doc("questions/q4.md", "Homologia persistente em grafos",
                "# Pergunta\n\nComo a homologia persistente se comporta "
                "em grafos densos?", type="question"))
    preview = CloseQuestion(settings, page="questions/q4.md",
                            answered_by="concepts/homologia.md"
                            ).execute(dry_run=True)["preview"]
    assert "verificado" in preview["note"]
    assert "FORÇA" not in preview["note"]


def test_fechar_recusa_quando_o_vinculo_nao_se_sustenta(settings, kb):
    """A verificação é GUARDA, não automatismo.

    A primeira versão desta guarda checava `abstained` e era TEATRO: medido,
    com `abstain_threshold=0.0` a abstenção quase nunca dispara, e perguntar
    o título de uma pergunta encontra a PRÓPRIA pergunta (uma página do
    bundle). Passava apontando para uma página de culinária. O que se
    verifica é o vínculo: perguntado o título, o produto chega à página
    declarada como resposta?"""
    _write(settings, kb,
           _doc("concepts/nada-a-ver.md", "Culinária",
                "# Culinária\n\nBolo de fubá com queijo."),
           _doc("questions/q2.md", "Topologia algébrica em grafos densos",
                "# Pergunta\n\nComo a homologia persistente se comporta?",
                type="question"))
    ato = CloseQuestion(settings, page="questions/q2.md",
                        answered_by="concepts/nada-a-ver.md")
    with pytest.raises(ValueError, match="vínculo não se sustenta"):
        ato.execute(dry_run=True)
    forcado = CloseQuestion(settings, page="questions/q2.md",
                            answered_by="concepts/nada-a-ver.md", force=True)
    preview = forcado.execute(dry_run=True)["preview"]
    assert "FORÇA" in preview["note"]


def test_fechar_apontando_para_pagina_inexistente_e_recusado(settings, kb):
    _write(settings, kb,
           _doc("questions/q3.md", "Q3", "# Q\n\ntexto.", type="question"))
    ato = CloseQuestion(settings, page="questions/q3.md",
                        answered_by="concepts/nunca-existiu.md")
    with pytest.raises(ValueError, match="não existe no bundle"):
        ato.execute(dry_run=True)


def test_sucessor_pendurado_e_rejeitado_pelo_gate(settings, kb):
    """`policy.dangling_successor` não existia nem para `superseded_by`, que
    está no produto desde a v0.8: dava para aposentar uma página apontando
    para o vazio — ela saía da fila sem sucessora real."""
    writer = BundleWriter(settings.path("knowledge"))
    doc = _doc("concepts/orfa.md", "Órfã", "# Órfã\n\ntexto.",
               superseded_by="concepts/fantasma.md")
    with pytest.raises(HarnessRejection) as exc:
        writer.write([doc], log_kind="Creation", log_message="m",
                     commit_message="c")
    assert any(f.rule == "policy.dangling_successor"
               for f in exc.value.findings.errors())


def test_sucessora_escrita_no_mesmo_lote_e_valida(settings, kb):
    """A fusão escreve sucessora e aposentada no MESMO `write` — olhar só o
    disco reprovaria um ato legítimo."""
    writer = BundleWriter(settings.path("knowledge"))
    writer.write(
        [_doc("concepts/nova.md", "Nova", "# Nova\n\ntexto."),
         _doc("concepts/velha.md", "Velha", "# Velha\n\ntexto.",
              superseded_by="concepts/nova.md")],
        log_kind="Creation", log_message="m", commit_message="c")
    assert (kb / "bundle" / "concepts" / "velha.md").exists()


# ================================ a dívida do ADR-41.5, paga (docs/17)
def test_sucessao_resolve_o_bloco_e_nao_o_grupo(settings, kb):
    """`check_corpus` marcava o grupo INTEIRO como resolvido assim que UMA
    sucessão aparecesse. Com A, B e C no mesmo DOI, fundir A em B calava
    também o par (B, C) — item de VoI 0.85 saindo da fila sem tratamento.

    Falsificável — com o `any(...)` de volta, `restantes` fica vazio."""
    doi = "10.1000/abc999"
    _write(settings, kb,
           _doc("concepts/a.md", "A", f"# A\n\nDOI {doi}."),
           _doc("concepts/b.md", "B", f"# B\n\nDOI {doi}."),
           _doc("concepts/c.md", "C", f"# C\n\nDOI {doi}."))
    reader = BundleReader(kb / "bundle")
    assert check_corpus(list(reader.iter_concepts()), reader), "fixture inútil"
    _write(settings, kb,
           _doc("concepts/b.md", "B", f"# B\n\nDOI {doi}.",
                superseded_by="concepts/a.md"), kind="Update")
    reader = BundleReader(kb / "bundle")
    restantes = check_corpus(list(reader.iter_concepts()), reader)
    assert restantes, "a convivência com C não foi tratada e sumiu do radar"
    assert "concepts/c.md" in restantes[0].meta["pages"]


def test_invalid_at_tira_a_pagina_do_grupo(settings, kb):
    """Uma página que declarou não valer mais não contradiz ninguém."""
    doi = "10.1000/def888"
    _write(settings, kb,
           _doc("concepts/x.md", "X", f"# X\n\nDOI {doi}."),
           _doc("concepts/y.md", "Y", f"# Y\n\nDOI {doi}.",
                invalid_at="2020-01-01T00:00:00Z"))
    reader = BundleReader(kb / "bundle")
    assert check_corpus(list(reader.iter_concepts()), reader) == []
