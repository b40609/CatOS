from pathlib import Path
import tempfile
import unittest

from catos.market_collectors import MarketCollectionError
from catos.market_intel import MarketIntelStore
from catos.market_onchain import (
    BASELINE_DAYS,
    DAY_MS,
    BlockscoutEthereumTokenTransferTransport,
    OnchainDailyScope,
    collect_blockscout_daily_activity,
    persist_onchain_collection,
)


SYMBOL = "WBTC-USDT-SWAP"
TOKEN = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"


def address(index):
    return "0x" + f"{index:040x}"


def transfer(*, source_ms, sender, receiver, sequence, token=TOKEN):
    from datetime import datetime, timezone
    stamp = datetime.fromtimestamp(source_ms // 1000, tz=timezone.utc).replace(
        microsecond=(source_ms % 1000) * 1000).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")
    return {
        "block_number": 1000 + sequence,
        "from": {"hash": sender},
        "to": {"hash": receiver},
        "log_index": sequence,
        "timestamp": stamp,
        "token": {"address_hash": token},
        "token_type": "ERC-20",
        "transaction_hash": "0x" + f"{sequence + 1:064x}",
        "type": "token_transfer",
    }


class FakeTransport:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch_transfers(self, scope, cursor=None):
        self.calls.append(cursor)
        key = None if cursor is None else (cursor["block_number"], cursor["index"])
        payload = self.pages[key]
        if isinstance(payload, BaseException):
            raise payload
        return payload


class CaptureTransport(BlockscoutEthereumTokenTransferTransport):
    def __init__(self):
        super().__init__()
        self.paths = []

    def _get(self, path):
        self.paths.append(path)
        return {"items": [], "next_page_params": None}


