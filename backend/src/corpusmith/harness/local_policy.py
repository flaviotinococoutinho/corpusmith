from __future__ import annotations
import re
from .findings import Finding
from ..kernel.factual import divergencias, resumo
from ..normalize import analyze, findings as norm_findings
from ..normalize.detectors.identifiers import RE_GIT_SHA_CTX as COMMIT_REF
from ..okf.authorities import load_gazetteer, load_type_schemas
from ..okf.document import OKFDocument
from ..okf.links import parse_links, is_internal, resolve

CITATION_REF = re.compile(r"\[(\d+)\]")
SCHEMA_FIELD = re.compile(r"^\|\s*`?(\w+)`?\s*\|", re.M)
MACHINE = ("api:", "local:")

RECOMMENDED_TYPES = {
    "concept", "academic_paper", "runbook", "decision", "learning_note",
    "skill", "review", "question", "architectural_alert", "breaking_change",
    "collection_specification", "schema_specification", "field_profile",
    "message_channel", "feature_flag", "infrastructure_specification",
    "personal_reflection", "reference",
    "authority_record", "community_summary",
    # tipagem epistemológica explícita (v0.21, EPIC-11): a NATUREZA do
    # conteúdo é tipo de primeira classe — hipótese não vira fato sem
    # transição registrada (SUPERSEDE), nunca por edição silenciosa
    "fact", "claim", "hypothesis", "observation", "opinion"}

