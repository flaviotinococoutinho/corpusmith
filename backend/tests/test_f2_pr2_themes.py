"""F2-PR2 (RFC-001, docs/16) — identidade de tema por casamento de partições.

O problema é MEDIDO, não previsto: um tema de 5 páginas cuja página mais
conectada troca passa a ter **duas páginas canônicas**, nenhuma supersedida —
o produto fabricando a contradição que `policy.contradiction_candidate` existe
para acusar. `test_o_mesmo_tema_nao_gera_duas_paginas_vivas` é a negação disso.

Os limiares e o vocabulário vêm da calibração do RFC (§2.2), e dois resultados
dela mudaram o desenho e por isso viram teste:

1. **τ = 0,5 seria o pior valor possível** — é exatamente o Jaccard de um tema
   que DOBRA (crescimento legítimo) e de um tema que PARTE em dois. `TAU = 1/3`
   é o ponto médio da banda vazia medida entre 0,17 e 0,50;
2. **o valor do Jaccard não distingue `split` de `grew`** (0,50 nos dois). Quem
   distingue é a FORMA do casamento — e os testes abaixo usam exatamente os
   números medidos, não números convenientes.
"""
from __future__ import annotations
import json
import pytest
from corpusmith.kernel.themes import EVENTS, TAU, ThemeEvent, jaccard, match
from corpusmith.kernel.themes import theme_id as tid_de
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import SCHEMA_VERSIONS, connect
from corpusmith.usecases.detect_communities import DetectCommunities


def _pgs(prefixo: str, n: int, inicio: int = 0) -> set[str]:
    return {f"concepts/{prefixo}-{i}.md" for i in range(inicio, inicio + n)}


# ==================================== o limiar, e por que não é 0,5
def test_tau_esta_na_banda_vazia_medida():
    """Estritamente abaixo de 0,5 (senão um tema que dobra vira died+born) e
    estritamente acima de 0,17 (senão um tema que dissolve vira grew)."""
    assert 0.17 < TAU < 0.5


def test_tema_que_dobra_continua_o_mesmo_tema():
    """Medido: Jaccard 0,50. Com τ = 0,5 isso passaria raspando; com 1/3
    passa com folga, que é o ponto."""
    antes = {"thm_a": _pgs("alfa", 6)}
    depois = [_pgs("alfa", 12)]
    assert jaccard(antes["thm_a"], depois[0]) == pytest.approx(0.5)
    ev = match(antes, depois)
    assert [e.event for e in ev] == ["grew"]
    assert ev[0].theme_id == "thm_a", "a identidade tem de sobreviver ao grew"


def test_tema_que_dissolve_morre_em_vez_de_crescer():
    """Medido: Jaccard 0,17 quando as páginas migram para outros temas."""
    antes = {"thm_a": _pgs("alfa", 6)}
    depois = [_pgs("alfa", 1) | _pgs("beta", 5)]
    assert jaccard(antes["thm_a"], depois[0]) < TAU
    eventos = {e.event for e in match(antes, depois)}
    assert eventos == {"died", "born"}


# ==================================== a forma, não o valor
def test_split_e_reconhecido_pela_forma_nao_pelo_jaccard():
    """O achado que mudou o desenho: split e crescimento legítimo têm o MESMO
    Jaccard (0,50 medido). Uma antiga casando com DUAS novas é o que distingue."""
    antes = {"thm_a": _pgs("alfa", 6)}
    metade_a, metade_b = _pgs("alfa", 3), _pgs("alfa", 3, inicio=3)
    assert jaccard(antes["thm_a"], metade_a) == pytest.approx(0.5)
    assert jaccard(antes["thm_a"], metade_b) == pytest.approx(0.5)
    ev = match(antes, [metade_a, metade_b])
    tipos = [e.event for e in ev]
    assert tipos[0] == "split", tipos
    assert tipos.count("born") == 2, "cada metade nasce com id próprio"
    mae = ev[0]
    assert sorted(mae.related) == sorted(e.theme_id for e in ev[1:])
    # as filhas NÃO herdam o id: duas metades não são "o mesmo tema que antes"
    assert all(e.theme_id != "thm_a" for e in ev[1:])
    # e cada filha aponta para a mãe
    assert all(e.related == ["thm_a"] for e in ev[1:])