class OnchainProviderTests(unittest.TestCase):
    def setUp(self):
        self.day_start = 20 * DAY_MS
        self.day_end = self.day_start + DAY_MS
        self.required_start = self.day_start - BASELINE_DAYS * DAY_MS
        self.scope = OnchainDailyScope(
            SYMBOL, self.day_end, "ethereum", TOKEN, self.day_start, self.day_end)

    def _complete_pages(self):
        rows = []
        sequence = 0
        for day in range(BASELINE_DAYS):
            start = self.required_start + day * DAY_MS
            for sender_index in range(2):
                rows.append(transfer(
                    source_ms=start + DAY_MS // 2 + sender_index,
                    sender=address(1000 + day * 10 + sender_index),
                    receiver=address(9000),
                    sequence=sequence,
                ))
                sequence += 1
        for sender_index in range(6):
            rows.append(transfer(
                source_ms=self.day_start + DAY_MS // 2 + sender_index,
                sender=address(5000 + sender_index),
                receiver=address(9000),
                sequence=sequence,
            ))
            sequence += 1
        rows.sort(key=lambda item: item["timestamp"], reverse=True)
        split = len(rows) // 2
        cursor = {"block_number": 777, "index": split}
        old = transfer(
            source_ms=self.required_start - 1,
            sender=address(6000),
            receiver=address(9000),
            sequence=sequence,
        )
        return {
            None: {"items": rows[:split], "next_page_params": cursor},
            (777, split): {"items": rows[split:] + [old], "next_page_params": {
                "block_number": 700, "index": 1,
            }},
        }

    def test_complete_fifteen_day_window_feeds_public_reducer_and_persists_linked_source(self):
        transport = FakeTransport(self._complete_pages())
        result = collect_blockscout_daily_activity(self.scope, transport, max_pages=4)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.issues, ())
        self.assertEqual(result.evidence["coverage_status"], "complete_bounded_window")
        self.assertEqual(result.evidence["daily_outgoing_distinct"], [2] * 14 + [6])
        self.assertEqual(result.activity.outgoing_distinct, 6)
        self.assertEqual(str(result.activity.baseline_live), "2")
        self.assertEqual(str(result.activity.live_ratio), "3")
        self.assertEqual(result.activity.state, "FLAGGED")
        self.assertEqual(result.source_scope["calendar_boundary_contract"],
                         "caller_supplied_not_inferred")

        with tempfile.TemporaryDirectory() as root:
            store = MarketIntelStore(Path(root) / "market.sqlite")
            try:
                persist_onchain_collection(store, result)
                self.assertEqual(
                    store.connection.execute("SELECT count(*) FROM onchain_source_run").fetchone()[0], 1)
                self.assertEqual(
                    store.connection.execute("SELECT count(*) FROM onchain_activity").fetchone()[0], 1)
            finally:
                store.close()

    def test_page_budget_truncation_keeps_missing_and_persists_only_source_evidence(self):
        first = self._complete_pages()[None]
        result = collect_blockscout_daily_activity(
            self.scope, FakeTransport({None: first}), max_pages=1)
        self.assertEqual(result.status, "issues")
        self.assertEqual(result.issues, ("provider_page_limit_truncated",))
        self.assertEqual(result.evidence["coverage_status"], "provider_page_limit_truncated")
        self.assertIsNone(result.evidence["daily_outgoing_distinct"])
        self.assertIsNone(result.activity)
        self.assertTrue(any(not item["complete"] for item in result.evidence["window_lower_bounds"]))

        with tempfile.TemporaryDirectory() as root:
            store = MarketIntelStore(Path(root) / "market.sqlite")
            try:
                persist_onchain_collection(store, result)
                self.assertEqual(
                    store.connection.execute("SELECT count(*) FROM onchain_source_run").fetchone()[0], 1)
                self.assertEqual(
                    store.connection.execute("SELECT count(*) FROM onchain_activity").fetchone()[0], 0)
            finally:
                store.close()

    def test_mint_and_self_transfer_are_excluded_without_inventing_owner_identity(self):
        rows = []
        sequence = 0
        for day in range(BASELINE_DAYS + 1):
            start = self.required_start + day * DAY_MS
            rows.append(transfer(
                source_ms=start + 100,
                sender=address(100 + day), receiver=address(9000), sequence=sequence))
            sequence += 1
        rows.extend((
            transfer(source_ms=self.day_start + 90, sender="0x" + "0" * 40,
                     receiver=address(8000), sequence=sequence),
            transfer(source_ms=self.day_start + 80, sender=address(7000),
                     receiver=address(7000), sequence=sequence + 1),
            transfer(source_ms=self.required_start - 1, sender=address(6000),
                     receiver=address(9000), sequence=sequence + 2),
        ))
        rows.sort(key=lambda item: item["timestamp"], reverse=True)
        result = collect_blockscout_daily_activity(
            self.scope,
            FakeTransport({None: {"items": rows, "next_page_params": None}}),
            max_pages=1,
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.activity.outgoing_distinct, 1)
        self.assertEqual(result.source_scope["beneficial_owner_aggregation"], "not_available")

    def test_scope_mismatch_and_repeated_cursor_fail_closed(self):
        bad = transfer(
            source_ms=self.day_start + 1,
            sender=address(1), receiver=address(2), sequence=1,
            token="0x" + "ab" * 20,
        )
        mismatch = collect_blockscout_daily_activity(
            self.scope,
            FakeTransport({None: {"items": [bad], "next_page_params": None}}),
            max_pages=1,
        )
        self.assertEqual(mismatch.issues, ("scope_mismatch",))
        self.assertIsNone(mismatch.activity)

        cursor = {"block_number": 1000, "index": 1}
        first = transfer(
            source_ms=self.day_start + 2,
            sender=address(3), receiver=address(4), sequence=2,
        )
        second = transfer(
            source_ms=self.day_start + 1,
            sender=address(5), receiver=address(6), sequence=3,
        )
        repeated = collect_blockscout_daily_activity(
            self.scope,
            FakeTransport({
                None: {"items": [first], "next_page_params": cursor},
                (1000, 1): {"items": [second], "next_page_params": cursor},
            }),
            max_pages=4,
        )
        self.assertEqual(repeated.issues, ("repeated_cursor",))
        self.assertIsNone(repeated.activity)

    def test_transport_uses_only_fixed_token_path_and_validated_cursor(self):
        transport = CaptureTransport()
        transport.fetch_transfers(self.scope)
        transport.fetch_transfers(self.scope, {"block_number": 123, "index": 7})
        self.assertEqual(transport.paths, [
            f"/api/v2/tokens/{TOKEN}/transfers",
            f"/api/v2/tokens/{TOKEN}/transfers?block_number=123&index=7",
        ])
        with self.assertRaisesRegex(MarketCollectionError, "malformed_response"):
            transport.fetch_transfers(self.scope, {"block_number": 123, "index": 7, "extra": 1})


if __name__ == "__main__":
    unittest.main()