def check(docs, reader, git, mode: str = "write",
          intent: str | None = None) -> list[Finding]:
    out: list[Finding] = []
    gaz = load_gazetteer(reader) if docs else None
    schemas = load_type_schemas(reader) if docs else {}
    for d in docs:
        x = d.meta.model_dump()
        via = str(x.get("generated_via", ""))

        # RFC-003 (F3, P-7): o caminho destrutivo dominante não é UPDATE —
        # é ADD sobre `rel_path` existente, gravado no log como "Creation".
        # Medido: dois promotes do mesmo título, o segundo APAGA 40 linhas
        # de anotação humana e o log mente. A regra lê o FILESYSTEM, não a
        # projeção: vale mesmo com o índice irreparavelmente atrasado.
        if intent == "Creation" and reader.exists(d.rel_path):
            out.append(Finding(
                "error", "policy.path_collision", d.rel_path,
                "intenção declarada é Creation mas a página JÁ EXISTE — "
                "sobrescrever seria destruição registrada como criação; "
                "declare Update (fundindo frontmatter) ou use outro slug"))

        if x.get("privacy") not in ("local_only", "api_allowed"):
            out.append(Finding("error", "policy.privacy_required", d.rel_path,
                               "toda página escrita precisa de privacy: "
                               "local_only|api_allowed"))

        # ---- normalização (v0.8 §4.3): grafia, checksums, PII, temporal ----
        report = analyze(d.body, gaz=gaz)
        machine = via.startswith(MACHINE)
        for sev, rule, path, msg in norm_findings(d.rel_path, report,
                                                  machine=machine):
            out.append(Finding(sev, rule, path, msg))
        # PII detectada com checksum válido ⇒ privacidade obrigatoriamente local
        if report.sensitive and x.get("privacy") == "api_allowed":
            out.append(Finding("error", "policy.pii_requires_local", d.rel_path,
                               "documento pessoal (CPF/CNPJ/IBAN) detectado; "
                               "privacy deve ser local_only"))
        # bi-temporalidade coerente (§6)
        va, ia = x.get("valid_at"), x.get("invalid_at")
        if va and ia and str(ia) <= str(va):
            out.append(Finding("error", "policy.temporal_order", d.rel_path,
                               "invalid_at deve ser posterior a valid_at"))

        # proveniência: só páginas geradas por MÁQUINA exigem source_sha256
        # (promoções humanas usam generated_via: human:* e campo source)
        if via.startswith(MACHINE) and not x.get("source_sha256"):
            out.append(Finding("error", "policy.source_sha_required", d.rel_path,
                               "página gerada por máquina sem source_sha256"))

        # citações: POLÍTICA LOCAL (SPEC trata # Citations como SHOULD)
        if via.startswith("api:"):
            refs = {int(n) for n in CITATION_REF.findall(d.body)}
            m = re.search(r"^#{1,2}\s*Citations\s*$", d.body, re.M)
            listed = {int(n) for n in CITATION_REF.findall(
                d.body[m.end():])} if m else set()
            if not m or not listed:
                out.append(Finding("error", "policy.citation_required", d.rel_path,
                                   "conteúdo de API sem seção # Citations"))
            elif refs and not refs <= listed:
                out.append(Finding("error", "policy.citation_invalid", d.rel_path,
                                   f"refs {sorted(refs - listed)} sem entrada "
                                   "em Citations"))

        # F3-PR2 (P-3): SUCESSOR PENDURADO. `superseded_by` e `answered_by`
        # apontam para uma página canônica — apontar para o que não existe
        # aposenta a origem e não entrega a sucessora, tirando o item da fila
        # sem que nada tenha sido resolvido. A regra não existia nem para
        # `superseded_by`, que está no produto desde a v0.8.
        #
        # Vale para o LOTE inteiro: uma fusão que escreve a sucessora e a
        # aposentada no mesmo `write` é legítima, e olhar só o disco a
        # reprovaria.
        no_lote = {doc.rel_path for doc in docs}
        for chave in ("superseded_by", "answered_by"):
            alvo = x.get(chave)
            if alvo and alvo not in no_lote and not reader.exists(str(alvo)):
                out.append(Finding(
                    "error", "policy.dangling_successor", d.rel_path,
                    f"{chave} aponta para '{alvo}', que não existe no "
                    f"bundle — a página sairia da fila sem sucessora real"))

        for sha in COMMIT_REF.findall(d.body + " " + str(x.get("stale_as_of", ""))):
            if not git.has_commit(sha):
                out.append(Finding("error", "policy.bad_commit_ref", d.rel_path,
                                   f"commit inexistente: {sha}"))

        if reader.exists(d.rel_path):
            old = reader.load(d.rel_path)
            lost = set(SCHEMA_FIELD.findall(_section(old.body, "Schema"))) \
                 - set(SCHEMA_FIELD.findall(_section(d.body, "Schema")))
            if lost and not x.get("supersedes"):
                out.append(Finding("error", "policy.schema_shrink", d.rel_path,
                                   f"campos removidos sem supersedes: {sorted(lost)}"))
            lost_keys = set(old.meta.model_dump(exclude_none=True)) \
                      - set(d.meta.model_dump(exclude_none=True)) - {"timestamp"}
            if lost_keys:
                out.append(Finding("warn", "policy.metadata_shrink", d.rel_path,
                                   f"frontmatter perdeu chaves: {sorted(lost_keys)}"))

        if d.meta.type not in RECOMMENDED_TYPES:
            out.append(Finding("info", "policy.unknown_type", d.rel_path,
                               f"type fora da taxonomia recomendada: {d.meta.type}"))

        # schemas por tipo (DTT lite, v0.10): collection_specification com
        # `applies_to` declara campos obrigatórios — contrato opt-in curado
        # no próprio bundle
        schema = schemas.get(d.meta.type)
        if schema:
            present = set(d.meta.model_dump(exclude_none=True))
            missing = [f for f in schema["required_fields"] if f not in present]
            if missing:
                out.append(Finding("error", "policy.schema_required_field",
                                   d.rel_path,
                                   f"type '{d.meta.type}' exige campos "
                                   f"{missing} (schema: {schema['page']})"))

        if mode == "release":
            for link in parse_links(d.body):
                if is_internal(link.target) and \
                   not reader.exists(resolve(link.target, d.rel_path)):
                    out.append(Finding("error", "policy.release_broken_link",
                                       d.rel_path,
                                       f"release com link quebrado: {link.target}"))
    return out

