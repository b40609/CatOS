"""OKX Demo adapter for LocalSupervisor: the FakeExchange submit/query/cancel contract on a real Demo account.

M1 step 3 (2026-11-16). Supervisor stays the only order exit: it builds the payload
(fixed tag, cross, net, reduceOnly), the journal records every state, and this
adapter only forwards and translates.

Uncertainty rules (INVARIANTS: UNKNOWN is never blindly resent or released):
- A transport failure, timeout or an OKX error that is not an order-level rejection
  raises OSError, which the Supervisor records as UNKNOWN; the runner then queries.
- Only an order-level rejection (sCode 51xxx etc. on the order row) is REJECTED.
- "Not found" on a query is NOT_FOUND, which the journal treats as no evidence.
- A report is ``complete`` only when the order is terminal and the listed trades sum
  to the filled size; until then the order stays unsettled and is queried again.
Fees: OKX reports a charge as negative; the ledger stores a cost as positive, so the
sign is flipped.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from catos import ipc
from catos.fake_exchange import TAG, Fill, Report
from catos.okx_demo import DemoClient, DemoError, OkxApiError

_STATES = {"live": "LIVE", "partially_filled": "PARTIAL", "filled": "FILLED",
           "canceled": "CANCELED", "mmp_canceled": "CANCELED"}
# Codes for which OKX did not take the request at all; anything else is uncertain.
_REQUEST_REJECTED = frozenset(("51000", "51001", "51008", "51010", "51020", "51121", "51124",
                               "51169", "51202", "51203", "51004", "51006", "51007"))
POLL_SECONDS = 0.3
POLL_TRIES = 8  # inside Supervisor's 5-second exchange timeout


class OkxDemoExchange:
    def __init__(self, client: DemoClient, account_id: str, inst_id: str, *, sleep=asyncio.sleep):
        if not isinstance(client, DemoClient):
            raise ipc.ProtocolError("DemoClient required")
        self.account_id = ipc.token(account_id, "demo account")
        self.inst_id = inst_id
        self._client = client
        self._sleep = sleep
        self.calls = []

    async def _call(self, method, *args):
        return await asyncio.to_thread(method, *args)

    async def submit(self, payload):
        if payload.get("tag") != TAG or payload.get("tdMode") != "cross" or payload.get("posSide") != "net":
            raise ipc.ProtocolError("invalid Supervisor payload")
        if payload.get("instId") != self.inst_id:
            raise ipc.ProtocolError("payload instrument is not this Bot's contract")
        self.calls.append(("submit", dict(payload)))
        cl_ord_id = payload["clOrdId"]
        try:
            await self._call(self._client.submit_supervisor_payload, payload)
        except OkxApiError as exc:
            if exc.code in _REQUEST_REJECTED:
                return Report(cl_ord_id, "rejected" + cl_ord_id, 1, "REJECTED", Decimal("0"), (), True)
            raise OSError(f"okx_demo_submit_uncertain:{exc.code}") from None
        except DemoError:
            raise OSError("okx_demo_submit_uncertain") from None
        # A market order normally settles within milliseconds; poll briefly for the fills.
        report = None
        for _ in range(POLL_TRIES):
            report = await self._report(cl_ord_id)
            if report.complete:
                return report
            await self._sleep(POLL_SECONDS)
        return report

    async def query(self, cl_ord_id):
        self.calls.append(("query", {"clOrdId": cl_ord_id}))
        return await self._report(cl_ord_id)

    async def cancel(self, cl_ord_id):
        self.calls.append(("cancel", {"clOrdId": cl_ord_id}))
        try:
            await self._call(self._client.cancel_by_client_id, self.inst_id, cl_ord_id)
        except OkxApiError as exc:
            # 51400/51401/51402: already filled/canceled/not exist; the query below decides.
            if exc.code not in ("51400", "51401", "51402", "51410"):
                raise OSError(f"okx_demo_cancel_uncertain:{exc.code}") from None
        except DemoError:
            raise OSError("okx_demo_cancel_uncertain") from None
        return await self._report(cl_ord_id)

    async def protection(self, operation, payload):
        # P6 disaster stop defaults to 0% (disabled); exchange-side algo orders are not wired for Demo yet.
        raise ipc.ProtocolError("protection orders are not supported on the OKX Demo adapter")

    async def _report(self, cl_ord_id):
        try:
            order = await self._call(self._client.order_by_client_id, self.inst_id, cl_ord_id)
            if order is None:
                return Report(cl_ord_id, None, 1, "NOT_FOUND")
            status = _STATES.get(order["state"])
            if status is None:
                raise OSError(f"okx_demo_unknown_state:{order['state']}")
            if order["tag"] not in (TAG, None, ""):
                raise ipc.ProtocolError("order on the exchange carries a different tag")
            fills = ()
            if order["acc_fill_sz"] > 0:
                rows = await self._call(self._client.order_fills, self.inst_id, order["ord_id"])
                fills = tuple(Fill(row["trade_id"], row["fill_sz"], row["fill_px"], -row["fee"]) for row in rows)
                # Fees are booked in USDT; a fee in another currency is never settled silently.
                if any(row["fee_ccy"] not in ("", "USDT") for row in rows):
                    raise OSError("okx_demo_fee_currency_not_usdt")
        except DemoError:
            raise OSError("okx_demo_query_uncertain") from None
        listed = sum((fill.quantity for fill in fills), Decimal("0"))
        complete = status in ("FILLED", "CANCELED") and listed == order["acc_fill_sz"]
        if listed > order["acc_fill_sz"]:
            raise OSError("okx_demo_fills_exceed_order")
        # OKX uTime grows on every order update; trades listed later bump the revision too.
        revision = max(1, order["u_time"] * 1000 + len(fills))
        return Report(cl_ord_id, order["ord_id"], revision, status, order["acc_fill_sz"], fills, complete)
