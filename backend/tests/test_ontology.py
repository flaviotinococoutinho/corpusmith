"""RFC-004 — a ontologia não pode divergir do código, e a fusão não pode
decidir governança por acidente de dicionário.

Mesmo padrão de `test_architecture_toml` e `test_epistemics_toml`: o
registro declarado (`ontology.toml`) é cruzado com as constantes reais
(`kernel/ontology.py`). Aqui há, além disso, uma REGRESSÃO real — a tabela
de fraqueza de `merge_meta` tinha três valores e o produto escreve quatro.
"""
from __future__ import annotations
import itertools
import tomllib
from pathlib import Path
import pytest
from corpusmith.harness.ontology import lint, overview
from corpusmith.kernel import ontology as onto
from corpusmith.kernel.curation import merge_meta

_ROOT = Path(__file__).resolve().parents[2]


def _toml() -> dict:
    return tomllib.loads((_ROOT / "ontology.toml").read_text())


# ==================================================== o registro é honesto
def test_lint_do_registro_esta_verde():
    _, findings = lint()
    erros = [f for f in findings if f.severity == "error"]
    assert not erros, [f.to_dict() for f in erros]


def test_toml_declara_o_vocabulario_real_do_kernel():
    """Se alguém acrescentar um valor a um eixo sem declará-lo (ou o
    contrário), o registro passa a mentir sobre o código."""
    declarados = _toml()["axes"]
    for eixo, vocab in onto.AXES.items():
        assert tuple(declarados[eixo]["values"]) == vocab, eixo


def test_nenhum_valor_responde_a_duas_perguntas():
    """A propriedade que define um EIXO. É ela que `confidence` violava:
    `extracted` responde 'como derivou', `ambiguous` responde 'resolveu?'
    e `human_approved` responde 'quem autorizou' — no mesmo campo."""
    for valor in itertools.chain.from_iterable(onto.AXES.values()):
        assert len(onto.eixos_de(valor)) == 1, (
            f"`{valor}` está em {onto.eixos_de(valor)}")


def test_todo_eixo_declara_a_pergunta_que_responde():
    """Sem a pergunta não há como testar se um valor entrou no eixo por
    engano — que é exatamente como a conflação se instala."""
    for eixo in onto.AXES:
        assert onto.QUESTIONS[eixo].strip()
        assert _toml()["axes"][eixo]["question"].strip()


def test_evaluation_status_nao_e_redefinido_aqui():
    """O quarto eixo já existe fechado em `epistemic/model.py`, aplicado a
    MECANISMO. Redefini-lo criaria a segunda definição do mesmo termo — o
    defeito que este módulo combate."""
    from corpusmith.epistemic.model import EvaluationStatus
    assert "evaluation_status" not in onto.AXES
    declarado = _toml()["axes"]["evaluation_status"]
    assert declarado["applies_to"] == "mechanism"
    assert tuple(declarado["values"]) == tuple(
        e.value for e in EvaluationStatus)


def test_cada_termo_diz_o_que_NAO_e():
    """Um verbete que só diz o que a palavra significa não impede o
    sentido novo de entrar; o que segura a deriva é a fronteira."""
    for termo, corpo in _toml()["terms"].items():
        for chave in ("roots", "means", "not_means", "constrains"):
            assert corpo.get(chave, "").strip(), f"{termo}.{chave}"


# ============================== a fusão decide governança por REGRA
# A tabela inteira, célula a célula. Preferida a uma propriedade esperta
# porque a regra tem três eixos e um encoding com perda: uma propriedade
# que coubesse numa linha esconderia justamente a célula que mudou.
_TABELA = {
    ("extracted", "extracted"): "extracted",
    ("extracted", "inferred"): "inferred",       # não promove
    ("extracted", "ambiguous"): "ambiguous",     # resolução domina
    ("extracted", "human_approved"): "inferred",  # ratificação não cobre a fusão
    ("inferred", "inferred"): "inferred",
    ("inferred", "ambiguous"): "ambiguous",
    ("inferred", "human_approved"): "inferred",
    ("ambiguous", "ambiguous"): "ambiguous",
    ("ambiguous", "human_approved"): "ambiguous",
    ("human_approved", "human_approved"): "human_approved",
}


@pytest.mark.parametrize("par,esperado", sorted(_TABELA.items()))
def test_tabela_de_fusao_de_confidence(par, esperado):
    a, b = par
    assert onto.merge_confidence(a, b) == esperado