# Subkinds que formam SUJEITO de contradição/conflito factual — duas
# páginas que citam o mesmo identificador falam da mesma coisa.
#
# RFC-006 V1: as NORMAS entram (iso/nbr/rfc/nist/ieee/eu_reg/circular) —
# um documento normativo identifica tão fortemente quanto um DOI, e é o
# material de quem estuda padrões. `regulator` fica FORA de propósito:
# "LGPD" ou "OWASP" nomeiam um REFERENTE (lei, organização), não um
# documento — duas páginas que mencionam OWASP não estão falando "do mesmo
# texto", e incluí-lo compraria o sujeito inventado que a RFC-005 §3
# recusou. A reconciliação usa STRONG_IDS próprio (reconcile_candidate.py)
# — ampliar AQUI não faz duas notas sobre a mesma ISO parecerem o mesmo
# documento lá.
CONTRADICTION_IDS = ("doi", "isbn", "issn", "arxiv",
                     "iso", "nbr", "rfc", "nist", "ieee", "eu_reg",
                     "circular")
#: Kinds de Match cujos subkinds acima podem formar grupo. `identifier`
#: cobre doi/isbn/issn/arxiv; `standard` cobre as normas.
_KINDS_DE_SUJEITO = ("identifier", "standard")


def _alias_conflitantes(gaz, usos: dict[str, set[str]]) -> list[Finding]:
    """`policy.alias_conflict` — duas identidades curadas disputam o mesmo
    alias (RFC-006 V2).

    **Determinístico E contratado, e a distinção importa.** A detecção é
    igualdade de alias entre registros da mesma camada — sem limiar, sem
    calibração, como o `valid_at` legado do F4-PR3c. Mas aquele é um ATO
    cuja assinatura é COMPLETA sobre o corpus (toda página de máquina com
    os carimbos iguais é legado), enquanto este é um DETECTOR com lacuna
    de recall: ele só enxerga a ambiguidade que alguém já CUROU em dois
    registros. Um bundle sem `authority_record` tem zero conflitos e
    vocabulário inteiramente por resolver — e ler esse silêncio como
    "está desambiguado" é a inferência falsa que `[mechanisms.
    alias_conflict]` existe para impedir.

    A mensagem NOMEIA o ato que resolve, e ele depende do diagnóstico:
    canônicos já qualificados por sentido pedem que o alias NU saia de um
    dos registros (o alias curto não pode servir a dois donos); canônicos
    sem qualificador pedem que o sentido seja declarado. Dizer só "há
    conflito" deixaria o curador adivinhando qual das duas edições fazer."""
    out: list[Finding] = []
    for alias, cands in gaz.conflitos().items():
        paginas_de_uso = sorted(usos.get(alias, ()))
        alvo = next((c.page for c in cands if c.page), None) \
            or (paginas_de_uso[0] if paginas_de_uso else None)
        if alvo is None:
            continue          # nem registro editável nem uso: nada a fazer
        sentidos = [c.sentido for c in cands]
        nomes = ", ".join(f"`{c.canonical}`" for c in cands)
        if all(sentidos):
            comoresolver = (f"os sentidos já estão declarados ({', '.join(sentidos)}), "
                            f"mas o alias `{alias}` continua servindo aos dois — "
                            "tire-o de um dos registros ou qualifique o uso")
        else:
            comoresolver = ("declare o sentido no canônico de cada registro "
                            "(ex.: `Entropia (física)` e `Entropia "
                            "(informação)`) para que sejam identidades "
                            "distintas")
        onde = (f"; usado em {len(paginas_de_uso)} página(s): "
                f"{paginas_de_uso[:3]}" if paginas_de_uso else
                "; nenhuma página usa o alias hoje")
        out.append(Finding(
            "warn", "policy.alias_conflict", alvo,
            f"o alias `{alias}` é reivindicado por {len(cands)} identidades "
            f"({nomes}) — {comoresolver}{onde}. Enquanto durar, o termo é "
            "lido como AMBÍGUO: não é reescrito, não entra no índice de "
            "entidades e não liga páginas",
            meta={"alias": alias,
                  "candidates": [c.canonical for c in cands],
                  "senses": sentidos,
                  "records": [c.page for c in cands if c.page],
                  "pages": paginas_de_uso}))
    return out


