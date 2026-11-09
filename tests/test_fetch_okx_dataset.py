"""tools/fetch_okx_candles.py against a scripted fake OKX (no network)."""

import importlib.util
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest import mock
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

    def __init__(self, time, *, days_of_data=5, drop=(), unclosed=(), funding_from=None, funding_until=END,
                 script=None, instrument=INSTRUMENT, break_cursor=False):
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
                        for ms in range(start_funding, funding_until, EIGHT_H)]

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

    def test_gap_or_funding_that_stops_early_stops_without_writing(self):
        code, _, err, _ = self.run_tool(FakeOKX(self.time, drop={END - 10 * TF}))
        self.assertEqual(code, 1)
        self.assertIn("dataset_has_gaps", err)
        code, _, err, _ = self.run_tool(FakeOKX(self.time, funding_until=END - EIGHT_H))
        self.assertEqual(code, 1)
        self.assertIn("funding_stops_before_end", err)
        self.assertEqual(self.written(), [])

    def test_short_funding_history_is_written_as_partial_and_disclosed(self):
        # OKX keeps about three months of funding: the run starts late, never ends early.
        code, out, err, _ = self.run_tool(FakeOKX(self.time, funding_from=END - DAY))
        self.assertEqual(code, 0, err)
        summary = json.loads(out)
        target = self.root / "BTC-USDT-SWAP" / "15m" / summary["dataset_id"]
        manifest = json.loads((target / datasets.MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual((manifest["funding"]["complete"], manifest["funding"]["events"]), (False, 3))
        dataset = datasets.load_manifest(target / datasets.MANIFEST, self.root)
        self.assertEqual(dataset.funding_summary(), {"source": "dataset", "complete": False,
                                                     "from_ms": END - DAY, "interval_ms": EIGHT_H})
        self.assertIn("資金費自", dataset.name)
        self.assertIn("之前的期間未計資金費", dataset.notice)

    def test_days_cap_follows_the_authorization(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            fetch.main(["--days", str(fetch.MAX_DAYS + 1)], client=object(), now_ms=END, root=self.root)
        self.assertEqual(fetch.MAX_DAYS, 1_830)

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

    def test_request_cap_from_the_authorization_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "max_requests"):
            fetch.Client(max_requests=fetch.MAX_REQUESTS_CAP + 1, opener=FakeOKX(self.time))
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit):
            fetch.main(["--days", "3", "--max-requests", "151"], now_ms=END, root=self.root)
        self.assertIn("authorized cap", err.getvalue())
        self.assertEqual(self.written(), [])

    def test_only_the_three_public_endpoints_are_allowed(self):
        client = fetch.Client(max_requests=5, opener=FakeOKX(self.time), clock=self.time.clock,
                              sleep=self.time.sleep)
        with self.assertRaisesRegex(fetch.FetchError, "endpoint_not_allowed"):
            client.get("/api/v5/account/balance", {})
        self.assertEqual(client.requests, 0)


if __name__ == "__main__":
    unittest.main()


class ResumableFetchTest(unittest.TestCase):
    """2026-11-07: long ranges are fetched over several runs, each within the request cap."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "okx"
        self.time = FakeTime()

    def run_tool(self, okx, *args, max_requests=8):
        client = fetch.Client(max_requests=max_requests, opener=okx, clock=self.time.clock,
                              sleep=self.time.sleep, base_url="https://fake.invalid")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = fetch.main(["--days", "3", "--end-ms", str(END), *args], client=client,
                              now_ms=END + 5 * 60_000, root=self.root)
        return code, out.getvalue(), err.getvalue(), client

    def test_runs_continue_until_the_dataset_is_written_like_a_single_run(self):
        okx = FakeOKX(self.time)
        code, out, err, client = self.run_tool(okx, "--resume")
        self.assertEqual(code, fetch.IN_PROGRESS, err)
        self.assertEqual(client.requests, 2)  # instrument + one page; the rest is the funding reserve
        staged = fetch._staging_path(self.root, "BTC-USDT-SWAP", "15m")
        self.assertTrue(staged.exists())
        self.assertEqual(datasets.list_datasets(self.root), ([], []))  # staging is not a dataset
        code, out, err, client = self.run_tool(okx, "--resume")
        self.assertEqual(code, 0, err)
        self.assertFalse(staged.exists())
        summary = json.loads(out)
        self.assertEqual(summary["requests"], 5)
        resumed = self.root / "BTC-USDT-SWAP" / "15m" / summary["dataset_id"]
        single_root = Path(self.tmp.name) / "single"
        client = fetch.Client(max_requests=50, opener=FakeOKX(self.time), clock=self.time.clock,
                              sleep=self.time.sleep, base_url="https://fake.invalid")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(fetch.main(["--days", "3", "--end-ms", str(END)], client=client,
                                        now_ms=END + 5 * 60_000, root=single_root), 0)
        single = single_root / "BTC-USDT-SWAP" / "15m" / summary["dataset_id"]
        for name in (datasets.CANDLES, datasets.FUNDING, datasets.INSTRUMENT):
            self.assertEqual((resumed / name).read_bytes(), (single / name).read_bytes(), name)

    def test_a_different_range_cannot_resume_a_staged_fetch(self):
        okx = FakeOKX(self.time)
        self.assertEqual(self.run_tool(okx, "--resume")[0], fetch.IN_PROGRESS)
        client = fetch.Client(max_requests=8, opener=okx, clock=self.time.clock, sleep=self.time.sleep,
                              base_url="https://fake.invalid")
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = fetch.main(["--days", "2", "--end-ms", str(END), "--resume"], client=client,
                              now_ms=END + 5 * 60_000, root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("resume_range_mismatch", err.getvalue())

    # F acceptance O10 (2026-11-08)
    def test_resume_refuses_a_budget_that_never_advances(self):
        for budget in ("6", "7"):
            with self.subTest(budget=budget), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
                fetch.main(["--days", "3", "--end-ms", str(END), "--resume", "--max-requests", budget],
                           now_ms=END + 5 * 60_000, root=self.root)
            self.assertEqual(stop.exception.code, 2)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_tool(FakeOKX(self.time), "--resume", max_requests=fetch.MIN_RESUME_REQUESTS - 1)
        self.assertFalse(fetch._staging_path(self.root, "BTC-USDT-SWAP", "15m").exists())
        self.assertEqual(self.run_tool(FakeOKX(self.time), "--resume",
                                       max_requests=fetch.MIN_RESUME_REQUESTS)[0], fetch.IN_PROGRESS)

    def test_funding_failure_on_the_last_run_keeps_this_runs_candles(self):
        okx = FakeOKX(self.time)
        self.assertEqual(self.run_tool(okx, "--resume")[0], fetch.IN_PROGRESS)

        class FailFundingOnce:
            failed = False

            def __call__(self, url):
                if not self.failed and fetch.FUNDING_PATH in url:
                    self.failed = True
                    return 400, b"{}"
                return okx(url)

        code, _, err, _ = self.run_tool(FailFundingOnce(), "--resume")
        self.assertEqual(code, 1)
        self.assertIn("http_400", err)
        staged = json.loads(fetch._staging_path(self.root, "BTC-USDT-SWAP", "15m").read_text(encoding="utf-8"))
        self.assertLessEqual(staged["cursor"], staged["start_ms"])  # every candle is kept
        self.assertEqual(staged["requests"], 2 + 3)  # run 1: instrument + page; run 2: 2 pages + failed funding
        before = len(okx.calls)
        code, out, err, _ = self.run_tool(okx, "--resume")
        self.assertEqual(code, 0, err)
        self.assertEqual([path for _, path, _ in okx.calls[before:]], [fetch.FUNDING_PATH])
        self.assertEqual(json.loads(out)["requests"], 6)

    # F fix acceptance N4 (2026-11-08)
    def test_a_first_run_paging_failure_still_counts_its_requests(self):
        okx = FakeOKX(self.time, script=[200, 400])  # instrument ok, first candle page fails
        code, _, err, client = self.run_tool(okx, "--resume")
        self.assertEqual((code, client.requests), (1, 2), err)
        staged = json.loads(fetch._staging_path(self.root, "BTC-USDT-SWAP", "15m").read_text(encoding="utf-8"))
        self.assertEqual((staged["requests"], staged["cursor"], staged["candles"]), (2, staged["end_ms"], []))
        spent = 2
        for _ in range(10):
            code, out, err, client = self.run_tool(okx, "--resume")
            spent += client.requests
            if code != fetch.IN_PROGRESS:
                break
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["requests"], spent)
        self.assertEqual([path for _, path, _ in okx.calls].count(fetch.INSTRUMENTS_PATH), 1)

    def test_staging_write_is_atomic_and_runs_are_paced_across_processes(self):
        clock = [100.0]
        okx = FakeOKX(self.time)
        with mock.patch.object(fetch, "wall_clock", lambda: clock[0]):
            self.assertEqual(self.run_tool(okx, "--resume")[0], fetch.IN_PROGRESS)
            path = fetch._staging_path(self.root, "BTC-USDT-SWAP", "15m")
            self.assertEqual(sorted(item.name for item in path.parent.iterdir()), [path.name])
            saved = path.read_bytes()
            with mock.patch.object(fetch.os, "replace", side_effect=OSError("disk full")):
                code, _, err, _ = self.run_tool(okx, "--resume")
            self.assertEqual(code, 1)
            self.assertIn("disk full", err)
            self.assertEqual(path.read_bytes(), saved)  # an interrupted write leaves the previous file
            clock[0] = 100.1
            sleeps = len(self.time.sleeps)
            calls = len(okx.calls)
            self.assertEqual(self.run_tool(okx, "--resume")[0], 0)
            self.assertAlmostEqual(self.time.sleeps[sleeps], fetch.MIN_INTERVAL_S - 0.1)
            self.assertGreater(len(okx.calls), calls)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