@pytest.mark.parametrize("a,b", sorted(_TABELA))
def test_fusao_e_simetrica(a, b):
    """O defeito mais barato de reproduzir e o mais caro de conviver: a
    tabela antiga ordenava por `fraqueza.get(c, 0)` e `human_approved` não
    estava nela, então empatava em 0 com `extracted` — e `max` devolve o
    PRIMEIRO dos empatados. Medido antes da correção:

        merge("human_approved", "extracted") -> "human_approved"
        merge("extracted", "human_approved") -> "extracted"

    A mesma fusão com dois resultados conforme a ordem dos argumentos, ou
    seja: conforme qual página o curador clicou primeiro.

    A asserção passa por `merge_meta` de propósito: ela é sobre o caminho
    que o produto percorre, não sobre a função nova. Verificar simetria só
    em `merge_confidence` daria verde com o defeito intacto no chamador."""
    assert merge_meta({"confidence": a}, {"confidence": b})["confidence"] \
        == merge_meta({"confidence": b}, {"confidence": a})["confidence"]


def test_ratificacao_nao_sobrevive_a_fusao_com_nao_ratificado():
    """A célula que MUDOU de comportamento. Ratificação é ato sobre um
    conteúdo; a fusão produz outro conteúdo, que ninguém ratificou.

    Falsificável: com a tabela antiga (`fraqueza` de três valores) esta
    asserção devolve `human_approved` e o teste reprova."""
    fundido = merge_meta({"confidence": "human_approved", "title": "A"},
                         {"confidence": "extracted"})
    assert fundido["confidence"] != "human_approved"
    assert fundido["confidence"] == "inferred"


def test_fusao_de_dois_ratificados_permanece_ratificada():
    fundido = merge_meta({"confidence": "human_approved"},
                         {"confidence": "human_approved"})
    assert fundido["confidence"] == "human_approved"


def test_fusao_nunca_assenta_uma_ambiguidade():
    for outro in onto.LEGACY_CONFIDENCE:
        assert merge_meta({"confidence": "ambiguous"},
                          {"confidence": outro})["confidence"] == "ambiguous"


def test_merge_meta_preserva_as_demais_regras():
    """A troca da regra de `confidence` não pode ter mexido nas outras —
    listas se unem sem duplicar e `valid_at` fica com o mais antigo."""
    fundido = merge_meta(
        {"tags": ["a", "b"], "valid_at": "2026-05-01", "title": "alvo"},
        {"tags": ["b", "c"], "valid_at": "2024-01-01", "title": "fonte"})
    assert fundido["tags"] == ["a", "b", "c"]
    assert fundido["valid_at"] == "2024-01-01"
    assert fundido["title"] == "alvo"


# ======================================================= classificação
def test_pagina_de_maquina_sem_ato_humano_e_proposta():
    """ADR-53 §3: chamar de ratificado o que ninguém ratificou é a
    alegação proibida. O default tem de cair para `proposed`."""
    eixos = onto.classificar({"generated_via": "api:compile",
                              "confidence": "extracted"})
    assert eixos["governance_status"] == "proposed"


def test_pagina_aposentada_e_retired_mesmo_tendo_sido_ratificada():
    """Aposentar é o gesto mais recente e vence a ratificação anterior —
    a página segue no bundle, só deixa de valer como afirmação corrente."""
    eixos = onto.classificar({"generated_via": "human:promote",
                              "confidence": "human_approved",
                              "superseded_by": "concepts/nova.md"})
    assert eixos["governance_status"] == "retired"


def test_classificar_devolve_valor_valido_em_todo_eixo():
    metas: list[dict] = [
        {}, {"generated_via": "human:promote"}, {"invalid_at": "2026-01-01"},
        *({"confidence": v} for v in onto.LEGACY_CONFIDENCE)]
    for meta in metas:
        for eixo, valor in onto.classificar(meta).items():
            assert onto.valido(eixo, valor), (meta, eixo, valor)


# ============================================ o registro de deriva é vivo
def test_deriva_registrada_ainda_existe_no_codigo():
    """O ponto do `marker`: uma deriva declarada aberta cujo sentido sumiu
    do código vira warn, e uma separação declarada resolvida que perdeu um
    nome vira erro. Sem isto o registro vira confissão decorativa."""
    _, findings = lint()
    assert not [f for f in findings
                if f.code in ("ontology.drift_sense_gone",
                              "ontology.drift_regressed")], \
        [f.to_dict() for f in findings]


