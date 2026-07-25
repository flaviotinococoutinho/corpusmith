"""Links do bundle — o ÚNICO parser de link do produto (F1-PR4).

`MD_LINK` alimenta três coisas de uma vez: as arestas de `graph_edges`
(`retrieval/fts.py`), a regra `okf.broken_link` do conformance e a
`policy.release_broken_link`. Qualquer mudança aqui é mudança de
comportamento do produto inteiro — por isso vem acompanhada de bump de
`INDEX_GENERATION` (INV-002).

**Atributo de título** (v1.8.2): a sintaxe padrão do Markdown
`[texto](alvo "titulo")` NÃO casava — a classe do alvo para no espaço.
Consequência MEDIDA: escrever esse formato fazia a aresta desaparecer de
`graph_edges` em silêncio. Agora casa, e o título fica em `Link.title`
para a Fase 5 usar como relação tipada (`rel:refines`). A mudança é
ESTRITAMENTE ADITIVA: verificado caso a caso que tudo o que já casava
produz exatamente o mesmo `(text, target)`.

**Grupos NOMEADOS são obrigatórios.** Capturar o `!` da imagem acrescenta
um grupo à esquerda e renumeraria os posicionais: `parse_links` passaria a
ler `!` como texto e o texto como alvo, em silêncio. Há teste fixando
`groupindex`.

**A máscara é a outra metade.** `normalize/masking.py` tem a SEGUNDA cópia
deste padrão, e é ela que marca o alvo como região que nenhum detector
pode tocar. Enquanto ela não conhecesse o formato anotado, `rewrite()`
CORROMPIA o alvo no canônico (medido: `/p.md#k8s` virava
`/p.md#Kubernetes`). As duas cópias mudam juntas, e um teste PIN
comportamental impede que voltem a divergir.
"""
from __future__ import annotations
import posixpath, re
from dataclasses import dataclass

# `bang` captura o '!' da imagem (ninguém consome ainda — imagem seguir
# virando "aresta" é dívida DECLARADA, não regressão deste PR); `title` é
# o atributo padrão do Markdown. O título NÃO atravessa linha: sem essa
# barreira, aspas soltas em linhas diferentes da prosa seriam engolidas.
MD_LINK = re.compile(
    r'(?P<bang>!)?\[(?P<text>[^\]]*)\]'
    r'\((?P<target>[^)\s]+)(?:[ \t]+"(?P<title>(?:[^"\\\n]|\\.)*)"[ \t]*)?\)')
WIKILINK = re.compile(r"\[\[([^\]#|]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
_EXTERNAL = ("http://", "https://", "mailto:", "urn:", "ftp://")
_REL = re.compile(r"^rel:([a-z_]+)$")

@dataclass
class Link:
    text: str
    target: str
    kind: str                              # "markdown" | "wikilink"
    title: str | None = None               # atributo do Markdown (v1.8.2)

    @property
    def rel(self) -> str | None:
        """Relação tipada DERIVADA do título (`rel:refines` ⇒ `refines`).
        Derivada e não armazenada: o vocabulário é decisão da Fase 5 e
        pode mudar sem migrar nada do canônico."""
        found = _REL.match(self.title or "")
        return found.group(1) if found else None

def parse_links(body: str) -> list[Link]:
    out = [Link(m.group("text"), m.group("target"), "markdown",
                m.group("title"))
           for m in MD_LINK.finditer(body)]
    out += [Link(m.group(2) or m.group(1).strip(), m.group(1).strip(), "wikilink")
            for m in WIKILINK.finditer(body)]
    return out

def is_internal(target: str) -> bool:
    return not target.startswith(_EXTERNAL) and not target.startswith("#")

def resolve(target: str, from_rel: str) -> str:
    t = target.split("#")[0]
    rel = t.lstrip("/") if t.startswith("/") else posixpath.normpath(
        posixpath.join(posixpath.dirname(from_rel), t))
    return rel if rel.endswith(".md") else rel + ".md"

def safe_link_text(title: str) -> str:
    """Texto de link que o próprio parser consegue reler.

    `[` e `]` no texto quebram o casamento — medido: `md_link('Array[] em
    Go', p)` produzia ZERO links, ou seja, os bytes entravam no canônico,
    o Harness aprovava e a aresta nunca existia. Quebra de linha idem.
    Vazio cai para travessão: texto vazio é link legítimo mas ilegível."""
    limpo = title.replace("[", "(").replace("]", ")")
    limpo = " ".join(limpo.split())          # colapsa quebras e espaços
    return limpo or "—"

def md_link(title: str, rel_path: str, rel: str | None = None) -> str:
    """Emite o link canônico. Sem `rel`, byte-idêntico ao formato antigo."""
    texto = safe_link_text(title)
    if rel:
        return f'[{texto}](/{rel_path} "rel:{rel}")'
    return f"[{texto}](/{rel_path})"

def rewrite_wikilinks(body: str, resolve_title) -> str:
    def sub(m: re.Match) -> str:
        target, alias = m.group(1).strip(), m.group(2)
        rel = resolve_title(target)
        return md_link(alias or target, rel) if rel else m.group(0)
    return WIKILINK.sub(sub, body)
