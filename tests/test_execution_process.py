"""Bounded real process crashes; no market data or remote calls."""

from decimal import Decimal as D
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from catos import risk
from catos.journal import Journal
from catos.fake_exchange import Fill
from test_ipc import config
from test_journal import prepare_and_commit, proof
from test_execution import report


class ExecutionProcessTests(unittest.TestCase):
    def test_process_death_before_after_commit_and_after_handoff(self):
        repo = Path(__file__).resolve().parents[1]
        script = repo / "tests" / "fixtures" / "execution_process.py"
        bootstrap = f"import sys,runpy;sys.path[:0]=[{str(repo)!r},{str(repo / 'tests')!r}];runpy.run_path({str(script)!r},run_name='__main__')"
        for mode, exit_code in (("before_commit", 71), ("after_commit", 72), ("after_handoff", 73)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "state.sqlite3"
                j = Journal(path, "fake-account", D("100"), risk.Limits(), True)
                j.register("bot", config())
                j.reconcile("bot", proof(0))
                prepare_and_commit(j, 0)
                prepare_and_commit(j, 1)
                j.close()
                result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", bootstrap,
                    mode, str(Path(directory) / "locks"), str(path)], capture_output=True, text=True,
                    timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.assertEqual(result.returncode, exit_code, result.stderr)
                j = Journal(path, "fake-account", D("100"), risk.Limits(), True)
                try:
                    orders = j.execution.unresolved()
                    self.assertEqual(j.total_reserved(), D("2"))
                    self.assertEqual(j.snapshot("bot")["health"], "RECONCILING")
                    if mode == "before_commit":
                        self.assertEqual(orders, [])
                    else:
                        self.assertEqual(len(orders), 1)
                        self.assertEqual(orders[0]["state"], "UNKNOWN")
                        key = orders[0]["order_key"]
                        self.assertIsNone(j.execution.prepare("bot", key, 0))
                        j.execution.apply(key, report(key, status="FILLED", fills=(Fill("recovered", D("2"), D("100")),), complete=True))
                        self.assertEqual(j.snapshot("bot")["owner"]["position"], "2")
                        self.assertEqual(j.total_reserved(), 0)
                    if mode == "after_handoff":
                        self.assertIn("HANDED_OFF:1", result.stdout)
                        self.assertEqual(j.risk_state().mode, "FLAT")
                finally:
                    j.close()


if __name__ == "__main__":
    unittest.main()