def test_deriva_do_confidence_esta_registrada_como_paga_em_parte():
    """A entrada não pode ser fechada: os sentidos numéricos (autorrelato,
    taxa, intervalo) continuam no mesmo nome. Fechar aqui seria alegar um
    conserto que o código não tem."""
    entrada = _toml()["drift"]["confidence"]
    assert entrada["status"] == "open"
    assert len(entrada["senses"]) >= 5
    assert "kernel/ontology.py" in entrada["paid"]


def test_overview_expoe_a_mesma_fonte_da_cli():
    data = overview()
    assert data["ok"] is True
    assert {a["axis"] for a in data["axes"]} >= set(onto.AXES)
    assert data["version"]


# ================================ a perda de ratificação é DECLARADA
# docs/26 §3: a regra nova de fusão derruba a ratificação quando só um
# lado a tem — correto (ela cobria outro conteúdo), mas derrubá-la em
# silêncio é *audit erasure* no eixo de governança. O produto protege o
# CONTEÚDO contra apagamento (A-2); estes testes estendem a proteção ao
# atributo epistêmico: toda perda aparece no preview (eixo humano) ou no
# resultado/evento (eixo de máquina).

def test_ratificacao_perdida_diz_qual_lado_a_tinha():
    perda = onto.ratificacao_perdida("human_approved", "extracted")
    assert perda == {"axis": "governance_status", "before": "ratified",
                     "after": "proposed", "ratified_side": "alvo",
                     "merged_confidence": "inferred"}
    assert onto.ratificacao_perdida(
        "extracted", "human_approved")["ratified_side"] == "fonte"


def test_ratificacao_perdida_none_quando_nao_ha_perda():
    # ambos ratificados: a fusão PRESERVA — nada a declarar
    assert onto.ratificacao_perdida("human_approved",
                                    "human_approved") is None
    # nenhum ratificado: não havia o que perder
    assert onto.ratificacao_perdida("extracted", "inferred") is None
    assert onto.ratificacao_perdida("ambiguous", "extracted") is None


def test_update_de_maquina_declara_a_ratificacao_perdida(settings, kb):
    """O caminho que o produto percorre SOZINHO: recompilação de máquina
    sobre página promovida (human_approved). A fusão derruba a
    ratificação — e o resultado tem de dizer isso, não só o diff.

    Falsificável: sem o rastreio em `_merged_with_resident`, o resultado
    sai sem `ratification_lost` e a primeira asserção reprova."""
    from corpusmith.okf.writer import BundleWriter
    from corpusmith.usecases.base import DraftPage, MachinePageUseCase
    from corpusmith.usecases.promote_memory import PromoteToMemory

    PromoteToMemory(settings, kind="semantic", title="Docker",
                    content="anotação humana ratificada").execute()

    class _Compilador(MachinePageUseCase):
        MODULE = "compile"

        def _produce(self):
            return DraftPage(
                rel_path="concepts/rascunho.md", title="Docker",
                body="# Docker\n\nCorpo recompilado.\n",
                meta={"generated_via": "local:test",
                      "source_sha256": "0" * 64})

        def _reconcile(self, document, report):
            return {"op": "UPDATE", "target": "concepts/docker.md"}

    resultado = _Compilador(settings).execute()
    perda = resultado.get("ratification_lost")
    assert perda, "a perda de ratificação foi silenciosa (audit erasure)"
    assert perda["axis"] == "governance_status"
    assert perda["ratified_side"] == "fonte"      # a residente promovida
    meta = BundleWriter(settings.path("knowledge")).reader.load(
        "concepts/docker.md").meta
    assert meta.model_dump().get("confidence") == "inferred", (
        "a fusão devia rebaixar para inferred (RFC-004 §5.4)")


def test_add_de_maquina_nao_inventa_perda(settings, kb):
    """Página nova (ADD): não há residente, não há ratificação, não pode
    haver declaração de perda — senão o sinal vira ruído."""
    from corpusmith.usecases.base import DraftPage, MachinePageUseCase

    class _Compilador(MachinePageUseCase):
        MODULE = "compile"

        def _produce(self):
            return DraftPage(
                rel_path="concepts/pagina-nova.md", title="Nova",
                body="# Nova\n\nCorpo.\n",
                meta={"generated_via": "local:test",
                      "source_sha256": "0" * 64})

    resultado = _Compilador(settings).execute()
    assert resultado["op"] == "ADD"
    assert "ratification_lost" not in resultado


