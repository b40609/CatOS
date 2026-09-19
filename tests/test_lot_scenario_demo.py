"""S8 fixed local scenario example: real data path plus filesystem/CLI failures."""

from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser
import io
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from examples import lot_scenario_demo as demo


class Rows(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.rows, self.text, self.reasons = {}, [], []
        self.in_reasons = self.in_reason_code = False
        self.key = self.cell = None
        self.cells = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and attrs.get("id") == "reasons":
            self.in_reasons = True
        if tag == "code" and self.in_reasons:
            self.in_reason_code = True
        if tag == "tr":
            self.key, self.cells = attrs.get("data-field"), []
        elif tag == "td" and self.key is not None:
            self.cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self.in_reason_code:
            self.reasons.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "code":
            self.in_reason_code = False
        if tag == "section":
            self.in_reasons = False
        if tag == "td" and self.cell is not None:
            self.cells.append("".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.key is not None:
            self.rows[self.key] = tuple(self.cells)
            self.key = None


def invoke(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = demo.main(argv)
    return code, out.getvalue(), err.getvalue()


class RealScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_example(self, name="run"):
        target = self.root / name
        code, out, err = invoke(["--output-dir", str(target)])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), [
            f"database={target.resolve() / 'scenario.sqlite3'}",
            f"complete={target.resolve() / 'complete.html'}",
            f"degraded={target.resolve() / 'degraded.html'}",
        ])
        return target

    def test_a01_real_journal_partial_fill_and_retained_database(self):
        target = self.run_example()
        db = target / "scenario.sqlite3"
        uri = db.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM lot_fill_orders").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM lot_fill_events").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM lot_fill_terminals").fetchone()[0], 0)
            row = connection.execute(
                "SELECT resolved_quantity FROM lot_fill_orders"
            ).fetchone()
            self.assertEqual(row[0], "3")
            row = connection.execute(
                "SELECT quantity,price,fee_paid,fee_currency FROM lot_fill_events"
            ).fetchone()
            self.assertEqual((row[0], row[2], row[3]), ("1", "0.01", "USDT"))
            self.assertEqual(row[1], "1E+2")
        finally:
            connection.close()

    def test_a02_complete_report_exact_semantics(self):
        doc = Rows((self.run_example() / "complete.html").read_text(encoding="utf-8"))
        values = {
            "comparison_status": "合成情境數量相符（MATCH）",
            "observed_long_qty": "1", "observed_short_qty": "0",
            "observed_gross_qty": "1", "observed_net_qty": "1",
            "physical_qty": "1", "delta_qty": "0",
            "pending_buy_qty": "2", "pending_sell_qty": "0",
            "synthetic_buy_qty": "2", "synthetic_sell_qty": "0",
            "held_buy_qty": "0", "held_sell_qty": "0",
            "exchange_buy_qty": "0", "exchange_sell_qty": "0",
            "physical_scenario_upper_qty": "3", "virtual_gross_scenario_upper_qty": "3",
            "observed_gross_notional": "1.00123456789012345678901234",
            "observed_signed_net_notional": "1.00123456789012345678901234",
            "physical_notional": "1.00123456789012345678901234",
            "unresolved_lot_count": "1", "pending_unique_count": "1",
            "pending_duplicate_count": "0", "scenario.mark": "100.123456789012345678901234",
        }
        for key, value in values.items():
            with self.subTest(key=key):
                self.assertEqual(value, doc.rows[key][0])
        for key in ("lot_complete", "pending_complete", "lot_fresh", "physical_fresh",
                    "pending_fresh", "physical_verified", "mark_fresh"):
            self.assertEqual(doc.rows[key][0], "是（true）")
        self.assertEqual(doc.rows["has_unknown"][0], "否（false）")
        text = "".join(doc.text)
        self.assertIn("無降級原因", text)

    def test_a03_degraded_report_exact_semantics(self):
        doc = Rows((self.run_example() / "degraded.html").read_text(encoding="utf-8"))
        self.assertEqual(doc.rows["comparison_status"][0], "無法比較（UNAVAILABLE）")
        for key in ("observed_long_qty", "observed_gross_qty", "observed_net_qty", "physical_qty"):
            self.assertEqual(doc.rows[key][0], "1")
        for key in ("pending_buy_qty", "pending_sell_qty", "synthetic_buy_qty",
                    "synthetic_sell_qty", "held_buy_qty", "held_sell_qty",
                    "exchange_buy_qty", "exchange_sell_qty", "physical_scenario_upper_qty",
                    "virtual_gross_scenario_upper_qty", "observed_gross_notional",
                    "observed_signed_net_notional", "physical_notional", "delta_qty"):
            self.assertEqual(doc.rows[key][0], "不可用")
        self.assertEqual(doc.rows["pending_complete"][0], "是（true）")
        self.assertEqual(doc.rows["physical_verified"][0], "否（false）")
        self.assertEqual(doc.rows["mark_fresh"][0], "否（false）")
        self.assertEqual(doc.rows["has_unknown"][0], "否（false）")
        self.assertEqual(doc.rows["quote_id"][0], "未提供")
        self.assertEqual(doc.rows["scenario.mark"][0], "未提供")
        self.assertEqual(doc.reasons, ["mark_missing", "physical_unverified"])
        for key in ("lot_complete", "lot_fresh", "physical_fresh", "pending_fresh"):
            self.assertEqual(doc.rows[key][0], "是（true）")
        for key, number in (("observed_short_qty", "0"), ("unresolved_lot_count", "1"),
                            ("pending_unique_count", "1"), ("pending_duplicate_count", "0")):
            self.assertEqual(doc.rows[key][0], number)
        for key in ("scenario.mark_observed_at_ms", "scenario.mark_valid_until_ms"):
            self.assertEqual(doc.rows[key][0], "未提供")
        text = "\n".join(doc.text)
        self.assertIn("mark_missing", text)
        self.assertIn("physical_unverified", text)
        for reason in ("lot_stale", "physical_stale", "mark_stale", "pending_stale",
                       "pending_missing", "pending_incomplete", "pending_cut_mismatch"):
            self.assertNotIn(reason, text)

    def test_a04_one_capture_two_render_calls_same_capture(self):
        target = self.root / "call-order"
        seen = []
        real_render = demo.render_synthetic_scenario_report
        real_capture = demo.Journal.capture_lot_snapshot
        captures = []
        def record_capture(journal, **kwargs):
            result = real_capture(journal, **kwargs)
            captures.append(result)
            return result
        with patch.object(demo.Journal, "capture_lot_snapshot", autospec=True, side_effect=record_capture) as capture_call, patch.object(demo, "render_synthetic_scenario_report") as renderer:
            def record(**kwargs):
                seen.append((id(kwargs["capture"]), kwargs["scenario"].scenario_cut_id, kwargs["now_ms"]))
                return real_render(**kwargs)
            renderer.side_effect = record
            code, _, err = invoke(["--output-dir", str(target)])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(renderer.call_count, 2)
        self.assertEqual(capture_call.call_count, 1)
        self.assertEqual(seen[0][0], id(captures[0]))
        self.assertEqual([row[1:] for row in seen], [
            ("s8-complete-cut", 1500), ("s8-degraded-cut", 1500)
        ])
        self.assertEqual(seen[0][0], seen[1][0])

    def test_b01_two_runs_are_byte_reproducible_without_bom(self):
        first, second = self.run_example("one"), self.run_example("two")
        for name in ("complete.html", "degraded.html"):
            left, right = (first / name).read_bytes(), (second / name).read_bytes()
            self.assertEqual(left, right)
            self.assertFalse(left.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"100.123456789012345678901234" if name == "complete.html" else b"UNAVAILABLE", left)


class PathAndCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_b02_existing_directory_file_and_nonempty_directory_are_rejected_before_journal(self):
        paths = []
        empty = self.root / "empty"; empty.mkdir(); paths.append(empty)
        nonempty = self.root / "nonempty"; nonempty.mkdir(); (nonempty / "sentinel").write_text("keep"); paths.append(nonempty)
        file_path = self.root / "file"; file_path.write_text("keep"); paths.append(file_path)
        with patch.object(demo, "Journal") as journal:
            for path in paths:
                with self.subTest(path=path.name):
                    code, out, err = invoke(["--output-dir", str(path)])
                    self.assertEqual((code, out), (1, ""))
                    self.assertIn("stage=output_dir", err)
                    self.assertNotIn("artifacts=", err)
            journal.assert_not_called()
        self.assertEqual((nonempty / "sentinel").read_text(), "keep")
        self.assertEqual(file_path.read_text(), "keep")

    def test_b03_symlink_targets_are_rejected_when_supported(self):
        target = self.root / "real"; target.mkdir(); (target / "sentinel").write_text("keep")
        link = self.root / "link"
        dangling = self.root / "dangling"
        try:
            link.symlink_to(target, target_is_directory=True)
            dangling.symlink_to(self.root / "missing", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with patch.object(demo, "Journal") as journal:
            for path in (link, dangling):
                code, out, err = invoke(["--output-dir", str(path)])
                self.assertEqual((code, out), (1, ""))
                self.assertIn("stage=output_dir", err)
            journal.assert_not_called()
        self.assertEqual((target / "sentinel").read_text(), "keep")
        self.assertTrue(link.is_symlink())
        self.assertTrue(dangling.is_symlink())

    def test_b04_missing_parent_and_parent_file_are_rejected(self):
        parent_file = self.root / "parent-file"; parent_file.write_text("keep")
        for path in (self.root / "missing" / "child", parent_file / "child"):
            with self.subTest(path=str(path)):
                code, out, err = invoke(["--output-dir", str(path)])
                self.assertEqual((code, out), (1, ""))
                self.assertIn("stage=output_dir", err)
        self.assertFalse((self.root / "missing").exists())

    def test_d01_help_usage_empty_unknown_and_abbreviation_have_no_side_effect(self):
        directory_creation = patch.object(Path, "mkdir", side_effect=AssertionError("unexpected directory creation"))
        journal_creation = patch.object(demo, "Journal", side_effect=AssertionError("unexpected Journal"))
        mkdir = directory_creation.start()
        journal = journal_creation.start()
        self.addCleanup(directory_creation.stop)
        self.addCleanup(journal_creation.stop)
        with self.assertRaises(SystemExit) as help_exit:
            with redirect_stdout(io.StringIO()) as help_out:
                demo.main(["--help"])
        self.assertEqual(help_exit.exception.code, 0)
        help_text = help_out.getvalue()
        normalized_help = " ".join(help_text.split())
        self.assertIn("retains its SQLite database", normalized_help)
        self.assertIn("never overwrites", normalized_help)
        for argv in ([], ["--bad"], ["--output"], ["--output-dir", ""]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as caught:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    demo.main(argv)
            self.assertEqual(caught.exception.code, 2)
        self.assertEqual(list(self.root.iterdir()), [])
        mkdir.assert_not_called()
        journal.assert_not_called()

    def test_d02_module_launch_with_spaces_prints_exact_success_paths(self):
        target = self.root / "run with spaces"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "examples.lot_scenario_demo", "--output-dir", str(target)],
            cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.splitlines(), [
            f"database={target.resolve() / 'scenario.sqlite3'}",
            f"complete={target.resolve() / 'complete.html'}",
            f"degraded={target.resolve() / 'degraded.html'}",
        ])

    def test_d03_production_source_has_no_test_private_hash_env_or_network_dependencies(self):
        source = Path(demo.__file__).read_text(encoding="utf-8")
        for forbidden in ("from tests", "import tests", "snapshot._capture_id", "lot_snapshot._capture_id",
                          "os.environ", "getenv(",
                          "socket", "requests", "urllib", "http://", "https://", "force"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_c01_journal_init_failure_retains_new_directory_without_html(self):
        target = self.root / "journal-fail"
        with patch.object(demo, "Journal", side_effect=RuntimeError("boom")):
            code, out, err = invoke(["--output-dir", str(target)])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("stage=journal_init; error=RuntimeError", err)
        self.assertIn(f"artifacts={target.resolve()}; retained", err)
        self.assertTrue(target.is_dir())
        self.assertFalse((target / "complete.html").exists())

    def test_c01_scenario_failure_closes_journal_and_writes_no_html(self):
        target = self.root / "scenario-fail"
        real = demo.Journal
        holder = {}
        def make(*args, **kwargs):
            holder["journal"] = real(*args, **kwargs)
            holder["close"] = Mock(wraps=holder["journal"].close)
            holder["journal"].close = holder["close"]
            return holder["journal"]
        with patch.object(demo, "Journal", side_effect=make), patch.object(
            demo, "_render_run", side_effect=RuntimeError("scenario")
        ):
            code, out, err = invoke(["--output-dir", str(target)])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("stage=scenario; error=RuntimeError", err)
        holder["close"].assert_called_once_with()
        self.assertFalse((target / "complete.html").exists())

    def test_c02_close_failure_blocks_html_and_double_failure_preserves_group(self):
        for scenario_fails in (False, True):
            with self.subTest(scenario_fails=scenario_fails):
                target = self.root / f"close-{scenario_fails}"
                fake = Mock()
                fake.close.side_effect = RuntimeError("close")
                if scenario_fails:
                    render = patch.object(demo, "_render_run", side_effect=ValueError("scenario"))
                else:
                    render = patch.object(demo, "_render_run", return_value=("a", "b"))
                with patch.object(demo, "Journal", return_value=fake), render:
                    code, out, err = invoke(["--output-dir", str(target)])
                self.assertEqual((code, out), (1, ""))
                self.assertIn("stage=journal_close", err)
                self.assertIn("error=ExceptionGroup" if scenario_fails else "error=RuntimeError", err)
                self.assertFalse((target / "complete.html").exists())

    def test_c03_complete_and_degraded_write_failures_retain_prior_artifacts(self):
        for failing_name in ("complete.html", "degraded.html"):
            with self.subTest(failing_name=failing_name):
                target = self.root / failing_name.replace(".", "-")
                real_write = demo._write_exclusive
                def fail(path, content):
                    if path.name == failing_name:
                        path.write_text("sentinel", encoding="utf-8")
                    real_write(path, content)
                with patch.object(demo, "_write_exclusive", side_effect=fail):
                    code, out, err = invoke(["--output-dir", str(target)])
                self.assertEqual((code, out), (1, ""))
                self.assertIn("stage=write_" + failing_name[:-5], err)
                self.assertEqual((target / failing_name).read_text(encoding="utf-8"), "sentinel")
                if failing_name == "degraded.html":
                    self.assertTrue((target / "complete.html").exists())

    def test_d04_keyboard_interrupt_closes_journal_and_propagates(self):
        target = self.root / "interrupt"
        fake = Mock()
        fake.close.return_value = None
        with patch.object(demo, "Journal", return_value=fake), patch.object(
            demo, "_render_run", side_effect=KeyboardInterrupt()
        ), self.assertRaises(KeyboardInterrupt):
            demo.main(["--output-dir", str(target)])
        fake.close.assert_called_once_with()

    def test_b04_permission_failure_does_not_open_journal(self):
        target = self.root / "permission"
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")), patch.object(demo, "Journal") as factory:
            code, out, err = invoke(["--output-dir", str(target)])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("stage=output_dir; error=PermissionError", err)
        self.assertNotIn("artifacts=", err)
        factory.assert_not_called()

    def test_c01_each_data_and_render_failure_closes_real_journal(self):
        for failure in ("bind", "fill", "capture", "render1", "render2"):
            with self.subTest(failure=failure):
                target = self.root / failure
                real_factory = demo.Journal
                holder = {}
                def make(*args, **kwargs):
                    journal = real_factory(*args, **kwargs)
                    holder["journal"] = journal
                    holder["close"] = Mock(wraps=journal.close)
                    journal.close = holder["close"]
                    owner, attr = {
                        "bind": (journal.lot_fills, "bind_order"),
                        "fill": (journal.lot_fills, "apply_fill"),
                        "capture": (journal, "capture_lot_snapshot"),
                    }.get(failure, (None, None))
                    if owner is not None:
                        setattr(owner, attr, Mock(side_effect=RuntimeError(failure)))
                    return journal
                real_render = demo.render_synthetic_scenario_report
                render_count = 0
                def render(**kwargs):
                    nonlocal render_count
                    render_count += 1
                    if failure == f"render{render_count}":
                        raise RuntimeError(failure)
                    return real_render(**kwargs)
                with patch.object(demo, "Journal", side_effect=make), patch.object(demo, "render_synthetic_scenario_report", side_effect=render), patch.object(demo, "_write_exclusive") as writer:
                    code, out, err = invoke(["--output-dir", str(target)])
                self.assertEqual((code, out), (1, ""))
                self.assertIn("stage=scenario; error=RuntimeError", err)
                holder["close"].assert_called_once_with()
                writer.assert_not_called()
                with self.assertRaises(sqlite3.ProgrammingError):
                    holder["journal"].connection.execute("SELECT 1")

    def test_c02_double_failure_keeps_original_exception_objects(self):
        body_error, close_error = ValueError("body"), RuntimeError("close")
        fake = Mock()
        fake.close.side_effect = close_error
        with patch.object(demo, "Journal", return_value=fake), patch.object(demo, "_render_run", side_effect=body_error), patch.object(demo, "_failure", return_value=1) as failure, patch.object(demo, "_write_exclusive") as writer:
            self.assertEqual(demo.main(["--output-dir", str(self.root / "group")]), 1)
        stage, group, _ = failure.call_args.args
        self.assertEqual(stage, "journal_close")
        self.assertIsInstance(group, ExceptionGroup)
        self.assertIs(group.exceptions[0], body_error)
        self.assertIs(group.exceptions[1], close_error)
        writer.assert_not_called()

    def test_c03_stream_write_and_close_failures_retain_partial_files(self):
        real_open = Path.open
        for name in ("complete.html", "degraded.html"):
            for operation in ("write", "close"):
                with self.subTest(name=name, operation=operation):
                    target = self.root / (name + "-" + operation)
                    def faulty_open(path, *args, **kwargs):
                        stream = real_open(path, *args, **kwargs)
                        if path.name != name:
                            return stream
                        class FailingStream:
                            def __enter__(self):
                                return self
                            def write(self, content):
                                if operation == "write":
                                    stream.write("partial")
                                    raise OSError("write failure")
                                return stream.write(content)
                            def __exit__(self, kind, value, tb):
                                stream.close()
                                if operation == "close":
                                    raise OSError("close failure")
                                return False
                        return FailingStream()
                    with patch.object(Path, "open", faulty_open):
                        code, out, err = invoke(["--output-dir", str(target)])
                    self.assertEqual((code, out), (1, ""))
                    self.assertIn("stage=write_" + name[:-5] + "; error=OSError", err)
                    self.assertTrue((target / "scenario.sqlite3").exists())
                    content = (target / name).read_text(encoding="utf-8")
                    if operation == "write":
                        self.assertEqual(content, "partial")
                    else:
                        self.assertTrue(content.startswith("<!DOCTYPE html>"))
                    if name == "degraded.html":
                        self.assertTrue((target / "complete.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))
                    else:
                        self.assertFalse((target / "degraded.html").exists())

    def test_c04_journal_is_closed_before_first_html_open(self):
        holder = {}
        real_factory, real_write = demo.Journal, demo._write_exclusive
        def make(*args, **kwargs):
            holder["journal"] = real_factory(*args, **kwargs)
            return holder["journal"]
        def write(path, content):
            with self.assertRaises(sqlite3.ProgrammingError):
                holder["journal"].connection.execute("SELECT 1")
            real_write(path, content)
        with patch.object(demo, "Journal", side_effect=make), patch.object(demo, "_write_exclusive", side_effect=write):
            code, _, err = invoke(["--output-dir", str(self.root / "closed-first")])
        self.assertEqual((code, err), (0, ""))

    def test_d04_console_failure_is_nonzero_and_retains_all_artifacts(self):
        target = self.root / "console"
        stdout, stderr = Mock(), io.StringIO()
        stdout.write.side_effect = OSError("console")
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = demo.main(["--output-dir", str(target)])
        self.assertEqual(code, 1)
        self.assertIn("error=OSError", stderr.getvalue())
        for name in ("scenario.sqlite3", "complete.html", "degraded.html"):
            self.assertTrue((target / name).is_file())


if __name__ == "__main__":
    unittest.main()
