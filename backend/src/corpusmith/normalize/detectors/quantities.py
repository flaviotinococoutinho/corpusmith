from __future__ import annotations
import re
from ..model import Match

# unidade → (exibição canônica, unidade SI, fator, dimensão)
UNITS: dict[str, tuple[str, str, float, str]] = {
    # comprimento / massa / tempo
    "km": ("km", "m", 1e3, "len"), "m": ("m", "m", 1.0, "len"),
    "cm": ("cm", "m", 1e-2, "len"), "mm": ("mm", "m", 1e-3, "len"),
    "nm": ("nm", "m", 1e-9, "len"), "mi": ("mi", "m", 1609.344, "len"),
    "ft": ("ft", "m", 0.3048, "len"), "in": ("in", "m", 0.0254, "len"),
    "kg": ("kg", "kg", 1.0, "mass"), "g": ("g", "kg", 1e-3, "mass"),
    "mg": ("mg", "kg", 1e-6, "mass"), "µg": ("µg", "kg", 1e-9, "mass"),
    "μg": ("µg", "kg", 1e-9, "mass"), "lb": ("lb", "kg", 0.45359237, "mass"),
    "oz": ("oz", "kg", 0.028349523125, "mass"),
    "ms": ("ms", "s", 1e-3, "time"), "s": ("s", "s", 1.0, "time"),
    "min": ("min", "s", 60.0, "time"), "h": ("h", "s", 3600.0, "time"),
    # dados / frequência / energia / temperatura / volume
    "KiB": ("KiB", "B", 2**10, "data"), "MiB": ("MiB", "B", 2**20, "data"),
    "GiB": ("GiB", "B", 2**30, "data"), "TiB": ("TiB", "B", 2**40, "data"),
    "KB": ("KB", "B", 1e3, "data"), "MB": ("MB", "B", 1e6, "data"),
    "GB": ("GB", "B", 1e9, "data"), "TB": ("TB", "B", 1e12, "data"),
    "Hz": ("Hz", "Hz", 1.0, "freq"), "kHz": ("kHz", "Hz", 1e3, "freq"),
    "MHz": ("MHz", "Hz", 1e6, "freq"), "GHz": ("GHz", "Hz", 1e9, "freq"),
    "W": ("W", "W", 1.0, "power"), "kW": ("kW", "W", 1e3, "power"),
    "kWh": ("kWh", "J", 3.6e6, "energy"), "V": ("V", "V", 1.0, "volt"),
    "°C": ("°C", "°C", 1.0, "temp"), "°F": ("°F", "°C", 1.0, "temp"),
    "L": ("L", "m3", 1e-3, "vol"), "mL": ("mL", "m3", 1e-6, "vol"),
    "%": ("%", "%", 1.0, "ratio"),
}
_ALTS = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
_NUM = r"[+-]?\d{1,3}(?:[  .]\d{3})+(?:[.,]\d+)?|[+-]?\d+(?:[.,]\d+)?"
RE_QTY = re.compile(rf"(?<![\w,.\-])({_NUM})\s*({_ALTS})(?![\w°%])")

def canonical_number(s: str, locale: str = "pt-BR") -> tuple[float, str]:
    """pt-BR: vírgula decimal; en: ponto decimal. Ambos os separadores presentes
    ⇒ o último é decimal (extracted). Um separador com 3 casas ⇒ milhar (inferred)."""
    s = s.replace(" ", "").replace(" ", "")
    conf = "extracted"
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in s:
        frac = len(s) - s.rfind(",") - 1
        if frac == 3 and not locale.startswith("pt"):
            s, conf = s.replace(",", ""), "inferred"
        else:
            s, conf = s.replace(",", "."), ("inferred" if frac == 3 else "extracted")
    elif s.count(".") >= 1:
        frac = len(s) - s.rfind(".") - 1
        if s.count(".") > 1 or (frac == 3 and locale.startswith("pt")):
            s, conf = s.replace(".", ""), "inferred"
    return float(s), conf

def detect(text: str, locale: str = "pt-BR") -> list[Match]:
    out: list[Match] = []
    for m in RE_QTY.finditer(text):
        try:
            value, conf = canonical_number(m.group(1), locale)
        except ValueError:
            continue
        disp, si_unit, factor, dim = UNITS[m.group(2)]
        if len(m.group(2)) == 1:                       # §1.6: 1 letra é arriscado
            conf = "inferred"
        si = value * factor if dim not in ("temp",) else None
        out.append(Match(m.start(), m.end(), "quantity", "qty", m.group(0),
                         f"{value:g} {disp}", confidence=conf,
                         data={"value": value, "unit": disp, "dim": dim,
                               **({"si": {"value": si, "unit": si_unit}}
                                  if si is not None else {})}))
    return out
