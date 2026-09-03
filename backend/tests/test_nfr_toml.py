"""`nfr.toml` — o registro de requisitos não funcionais NÃO pode mentir.

Antes daqui os NFRs eram prosa com selo em docs/10 §5–§17, e o selo citava
ARQUIVOS ("segurança ✅ — harness/local_policy.py") onde nada do que ele
prometia vivia. A doc contradizia a si mesma sobre durabilidade (§5.2 proíbe
prometer RPO 0 sob synchronous=NORMAL; §15 promete RPO 0 após ACK para os
mesmos stores) e ninguém lia os PRAGMAs por teste.

Este arquivo dá ao registro o mesmo tratamento de `architecture.toml [gate]`:
- todo `verified_by` resolve para um teste que EXISTE na suíte (arquivo e
  função), senão o requisito está fingindo prova;
- `pinned` exige prova; `declared` exige dizer o que falta (`notes`);
- vocabulários fechados — status/level/category fora da lista quebram;
- e três requisitos ganham aqui a prova que não tinham (PRAGMAs aplicados,
  handshake 0600, loopback por default), porque um registro que só
  cataloga o que já era testado não muda nada.
"""
from __future__ import annotations

import re
import stat
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TESTS = Path(__file__).resolve().parent
_TOML = _ROOT / "nfr.toml"

LEVELS = {"guarantee", "premise", "target"}
STATUSES = {"pinned", "measured", "declared"}
CATEGORIES = {"durability", "consistency", "integrity", "queue", "retention",
              "slo", "scale", "security", "privacy", "offline",
              "reproducibility", "observability", "packaging",
              "accessibility", "i18n"}
_ID = re.compile(r"^NFR-[A-Z0-9]+-\d{3}$")


def _load() -> dict:
    return tomllib.loads(_TOML.read_text())


def _nfrs() -> list[dict]:
    return _load()["nfr"]


def _teste_existe(ref: str) -> bool:
    """`arquivo.py::função` ⇒ a função está DEFINIDA no arquivo; só
    `arquivo.py` ⇒ o arquivo existe. Regex sobre o fonte, não coleta do
    pytest: barato e sem efeito colateral."""
    arquivo, _, funcao = ref.partition("::")
    path = _TESTS / arquivo
    if not path.is_file():
        return False
    if not funcao:
        return True
    return re.search(rf"^def {re.escape(funcao)}\(", path.read_text(),
                     re.M) is not None


# ------------------------------------------------------------ estrutura
def test_registro_existe_e_declara_versao():
    data = _load()
    assert data["schema_version"] == 1
    assert data["registry"]["version"]
    assert (_ROOT / data["registry"]["doctrine"]).is_file()


def test_ids_unicos_e_no_formato():
    ids = [n["id"] for n in _nfrs()]
    assert len(ids) == len(set(ids)), "id de NFR repetido"
    fora = [i for i in ids if not _ID.match(i)]
    assert fora == [], f"ids fora do formato NFR-XXX-000: {fora}"


@pytest.mark.parametrize("nfr", _nfrs(), ids=lambda n: n["id"])
def test_vocabularios_fechados(nfr: dict):
    assert nfr["level"] in LEVELS, nfr["id"]
    assert nfr["status"] in STATUSES, nfr["id"]
    assert nfr["category"] in CATEGORIES, nfr["id"]
    assert nfr["scope"] == "S0", nfr["id"]
    assert nfr["statement"].strip(), nfr["id"]
    assert nfr["doc_anchor"].startswith("docs/10"), nfr["id"]


@pytest.mark.parametrize("nfr", _nfrs(), ids=lambda n: n["id"])
def test_todo_verified_by_resolve_para_teste_existente(nfr: dict):
    """A guarda central: citar teste que não existe é o mesmo selo falso
    que citar arquivo em vez de teste — só que mais difícil de ver."""
    fantasmas = [r for r in nfr["verified_by"] if not _teste_existe(r)]
    assert fantasmas == [], (
        f"{nfr['id']} cita teste inexistente: {fantasmas}")


@pytest.mark.parametrize("nfr", _nfrs(), ids=lambda n: n["id"])
def test_status_e_coerente_com_a_prova(nfr: dict):
    """pinned sem teste é decoração; declared sem notes é promessa vaga;
    measured sem measured_by não diz de onde veio o número."""
    if nfr["status"] == "pinned":
        assert nfr["verified_by"], f"{nfr['id']}: pinned sem verified_by"
    elif nfr["status"] == "declared":
        assert not nfr["verified_by"], (
            f"{nfr['id']}: declared com teste — então é pinned")
        assert nfr.get("notes", "").strip(), (
            f"{nfr['id']}: declared precisa dizer em `notes` o que falta")
    elif nfr["status"] == "measured":
        assert nfr.get("measured_by", "").strip(), (
            f"{nfr['id']}: measured sem measured_by")


def test_premissa_diz_o_que_nao_detecta():
    """`premise` é o nível honesto para o que o produto ASSUME e não vigia:
    precisa de `notes` explicando a consequência, senão vira garantia por
    osmose na próxima leitura."""
    sem = [n["id"] for n in _nfrs()
           if n["level"] == "premise" and not n.get("notes", "").strip()]
    assert sem == [], f"premissas sem notes: {sem}"


def test_agents_cita_o_registro_como_fonte_de_verdade():
    """AGENTS.md §6 lista as fontes de verdade; NFR sem lugar nela é
    requisito que o agente não sabe onde consultar."""
    agents = (_ROOT / "AGENTS.md").read_text()
    assert "nfr.toml" in agents


# --------------------------------------------- as provas que faltavam
def test_pragmas_declarados_sao_os_aplicados(tmp_path):
    """NFR-DUR-003: a política é uniforme (WAL + NORMAL) e a doc dizia
    duas coisas sobre ela. O teste fixa o que o código FAZ; se alguém
    introduzir a StoragePolicy por store, este teste e o registro mudam
    JUNTOS — que é o ponto."""
    from corpusmith.runtime.db import connect, reset_initialized
    reset_initialized()
    for nome in ("runtime.db", "index.db", "cognitive.db"):
        conn = connect(tmp_path / nome)
        try:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            # synchronous: 0=OFF 1=NORMAL 2=FULL 3=EXTRA
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1, (
                f"{nome}: synchronous mudou — atualize NFR-DUR-003")
        finally:
            conn.close()
    reset_initialized()


def test_handshake_nasce_0600(tmp_path):
    """NFR-SEC-001: o token da sessão fica num arquivo que só o dono lê.
    `chmod(0o600)` existia sem teste — configuração não é asserção."""
    from corpusmith.api.system import issue_token
    from corpusmith.settings import Settings
    s = Settings(home=tmp_path)
    token = issue_token(s)
    hs = s.app_support / "daemon.json"
    assert token and hs.is_file()
    assert stat.S_IMODE(hs.stat().st_mode) == 0o600
    assert token in hs.read_text()


def test_loopback_e_o_default():
    """NFR-SEC-002: nem Settings nem o compose expõem o daemon fora da
    máquina sem decisão explícita."""
    from corpusmith.settings import Settings
    assert Settings().server["host"] == "127.0.0.1"
    compose = (_ROOT / "docker-compose.yml").read_text()
    portas = re.findall(r'^\s*-\s*"?([\d.]+:)?\d+:\d+"?\s*$', compose, re.M)
    assert portas and all(p == "127.0.0.1:" for p in portas), (
        f"compose publica porta fora do loopback: {portas}")
