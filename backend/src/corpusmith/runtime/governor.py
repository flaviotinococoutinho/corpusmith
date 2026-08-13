"""Governor de custos de API (Parte V §5.6).

Orçamento diário em USD; toda chamada de API registra no ledger e o
governor bloqueia novas chamadas quando o orçamento do dia acaba.
"""
from __future__ import annotations
import time
from sqlite3 import Connection
from ..settings import Settings


class BudgetExceeded(RuntimeError):
    pass


class Governor:
    def __init__(self, s: Settings, db: Connection):
        self.s = s
        self.db = db

    def spent_today(self) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(usd),0) usd FROM ledger "
            "WHERE ts > strftime('%s','now','start of day')").fetchone()
        return float(row["usd"])

    def budget_left(self) -> float:
        return max(0.0, float(self.s.budget.get("daily_usd", 0)) - self.spent_today())

    def allow_api(self, est_usd: float = 0.0) -> bool:
        return self.budget_left() - est_usd > 0

    def record(self, *, provider: str, model: str, usd: float,
               tokens_in: int = 0, tokens_out: int = 0,
               job_id: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO ledger(ts,provider,model,tokens_in,tokens_out,usd,job_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (time.time(), provider, model, tokens_in, tokens_out, usd, job_id))
        self.db.commit()
