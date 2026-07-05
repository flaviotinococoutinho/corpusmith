from __future__ import annotations
import re
from ..model import Match

# ---------- validadores (dígitos verificadores = anti-alucinação, §1.3) ----------
def _digits(s: str) -> list[int]:
    return [int(c) for c in re.sub(r"\D", "", s)]

def valid_cpf(s: str) -> bool:
    d = _digits(s)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):                       # DV1: pesos 10..2 · DV2: pesos 11..2
        if (sum(d[i] * (n + 1 - i) for i in range(n)) * 10) % 11 % 10 != d[n]:
            return False
    return True

_CNPJ_W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_W2 = [6] + _CNPJ_W1

def valid_cnpj(s: str) -> bool:
    """Aceita o CNPJ numérico clássico E o alfanumérico (vigente a partir de
    jul/2026): 12 posições [A-Z0-9] + 2 DVs numéricos, valor = ord(ch) - 48."""
    x = re.sub(r"[./\- ]", "", s.strip().upper())
    if not re.fullmatch(r"[A-Z0-9]{12}\d{2}", x) or len(set(x)) == 1:
        return False
    v = [ord(c) - 48 for c in x]
    for w, pos in ((_CNPJ_W1, 12), (_CNPJ_W2, 13)):
        r = sum(a * b for a, b in zip(v[:pos], w)) % 11
        if v[pos] != (0 if r < 2 else 11 - r):
            return False
    return True

def valid_isbn(s: str) -> bool:
    x = re.sub(r"[\- ]", "", s).upper()
    if re.fullmatch(r"\d{9}[\dX]", x):      # ISBN-10: mod 11, X = 10
        return sum((10 - i) * (10 if c == "X" else int(c))
                   for i, c in enumerate(x)) % 11 == 0
    if re.fullmatch(r"97[89]\d{10}", x):    # ISBN-13: pesos 1/3 alternados, mod 10
        return sum(int(c) * (1 if i % 2 == 0 else 3)
                   for i, c in enumerate(x)) % 10 == 0
    return False

def valid_issn(s: str) -> bool:
    x = s.replace("-", "").upper()
    if not re.fullmatch(r"\d{7}[\dX]", x):
        return False
    dv = (11 - sum(int(c) * (8 - i) for i, c in enumerate(x[:7])) % 11) % 11
    return x[7] == ("X" if dv == 10 else str(dv))

def valid_orcid(s: str) -> bool:            # ISNI MOD 11-2
    x = re.sub(r"[\- ]", "", s).upper()
    if not re.fullmatch(r"\d{15}[\dX]", x):
        return False
    total = 0
    for c in x[:15]:
        total = (total + int(c)) * 2
    chk = (12 - total % 11) % 11
    return x[15] == ("X" if chk == 10 else str(chk))

def valid_iban(s: str) -> bool:             # mod 97 (ISO 13616)
    x = re.sub(r"\s", "", s).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", x):
        return False
    return int("".join(str(int(c, 36)) for c in x[4:] + x[:4])) % 97 == 1

def valid_ean13(s: str) -> bool:
    d = _digits(s)
    return len(d) == 13 and sum(v * (1 if i % 2 == 0 else 3)
                                for i, v in enumerate(d)) % 10 == 0

# ---------- padrões ----------
RE_CPF   = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
RE_CNPJ  = re.compile(r"\b[A-Z0-9]{2}\.?[A-Z0-9]{3}\.?[A-Z0-9]{3}/?[A-Z0-9]{4}-?\d{2}\b")
RE_DOI   = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>)\]]+")
RE_ARXIV = re.compile(r"\barXiv[:\s]*(\d{4}\.\d{4,5})(v\d+)?\b", re.I)
RE_ISBN  = re.compile(r"\bISBN[:\s]*((?:97[89][\- ]?)?\d{1,5}[\- ]?\d{1,7}"
                      r"[\- ]?\d{1,7}[\- ]?[\dXx])\b")
RE_ISSN  = re.compile(r"\bISSN[:\s]*(\d{4}-\d{3}[\dXx])\b")
RE_ORCID = re.compile(r"\b(\d{4}-\d{4}-\d{4}-\d{3}[\dXx])\b")
RE_CVE   = re.compile(r"\bCVE-(\d{4})-(\d{4,7})\b", re.I)
RE_UUID  = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}"
                      r"-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I)
RE_SEMVER = re.compile(r"(?<![\w.])v?(\d+)\.(\d+)\.(\d+)"
                       r"(?:-[0-9A-Za-z.\-]+)?(?:\+[0-9A-Za-z.\-]+)?(?![\w.])")
RE_IBAN  = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
# SHA de commit: MESMO contexto exigido pelo policy.bad_commit_ref (fonte única, §4.3)
RE_GIT_SHA_CTX = re.compile(r"(?:commit|stale_as_of|detected_at_commit)\D{0,4}"
                            r"([0-9a-f]{7,40})", re.I)

def _fmt_cpf(x: str) -> str:
    d = re.sub(r"\D", "", x)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"

def _fmt_cnpj(x: str) -> str:
    d = re.sub(r"[./\- ]", "", x).upper()
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"

def detect(text: str) -> list[Match]:
    out: list[Match] = []

    def add(m, sub, canonical, *, valid=None, conf="extracted", data=None):
        out.append(Match(m.start(), m.end(), "identifier", sub, m.group(0),
                         canonical, confidence=conf, valid=valid,
                         data=data or {}))

    for m in RE_CPF.finditer(text):
        add(m, "cpf", _fmt_cpf(m.group(0)), valid=valid_cpf(m.group(0)),
            data={"sensitive": True})
    for m in RE_CNPJ.finditer(text):
        if any(c.isdigit() for c in m.group(0)):        # descarta siglas puras
            add(m, "cnpj", _fmt_cnpj(m.group(0)), valid=valid_cnpj(m.group(0)),
                data={"sensitive": True})
    for m in RE_DOI.finditer(text):
        doi = m.group(0).rstrip(".,;:")
        add(m, "doi", doi.lower(),
            data={"url": f"https://doi.org/{doi.lower()}"})
    for m in RE_ARXIV.finditer(text):
        add(m, "arxiv", f"arXiv:{m.group(1)}{m.group(2) or ''}")
    for m in RE_ISBN.finditer(text):
        add(m, "isbn", "ISBN " + re.sub(r"[\- ]", "", m.group(1)).upper(),
            valid=valid_isbn(m.group(1)))
    for m in RE_ISSN.finditer(text):
        add(m, "issn", "ISSN " + m.group(1).upper(), valid=valid_issn(m.group(1)))
    for m in RE_ORCID.finditer(text):
        if valid_orcid(m.group(1)):                     # sem prefixo textual ⇒ só se DV bate
            add(m, "orcid", "ORCID " + m.group(1).upper(), valid=True)
    for m in RE_CVE.finditer(text):
        add(m, "cve", f"CVE-{m.group(1)}-{m.group(2)}")
    for m in RE_UUID.finditer(text):
        add(m, "uuid", m.group(0).lower())
    for m in RE_SEMVER.finditer(text):
        add(m, "semver", f"{m.group(1)}.{m.group(2)}.{m.group(3)}",
            conf="inferred")                            # anexo apenas; nunca reescreve
    for m in RE_IBAN.finditer(text):
        if valid_iban(m.group(0)):                      # só com mod-97 válido (FP alto)
            add(m, "iban", re.sub(r"\s", "", m.group(0)).upper(),
                valid=True, data={"sensitive": True})
    for m in RE_GIT_SHA_CTX.finditer(text):
        add(m, "git_sha", m.group(1).lower())
    return out
