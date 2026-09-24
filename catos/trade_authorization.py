"""Explicit, in-memory authorization for bounded OKX Demo write exercises.

Reconciliation evidence and trading permission are deliberately separate.  A
grant is never durable and therefore never survives a Supervisor restart.
"""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from catos import ipc, research, risk


@dataclass(frozen=True)
class DemoTradeGrant:
    authorization_id: str
    account_id: str
    bot_id: str
    inst_id: str
    reconciliation_evidence_id: str
    bot_revision: int
    starts_at_ms: int
    entry_cutoff_ms: int
    max_entry_mark_notional_usdt: Decimal
    environment: str = "demo"

    def __post_init__(self):
        ipc.token(self.authorization_id, "demo authorization id")
        ipc.token(self.account_id, "demo authorization account")
        ipc.token(self.bot_id, "demo authorization bot")
        ipc.token(self.reconciliation_evidence_id, "demo reconciliation evidence")
        ipc.integer(self.bot_revision, "demo reconciliation revision")
        ipc.integer(self.starts_at_ms, "demo authorization start")
        ipc.integer(self.entry_cutoff_ms, "demo authorization cutoff")
        amount = risk.decimal(self.max_entry_mark_notional_usdt, "demo entry mark notional limit")
        if (self.environment != "demo" or type(self.inst_id) is not str
                or not self.inst_id.endswith("-USDT-SWAP")
                or self.starts_at_ms > self.entry_cutoff_ms or amount <= 0):
            raise ipc.ProtocolError("invalid bounded Demo trade grant")


def entry_blocker(grant, *, now_ms, account_id, bot_id, inst_id,
                  reconciliation_evidence_id, reconciled_revision):
    """Return a stable fail-closed reason for an exposure-increasing request."""
    if not isinstance(grant, DemoTradeGrant):
        return "demo_trade_grant_required"
    if (grant.environment != "demo" or grant.account_id != account_id
            or grant.bot_id != bot_id or grant.inst_id != inst_id):
        return "demo_trade_grant_scope_mismatch"
    if (reconciled_revision is None
            or grant.bot_revision != reconciled_revision
            or grant.reconciliation_evidence_id != reconciliation_evidence_id):
        return "demo_trade_grant_stale_reconciliation"
    if now_ms < grant.starts_at_ms:
        return "demo_trade_grant_not_started"
    if now_ms > grant.entry_cutoff_ms:
        return "demo_trade_grant_expired"
    return None


def entry_mark_notional(quantity, base_per_contract, mark):
    """Return the pre-submit mark notional for one Supervisor-owned entry order."""
    quantity = risk.decimal(quantity, "demo entry quantity")
    base_per_contract = risk.decimal(base_per_contract, "demo contract base quantity")
    mark = risk.decimal(mark, "demo entry mark")
    if quantity == 0 or base_per_contract <= 0 or mark <= 0:
        raise ipc.ProtocolError("invalid Demo entry mark notional inputs")
    with localcontext(research._CONTEXT):
        return abs(quantity) * base_per_contract * mark