def test_preview_da_fusao_humana_declara_a_perda(settings, kb):
    """Eixo humano: o contrato de todo ato é preview ANTES do efeito. Uma
    fusão que perde ratificação tem de dizê-lo no preview — e dizer de
    QUAL página a aprovação era."""
    from corpusmith.okf.document import OKFDocument, OKFFrontMatter
    from corpusmith.okf.writer import BundleWriter
    from corpusmith.usecases.curate import MergePages

    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/maquina.md",
                     body="# Máquina\n\ncorpo compilado.\n",
                     meta=OKFFrontMatter(type="concept", title="Máquina",
                                         privacy="local_only",
                                         confidence="extracted")),
         OKFDocument(rel_path="concepts/humana.md",
                     body="# Humana\n\nanotação aprovada.\n",
                     meta=OKFFrontMatter(type="concept", title="Humana",
                                         privacy="local_only",
                                         confidence="human_approved"))],
        log_kind="Creation", log_message="m", commit_message="c")

    out = MergePages(settings, page="concepts/humana.md",
                     into="concepts/maquina.md").execute(dry_run=True)
    nota = out["preview"]["note"]
    assert "PERDE a ratificação" in nota
    assert "concepts/humana.md" in nota, "o preview tem de dizer QUAL página"
    # e quando nenhum lado é ratificado, o preview NÃO menciona perda
    out2 = MergePages(settings, page="concepts/maquina.md",
                      into="concepts/humana.md").execute(dry_run=True)
    # (humana é ratificada e é a vencedora: perde mesmo assim — o conteúdo
    # muda com a absorção; a regra é sobre a FUSÃO, não sobre quem vence)
    assert "PERDE a ratificação" in out2["preview"]["note"]


# ================================== RFC-005 · conflito factual (F4-PR3a)
# O núcleo puro do detector. Ele NÃO está ligado a nenhum caminho ainda
# (isso é F4-PR3b): estes testes fixam a REGRA antes da obra, que é o mesmo
# padrão do PR-0 e do F3-PR0.

def test_divergencia_alem_da_tolerancia_e_conflito():
    from corpusmith.kernel import factual
    out = factual.divergencias({
        "a.md": [{"dim": "len", "si": 12000.0, "unit": "km", "surface": "12 km"}],
        "b.md": [{"dim": "len", "si": 20000.0, "unit": "km", "surface": "20 km"}]})
    assert len(out) == 1
    assert out[0]["dim"] == "len"
    assert set(out[0]["pages"]) == {"a.md", "b.md"}
    assert out[0]["spread"] > 0.01


def test_mesmo_valor_em_unidades_diferentes_NAO_e_conflito():
    """I-4: a cláusula 'unidade idêntica' de docs/14 §P-5 foi REMOVIDA
    justamente por descartar o caso que a normalização SI existe para
    resolver. 12 km e 12000 m são o mesmo valor — e o detector precisa
    saber disso, senão compra falso positivo no lugar do falso negativo."""
    from corpusmith.kernel import factual
    assert factual.divergencias({
        "a.md": [{"dim": "len", "si": 12000.0, "unit": "km", "surface": "12 km"}],
        "b.md": [{"dim": "len", "si": 12000.0, "unit": "m", "surface": "12000 m"}],
    }) == []


def test_diferenca_dentro_da_tolerancia_e_arredondamento():
    from corpusmith.kernel import factual
    # 0.08% — transcrição, não divergência
    assert factual.divergencias({
        "a.md": [{"dim": "len", "si": 12500.0, "unit": "km", "surface": "12.5 km"}],
        "b.md": [{"dim": "len", "si": 12510.0, "unit": "km", "surface": "12.51 km"}],
    }) == []


def test_pagina_que_afirma_dois_valores_e_faixa_nao_conflito():
    """I-2, a guarda de precisão que o plano de docs/14 não previa: uma
    página que menciona 12 km E 20 km descreve faixa ou comparação. Comparar
    o extremo dela com o de outra página seria ler mal o texto.

    Falsificável: sem a guarda, este caso vira conflito (12000 vs 20000)."""
    from corpusmith.kernel import factual
    assert factual.divergencias({
        "a.md": [{"dim": "len", "si": 12000.0, "unit": "km", "surface": "12 km"},
                 {"dim": "len", "si": 20000.0, "unit": "km", "surface": "20 km"}],
        "b.md": [{"dim": "len", "si": 90000.0, "unit": "km", "surface": "90 km"}],
    }) == []


