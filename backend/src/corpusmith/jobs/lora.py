"""Job `lora_train` (Manual Ap. C): fine-tuning procedural local (MLX/PEFT,
extra [ml]). Aqui: prepara o dataset a partir das páginas procedurais e
delega ao script externo configurado; o adapter ativo fica em
adapters/ACTIVE (consumido por /cockpit/memory)."""
from __future__ import annotations
import json
from ..okf.bundle import BundleReader
from ..settings import Settings

PROCEDURAL = {"runbook", "skill"}


def run(s: Settings, payload: dict, emit) -> dict:
    kb = s.path("knowledge")
    reader = BundleReader(kb / "bundle")
    samples = [{"page": d.rel_path, "title": d.meta.title, "text": d.body}
               for d in reader.iter_concepts() if d.meta.type in PROCEDURAL]
    dataset = s.path("adapters") / "dataset.jsonl"
    dataset.write_text("\n".join(json.dumps(x, ensure_ascii=False)
                                 for x in samples))
    emit("lora.dataset", {"samples": len(samples), "path": str(dataset)})
    if not samples:
        return {"samples": 0, "skipped": "nenhuma página procedural"}
    # treino de fato é opt-in: exige extra [ml] + configuração de script
    trainer = s.models.get("lora", {}).get("trainer")
    if not trainer:
        return {"samples": len(samples),
                "skipped": "models.lora.trainer não configurado"}
    import subprocess
    subprocess.run([trainer, str(dataset)], check=True)
    return {"samples": len(samples), "trained": True}
