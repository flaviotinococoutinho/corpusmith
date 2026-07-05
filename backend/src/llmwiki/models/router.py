"""Roteador de modelos (Parte V §6).

Decide LOCAL (Ollama) × API (Anthropic) respeitando:
1. privacidade — `local_only` NUNCA vai para API;
2. orçamento — Governor bloqueia quando o dia estourou;
3. disponibilidade — sem Ollama e sem chave, levanta ModelUnavailable
   (quem chama decide o fallback extrativo).

Retorno de `complete`: {"text", "via", "usd"} — `via` no formato
"local:<modelo>" | "api:<modelo>", que alimenta `generated_via`.
"""
from __future__ import annotations
import os
import httpx
from ..runtime.governor import Governor
from ..settings import Settings

# preço aproximado por MTok (entrada, saída) — só para o ledger local
_API_PRICE = {"default": (1.0, 5.0)}


class ModelUnavailable(RuntimeError):
    pass


class ModelRouter:
    def __init__(self, s: Settings, gov: Governor | None = None):
        self.s = s
        self.gov = gov

    # ------------------------------------------------------------- helpers
    def _ollama_base(self) -> str:
        return self.s.models["local"].get("base_url", "http://127.0.0.1:11434")

    def local_available(self) -> bool:
        try:
            httpx.get(self._ollama_base() + "/api/tags", timeout=1.5)
            return True
        except Exception:
            return False

    def api_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY")) and \
            (self.gov is None or self.gov.allow_api())

    # ------------------------------------------------------------ complete
    def complete(self, prompt: str, *, privacy: str = "local_only",
                 system: str | None = None, deep: bool = False,
                 prefer_local: bool = True, max_tokens: int = 1024) -> dict:
        want_api = privacy == "api_allowed" and (deep or not prefer_local)
        if want_api and self.api_available():
            return self._api(prompt, system, max_tokens)
        if self.local_available():
            return self._local(prompt, system, max_tokens)
        if privacy == "api_allowed" and self.api_available():
            return self._api(prompt, system, max_tokens)
        raise ModelUnavailable(
            "nenhum modelo disponível (Ollama offline; API bloqueada por "
            "privacidade, orçamento ou chave ausente)")

    def _local(self, prompt: str, system: str | None, max_tokens: int) -> dict:
        model = self.s.models["local"].get("chat", "qwen2.5:7b-instruct")
        r = httpx.post(self._ollama_base() + "/api/generate", json={
            "model": model, "prompt": prompt, "system": system or "",
            "stream": False, "options": {"num_predict": max_tokens},
        }, timeout=300)
        r.raise_for_status()
        return {"text": r.json().get("response", ""),
                "via": f"local:{model}", "usd": 0.0}

    def _api(self, prompt: str, system: str | None, max_tokens: int) -> dict:
        model = self.s.models["api"].get("chat", "claude-haiku-4-5-20251001")
        body = {"model": model, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        r = httpx.post("https://api.anthropic.com/v1/messages", json=body,
                       headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                                "anthropic-version": "2023-06-01"},
                       timeout=120)
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage", {})
        pin, pout = _API_PRICE["default"]
        usd = (usage.get("input_tokens", 0) * pin
               + usage.get("output_tokens", 0) * pout) / 1_000_000
        if self.gov:
            self.gov.record(provider="anthropic", model=model, usd=usd,
                            tokens_in=usage.get("input_tokens", 0),
                            tokens_out=usage.get("output_tokens", 0))
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return {"text": text, "via": f"api:{model}", "usd": usd}

    # ------------------------------------------------------------- embed
    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self.s.models["local"].get("embed", "nomic-embed-text")
        out: list[list[float]] = []
        for t in texts:
            r = httpx.post(self._ollama_base() + "/api/embeddings",
                           json={"model": model, "prompt": t}, timeout=120)
            r.raise_for_status()
            out.append(r.json()["embedding"])
        return out
