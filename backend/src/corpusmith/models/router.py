"""Roteador de modelos (Parte V §6 + ADR-42).

Decide LOCAL (Ollama) × API (Anthropic) respeitando:
1. privacidade — `local_only` NUNCA vai para API;
2. orçamento — Governor bloqueia quando o dia estourou;
3. disponibilidade — sem modelo utilizável e sem chave, levanta
   ModelUnavailable (quem chama decide o fallback extrativo).

`models.local.chat` é uma ESCADA de preferência (ADR-42): a primeira
entrada que estiver INSTALADA e couber no orçamento de memória ganha.
Duas regras que o formato fixo anterior não conseguia expressar:

- o roteador NUNCA baixa modelo sozinho — uma consulta não pode disparar
  download de gigabytes; aquisição é ato explícito (`pull_models.sh`);
- pedir um modelo maior que a RAM não é otimismo, é paginação até a
  inutilidade — por isso o orçamento (`memory_fraction`) veta.

Falha de modelo (ausente, 404, Ollama offline) vira SEMPRE
`ModelUnavailable`, nunca `HTTPStatusError` cru: o contrato de
degradação dos chamadores depende desse tipo.

Retorno de `complete`: {"text", "via", "usd"} — `via` no formato
"local:<modelo>" | "api:<modelo>", que alimenta `generated_via` e nomeia
o modelo EFETIVAMENTE usado, não o preferido.
"""
from __future__ import annotations
import os
import httpx
from ..runtime.governor import Governor
from ..settings import Settings

# preço aproximado por MTok (entrada, saída) — só para o ledger local
_API_PRICE = {"default": (1.0, 5.0)}

# fração da RAM total liberada para os pesos do modelo. O resto é do
# sistema, do cache de contexto (KV) e do próprio cockpit.
_DEFAULT_MEMORY_FRACTION = 0.6

# sentinela: distingue "ainda não resolvi" de "resolvi e não achei nada"
_UNSET = object()


class ModelUnavailable(RuntimeError):
    pass


def _total_ram_bytes() -> int:
    """RAM física total. Isolado em função para o teste substituir."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return 0


class ModelRouter:
    def __init__(self, s: Settings, gov: Governor | None = None):
        self.s = s
        self.gov = gov
        self._resolved: str | None | object = _UNSET

    # ------------------------------------------------------------- helpers
    def _ollama_base(self) -> str:
        return self.s.models["local"].get("base_url", "http://127.0.0.1:11434")

    def _chat_ladder(self) -> list[str]:
        """Aceita string (config antiga) ou lista (escada, ADR-42)."""
        chat = self.s.models["local"].get("chat", [])
        return [chat] if isinstance(chat, str) else list(chat)

    def installed_models(self) -> dict[str, int]:
        """{nome: bytes} do que o Ollama já tem em disco. Só LEITURA."""
        try:
            r = httpx.get(self._ollama_base() + "/api/tags", timeout=1.5)
            r.raise_for_status()
            return {m["name"]: int(m.get("size", 0))
                    for m in r.json().get("models", [])}
        except Exception:
            return {}

    def memory_budget_bytes(self) -> int:
        fraction = float(self.s.models["local"].get(
            "memory_fraction", _DEFAULT_MEMORY_FRACTION))
        return int(_total_ram_bytes() * fraction)

    def resolve_chat(self) -> str | None:
        """Primeiro da escada que está instalado E cabe na memória.

        Devolve o nome COMO O OLLAMA O CONHECE (com `:latest` quando for
        o caso), para que a chamada e o `via` falem do mesmo objeto.
        """
        if self._resolved is not _UNSET:
            return self._resolved            # type: ignore[return-value]
        installed = self.installed_models()
        budget = self.memory_budget_bytes()
        chosen: str | None = None
        for candidate in self._chat_ladder():
            for name in (candidate, f"{candidate}:latest"):
                if name not in installed:
                    continue
                if budget and installed[name] > budget:
                    break                    # cabe na máquina? não. próximo.
                chosen = name
                break
            if chosen:
                break
        self._resolved = chosen
        return chosen

    def local_available(self) -> bool:
        """Disponível = existe modelo de chat utilizável, não apenas um
        Ollama que atende no socket. Era essa a lacuna: Ollama de pé com
        o modelo ausente passava por 'disponível' e estourava adiante."""
        return self.resolve_chat() is not None

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
        model = self.resolve_chat()
        if model is None:
            raise ModelUnavailable(
                "nenhum modelo local utilizável: a escada "
                f"{self._chat_ladder()} não tem entrada instalada que caiba "
                f"em {self.memory_budget_bytes() / 1e9:.1f} GB "
                "(baixe um com scripts/pull_models.sh)")
        try:
            r = httpx.post(self._ollama_base() + "/api/generate", json={
                "model": model, "prompt": prompt, "system": system or "",
                "stream": False, "options": {"num_predict": max_tokens},
            }, timeout=300)
            r.raise_for_status()
            payload = r.json()
            text = payload.get("response", "")
        except Exception as e:
            # transporte não atravessa a fronteira: quem chama sabe
            # degradar por ModelUnavailable, não por HTTPStatusError.
            raise ModelUnavailable(f"modelo local {model} falhou: {e}") from e
        if not text.strip():
            # Variante "thinking" com orçamento curto gasta todo o
            # num_predict no raciocínio e devolve `response` vazio
            # (done_reason=length). Resposta vazia NÃO é resposta: virar
            # ModelUnavailable faz o chamador degradar para o extrativo em
            # vez de propagar um texto vazio como se fosse síntese.
            raise ModelUnavailable(
                f"modelo local {model} devolveu resposta vazia "
                f"(done_reason={payload.get('done_reason')!r}; "
                f"num_predict={max_tokens} pode ser curto demais para "
                "variante de raciocínio)")
        return {"text": text, "via": f"local:{model}", "usd": 0.0}

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
            try:
                r = httpx.post(self._ollama_base() + "/api/embeddings",
                               json={"model": model, "prompt": t}, timeout=120)
                r.raise_for_status()
                out.append(r.json()["embedding"])
            except Exception as e:
                # mesma regra do _local: erro de modelo é ModelUnavailable,
                # com código estável para o job terminar legível.
                raise ModelUnavailable(
                    f"modelo de embedding {model} falhou: {e}") from e
        return out
