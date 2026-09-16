"""Scripted, memory-only exchange for local failure tests. No network code."""

from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from catos import ipc, risk

D = Decimal
TAG = "41cb53c54d6dABDE"


@dataclass(frozen=True)
class Fill:
    trade_id: str
    quantity: Decimal
    price: Decimal
    fee: Decimal = D("0")

    def to_wire(self):
        ipc.token(self.trade_id, "trade id")
        for name in ("quantity", "price", "fee"):
            risk.decimal(getattr(self, name), name)
        if self.quantity <= 0 or self.price <= 0:
            raise ipc.ProtocolError("fill quantity and price must be positive")
        return dict(trade_id=self.trade_id, quantity=str(self.quantity), price=str(self.price), fee=str(self.fee))


@dataclass(frozen=True)
class Report:
    cl_ord_id: str
    exchange_id: str | None
    revision: int
    status: str
    cumulative: Decimal = D("0")
    fills: tuple = ()
    complete: bool = False

    def to_wire(self):
        ipc.token(self.cl_ord_id, "client order id")
        ipc.integer(self.revision, "report revision", 1)
        if self.exchange_id is not None:
            ipc.token(self.exchange_id, "exchange order id")
        if self.status not in {"LIVE", "PARTIAL", "FILLED", "CANCELED", "REJECTED", "NOT_FOUND"}:
            raise ipc.ProtocolError("invalid synthetic report status")
        if type(self.complete) is not bool or type(self.fills) is not tuple or len(self.fills) > 128:
            raise ipc.ProtocolError("invalid or unbounded fill evidence")
        if risk.decimal(self.cumulative, "cumulative fill") < 0:
            raise ipc.ProtocolError("negative cumulative fill")
        result = dict(cl_ord_id=self.cl_ord_id, exchange_id=self.exchange_id, revision=self.revision,
                      status=self.status, cumulative=str(self.cumulative),
                      fills=[fill.to_wire() for fill in self.fills], complete=self.complete)
        ipc.encode_frame(result)
        return result


def build_payload(contract, cl_ord_id, quantity, reduce_only):
    """Only Supervisor-owned scalar fields enter this builder; never merge Worker data."""
    ipc.token(cl_ord_id, "client order id")
    risk.decimal(quantity, "order quantity")
    if (not contract.inst_id.endswith("-USDT-SWAP") or len(cl_ord_id) > 32
            or not cl_ord_id.isascii() or not cl_ord_id.isalnum() or quantity == 0
            or type(reduce_only) is not bool):
        raise ipc.ProtocolError("unsupported simulated SWAP order")
    return dict(instId=contract.inst_id, tdMode="cross", posSide="net", ordType="market",
                side="buy" if quantity > 0 else "sell", sz=str(quantity.copy_abs()),
                reduceOnly=reduce_only, clOrdId=cl_ord_id, tag=TAG)


class FakeExchange:
    """Each call consumes an explicitly queued Report or Exception.

    Missing script means timeout/uncertainty, never an invented successful fill.
    Reuse this object across Supervisor restarts to represent remote survival.
    """
    def __init__(self, account_id):
        self.account_id = ipc.token(account_id, "fake account")
        self.calls = []
        self._scripts = {name: deque() for name in ('submit', 'query', 'cancel',
            'algo_create', 'algo_amend', 'algo_cancel', 'algo_query')}

    def enqueue(self, operation, outcome):
        from catos.protection import Report as ProtectionReport
        expected = ProtectionReport if operation.startswith('algo_') else Report
        if operation not in self._scripts or not isinstance(outcome, (expected, Exception)):
            raise ValueError("queue a synthetic Report or Exception")
        self._scripts[operation].append(outcome)

    def _reply(self, operation, request):
        self.calls.append((operation, dict(request)))
        if not self._scripts[operation]:
            raise TimeoutError("no scripted evidence; outcome remains unknown")
        result = self._scripts[operation].popleft()
        if isinstance(result, Exception):
            raise result
        return result

    async def submit(self, payload):
        # The fake also asserts the invariant, independently of the builder.
        if payload.get("tag") != TAG or payload.get("tdMode") != "cross" or payload.get("posSide") != "net":
            raise ipc.ProtocolError("invalid Supervisor payload")
        return self._reply("submit", payload)

    async def query(self, cl_ord_id):
        return self._reply("query", dict(clOrdId=cl_ord_id))

    async def cancel(self, cl_ord_id):
        return self._reply("cancel", dict(clOrdId=cl_ord_id))

    async def protection(self, operation, payload):
        if operation not in ('algo_create', 'algo_amend', 'algo_cancel', 'algo_query'):
            raise ipc.ProtocolError('unsupported protection operation')
        if (payload.get('tag') != TAG or payload.get('tdMode') != 'cross'
                or payload.get('posSide') != 'net' or payload.get('reduceOnly') is not True
                or payload.get('closeFraction') != '1'):
            raise ipc.ProtocolError('invalid Supervisor protection payload')
        return self._reply(operation, payload)
