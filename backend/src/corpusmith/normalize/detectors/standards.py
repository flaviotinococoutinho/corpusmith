from __future__ import annotations
import re
from ..model import Match

RE_ISO  = re.compile(r"\b(ISO(?:/IEC|/TS|/TR|/IEEE)?)[\s\-]*(\d{3,6})"
                     r"(?:-(\d{1,3}))?(?::(\d{4}))?\b", re.I)
RE_NBR  = re.compile(r"\b(?:ABNT\s+)?NBR\s+(?:(ISO(?:/IEC)?)\s+)?(\d{3,6})"
                     r"(?::(\d{4}))?\b", re.I)
RE_RFC  = re.compile(r"\bRFC[\s\-]?0*(\d{1,5})\b", re.I)
RE_NIST = re.compile(r"\bNIST\s+SP\s*(\d{3})[\s\-]?(\d+[A-Za-z]?)"
                     r"(?:\s+Rev(?:\.|ision)?\s*(\d+))?\b", re.I)
RE_IEEE = re.compile(r"\bIEEE\s+(\d{1,4}(?:\.\d+)*[a-z]{0,2})\b")
RE_EU   = re.compile(r"\bRegula(?:tion|mento)\s*\(?(EU|UE)\)?\s*(?:n[ºo°.]*\s*)?"
                     r"(\d{4})/(\d+)\b", re.I)
# Circulares normativas (BCB, SUSEP…). "circular" é adjetivo comum em
# pt-BR ("referência circular", "economia circular") — precisão > recall:
# C maiúsculo obrigatório (sem re.I) E o número precisa de ponto de milhar
# OU do marcador nº. "Economia Circular 2030" não casa; "Circular 3.978" e
# "Circular nº 979" casam. O FP residual (título em caixa-alta seguido de
# nº) está declarado no contrato do factual_conflict.
RE_CIRC = re.compile(r"\bCircular\s+(?:(?:n[ºo°.]+\s*)(\d{1,4}(?:\.\d{3})*)"
                     r"|(\d{1,4}\.\d{3}))(?:/(\d{4}))?\b")

# reguladores/leis nomeados: casamento por alias, forma canônica curada
NAMED = {
    "lgpd": ("LGPD", "Lei nº 13.709/2018 (LGPD)"),
    "lei 13.709": ("LGPD", "Lei nº 13.709/2018 (LGPD)"),
    "lei 13709": ("LGPD", "Lei nº 13.709/2018 (LGPD)"),
    "gdpr": ("GDPR", "GDPR — Regulation (EU) 2016/679"),
    "hipaa": ("HIPAA", "HIPAA"),
    "sox": ("SOX", "SOX (Sarbanes–Oxley Act)"),
    "pci dss": ("PCI DSS", "PCI DSS"), "pci-dss": ("PCI DSS", "PCI DSS"),
    "basel iii": ("Basel III", "Basel III"), "basileia iii": ("Basel III", "Basel III"),
    "wcag": ("WCAG", "WCAG"), "owasp": ("OWASP", "OWASP"),
}
_NALTS = "|".join(sorted((re.escape(k) for k in NAMED), key=len, reverse=True))
RE_NAMED = re.compile(rf"(?<![\w./])({_NALTS})(?!\w|\.\w)", re.I)

def detect(text: str) -> list[Match]:
    out: list[Match] = []
    for m in RE_ISO.finditer(text):
        body = m.group(1).upper().replace(" ", "")
        canon = f"{body} {m.group(2)}" \
                + (f"-{m.group(3)}" if m.group(3) else "") \
                + (f":{m.group(4)}" if m.group(4) else "")
        out.append(Match(m.start(), m.end(), "standard", "iso",
                         m.group(0), canon))
    for m in RE_NBR.finditer(text):
        canon = "ABNT NBR " + (f"{m.group(1).upper()} " if m.group(1) else "") \
                + m.group(2) + (f":{m.group(3)}" if m.group(3) else "")
        out.append(Match(m.start(), m.end(), "standard", "nbr",
                         m.group(0), canon))
    for m in RE_RFC.finditer(text):
        out.append(Match(m.start(), m.end(), "standard", "rfc",
                         m.group(0), f"RFC {int(m.group(1))}"))
    for m in RE_NIST.finditer(text):
        canon = f"NIST SP {m.group(1)}-{m.group(2).upper()}" \
                + (f" Rev. {m.group(3)}" if m.group(3) else "")
        out.append(Match(m.start(), m.end(), "standard", "nist",
                         m.group(0), canon))
    for m in RE_IEEE.finditer(text):
        out.append(Match(m.start(), m.end(), "standard", "ieee",
                         m.group(0), f"IEEE {m.group(1)}"))
    for m in RE_EU.finditer(text):
        out.append(Match(m.start(), m.end(), "standard", "eu_reg", m.group(0),
                         f"Regulation (EU) {m.group(2)}/{m.group(3)}"))
    for m in RE_CIRC.finditer(text):
        numero = m.group(1) or m.group(2)
        canon = f"Circular {numero}" \
                + (f"/{m.group(3)}" if m.group(3) else "")
        out.append(Match(m.start(), m.end(), "standard", "circular",
                         m.group(0), canon))
    for m in RE_NAMED.finditer(text):
        key, canon = NAMED[m.group(1).lower()]
        out.append(Match(m.start(), m.end(), "standard", "regulator",
                         m.group(0), canon, data={"key": key}))
    return out
