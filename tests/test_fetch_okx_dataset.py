"""tools/fetch_okx_candles.py against a scripted fake OKX (no network)."""

import importlib.util
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from catos import research_datasets as datasets

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("fetch_okx_candles", ROOT / "tools" / "fetch_okx_candles.py")
fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch)

TF = 900_000
EIGHT_H = 28_800_000
DAY = 86_400_000
END = 1_790_726_400_000 + 3 * DAY  # bar- and 8h-aligned
INSTRUMENT = {
    "instId": "BTC-USDT-SWAP", "instType": "SWAP", "ctType": "linear", "settleCcy": "USDT",
    "ctValCcy": "BTC", "ctVal": "0.01", "ctMult": "1", "tickSz": "0.1", "lotSz": "0.01",
    "minSz": "0.01", "state": "live",
}


class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeOKX:
    """Serves history candles/funding newest first, strictly older than `after`."""

    def __init__(self, time, *, days_of_data=5, drop=(), unclosed=(), funding_from=None, script=None,
                 instrument=INSTRUMENT, break_cursor=False):
        self.time = time
        self.calls = []
        self.script = list(script or [])
        self.instrument = instrument
        self.break_cursor = break_cursor
        first = END - days_of_data * DAY
        self.candles = [[str(ms), "60000.0", "60010.0", "59990.0", "60005.0", "1", "1", "1",
                         "0" if ms in unclosed else "1"]
                        for ms in range(first, END + TF, TF) if ms not in drop]
        self.candles[-1][8] = "0"  # the forming bar at END
        start_funding = first if funding_from is None else funding_from
        self.funding = [{"instId": "BTC-USDT-SWAP", "instType": "SWAP", "fundingTime": str(ms),
                         "fundingRate": "0.00012", "realizedRate": "0.0001", "method": "current_period"}
                        for ms in range(start_funding, END, EIGHT_H)]

    def __call__(self, url):
        parts = urlsplit(url)
        query = {key: values[0] for key, values in parse_qs(parts.query).items()}
        self.calls.append((self.time.now, parts.path, query))
        if self.script:
            status = self.script.pop(0)
            if status != 200:
                return status, b"{}"
        if parts.path == fetch.INSTRUMENTS_PATH:
            data = [self.instrument]
        else:
            after, limit = int(query["after"]), int(query["limit"])
            rows = self.candles if parts.path == fetch.CANDLES_PATH else self.funding
            key = (lambda row: int(row[0])) if parts.path == fetch.CANDLES_PATH else (
                lambda row: int(row["fundingTime"]))
            data = sorted((row for row in rows if self.break_cursor or key(row) < after),
                          key=key, reverse=True)[:limit]
        return 200, json.dumps({"code": "0", "msg": "", "data": data}).encode()


class FetchToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "okx"
        self.time = FakeTime()

    def run_tool(self, okx, *args, max_requests=50):
        client = fetch.Client(max_requests=max_requests, opener=okx, clock=self.time.clock,
                              sleep=self.time.sleep, base_url="https://fake.invalid")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = fetch.main(["--days", "3", *args], client=client, now_ms=END + 5 * 60_000, root=self.root)
        return code, out.getvalue(), err.getvalue(), client

    def written(self):
        return sorted(path.name for path in self.root.glob("*/*/okx-*")) if self.root.exists() else []

    def test_fetches_paces_and_writes_a_verified_dataset(self):
        okx = FakeOKX(self.time)
        code, out, err, client = self.run_tool(okx)
        self.assertEqual(code, 0, err)
        summary = json.loads(out)
        self.assertEqual((summary["bars"], summary["funding_events"]), (3 * 96, 9))
        self.assertEqual(summary["requests"], client.requests)
        self.assertEqual([path for _, path, _ in okx.calls],
                         [fetch.INSTRUMENTS_PATH] + [fetch.CANDLES_PATH] * 3 + [fetch.FUNDING_PATH])
        times = [at for at, _, _ in okx.calls]
        self.assertTrue(all(later - earlier >= fetch.MIN_INTERVAL_S for earlier, later in zip(times, times[1:])))
        self.assertEqual(okx.calls[1][2]["after"], str(END))
        dataset = datasets.load_manifest(self.root / "BTC-USDT-SWAP" / "15m" / summary["dataset_id"]
                                         / datasets.MANIFEST, self.root)
        self.assertEqual((dataset.start_ms, dataset.end_ms), (END - 3 * DAY, END))

    def test_gap_or_short_funding_history_stops_without_writing(self):
        code, _, err, _ = self.run_tool(FakeOKX(self.time, drop={END - 10 * TF}))
        self.assertEqual(code, 1)
        self.assertIn("dataset_has_gaps", err)
        code, _, err, _ = self.run_tool(FakeOKX(self.time, funding_from=END - 3 * DAY + EIGHT_H))
        self.assertEqual(code, 1)
        self.assertIn("funding_incomplete", err)
        self.assertEqual(self.written(), [])

    def test_unexpected_responses_stop_the_run(self):
        code, _, err, _ = self.run_tool(FakeOKX(self.time, unclosed={END - 5 * TF}))
        self.assertEqual((code, "unclosed_candle_in_range" in err), (1, True))
        code, _, err, _ = self.run_tool(FakeOKX(self.time, break_cursor=True))
        self.assertEqual((code, "pagination_unexpected" in err), (1, True))
        code, _, err, _ = self.run_tool(FakeOKX(self.time, instrument={**INSTRUMENT, "settleCcy": "USD"}))
        self.assertEqual((code, "instrument_not_linear_usdt_swap" in err), (1, True))
        self.assertEqual(self.written(), [])

    def test_retries_with_backoff_and_respects_the_request_budget(self):
        okx = FakeOKX(self.time, script=[200, 429, 503])
        code, _, err, client = self.run_tool(okx)
        self.assertEqual(code, 0, err)
        self.assertIn(1, self.time.sleeps)
        self.assertIn(2, self.time.sleeps)
        self.assertEqual(client.requests, 7)
        code, _, err, client = self.run_tool(FakeOKX(self.time), "--end-ms", str(END - DAY), max_requests=2)
        self.assertEqual((code, "request_budget_exhausted" in err, client.requests), (1, True, 2))

    def test_existing_dataset_is_not_overwritten(self):
        self.assertEqual(self.run_tool(FakeOKX(self.time))[0], 0)
        code, _, err, _ = self.run_tool(FakeOKX(self.time))
        self.assertEqual((code, "dataset_exists" in err), (1, True))

    def test_only_the_three_public_endpoints_are_allowed(self):
        client = fetch.Client(max_requests=5, opener=FakeOKX(self.time), clock=self.time.clock,
                              sleep=self.time.sleep)
        with self.assertRaisesRegex(fetch.FetchError, "endpoint_not_allowed"):
            client.get("/api/v5/account/balance", {})
        self.assertEqual(client.requests, 0)


if __name__ == "__main__":
    unittest.main()
