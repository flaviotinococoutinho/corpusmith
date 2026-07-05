"""Job `ocr` (Manual Ap. C): OCR de PDFs escaneados via tesseract quando
instalado no sistema; caso contrário falha com mensagem acionável."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract não instalado (brew install tesseract)")
    src = Path(payload["path"]).expanduser()
    out = src.with_suffix(".ocr.txt")
    subprocess.run(["tesseract", str(src), str(out.with_suffix(""))],
                   check=True, capture_output=True)
    return {"output": str(out)}