def test_temperatura_e_porcentagem_ficam_fora_e_a_exclusao_e_declarada():
    """I-3. `temp` porque quantities.py:65 suprime o payload SI (não há
    conversão afim °C↔°F); `ratio` porque porcentagem não é dimensão física
    e 50% vs 80% podem ser percentuais DE COISAS DIFERENTES."""
    from corpusmith.kernel import factual
    assert set(factual.EXCLUIDAS) == {"temp", "ratio"}
    for dim in factual.EXCLUIDAS:
        assert factual.divergencias({
            "a.md": [{"dim": dim, "si": 10.0, "unit": "x", "surface": "10"}],
            "b.md": [{"dim": dim, "si": 90.0, "unit": "x", "surface": "90"}],
        }) == [], dim


def test_uma_voz_so_nao_e_divergencia():
    from corpusmith.kernel import factual
    assert factual.divergencias({
        "a.md": [{"dim": "len", "si": 1.0, "unit": "m", "surface": "1 m"},
                 {"dim": "mass", "si": 5.0, "unit": "kg", "surface": "5 kg"}],
    }) == []


def test_medida_sem_payload_si_e_ignorada():
    """Temperatura chega assim do detector real (si suprimido). O módulo não
    pode explodir nem inventar comparação — ignora e segue."""
    from corpusmith.kernel import factual
    assert factual.divergencias({
        "a.md": [{"dim": "len", "unit": "km", "surface": "12 km"}],
        "b.md": [{"dim": "len", "si": 20000.0, "unit": "km", "surface": "20 km"}],
    }) == []


def test_dimensoes_distintas_nao_se_misturam():
    from corpusmith.kernel import factual
    assert factual.divergencias({
        "a.md": [{"dim": "len", "si": 10.0, "unit": "m", "surface": "10 m"}],
        "b.md": [{"dim": "mass", "si": 900.0, "unit": "kg", "surface": "900 kg"}],
    }) == []


def test_saida_e_estavel_e_ordenada_por_dimensao():
    """`meta` é contrato de fato da fila (next_actions usa meta['pages']
    como chave de supressão). Saída instável quebraria a supressão em
    silêncio, que é o defeito que a supressão existe para evitar."""
    from corpusmith.kernel import factual
    medidas = {
        "b.md": [{"dim": "mass", "si": 1.0, "unit": "kg", "surface": "1 kg"},
                 {"dim": "len", "si": 1.0, "unit": "m", "surface": "1 m"}],
        "a.md": [{"dim": "mass", "si": 9.0, "unit": "kg", "surface": "9 kg"},
                 {"dim": "len", "si": 9.0, "unit": "m", "surface": "9 m"}]}
    out = factual.divergencias(medidas)
    assert [d["dim"] for d in out] == ["len", "mass"]
    assert list(out[0]["pages"]) == ["a.md", "b.md"]
    assert factual.divergencias(medidas) == out          # determinístico


def test_resumo_mostra_a_superficie_nao_o_si():
    """Quem vai conferir procura no TEXTO o que está escrito — mostrar o
    valor convertido mandaria a pessoa procurar algo que não existe lá."""
    from corpusmith.kernel import factual
    d = factual.divergencias({
        "a.md": [{"dim": "len", "si": 12000.0, "unit": "km", "surface": "12 km"}],
        "b.md": [{"dim": "len", "si": 20000.0, "unit": "km", "surface": "20 km"}]})[0]
    texto = factual.resumo(d)
    assert "12 km" in texto and "20 km" in texto
    assert "12000" not in texto


def test_tolerancia_e_declarada_e_nao_calibrada():
    """RFC-005 §5.2: primeiro limiar numérico do Harness, e não há golden
    set. O docstring precisa DIZER isso — chamar de calibrado o que não foi
    medido é a alegação que ADR-53 §3 proíbe."""
    from corpusmith.kernel import factual
    assert factual.TOLERANCIA_RELATIVA == 0.01
    assert "não é calibrado" in factual.__doc__ .lower() \
        or "Não é calibrado" in __import__("inspect").getsource(factual)


def test_contested_so_aparece_com_conflito_declarado():
    """I-5 e o primeiro produtor do valor: `contested` estava no vocabulário
    fechado sem nenhum escritor (docs/18 O-2)."""
    assert onto.classificar({})["resolution_status"] == "resolved"
    assert onto.classificar(
        {}, em_conflito=True)["resolution_status"] == "contested"
    assert onto.valido("resolution_status", "contested")


def test_conflito_vence_ambiguidade_da_leitura():
    """`ambiguous` diz que ESTA leitura não foi assentada; `contested` diz
    que duas páginas se contradizem. A segunda é a que tem destino na fila,
    e é a mais cara de perder."""
    assert onto.classificar({"confidence": "ambiguous"},
                            em_conflito=True)["resolution_status"] == "contested"