def test_merged_herda_o_id_da_de_maior_intersecao():
    """Ramo DECLARADO e não observado na calibração (RFC §2.3): modularidade
    resiste a fundir cliques densos. Existe porque a forma 2→1 é bem definida,
    e é testado para não apodrecer — mas nenhuma interface o pressupõe.

    Os tamanhos aqui são COMPARÁVEIS (6 e 5) por uma razão que o teste seguinte
    documenta: com tamanhos desiguais o menor cai abaixo de τ e a forma deixa
    de ser 2→1."""
    a, b = _pgs("alfa", 6), _pgs("beta", 5)
    antes = {"thm_a": a, "thm_b": b}
    uniao = a | b
    assert jaccard(a, uniao) >= TAU and jaccard(b, uniao) >= TAU
    ev = match(antes, [uniao])
    por_tipo = {e.event: e for e in ev}
    assert set(por_tipo) == {"merged", "died"}
    assert por_tipo["merged"].theme_id == "thm_a", "herda o de maior interseção"
    assert por_tipo["died"].theme_id == "thm_b"
    assert por_tipo["died"].related == ["thm_a"]


def test_fusao_assimetrica_le_como_crescimento_e_morte():
    """Propriedade MEDIDA do desenho, não defeito: quando um tema grande
    absorve um pequeno (8 e 3), o pequeno tem Jaccard 3/11 = 0,27 com a união
    — abaixo de τ. A forma não é 2→1, então o evento é `grew` no grande e
    `died` no pequeno.

    Isso é a leitura mais honesta disponível: com 27% de sobreposição, dizer
    "estes dois temas se fundiram" afirmaria continuidade que o dado não
    sustenta. E reforça o RFC §2.3 — `merged` é ainda mais raro do que a
    calibração sugeria."""
    grande, pequeno = _pgs("alfa", 8), _pgs("beta", 3)
    uniao = grande | pequeno
    assert jaccard(pequeno, uniao) < TAU
    ev = {e.event: e.theme_id
          for e in match({"thm_g": grande, "thm_p": pequeno}, [uniao])}
    assert ev == {"grew": "thm_g", "died": "thm_p"}


def test_tema_novo_nasce_sem_tocar_os_antigos():
    antes = {"thm_a": _pgs("alfa", 6)}
    ev = match(antes, [_pgs("alfa", 6), _pgs("delta", 5)])
    assert [e.event for e in ev] == ["born"], "o antigo, intocado, não vira época"
    assert ev[0].members == _pgs("delta", 5)


def test_particao_identica_nao_gera_epoca():
    """Sem isto, cada execução do job registraria uma época por tema e a
    trilha viraria ruído — a mesma armadilha do rótulo que trocava a cada
    execução (ADR-43)."""
    antes = {"thm_a": _pgs("alfa", 6), "thm_b": _pgs("beta", 4)}
    assert match(antes, [_pgs("alfa", 6), _pgs("beta", 4)]) == []


def test_primeira_execucao_e_tudo_born():
    ev = match({}, [_pgs("alfa", 3), _pgs("beta", 3)])
    assert [e.event for e in ev] == ["born", "born"]


def test_particao_vazia_nao_mata_nada_sem_motivo():
    """Bundle sem aresta ⇒ partição vazia. Isso NÃO é o mundo dizendo que
    todos os temas morreram — mas o casamento não tem como saber, então o
    chamador é que recusa. Aqui só se fixa o comportamento puro."""
    assert [e.event for e in match({"thm_a": _pgs("alfa", 3)}, [])] == ["died"]


# ==================================== o id é opaco e estável
def test_id_e_deterministico_e_independente_da_ordem():
    a = tid_de({"concepts/x.md", "concepts/y.md"})
    b = tid_de({"concepts/y.md", "concepts/x.md"})
    assert a == b and a.startswith("thm_") and len(a) == 16


def test_id_nao_muda_quando_o_tema_cresce():
    """A razão de o id ser atribuído no NASCIMENTO: derivado da composição
    vigente, ele mudaria a cada página nova e `grew` nunca existiria."""
    antes = {"thm_a": _pgs("alfa", 6)}
    for n in (7, 8, 12):
        ev = match(antes, [_pgs("alfa", n)])
        assert [e.theme_id for e in ev] == ["thm_a"]


def test_evento_fora_do_vocabulario_e_recusado():
    with pytest.raises(ValueError, match="vocabulário fechado"):
        ThemeEvent("renamed", set())
    assert set(EVENTS) == {"born", "grew", "shrank", "merged", "split", "died"}


