"""Synthetic regression tests for the extra CLI's output and explicit specs."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import cli


class CLIOutputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.csv_path = self.root / "candles.csv"
        self.output = self.root / "report.html"
        self.contract = cli.ContractSpec("SYNTHETIC-USDT-SWAP", Decimal("0.01"),
                                         Decimal("0.1"), Decimal("1"), Decimal("1"))
        self.csv_text = "open_time_ms,open,high,low,close,closed\n" + "".join(
            f"{i * 900000},100,100,100,100,1\n" for i in range(8)
        )
        self.csv_path.write_text(self.csv_text, encoding="utf-8")

    def run_report(self, *, csv_path=None, output=None):
        return cli.run_cli(
            csv_path=str(self.csv_path if csv_path is None else csv_path),
            symbol="SYNTHETIC-USDT-SWAP", fast=1, slow=2,
            report_path=str(self.output if output is None else output),
            contract=self.contract,
        )

    def test_specs_are_required_and_must_match_symbol(self):
        for contract in (None, replace(self.contract, inst_id="OTHER-USDT-SWAP")):
            with self.subTest(contract=contract), patch.object(cli, "backtest") as run:
                with self.assertRaisesRegex(ValueError, "explicit ContractSpec"):
                    cli.run_cli(str(self.csv_path), "SYNTHETIC-USDT-SWAP", 1, 2,
                                str(self.output), contract=contract)
                run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_nondefault_spec_is_used_without_hidden_override(self):
        self.contract = replace(self.contract, base_per_contract=Decimal("0.2"),
                                tick_size=Decimal("0.01"), lot_size=Decimal("0.5"), min_size=Decimal("0.5"))
        with patch.object(cli, "backtest", wraps=cli.backtest) as run, redirect_stdout(StringIO()):
            self.run_report()
        self.assertEqual(run.call_args.kwargs["config"].contract, self.contract)

    def test_main_requires_explicit_specs(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            cli.main(["--csv", str(self.csv_path), "--symbol", "SYNTHETIC-USDT-SWAP",
                      "--report", str(self.output)])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_new_report_creates_parents_and_preserves_input(self):
        target = self.root / "nested" / "deep" / "report.HTML"
        with redirect_stdout(StringIO()):
            self.assertEqual(self.run_report(output=target), target.resolve())
        content = target.read_text(encoding="utf-8")
        self.assertIn("SYNTHETIC-USDT-SWAP", content)
        self.assertIn("</html>", content.lower())
        self.assertEqual(self.csv_path.read_text(encoding="utf-8"), self.csv_text)

    def test_existing_report_is_rejected_before_reading_candles(self):
        original = b"existing report\x00must survive"
        self.output.write_bytes(original)
        with patch.object(cli, "detect_timeframe_ms") as detect:
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.run_report()
            detect.assert_not_called()
        self.assertEqual(self.output.read_bytes(), original)

    def test_same_input_path_is_rejected_including_html_and_normalized_alias(self):
        for suffix in ("csv", "html"):
            with self.subTest(suffix=suffix):
                source = self.root / f"source.{suffix}"
                source.write_text(self.csv_text, encoding="utf-8")
                parent = self.root / "alias"
                parent.mkdir(exist_ok=True)
                target = parent / ".." / source.name
                with patch.object(cli, "detect_timeframe_ms") as detect:
                    with self.assertRaisesRegex(ValueError, "same as input"):
                        self.run_report(csv_path=source, output=target)
                    detect.assert_not_called()
                self.assertEqual(source.read_text(encoding="utf-8"), self.csv_text)

    def test_non_html_output_is_rejected_without_creating_directories(self):
        target = self.root / "not-created" / "report.txt"
        with patch.object(cli, "detect_timeframe_ms") as detect:
            with self.assertRaisesRegex(ValueError, r"end with \.html"):
                self.run_report(output=target)
            detect.assert_not_called()
        self.assertFalse(target.parent.exists())

    def test_missing_input_does_not_create_output(self):
        target = self.root / "not-created" / "report.html"
        with self.assertRaises(FileNotFoundError):
            self.run_report(csv_path=self.root / "missing.csv", output=target)
        self.assertFalse(target.parent.exists())

    def test_backtest_or_render_failure_does_not_create_output(self):
        for stage in ("backtest", "render_report"):
            with self.subTest(stage=stage):
                target = self.root / stage / "report.html"
                with patch.object(cli, stage, side_effect=ValueError("synthetic failure")):
                    with self.assertRaisesRegex(ValueError, "synthetic failure"):
                        self.run_report(output=target)
                self.assertFalse(target.parent.exists())

    def test_partial_output_is_removed_on_write_flush_close_or_interrupt(self):
        real_open = open
        for failure in ("write", "flush", "close", "interrupt"):
            with self.subTest(failure=failure):
                target = self.root / f"{failure}.html"

                class FailingWriter:
                    def __init__(self, stream):
                        self.stream = stream

                    def fileno(self):
                        return self.stream.fileno()

                    def write(self, text):
                        self.stream.write(text[:10])
                        if failure == "interrupt":
                            raise KeyboardInterrupt()
                        if failure == "write":
                            raise OSError("synthetic write failure")

                    def flush(self):
                        self.stream.flush()
                        if failure == "flush":
                            raise OSError("synthetic flush failure")

                    def close(self):
                        self.stream.close()
                        if failure == "close":
                            raise OSError("synthetic close failure")

                def opening(file, *args, **kwargs):
                    stream = real_open(file, *args, **kwargs)
                    if Path(file).resolve() == target:
                        self.assertEqual(kwargs.get("mode"), "x")
                        return FailingWriter(stream)
                    return stream

                stdout = StringIO()
                with patch("catos.cli.open", side_effect=opening), redirect_stdout(stdout):
                    expected = KeyboardInterrupt if failure == "interrupt" else OSError
                    with self.assertRaises(expected):
                        self.run_report(output=target)
                self.assertFalse(target.exists())
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(self.csv_path.read_text(encoding="utf-8"), self.csv_text)

    def test_creation_race_preserves_other_writer(self):
        real_open = open

        def opening(file, *args, **kwargs):
            if Path(file).resolve() == self.output:
                self.assertEqual(kwargs.get("mode"), "x")
                with real_open(file, "x", encoding="utf-8") as competitor:
                    competitor.write("other writer")
            return real_open(file, *args, **kwargs)

        with patch("catos.cli.open", side_effect=opening):
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.run_report()
        self.assertEqual(self.output.read_text(encoding="utf-8"), "other writer")
        self.assertEqual(self.csv_path.read_text(encoding="utf-8"), self.csv_text)

    def test_cleanup_preserves_a_replacement_file(self):
        real_open = open
        target = self.output
        moved = self.root / "original-partial.html"

        class ReplacingWriter:
            def __init__(self, stream):
                self.stream = stream

            def fileno(self):
                return self.stream.fileno()

            def write(self, text):
                self.stream.write(text[:10])
                # Close before renaming so this fixture also works on Windows.
                self.stream.close()
                target.replace(moved)
                target.write_text("replacement file", encoding="utf-8")
                raise OSError("synthetic replacement failure")

            def close(self):
                self.stream.close()

        def opening(file, *args, **kwargs):
            stream = real_open(file, *args, **kwargs)
            return ReplacingWriter(stream) if Path(file).resolve() == target else stream

        with patch("catos.cli.open", side_effect=opening):
            with self.assertRaisesRegex(OSError, "synthetic replacement failure"):
                self.run_report()
        self.assertEqual(target.read_text(encoding="utf-8"), "replacement file")
        self.assertTrue(moved.exists())

    def test_main_reports_protection_failure_without_success_output(self):
        self.output.write_text("keep", encoding="utf-8")
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = cli.main([
                "--csv", str(self.csv_path), "--report", str(self.output),
                "--symbol", "SYNTHETIC-USDT-SWAP", "--fast", "1", "--slow", "2",
                "--base-per-contract", "0.01", "--tick-size", "0.1",
                "--lot-size", "1", "--min-size", "1",
            ])
        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("already exists", stderr.getvalue())
        self.assertEqual(self.output.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
