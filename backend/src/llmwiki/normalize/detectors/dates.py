from __future__ import annotations
import re, unicodedata
from datetime import date
from ..model import Match

_M_PT = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
         "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
         "novembro": 11, "dezembro": 12}
_M_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
         "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

RE_ISO = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:Z|[+-]\d{2}:?\d{2})?)?\b")
RE_NUM = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
RE_PT  = re.compile(r"\b(\d{1,2})\s*º?\s*de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})\b", re.I)
RE_MDY = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
                    r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")
RE_DMY = re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                    r"[a-z]*\.?\s+(\d{4})\b")
RE_YM  = re.compile(r"\b(\d{4})-(\d{2})\b(?!-)")          # precisão reduzida ISO 8601

def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def _numeric(a: int, b: int, y: int, locale: str):
    if a > 12 and b <= 12:   return a, b, "extracted"
    if b > 12 and a <= 12:   return b, a, "extracted"
    if a > 12 and b > 12:    return None
    d, m = (a, b) if locale.startswith("pt") else (b, a)
    return d, m, ("extracted" if a == b else "inferred")

def _mk(m, iso: str, conf: str) -> Match:
    return Match(m.start(), m.end(), "date", "date", m.group(0), iso,
                 confidence=conf, data={"iso": iso})

def detect(text: str, locale: str = "pt-BR") -> list[Match]:
    out: list[Match] = []
    for m in RE_ISO.finditer(text):
        out.append(_mk(m, m.group(0).replace(" ", "T"), "extracted"))
    for m in RE_NUM.finditer(text):
        r = _numeric(int(m[1]), int(m[2]), int(m[3]), locale)
        if not r:
            out.append(Match(m.start(), m.end(), "date", "date", m.group(0),
                             m.group(0), confidence="ambiguous"))
            continue
        d, mo, conf = r
        try:
            out.append(_mk(m, date(int(m[3]), mo, d).isoformat(), conf))
        except ValueError:
            pass
    for m in RE_PT.finditer(text):
        mo = _M_PT.get(_fold(m[2]))
        if mo:
            try:
                out.append(_mk(m, date(int(m[3]), mo, int(m[1])).isoformat(),
                               "extracted"))
            except ValueError:
                pass
    for pat, di, mi in ((RE_MDY, 2, 1), (RE_DMY, 1, 2)):
        for m in pat.finditer(text):
            mo = _M_EN[m[mi].lower()[:3]]
            try:
                out.append(_mk(m, date(int(m[3]), mo, int(m[di])).isoformat(),
                               "extracted"))
            except ValueError:
                pass
    for m in RE_YM.finditer(text):
        y, mo = int(m[1]), int(m[2])
        if 1 <= mo <= 12 and 1500 <= y <= 2200:
            out.append(_mk(m, f"{y:04d}-{mo:02d}", "inferred"))
    return out
