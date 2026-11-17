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
import time

from catos import ipc
from catos.fake_exchange import TAG, Fill, Report
from catos.okx_demo import DemoClient, DemoError, OkxApiError
from catos.protection import Report as ProtectionReport

D = Decimal
_STATES = {"live": "LIVE", "partially_filled": "PARTIAL", "filled": "FILLED",
           "canceled": "CANCELED", "mmp_canceled": "CANCELED"}
# OKX algo order states. Triggered (effective) or triggered-but-failed both end the run:
# the position may be closed or may still be open, and the user checks on OKX.
_ALGO_STATES = {"live": "LIVE", "pause": "LIVE", "effective": "TRIGGERED", "partially_effective": "TRIGGERED",
                "order_failed": "TRIGGERED", "partially_failed": "TRIGGERED", "canceled": "CANCELED"}
# Codes for which OKX did not take the request at all; anything else is uncertain.
_REQUEST_REJECTED = frozenset(("51000", "51001", "51008", "51010", "51020", "51121", "51124",
                               "51169", "51202", "51203", "51004", "51006", "51007"))
POLL_SECONDS = 0.3
POLL_TRIES = 8  # inside Supervisor's 5-second exchange timeout
PROTECTION_POLL_TRIES = 4  # a protection step also spends a request on the create/amend/cancel itself


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
        """P6 disaster stop (2026-11-17): one OKX conditional order, reported like FakeExchange.

        The request is sent once; the answer always comes from querying the order by its
        algoClOrdId. A lost response or an unknown state stays uncertain (OSError), and
        the journal keeps blocking increases until a later query settles it.
        """
        if operation not in ("algo_create", "algo_amend", "algo_cancel", "algo_query"):
            raise ipc.ProtocolError("unsupported protection operation")
        if (payload.get("tag") != TAG or payload.get("tdMode") != "cross" or payload.get("posSide") != "net"
                or payload.get("reduceOnly") is not True or payload.get("closeFraction") != "1"
                or payload.get("instId") != self.inst_id):
            raise ipc.ProtocolError("invalid Supervisor protection payload")
        self.calls.append((operation, dict(payload)))
        request_id, algo_cl = payload["requestId"], payload["algoClOrdId"]
        try:
            if operation == "algo_create":
                await self._call(self._client.place_protection, payload)
            elif operation == "algo_amend":
                await self._call(self._client.amend_protection, payload)
            elif operation == "algo_cancel":
                current = await self._call(self._client.protection_order, self.inst_id, algo_cl)
                if current is not None and current["state"] in ("live", "pause"):
                    await self._call(self._client.cancel_protection, self.inst_id, current["algo_id"])
        except OkxApiError as exc:
            # 51xxx: OKX evaluated the new conditional order and refused it; 50xxx and transport
            # failures leave it uncertain (the query decides later).
            if operation == "algo_create" and str(exc.code).startswith("51"):
                return ProtectionReport(request_id, self._revision(), "REJECTED", complete=True)
            raise OSError(f"okx_demo_protection_uncertain:{exc.code}") from None
        except DemoError:
            raise OSError("okx_demo_protection_uncertain") from None
        wanted = D(payload["slTriggerPx"]) if operation in ("algo_create", "algo_amend") else None

        def settled(report):
            if operation == "algo_query":
                return True
            if report.status == "NOT_FOUND":
                return False  # just sent: OKX may not list it yet
            if operation == "algo_cancel":
                return report.status != "LIVE"
            return report.status != "LIVE" or (report.complete and report.price == wanted)

        report = None
        for _ in range(PROTECTION_POLL_TRIES):  # inside Supervisor's 5-second exchange timeout
            report = await self._protection_report(request_id, algo_cl)
            if settled(report):
                return report
            await self._sleep(POLL_SECONDS)
        return report

    def _revision(self):
        # Observation time, strictly increasing within this process and across restarts.
        self._last_revision = max(getattr(self, "_last_revision", 0) + 1, time.time_ns() // 1000)
        return self._last_revision

    async def _protection_report(self, request_id, algo_cl):
        try:
            order = await self._call(self._client.protection_order, self.inst_id, algo_cl)
        except DemoError:
            raise OSError("okx_demo_protection_query_uncertain") from None
        if order is None:
            return ProtectionReport(request_id, self._revision(), "NOT_FOUND")
        if order["tag"] not in (TAG, None, "") or order["ord_type"] != "conditional":
            raise ipc.ProtocolError("conditional order on the exchange is not this Supervisor's")
        status = _ALGO_STATES.get(order["state"])
        if status is None:
            raise OSError(f"okx_demo_unknown_algo_state:{order['state']}")
        if status == "LIVE":
            return ProtectionReport(request_id, self._revision(), "LIVE", order["sl_trigger_px"], order["side"],
                                    order["sl_trigger_px_type"], order["state"] == "live", order["algo_id"])
        return ProtectionReport(request_id, self._revision(), status, complete=True, algo_id=order["algo_id"])

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
