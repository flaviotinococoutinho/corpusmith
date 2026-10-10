"""Os dois blocos do projeto que o índice achou SEM prova direta.

A primeira execução de `ontology lint` com §4 (ADR-60) devolveu dois
avisos `ontology.block_unproven`: nenhum arquivo de `backend/tests/`
importava `daemon` nem `ingestion`. O daemon só era exercitado pela perna
`package` da CI (o binário empacotado sobe e responde) e a extração, só
de passagem, por quem a chamava. Cada teste abaixo prende o CONTRATO que o
módulo declara na própria docstring — não a sua implementação.
"""
from __future__ import annotations

import json
import stat

import pytest

from corpusmith.settings import Settings


# ============================================================ ingestion
def test_markdown_e_texto_sao_lidos_direto(tmp_path):
    from corpusmith.ingestion.extract import extract
    (tmp_path / "a.md").write_text("# Título\n\ncorpo\n")
    (tmp_path / "b.TXT").write_text("linha")
    assert extract(tmp_path / "a.md") == "# Título\n\ncorpo\n"
    assert extract(tmp_path / "b.TXT") == "linha"     # sufixo sem caixa


def test_formato_desconhecido_e_erro_controlado(tmp_path):
    """Erro com código estável (AGENTS §9), nunca traceback de I/O."""
    from corpusmith.ingestion.extract import ExtractError, extract
    alvo = tmp_path / "planilha.xlsx"
    alvo.write_bytes(b"PK")
    with pytest.raises(ExtractError, match="formato não suportado: .xlsx"):
        extract(alvo)


@pytest.mark.parametrize("sufixo", [".pdf", ".epub"])
def test_parser_ausente_ou_arquivo_invalido_vira_extract_error(tmp_path,
                                                               sufixo):
    """O parser AGPL roda em subprocesso (fora do binário, §8.1). Sem o
    extra `[parsers]` — o caso da CI — OU com um arquivo que não é do
    formato, o subprocesso falha; o contrato é que isso chegue como
    `ExtractError` nomeando o arquivo, e não como exceção crua."""
    from corpusmith.ingestion.extract import ExtractError, extract
    alvo = tmp_path / f"falso{sufixo}"
    alvo.write_text("isto não é um documento binário")
    with pytest.raises(ExtractError, match=f"falso{sufixo}"):
        extract(alvo)


# =============================================================== daemon
def test_daemon_compoe_sobe_e_desmonta_limpo(tmp_path, monkeypatch):
    """O ciclo que `daemon.main()` promete: bootstrap idempotente, handshake
    com token e permissão 0600 ENQUANTO serve, worker vivo — e, no
    shutdown limpo, worker parado e handshake retirado (senão o CLI e o
    Electron acham um daemon que não existe). `uvicorn.run` é o único
    ponto substituído: tudo antes e depois dele roda de verdade."""
    from corpusmith import daemon

    monkeypatch.setenv("CORPUSMITH_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CORPUSMITH_CONFIG", raising=False)
    monkeypatch.delenv("LLMWIKI_CONFIG", raising=False)
    criados = []

    class _Espia(daemon.Worker):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            criados.append(self)

    visto: dict = {}

    def _servir(app, host, port, log_level):
        handshake = Settings.load().app_support / "daemon.json"
        visto["handshake"] = json.loads(handshake.read_text())
        visto["modo"] = stat.S_IMODE(handshake.stat().st_mode)
        visto["rotas"] = {getattr(r, "path", "") for r in app.routes}
        visto["worker_vivo"] = criados[0].is_alive()
        visto["host"] = host

    monkeypatch.setattr(daemon, "Worker", _Espia)
    monkeypatch.setattr(daemon.uvicorn, "run", _servir)
    daemon.main()

    assert visto["handshake"]["token"] and visto["modo"] == 0o600
    assert visto["host"] == "127.0.0.1", "o daemon é local por construção"
    assert {"/health", "/health/full"} <= visto["rotas"]
    assert visto["worker_vivo"]
    criados[0].join(timeout=10)
    assert not criados[0].is_alive(), "shutdown limpo deixou o worker vivo"
    app_support = Settings.load().app_support
    assert not (app_support / "daemon.json").exists(), (
        "handshake órfão depois de shutdown LIMPO")
    assert (app_support / "runtime.db").is_file()
    assert (app_support / "index.db").is_file()