# ==================================== ponta a ponta: o problema do RFC §2.1
@pytest.fixture
def base(settings, kb):
    """O cenário medido do RFC §2.1: um tema de 5 páginas em que a página
    mais conectada troca. Antes deste PR isso produzia DUAS páginas
    canônicas descrevendo o mesmo tema."""
    def pagina(nome, vizinhos):
        corpo = "\n".join(f"- [{v}](/concepts/{v}.md)" for v in vizinhos)
        return OKFDocument(
            rel_path=f"concepts/{nome}.md", body=f"# {nome}\n\n{corpo}\n",
            meta=OKFFrontMatter(type="concept", title=nome,
                                privacy="local_only",
                                generated_via="human:promote"))
    membros = ["ana", "bia", "caio", "dora", "elo"]
    docs = [pagina(m, [x for x in membros if x != m] if m == "ana" else ["ana"])
            for m in membros]
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    settings._membros_do_teste = membros      # usado pela troca de hub
    settings._pagina = pagina
    return settings


def _vivas(kb) -> list[str]:
    dir_ = kb / "bundle/communities"
    if not dir_.is_dir():
        return []
    return sorted(p.name for p in dir_.glob("*.md")
                  if p.name != "index.md"
                  and "superseded_by" not in p.read_text())


def test_schema_migra_para_9_aditivamente(base):
    assert SCHEMA_VERSIONS["index.db"] >= 9
    idx = connect(base.app_support / "index.db")
    tabelas = {r["name"] for r in idx.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    idx.close()
    assert {"themes", "theme_epochs"} <= tabelas
    # aditiva: o que as versões 7 e 8 trouxeram continua
    assert {"graph_snapshot", "graph_centrality"} <= tabelas


def test_o_mesmo_tema_nao_gera_duas_paginas_vivas(base, kb):
    """A NEGAÇÃO do problema medido no RFC §2.1, e o teste que mais importa
    deste arquivo. Antes: `ana.md` e `elo.md` vivas descrevendo as mesmas 5
    páginas. Agora o caminho vem do `theme_id`, então trocar o hub não cria
    arquivo."""
    DetectCommunities(base).execute()
    antes = _vivas(kb)
    assert antes, "o cenário precisa produzir página de tema"
    # `elo` passa a ser a mais conectada — MESMO tema, hub diferente
    membros = base._membros_do_teste
    BundleWriter(kb).write(
        [base._pagina(m, [x for x in membros if x != m] if m == "elo"
                      else ["elo"]) for m in membros],
        log_kind="Update", log_message="m", commit_message="c")
    rebuild_index(base)
    DetectCommunities(base).execute()
    depois = _vivas(kb)
    assert depois == antes, (
        f"trocar o hub criou página nova: {antes} -> {depois}")
    assert all(n.startswith("thm_") for n in depois), (
        f"o caminho não vem do theme_id: {depois}")


def test_o_tema_ganha_id_e_epoca_de_nascimento(base):
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    temas = [dict(r) for r in idx.execute("SELECT * FROM themes")]
    epocas = [dict(r) for r in idx.execute("SELECT * FROM theme_epochs")]
    idx.close()
    assert temas, "nenhum tema registrado"
    for t in temas:
        assert t["theme_id"].startswith("thm_")
        assert t["rel_path"] == f"communities/{t['theme_id']}.md"
        assert t["died_at"] is None
        assert json.loads(t["members"])
    assert {e["event"] for e in epocas} == {"born"}


def test_reexecucao_nao_acrescenta_epoca(base):
    """Job semanal sobre bundle imóvel não pode inflar a trilha."""
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    n1 = idx.execute("SELECT COUNT(*) c FROM theme_epochs").fetchone()["c"]
    idx.close()
    for _ in range(3):
        DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    n2 = idx.execute("SELECT COUNT(*) c FROM theme_epochs").fetchone()["c"]
    idx.close()
    assert n2 == n1, f"a trilha inflou sem o bundle mudar: {n1} -> {n2}"


def test_backend_diferente_recusa_o_casamento(base):
    """Partições de `leiden` e `components` são incomparáveis por construção:
    casá-las produziria épocas falsas em massa (RFC §8)."""
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    idx.execute("UPDATE graph_snapshot SET backend='components' WHERE id=1")
    idx.commit()
    n1 = idx.execute("SELECT COUNT(*) c FROM theme_epochs").fetchone()["c"]
    idx.close()
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    n2 = idx.execute("SELECT COUNT(*) c FROM theme_epochs").fetchone()["c"]
    idx.close()
    assert n2 == n1, "casou partições de backends diferentes"


def test_o_llm_nao_decide_identidade(base, monkeypatch):
    """RFC §4.4: nenhum campo que decida UPDATE/SUPERSEDE pode vir do modelo.
    Com o roteador devolvendo rótulo ABSURDO e diferente a cada chamada, o
    `theme_id` e o `rel_path` têm de sair idênticos."""
    from corpusmith.models.router import ModelRouter
    contador = {"n": 0}

    def falso(self, *a, **k):
        contador["n"] += 1
        return {"text": f"ROTULO: tema inventado {contador['n']}\n"
                        f"RESUMO: resumo inventado {contador['n']}",
                "via": "local:falso"}

    monkeypatch.setattr(ModelRouter, "complete", falso)
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    primeiro = sorted((r["theme_id"], r["rel_path"])
                      for r in idx.execute("SELECT * FROM themes"))
    idx.close()
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    segundo = sorted((r["theme_id"], r["rel_path"])
                     for r in idx.execute("SELECT * FROM themes"))
    idx.close()
    assert primeiro == segundo, "o rótulo do modelo mudou a identidade"
    assert contador["n"] > 0, "o cenário precisa exercitar o roteador"


# ==================================== RFC §4.5: as páginas antigas
def _legado(kb, nome, membros):
    """Página de tema no formato PRÉ-theme_id, bem formada."""
    p = kb / f"bundle/communities/{nome}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\ntype: community_summary\ntitle: " + nome + "\n"
        "privacy: local_only\ngenerated_via: local:leiden\n"
        "source_sha256: " + "a" * 64 + "\n---\n\n"
        "# " + nome + "\n\nTema antigo.\n\n## Membros centrais\n"
        + "\n".join(f"- [{m}](/{m})" for m in membros) + "\n")
    from corpusmith.okf.git_store import GitStore
    GitStore(kb).commit(f"página de tema no formato antigo: {nome}")


