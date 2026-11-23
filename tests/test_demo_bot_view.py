"""Read-only OKX Demo Bot view (catos/demo_bot_view.py) over a fixture run folder."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catos.demo_bot_view import mount_demo_bot

RUN = "a" * 32
OLD = "b" * 32


def _write_run(root, run_id, *, created, state, updated, events, stop_reason=None):
    d = root / run_id
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps(dict(
        run_id=run_id, created_at=created.isoformat(), mode="okx-demo-bot", approval_id="c" * 32,
        disaster_stop="0.1", starting_equity="5000", resumes=[{"at": "x"}],
        profile=dict(strategy_id="donchian-breakout", version="v1", parameters={"entry_bars": 192, "exit_bars": 48},
                     timeframe_ms=900_000, quantity="1", inst_id="BTC-USDT-SWAP"))), encoding="utf-8")
    (d / "status.json").write_text(json.dumps(dict(
        state=state, bars=5, fills=2, position="1", stop_reason=stop_reason, updated_at=updated.isoformat())),
        encoding="utf-8")
    (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events) + '{"kind": "bar", "trunc', encoding="utf-8")


class DemoBotViewTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        now = datetime.now(timezone.utc)
        t = lambda minutes: (now - timedelta(minutes=minutes)).isoformat()
        events = [
            {"kind": "started", "time": t(30), "resumed": False, "manifest": {"approval_record": {"secret": "x"}}},
            {"kind": "fill", "time": t(20), "leg": "開倉", "row": {"cl_ord_id": "o1", "state": "FILLED", "filled": "1"},
             "fills": [{"quantity": "1", "price": "100", "fee": "0.05"}]},
            {"kind": "protection", "time": t(19), "price": "90", "side": "sell", "algo_id": "7"},
            {"kind": "bar", "time": t(15), "bar": {"open_time_ms": 1, "close": "101"}, "mark": "101", "equity": "5001",
             "disposition": "NO_CHANGE", "reason": "hold", "target": "1", "risk_reasons": []},
            {"kind": "fill", "time": t(10), "leg": "出場", "row": {"cl_ord_id": "o2", "state": "FILLED", "filled": "1"},
             "fills": [{"quantity": "-1", "price": "102", "fee": "0.05"}]},
            {"kind": "protection", "time": t(9), "price": None},
        ]
        _write_run(self.root, RUN, created=now - timedelta(hours=1), state="running", updated=now - timedelta(hours=2),
                   events=events)
        _write_run(self.root, OLD, created=now - timedelta(days=1), state="stopped", updated=now - timedelta(days=1),
                   events=[], stop_reason="operator_stop_file")
        (self.root / "notarun").mkdir()
        app = FastAPI()
        mount_demo_bot(app, root=self.root)
        self.client = TestClient(app)

    def test_overview_newest_first_with_detail(self):
        data = self.client.get("/api/workspace/demo-bot").json()
        self.assertEqual(data["contract"], "catos.demo-bot.v1")
        self.assertEqual([r["run_id"] for r in data["runs"]], [RUN, OLD])
        current = data["current"]
        self.assertTrue(current["stale"])  # running, silent for 2 hours on a 15m bar
        self.assertEqual([f["side"] for f in current["fill_rows"]], ["sell", "buy"])
        self.assertIsNone(current["protection"])  # the last protection event canceled it
        self.assertEqual(current["last_bar"]["equity"], "5001")
        self.assertEqual(current["resumes"], 1)
        self.assertNotIn("secret", json.dumps(current))  # the manifest copy in "started" is not shown
        self.assertIn("protection", [e["kind"] for e in current["events"]])
        self.assertNotIn("bar", [e["kind"] for e in current["events"]])

    def test_single_run_and_hint(self):
        run = self.client.get(f"/api/workspace/demo-bot/runs/{OLD}").json()["run"]
        self.assertFalse(run["stale"])
        self.assertEqual(run["stop_reason"], "operator_stop_file")
        self.assertEqual(run["fill_rows"], [])

    def test_bad_or_missing_run_is_404(self):
        for run_id in ("..x", "notarun", "0" * 32, "A" * 32):
            self.assertEqual(self.client.get(f"/api/workspace/demo-bot/runs/{run_id}").status_code, 404)

    def test_missing_root_is_empty(self):
        app = FastAPI()
        mount_demo_bot(app, root=self.root / "missing")
        data = TestClient(app).get("/api/workspace/demo-bot").json()
        self.assertEqual((data["runs"], data["current"]), ([], None))


if __name__ == "__main__":
    unittest.main()