def _blocos_de_sucessao(group, pages: set[str]) -> list[set[str]]:
    """Partição das páginas do grupo pelas relações de sucessão declaradas.

    Union-find sobre `superseded_by`/`supersedes` restritos ao grupo: duas
    páginas ligadas por sucessão estão RESOLVIDAS entre si. Um bloco só ⇒
    nada a reportar; dois ou mais ⇒ as versões ainda convivem."""
    pai = {p: p for p in pages}

    def raiz(p: str) -> str:
        while pai[p] != p:
            pai[p] = pai[pai[p]]
            p = pai[p]
        return p

    for d, x in group:
        for chave in ("superseded_by", "supersedes"):
            outro = x.get(chave)
            if outro in pages and outro != d.rel_path:
                pai[raiz(d.rel_path)] = raiz(outro)
    blocos: dict[str, set[str]] = {}
    for p in pages:
        blocos.setdefault(raiz(p), set()).add(p)
    return list(blocos.values())


def _entrincheirada(itens):
    """A página que sobrevive à resolução: humana > máquina, empate por
    `rel_path`. UMA definição — o finding factual a aplica ao SUBCONJUNTO
    que diverge, não ao grupo inteiro, e duas cópias divergiriam."""
    return sorted(itens, key=lambda item: (
        not str(item[1].get("generated_via", "")).startswith("human:"),
        item[0].rel_path))[0][0]


def _medidas(report, corpo: str) -> list[dict]:
    """`NormReport` → a forma mínima que `kernel.factual.divergencias` pede.

    ACHATA o payload SI. `quantities.py:69` entrega `si` como DICT
    (`{"value", "unit"}`) e `factual.py:85` testa `isinstance(si, (int,
    float))` — sem o achatamento TODA quantidade seria descartada em
    silêncio e o detector nasceria inerte. É o modo de falha que este
    enxerto mais arrisca, e por isso a mutação que o teste executa.

    `dim == "temp"` já sai sem `si` na origem (`quantities.py:65`, não há
    conversão afim °C↔°F) e cai fora aqui. `ratio` cai no kernel, onde a
    exclusão é declarada com o motivo — repetir a lista aqui criaria dois
    donos da mesma decisão epistêmica.

    DESCARTA UNIDADE COMPOSTA. `RE_QTY` casa uma chave de `UNITS` por vez e
    o `/h` de `12 km/h` é engolido em silêncio: o match sai com
    `surface='12 km'`, `dim=len`, `si=12000 m` — uma VELOCIDADE lida como
    COMPRIMENTO. Sem esta guarda o detector produzia dois defeitos reais
    (medidos): falso positivo com dimensão errada, citando na mensagem um
    texto que não existe na página (`12 km` onde está escrito `12 km/h`), e
    falso NEGATIVO por mascaramento — a velocidade mal lida faz a página
    parecer declarar faixa, a guarda de faixa descarta a dimensão inteira e
    o conflito verdadeiro some.

    A correção é aqui e não em `quantities.py` de propósito: aquele
    detector alimenta `page_entities` e o gazetteer, e mudar a extração
    teria raio de explosão muito maior que o deste pacote. O que este
    módulo pode afirmar é mais estreito — *para comparação numérica entre
    páginas*, quantidade seguida de `/` não é medida confiável."""
    out = []
    for m in report.by_kind("quantity"):
        si = m.data.get("si")
        if not isinstance(si, dict):
            continue
        if corpo[m.end:m.end + 1] == "/":
            continue                       # 12 km/h, 30 mg/L, 5 MB/s …
        out.append({"dim": m.data.get("dim"), "si": float(si["value"]),
                    "unit": m.data.get("unit"), "surface": m.surface,
                    "span": [m.start, m.end]})
    return out