def test_pagina_antiga_e_supersedida_para_o_caminho_novo(base, kb):
    """Sem isto o PR entrega o INV-005 violado no primeiro upgrade: a página
    no caminho antigo continuaria VIVA ao lado da nova, as duas descrevendo o
    mesmo tema — o defeito que este PR fecha, com um arquivo a mais."""
    membros = [f"concepts/{m}.md" for m in base._membros_do_teste]
    _legado(kb, "ana", membros)
    DetectCommunities(base).execute()
    antiga = (kb / "bundle/communities/ana.md").read_text()
    assert "superseded_by: communities/thm_" in antiga, (
        "a página antiga não foi adotada")
    assert "Tema antigo." in antiga, "o corpo tem de seguir legível"
    assert _vivas(kb) and all(n.startswith("thm_") for n in _vivas(kb))


def test_pagina_antiga_sem_tema_correspondente_e_aposentada(base, kb):
    """Não casa com tema nenhum ⇒ supersedida sem sucessora, nunca removida."""
    _legado(kb, "fantasma", ["concepts/inexistente-1.md",
                             "concepts/inexistente-2.md"])
    DetectCommunities(base).execute()
    txt = (kb / "bundle/communities/fantasma.md").read_text()
    assert "invalid_at:" in txt and "superseded_by" not in txt
    assert (kb / "bundle/communities/fantasma.md").is_file()


def test_pagina_antiga_malformada_nao_bloqueia_as_outras(base, kb):
    """Uma escrita por página, e não uma só com todas: página editada à mão
    sem `source_sha256` faz o Harness recusar — corretamente. Numa escrita
    única essa recusa bloquearia a adoção de TODAS, e o INV-005 seguiria
    violado no bundle inteiro por causa de um arquivo."""
    membros = [f"concepts/{m}.md" for m in base._membros_do_teste]
    _legado(kb, "boa", membros)
    ruim = kb / "bundle/communities/ruim.md"
    ruim.write_text("---\ntype: community_summary\ntitle: ruim\n"
                    "privacy: local_only\ngenerated_via: local:leiden\n---\n\n"
                    "# ruim\n\n## Membros centrais\n"
                    + "\n".join(f"- [{m}](/{m})" for m in membros) + "\n")
    from corpusmith.okf.git_store import GitStore
    GitStore(kb).commit("página de tema malformada")
    DetectCommunities(base).execute()
    assert "superseded_by: communities/thm_" in \
        (kb / "bundle/communities/boa.md").read_text(), (
            "a página malformada bloqueou a adoção da boa")
    # a malformada continua lá, intocada e visível ao lint
    assert "superseded_by" not in ruim.read_text()


