from __future__ import annotations
import re, unicodedata
from ..model import Match

# seed mínimo (nome → alpha-2); estenda por authority_record (authority: country)
COUNTRIES = {
    "brasil": "BR", "brazil": "BR", "estados unidos": "US", "united states": "US",
    "eua": "US", "usa": "US", "u.s.": "US", "reino unido": "GB",
    "united kingdom": "GB", "uk": "GB", "alemanha": "DE", "germany": "DE",
    "franca": "FR", "france": "FR", "portugal": "PT", "espanha": "ES",
    "spain": "ES", "italia": "IT", "italy": "IT", "japao": "JP", "japan": "JP",
    "china": "CN", "india": "IN", "canada": "CA", "mexico": "MX",
    "argentina": "AR", "chile": "CL", "colombia": "CO", "peru": "PE",
    "uruguai": "UY", "uruguay": "UY", "paraguai": "PY", "paraguay": "PY",
    "holanda": "NL", "netherlands": "NL", "paises baixos": "NL", "suica": "CH",
    "switzerland": "CH", "suecia": "SE", "sweden": "SE", "noruega": "NO",
    "norway": "NO", "australia": "AU", "coreia do sul": "KR", "south korea": "KR",
    "russia": "RU", "irlanda": "IE", "ireland": "IE", "israel": "IL",
    "singapura": "SG", "singapore": "SG",
}
DISPLAY = {"BR": "Brasil", "US": "Estados Unidos", "GB": "Reino Unido",
           "DE": "Alemanha", "FR": "França", "NL": "Países Baixos"}  # fallback: título

def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

_CALTS = "|".join(sorted((re.escape(k) for k in COUNTRIES), key=len, reverse=True))
RE_COUNTRY = re.compile(rf"(?<![\w./])({_CALTS})(?!\w)", re.I)
RE_UF  = re.compile(r",\s*(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|"
                    r"PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)(?=[\s,.)]|$)")
RE_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")
RE_LOGR = re.compile(r"\b(Rua|Av\.?|Avenida|Alameda|Travessa|Rodovia|Estrada|"
                     r"Praça)\s+([^,\n]{3,60}),\s*(\d{1,6}|s/n)\b", re.I)

def detect(text: str) -> list[Match]:
    out: list[Match] = []
    for m in RE_COUNTRY.finditer(text):
        a2 = COUNTRIES[_fold(m.group(1))]
        out.append(Match(m.start(), m.end(), "geo", "country", m.group(0),
                         DISPLAY.get(a2, m.group(1).title()),
                         data={"alpha2": a2}))
    for m in RE_UF.finditer(text):                    # âncora "…, SP" — §1.4/§1.6
        out.append(Match(m.start(1), m.end(1), "geo", "uf", m.group(1),
                         m.group(1), data={"country": "BR"}))
    for m in RE_CEP.finditer(text):
        conf = "extracted" if "-" in m.group(0) else "ambiguous"
        out.append(Match(m.start(), m.end(), "geo", "cep", m.group(0),
                         f"{m.group(1)}-{m.group(2)}", confidence=conf))
    for m in RE_LOGR.finditer(text):
        out.append(Match(m.start(), m.end(), "geo", "address", m.group(0),
                         m.group(0), confidence="inferred",
                         data={"via": m.group(1), "nome": m.group(2).strip(),
                               "numero": m.group(3)}))
    return out
