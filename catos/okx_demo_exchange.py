"""OKX Demo adapter for LocalSupervisor: the FakeExchange submit/query/cancel contract on a real Demo account.

M1 step 3 (2026-11-16). Supervisor stays the only order exit: it builds the payload
(fixed tag, cross, net, reduceOnly), the journal records every state, and this
adapter only forwards and translates.

Uncertainty rules (INVARIANTS: UNKNOWN is never blindly resent or released):
- A transport failure, timeout or an OKX error that is not an order-level rejection
  raises OSError, which the Supervisor records as UNKNOWN; the runner then queries.
- Only an order-level rejection (sCode 51xxx etc. on the order row) is REJECTED.
- "Not found" on a query is NOT_FOUND, which the journal treats as no evidence. The one
  exception is an order sent with an OKX ``expTime`` (request deadline): OKX does not process a
  request once its server time is past that deadline, so "not found" well after it (server time
  estimated from public/time) proves the order was never taken and it is reported REJECTED.
  Reduce-only orders only. Assumes OKX lists an accepted order at once (protection-check: the
  first query after the send finds it).
  A flatten can then send a new reduce-only order instead of stopping (M1 acceptance R3, 2026-11-18).
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
from catos.okx_demo import DemoClient, DemoError, OkxApiError, altered_stop
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
                               "51169", "51202", "51203", "51004", "51006", "51007",
                               # expTime already past: not processed (Demo probe 2026-11-18, reports/flatten-resend-20261118)
                               "50036"))
POLL_SECONDS = 0.3
POLL_TRIES = 8  # inside Supervisor's 5-second exchange timeout
PROTECTION_POLL_TRIES = 4  # a protection step also spends a request on the create/amend/cancel itself
SUBMIT_DEADLINE_MS = 5_000    # expTime: OKX server time at send + this
PROOF_MARGIN_MS = 10_000      # "not found" counts as never taken only this long after the deadline
CLOCK_MAX_AGE_MS = 300_000    # re-read OKX server time when the offset is older than this
CLOCK_MAX_RTT_MS = 2_000      # an offset read with a slower round trip is not trusted


class OkxDemoExchange:
    def __init__(self, client: DemoClient, account_id: str, inst_id: str, *, sleep=asyncio.sleep):
        if not isinstance(client, DemoClient):
            raise ipc.ProtocolError("DemoClient required")
        self.account_id = ipc.token(account_id, "demo account")
        self.inst_id = inst_id
        self._client = client
        self._sleep = sleep
        self.calls = []
        self._offset = None       # (OKX server time - local time, local time it was read), ms
        self._deadlines = {}      # clOrdId -> expTime sent with it (OKX server time, ms)

    def _now(self):
        return self._client._clock_ms()

    async def _server_offset(self):
        """OKX server time minus local time, re-read every few minutes; None when it cannot be
        read precisely (the order then goes without a deadline, as before)."""
        if self._offset is not None and self._now() - self._offset[1] < CLOCK_MAX_AGE_MS:
            return self._offset[0]
        try:
            before = self._now()
            server = await self._call(self._client.server_time_ms)
            after = self._now()
        except DemoError:
            return None
        if after - before > CLOCK_MAX_RTT_MS:
            return None
        self._offset = (server - (before + after) // 2, after)
        return self._offset[0]

    def _never_taken(self, cl_ord_id, asked_ms):
        """``asked_ms``: local time the "not found" query was sent."""
        deadline = self._deadlines.get(cl_ord_id)
        return (deadline is not None and self._offset is not None
                and asked_ms + self._offset[0] > deadline + PROOF_MARGIN_MS)

    async def _call(self, method, *args):
        return await asyncio.to_thread(method, *args)

    async def submit(self, payload):
        if payload.get("tag") != TAG or payload.get("tdMode") != "cross" or payload.get("posSide") != "net":
            raise ipc.ProtocolError("invalid Supervisor payload")
        if payload.get("instId") != self.inst_id:
            raise ipc.ProtocolError("payload instrument is not this Bot's contract")
        self.calls.append(("submit", dict(payload)))
        cl_ord_id = payload["clOrdId"]
        # Only a reduce-only order gets a provable deadline: a second one can never add exposure
        # (OKX caps it at the position), so a wrong proof costs at most a position-mismatch stop.
        offset = await self._server_offset() if payload.get("reduceOnly") is True else None
        deadline = None if offset is None else self._now() + offset + SUBMIT_DEADLINE_MS
        if deadline is not None:
            self._deadlines[cl_ord_id] = deadline  # before sending: a lost answer can still be proven
        try:
            await self._call(self._client.submit_supervisor_payload, payload, deadline)
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
            # 51xxx: OKX evaluated the request and refused it; 50xxx and transport failures leave it
            # uncertain (the query decides later).
            business = str(exc.code).startswith("51")
            if operation == "algo_create" and business:
                return ProtectionReport(request_id, self._revision(), "REJECTED", complete=True)
            if operation == "algo_amend" and business:
                # Refused amend (Gemini review, 2026-11-18): if our stop is still live, it is unchanged
                # and the refusal is reported as such, instead of an "unconfirmed" that flips with
                # "mismatch" every check. A stop that is gone or fired is reported as OKX shows it.
                report = await self._protection_report(request_id, algo_cl, history=True)
                if report.status == "LIVE":
                    return ProtectionReport(request_id, self._revision(), "REJECTED", complete=True)
                return report
            if not (operation == "algo_cancel" and business):
                raise OSError(f"okx_demo_protection_uncertain:{exc.code}") from None
            # A refused cancel (already canceled, fired or gone, e.g. 51400-51402): the query decides,
            # as for ordinary orders.
        except DemoError:
            raise OSError("okx_demo_protection_uncertain") from None
        wanted = D(payload["slTriggerPx"]) if operation in ("algo_create", "algo_amend") else None
        # A stop that existed before and is no longer in order-algo is looked up in the algo history;
        # a just-created or amended one may simply not be listed yet, so it is only re-queried.
        # A cancel first re-queries order-algo once (OKX may lag right after the cancel), then also the
        # history (acceptance D1, 2026-11-18); a query is a single look that includes the history.
        def with_history(attempt):
            return operation == "algo_query" or (operation == "algo_cancel" and attempt >= 1)

        def settled(report, attempt):
            if operation == "algo_query":
                return True
            if report.status == "NOT_FOUND":
                return with_history(attempt)  # create/amend: just sent, OKX may not list it yet
            if operation == "algo_cancel":
                return report.status != "LIVE"
            # The whole request must show: an amend of the trigger source alone keeps the price
            # (2026-11-18 review gap), so the source is compared too.
            return report.status != "LIVE" or (report.complete and report.price == wanted
                                               and report.trigger == payload["slTriggerPxType"])

        report = None
        for attempt in range(PROTECTION_POLL_TRIES):  # inside Supervisor's 5-second exchange timeout
            report = await self._protection_report(request_id, algo_cl, history=with_history(attempt))
            if settled(report, attempt):
                return report
            await self._sleep(POLL_SECONDS)
        return report

    def _revision(self):
        # Observation time, strictly increasing within this process and across restarts.
        self._last_revision = max(getattr(self, "_last_revision", 0) + 1, time.time_ns() // 1000)
        return self._last_revision

    async def _protection_report(self, request_id, algo_cl, *, history=False):
        try:
            order = await self._call(self._client.protection_order, self.inst_id, algo_cl)
            if order is None and history:
                order = await self._call(self._client.protection_history, self.inst_id, algo_cl)
        except DemoError:
            raise OSError("okx_demo_protection_query_uncertain") from None
        if order is None:
            return ProtectionReport(request_id, self._revision(), "NOT_FOUND")
        if order["tag"] != TAG or order["ord_type"] != "conditional":
            raise ipc.ProtocolError("conditional order on the exchange is not this Supervisor's")
        status = _ALGO_STATES.get(order["state"])
        if status is None:
            raise OSError(f"okx_demo_unknown_algo_state:{order['state']}")
        if status == "LIVE":
            # 2026-11-18 review gaps: an empty trigger source is OKX's default, the last price (documented
            # for requests; unverified for responses), so it reads as "not mark" and is amended, instead of
            # failing the run. A stop changed outside CatOS to a limit price or a partial size is LIVE but
            # incomplete: the ledger keeps it unconfirmed (no increases) until it is canceled and re-placed.
            trigger = order["sl_trigger_px_type"] or "last"
            if (order["sl_trigger_px"] is None or order["sl_trigger_px"] <= 0 or order["side"] not in ("buy", "sell")
                    or trigger not in ("mark", "last", "index")):
                raise OSError("okx_demo_protection_unreadable")
            return ProtectionReport(request_id, self._revision(), "LIVE", order["sl_trigger_px"], order["side"],
                                    trigger, order["state"] == "live" and not altered_stop(order), order["algo_id"])
        return ProtectionReport(request_id, self._revision(), status, complete=True, algo_id=order["algo_id"])

    async def _report(self, cl_ord_id):
        try:
            asked = self._now()
            order = await self._call(self._client.order_by_client_id, self.inst_id, cl_ord_id)
            if order is None:
                if self._never_taken(cl_ord_id, asked):
                    return Report(cl_ord_id, "rejected" + cl_ord_id, 1, "REJECTED", Decimal("0"), (), True)
                return Report(cl_ord_id, None, 1, "NOT_FOUND")
            status = _STATES.get(order["state"])
            if status is None:
                raise OSError(f"okx_demo_unknown_state:{order['state']}")
            # OKX reports the tag on our orders (Demo probe 2026-11-18): an empty one is not ours either.
            if order["tag"] != TAG:
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