def check_corpus(docs, reader) -> list[Finding]:
    """Detecção AGM-inspirada de CONTRADIÇÃO candidata (v0.10, só no lint):
    o mesmo identificador forte em 2+ páginas sem relação de sucessão
    (superseded_by/supersedes dentro do grupo, ou invalid_at resolvendo o
    conflito no tempo) sugere duas versões da mesma verdade convivendo.
    A resolução NUNCA é automática — o finding nomeia a página mais
    ENTRINCHEIRADA (humana > máquina; mais desfechos úteis viriam depois)
    e o humano/SUPERSEDE decide. Warn, nunca error.

    **F4-PR3b (RFC-005)**: dentro de cada grupo já formado, mede também o
    CONFLITO FACTUAL — divergência numérica na mesma dimensão SI. É
    refinamento, não detector paralelo: o sujeito é o grupo de
    identificador forte que já existe, e por construção o detector não
    pode produzir mais grupos que o candidato genérico. Quem itera esta
    função **precisa filtrar por `f.rule`** — desde este PR ela emite dois
    códigos."""
    by_id: dict[str, list] = {}
    medidas: dict[str, list[dict]] = {}
    usos_ambiguos: dict[str, set[str]] = {}
    gaz = load_gazetteer(reader)
    for d in docs:
        x = d.meta.model_dump(exclude_none=True)
        report = analyze(d.body, gaz=gaz)     # MESMA passada de antes
        medidas[d.rel_path] = _medidas(report, d.body)
        for m in report.matches:
            if m.kind in _KINDS_DE_SUJEITO \
                    and m.subkind in CONTRADICTION_IDS \
                    and m.valid is not False:
                by_id.setdefault(m.canonical, []).append((d, x))
            elif m.kind == "entity" and m.confidence == "ambiguous" \
                    and d.meta.type != "authority_record":
                # mesma passada: onde o alias disputado é USADO. Sem isto o
                # finding diria que há conflito e não onde ele dói.
                # O próprio registro é DEFINIÇÃO, não uso — ele menciona o
                # termo que define por construção, e contá-lo faria o
                # finding apontar de volta para si mesmo
                usos_ambiguos.setdefault(m.surface.lower(),
                                         set()).add(d.rel_path)
    out: list[Finding] = _alias_conflitantes(gaz, usos_ambiguos)
    for ident, group in by_id.items():
        # F3-PR2 paga a dívida declarada no ADR-41.5 e confirmada pela
        # auditoria: `resolved = any(...)` silenciava o GRUPO INTEIRO assim
        # que UMA sucessão aparecesse nele. Com A, B e C compartilhando o
        # mesmo DOI, fundir A em B calava também o par (B, C) — sem que
        # aquela convivência tivesse sido tratada, e justamente no item de
        # maior valor epistêmico da fila (VoI 0.85).
        #
        # A relação de sucessão PARTICIONA o grupo: páginas ligadas por
        # supersede formam um bloco resolvido entre si; o conflito é o que
        # sobra ENTRE blocos. `invalid_at` tira a página do grupo — ela
        # declarou não valer mais, então não contradiz ninguém.
        vivas_no_grupo = [(d, x) for d, x in group if not x.get("invalid_at")]
        pages = {d.rel_path for d, _ in vivas_no_grupo}
        if len(pages) < 2:
            continue
        if len(_blocos_de_sucessao(vivas_no_grupo, pages)) < 2:
            continue
        group = vivas_no_grupo
        entrenched = _entrincheirada(group)
        out.append(Finding(
            "warn", "policy.contradiction_candidate", entrenched.rel_path,
            f"identificador {ident} em {len(pages)} páginas sem sucessão: "
            f"{sorted(pages)} — mais entrincheirada: {entrenched.rel_path}; "
            "resolva com supersede/invalid_at ou funda as páginas",
            meta={"identifier": ident, "pages": sorted(pages)}))

        # RFC-005 §3 — REFINAMENTO, não detector paralelo. Só chega aqui o
        # grupo que já passou pelas três guardas acima (invalid_at, len<2,
        # blocos de sucessão): a precisão é por construção, e o detector
        # NÃO PODE produzir mais grupos que o candidato genérico. Emitido
        # DEPOIS do candidato de propósito — há testes que indexam
        # `findings[0]` e a ordem por grupo é contrato de fato.
        #
        # UM finding por CONJUNTO DE PÁGINAS, não por dimensão. O primeiro
        # desenho emitia um por dimensão e isso era erro de granularidade
        # com consequência medida: dois findings do mesmo par produzem dois
        # itens de fila com o MESMO `pattern_key` (a chave só olha páginas),
        # e rejeitar um calava o outro — a dívida do ADR-41.5 que o F3-PR2
        # pagou, reintroduzida dentro do kind. A granularidade certa é a das
        # PÁGINAS porque é a dos ATOS: `edit`, `supersede`, `merge` e
        # `invalidate` operam sobre página, nunca sobre dimensão. Ninguém
        # resolve "o comprimento" e deixa "o tempo" pendente.
        por_paginas: dict[tuple, list[dict]] = {}
        for div in divergencias({p: medidas.get(p, []) for p in pages}):
            por_paginas.setdefault(tuple(sorted(div["pages"])), []).append(div)
        for envolvidas_paths, divs in sorted(por_paginas.items()):
            envolvidas = [it for it in group
                          if it[0].rel_path in envolvidas_paths]
            alvo = _entrincheirada(envolvidas)
            out.append(Finding(
                "warn", "policy.factual_conflict", alvo.rel_path,
                f"conflito factual sob o identificador {ident} — "
                + "; ".join(resumo(d) for d in divs)
                + "; confira o(s) número(s) nas duas páginas",
                meta={"identifier": ident,
                      "pages": list(envolvidas_paths),
                      "dims": [d["dim"] for d in divs],
                      "tolerance": divs[0]["tolerance"],
                      "divergences": divs}))
    return out