def test_adocao_e_idempotente(base, kb):
    """Job semanal não pode re-supersedir o que já supersedeu.

    A asserção é sobre a CONTAGEM de adoções e sobre os bytes da página —
    o HEAD imóvel em reexecução idêntica é medido à parte por
    `test_sumario_identico_nao_move_o_head` (T6, resolvido)."""
    membros = [f"concepts/{m}.md" for m in base._membros_do_teste]
    _legado(kb, "ana", membros)
    primeira = DetectCommunities(base).execute()
    assert primeira["themes_adopted"] == 1
    conteudo = (kb / "bundle/communities/ana.md").read_bytes()
    segunda = DetectCommunities(base).execute()
    assert segunda["themes_adopted"] == 0, "re-adotou o que já estava adotado"
    assert (kb / "bundle/communities/ana.md").read_bytes() == conteudo


def test_sumario_identico_nao_move_o_head(base, kb):
    """T6 (ADR-45): membros idênticos ⇒ mesmo `source_sha256` ⇒ o sumário
    derivado é o mesmo — reescrevê-lo movia o HEAD a cada job semanal,
    enchendo o Git canônico de commits sem informação. Segunda execução
    sem mudança no bundle: zero sumários escritos, HEAD imóvel."""
    from corpusmith.okf.git_store import GitStore
    DetectCommunities(base).execute()
    head = GitStore(kb).repo.head.commit.hexsha
    segunda = DetectCommunities(base).execute()
    assert segunda["summaries"] == 0, "reescreveu sumário sem mudança"
    assert GitStore(kb).repo.head.commit.hexsha == head, \
        "o job moveu o HEAD sem informação nova"


# ==================================== INV-005 no doctor
def test_inv005_acusa_duas_paginas_vivas_para_um_tema(base, kb):
    """Invariante do RFC §5 sem verificador seria promessa. ERROR e não warn:
    ao contrário de mapa velho (INV-004, servível com aviso), duas verdades
    vivas sobre o mesmo tema não têm leitura correta."""
    from corpusmith.usecases.diagnose import DiagnoseSystem
    DetectCommunities(base).execute()
    assert not [f for f in DiagnoseSystem(base).execute()["findings"]
                if f["inv"] == "INV-005"], "bundle são acusado à toa"
    # duas páginas vivas para o MESMO tema — o defeito medido do RFC §2.1
    membros = [f"concepts/{m}.md" for m in base._membros_do_teste]
    _legado(kb, "clone", membros)
    achados = [f for f in DiagnoseSystem(base).execute()["findings"]
               if f["inv"] == "INV-005"]
    assert achados, "o doctor não acusou duas páginas vivas para um tema"
    assert achados[0]["severity"] == "error"
    # e o job REPARA (adota o formato antigo)
    DetectCommunities(base).execute()
    assert not [f for f in DiagnoseSystem(base).execute()["findings"]
                if f["inv"] == "INV-005"]


def test_o_job_nao_deixa_o_doctor_vermelho(base):
    """Achado de auditoria CONFIRMADO por execução e corrigido aqui: o job
    escreve páginas `communities/` pelo writer, cada uma um commit, e não
    reindexava — então INV-002 (índice corresponde ao HEAD) disparava como
    ERROR a cada execução. Sendo semanal, o produto passaria a semana inteira
    acusando corrupção que ele mesmo produziu.

    Reindexar aqui só é seguro porque a D-E foi paga no F2-PR1:
    `communities/` está fora da construção do grafo."""
    from corpusmith.usecases.diagnose import DiagnoseSystem
    assert DiagnoseSystem(base).execute()["ok"], "cenário já sujo"
    DetectCommunities(base).execute()
    rel = DiagnoseSystem(base).execute()
    erros = [f for f in rel["findings"] if f["severity"] == "error"]
    assert not erros, f"o job deixou o doctor vermelho: {erros}"


def test_reindexar_no_job_nao_realimenta_o_grafo(base):
    """A guarda que torna o rebuild acima seguro (D-E). Se `communities/`
    voltasse ao grafo, cada rodada alteraria o grafo da seguinte e a partição
    mudaria sem o conhecimento mudar."""
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    primeira = {r["page"]: r["community"] for r in
                idx.execute("SELECT page, community FROM communities")}
    idx.close()
    for _ in range(3):
        DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    ultima = {r["page"]: r["community"] for r in
              idx.execute("SELECT page, community FROM communities")}
    idx.close()
    assert ultima == primeira, "o rebuild no job realimentou o grafo"