def check_quotations(docs, reader) -> list[Finding]:
    """Atribuição de citação (v1.2, porta do ADR-32 fechada): página que
    contém uma citação CONHECIDA do reference.db sem mencionar o autor
    em lugar nenhum do texto — ou está sem atribuição, ou atribuída a
    outra pessoa. Warn, nunca error: a curadoria decide. Custo: as
    normas vêm pré-computadas do banco; por página é 1 normalização do
    corpo + Q buscas de substring (Q = citações conhecidas)."""
    from ..okf.authorities import load_quotations
    quotations = load_quotations(reader)
    if not quotations:
        return []
    out: list[Finding] = []
    for d in docs:
        body_norm = " " + re.sub(r"[^a-z0-9]+", " ", d.body.lower()) + " "
        for q in quotations:
            if q["norm"] not in body_norm:
                continue
            surname = q["author"].lower().split()[-1]
            if re.sub(r"[^a-z0-9]+", " ", surname) in body_norm:
                continue                      # autor citado: ok
            out.append(Finding(
                "warn", "policy.quotation_attribution", d.rel_path,
                f"citação conhecida de {q['author']} "
                f"({q['source'] or 'fonte registrada'}) sem o autor no "
                f"texto — confira a atribuição",
                meta={"author": q["author"], "quote": q["quote"][:80]}))
    return out


def _section(body: str, name: str) -> str:
    m = re.search(rf"^#{{1,3}}\s*{name}\s*$(.*?)(?=^#{{1,3}}\s|\Z)",
                  body, re.M | re.S)
    return m.group(1) if m else ""
