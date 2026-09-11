"""Dedicated unit tests for catos.research_cli command-line module."""

import codecs
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal, InvalidOperation, localcontext
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from catos.research_cli import main, parse_config_json, run_pipeline

STEP = 900_000


def make_valid_csv(num_bars: int = 6, base_price: str = "100.00") -> str:
    lines = ["open_time_ms,open,high,low,close,closed"]
    for i in range(num_bars):
        t = i * STEP
        lines.append(f"{t},{base_price},{base_price},{base_price},{base_price},1")
    return "\n".join(lines) + "\n"


def make_valid_config_dict() -> dict:
    return {
        "contract": {
            "inst_id": "SYNTHETIC-USDT-SWAP",
            "base_per_contract": "0.01",
            "tick_size": "0.01",
            "lot_size": "1",
            "min_size": "1",
        },
        "timeframe_ms": STEP,
        "initial_balance": "1000",
        "fee_rate": "0.0005",
        "slippage_bps": "2",
        "funding_events": [],
        "warmup_bars": 2,
    }


class ResearchCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.tmp_dir.name)
        self.csv_path = self.dir_path / "data.csv"
        self.config_path = self.dir_path / "config.json"
        self.output_path = self.dir_path / "report.html"

        self.csv_path.write_text(make_valid_csv(8), encoding="utf-8")
        self.config_path.write_text(json.dumps(make_valid_config_dict()), encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_cli_end_to_end_success(self):
        ret = main([
            "--csv", str(self.csv_path),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(self.output_path),
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(self.output_path.exists())
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("SYNTHETIC-USDT-SWAP", content)
        self.assertIn("研究結果，非 Demo／Live 執行器", content)

    def test_subprocess_entrypoint(self):
        out_file = self.dir_path / "sub_report.html"
        cmd = [
            sys.executable, "-B", "-m", "catos.research_cli",
            "--csv", str(self.csv_path),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(out_file),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("報告已成功輸出至", proc.stdout)
        self.assertIn("聲明：本報告為純記憶體研究結果", proc.stdout)
        self.assertTrue(out_file.exists())

    def test_config_bom_and_decimal_precision_and_funding_events(self):
        cfg_dict = make_valid_config_dict()
        cfg_dict["contract"]["base_per_contract"] = "0.000000000000000001"
        cfg_dict["funding_events"] = [
            {
                "time_ms": 3 * STEP,
                "rate": "0.0001",
                "mark_price": "100.00",
            }
        ]
        bom_config_path = self.dir_path / "bom_config.json"
        raw_bytes = codecs.BOM_UTF8 + json.dumps(cfg_dict).encode("utf-8")
        bom_config_path.write_bytes(raw_bytes)

        out_file = self.dir_path / "bom_report.html"
        ret = main([
            "--csv", str(self.csv_path),
            "--config", str(bom_config_path),
            "--strategy", "sma-trend",
            "--output", str(out_file),
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("0.000000000000000001", content)
        self.assertIn("0.0001", content)

    def test_warmup_bars_effective(self):
        # 4 bars total, warmup 3 -> 1 evaluation bar
        short_csv = self.dir_path / "short.csv"
        short_csv.write_text(make_valid_csv(4), encoding="utf-8")

        cfg_dict = make_valid_config_dict()
        cfg_dict["warmup_bars"] = 3
        cfg_path = self.dir_path / "warmup3_cfg.json"
        cfg_path.write_text(json.dumps(cfg_dict), encoding="utf-8")

        out_file = self.dir_path / "warmup3_report.html"
        ret = main([
            "--csv", str(short_csv),
            "--config", str(cfg_path),
            "--strategy", "sma-trend",
            "--output", str(out_file),
        ])
        self.assertEqual(ret, 0)
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("預熱根數 (warmup_bars)</div>\n    <div class=\"card-value\">3</div>", content)

    def test_config_validation_rejects_bad_schemas(self):
        cases = [
            # Missing root key
            ("missing_warmup", lambda d: d.pop("warmup_bars")),
            # Extra root key
            ("extra_root_key", lambda d: d.update({"unexpected": 123})),
            # Missing contract key
            ("missing_contract_key", lambda d: d["contract"].pop("tick_size")),
            # Extra contract key
            ("extra_contract_key", lambda d: d["contract"].update({"extra": "1"})),
            # Financial number instead of string
            ("financial_float", lambda d: d.update({"fee_rate": 0.0005})),
            ("financial_int", lambda d: d.update({"initial_balance": 1000})),
            ("contract_float", lambda d: d["contract"].update({"tick_size": 0.01})),
            # Non-integer for integer fields
            ("bool_timeframe", lambda d: d.update({"timeframe_ms": True})),
            ("string_timeframe", lambda d: d.update({"timeframe_ms": "900000"})),
            ("float_timeframe", lambda d: d.update({"timeframe_ms": 900000.0})),
            ("bool_warmup", lambda d: d.update({"warmup_bars": False})),
            # Negative warmup
            ("negative_warmup", lambda d: d.update({"warmup_bars": -1})),
            # Invalid decimal string
            ("bad_decimal", lambda d: d.update({"initial_balance": "not_a_number"})),
            # Invalid contract inst_id
            ("bad_inst_id", lambda d: d["contract"].update({"inst_id": "BTC-USDT-SPOT"})),
            # Bad funding events structure
            ("bad_funding_events_type", lambda d: d.update({"funding_events": "not_a_list"})),
            ("bad_funding_event_key", lambda d: d.update({"funding_events": [{"time_ms": 1, "rate": "0.1"}]})),
            ("bad_funding_event_extra", lambda d: d.update({"funding_events": [{"time_ms": 1, "rate": "0.1", "mark_price": "100", "extra": 1}]})),
            ("bad_funding_event_num", lambda d: d.update({"funding_events": [{"time_ms": 1, "rate": 0.1, "mark_price": "100"}]})),
        ]

        for name, mutator in cases:
            with self.subTest(name=name):
                d = make_valid_config_dict()
                mutator(d)
                bad_cfg_file = self.dir_path / f"bad_{name}.json"
                bad_cfg_file.write_text(json.dumps(d), encoding="utf-8")

                ret = main([
                    "--csv", str(self.csv_path),
                    "--config", str(bad_cfg_file),
                    "--strategy", "sma-trend",
                    "--output", str(self.dir_path / f"report_{name}.html"),
                ])
                self.assertEqual(ret, 2)

    def test_duplicate_keys_rejected(self):
        duplicate_root = (
            '{"timeframe_ms": 900000, "timeframe_ms": 900000, "contract": {'
            '"inst_id": "SYNTHETIC-USDT-SWAP", "base_per_contract": "0.01", '
            '"tick_size": "0.01", "lot_size": "1", "min_size": "1"}, '
            '"initial_balance": "1000", "fee_rate": "0.0005", "slippage_bps": "2", '
            '"funding_events": [], "warmup_bars": 2}'
        )
        dup_file = self.dir_path / "dup_root.json"
        dup_file.write_text(duplicate_root, encoding="utf-8")
        ret = main([
            "--csv", str(self.csv_path),
            "--config", str(dup_file),
            "--strategy", "sma-trend",
            "--output", str(self.dir_path / "dup_report.html"),
        ])
        self.assertEqual(ret, 2)

    def test_json_constants_rejected(self):
        nan_json = (
            '{"contract": {"inst_id": "SYNTHETIC-USDT-SWAP", "base_per_contract": "0.01", '
            '"tick_size": "0.01", "lot_size": "1", "min_size": "1"}, '
            '"timeframe_ms": 900000, "initial_balance": NaN, "fee_rate": "0.0005", '
            '"slippage_bps": "2", "funding_events": [], "warmup_bars": 2}'
        )
        nan_file = self.dir_path / "nan.json"
        nan_file.write_text(nan_json, encoding="utf-8")
        ret = main([
            "--csv", str(self.csv_path),
            "--config", str(nan_file),
            "--strategy", "sma-trend",
            "--output", str(self.dir_path / "nan_report.html"),
        ])
        self.assertEqual(ret, 2)

    def test_missing_files_and_bad_csv(self):
        # 1. Nonexistent CSV
        ret_no_csv = main([
            "--csv", str(self.dir_path / "nonexistent.csv"),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(self.output_path),
        ])
        self.assertEqual(ret_no_csv, 2)
        self.assertFalse(self.output_path.exists())

        # 2. Nonexistent config
        ret_no_cfg = main([
            "--csv", str(self.csv_path),
            "--config", str(self.dir_path / "nonexistent.json"),
            "--strategy", "sma-trend",
            "--output", str(self.output_path),
        ])
        self.assertEqual(ret_no_cfg, 2)
        self.assertFalse(self.output_path.exists())

        # 3. Bad CSV (unclosed bar)
        bad_csv = self.dir_path / "unclosed.csv"
        bad_csv.write_text(
            "open_time_ms,open,high,low,close,closed\n"
            "0,100,100,100,100,0\n",
            encoding="utf-8",
        )
        ret_bad_csv = main([
            "--csv", str(bad_csv),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(self.output_path),
        ])
        self.assertEqual(ret_bad_csv, 2)
        self.assertFalse(self.output_path.exists())

    def test_output_protection(self):
        # 1. Output file already exists
        self.output_path.write_text("existing content", encoding="utf-8")
        ret_exists = main([
            "--csv", str(self.csv_path),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(self.output_path),
        ])
        self.assertEqual(ret_exists, 2)
        self.assertEqual(self.output_path.read_text(encoding="utf-8"), "existing content")

        # 2. Output not ending with .html
        ret_bad_ext = main([
            "--csv", str(self.csv_path),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(self.dir_path / "report.txt"),
        ])
        self.assertEqual(ret_bad_ext, 2)
        self.assertFalse((self.dir_path / "report.txt").exists())

        # 3. Output path same as input CSV or config
        ret_same_csv = main([
            "--csv", str(self.csv_path),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(self.csv_path),
        ])
        self.assertEqual(ret_same_csv, 2)

        # 4. Automatically creates non-existent parent directory
        nested_out = self.dir_path / "nested" / "deep" / "report.html"
        ret_nested = main([
            "--csv", str(self.csv_path),
            "--config", str(self.config_path),
            "--strategy", "sma-trend",
            "--output", str(nested_out),
        ])
        self.assertEqual(ret_nested, 0)
        self.assertTrue(nested_out.exists())

    def test_exclusive_write_cleanup_on_error(self):
        fail_out = self.dir_path / "cleanup_test.html"

        class FailingFileWriter:
            def __init__(self, real_file):
                self._real = real_file

            def write(self, s):
                raise OSError("simulated write error during disk flush")

            def flush(self):
                self._real.flush()

            def close(self):
                self._real.close()

            def fileno(self):
                return self._real.fileno()

        real_open = open

        def mock_open(file, *args, **kwargs):
            f = real_open(file, *args, **kwargs)
            if str(file) == str(fail_out.resolve()):
                return FailingFileWriter(f)
            return f

        with patch("catos.research_cli.open", side_effect=mock_open):
            ret = main([
                "--csv", str(self.csv_path),
                "--config", str(self.config_path),
                "--strategy", "sma-trend",
                "--output", str(fail_out),
            ])
            self.assertEqual(ret, 2)
            self.assertFalse(fail_out.exists(), "Partial output file must be cleaned up on write failure")

    def test_write_interrupt_close_failure_and_creation_race(self):
        real_open = open
        for failure in ("interrupt", "close", "race"):
            with self.subTest(failure=failure):
                target = self.dir_path / f"{failure}.html"

                class Writer:
                    def __init__(self, stream):
                        self.stream = stream

                    def fileno(self):
                        return self.stream.fileno()

                    def write(self, text):
                        self.stream.write(text[:10])
                        if failure == "interrupt":
                            raise KeyboardInterrupt()

                    def flush(self):
                        self.stream.flush()

                    def close(self):
                        self.stream.close()
                        if failure == "close":
                            raise OSError("simulated close failure")

                def opening(file, *args, **kwargs):
                    if failure == "race":
                        with real_open(file, "x", encoding="utf-8") as stream:
                            stream.write("other writer")
                        return real_open(file, *args, **kwargs)
                    return Writer(real_open(file, *args, **kwargs))

                with patch("catos.research_cli.open", side_effect=opening):
                    expected = KeyboardInterrupt if failure == "interrupt" else (ValueError if failure == "race" else OSError)
                    with self.assertRaises(expected):
                        run_pipeline(str(self.csv_path), str(self.config_path), "sma-trend", str(target))
                if failure == "race":
                    self.assertEqual(target.read_text(encoding="utf-8"), "other writer")
                else:
                    self.assertFalse(target.exists())

    def test_real_trades_funding_and_warmup_match_core(self):
        from catos.data_io import load_candles_csv
        from catos.research import backtest
        from catos.reporting import render_report
        from examples.closed_bar_demo import SMATrend

        prices = (100, 101, 103, 102, 99, 98, 100, 102)
        self.csv_path.write_text("open_time_ms,open,high,low,close,closed\n" + "".join(
            f"{i * STEP},{p},{p},{p},{p},1\n" for i, p in enumerate(prices)
        ), encoding="utf-8")
        config_data = make_valid_config_dict()
        config_data["funding_events"] = [{"time_ms": 3 * STEP + STEP // 2, "rate": "0.0001", "mark_price": "102"}]
        self.config_path.write_text(json.dumps(config_data), encoding="utf-8")
        config, warmup = parse_config_json(self.config_path)
        expected = backtest(strategy=SMATrend, candles=load_candles_csv(self.csv_path, config=config), config=config, warmup_bars=warmup)
        self.assertTrue(expected.trades)
        self.assertNotEqual(expected.performance.funding_paid, Decimal("0"))
        self.assertEqual(expected.trades[0].time_ms, 3 * STEP)
        self.assertTrue(all(t.decision_time_ms >= 3 * STEP for t in expected.trades))
        run_pipeline(str(self.csv_path), str(self.config_path), "sma-trend", str(self.output_path))
        self.assertEqual(self.output_path.read_text(encoding="utf-8"), render_report(expected))

    def test_nested_duplicate_constants_and_decimal_context(self):
        original = json.dumps(make_valid_config_dict())
        invalid_texts = [
            original.replace('"tick_size": "0.01"', '"tick_size": "0.01", "tick_size": "0.01"'),
            original.replace('"funding_events": []', '"funding_events": [{"time_ms": 0, "time_ms": 1, "rate": "0", "mark_price": "100"}]'),
            *(original.replace('"initial_balance": "1000"', f'"initial_balance": {value}') for value in ('Infinity', '-Infinity', 'NaN')),
            original.replace('"initial_balance": "1000"', '"initial_balance": "invalid"'),
        ]
        with localcontext() as context:
            context.traps[InvalidOperation] = False
            context.clear_flags()
            for text in invalid_texts:
                with self.subTest(text=text):
                    self.config_path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        parse_config_json(self.config_path)
            self.assertFalse(any(context.flags.values()))

    def test_same_input_html_paths_and_error_streams(self):
        for which in ("csv", "config"):
            with self.subTest(which=which):
                source = self.csv_path if which == "csv" else self.config_path
                target = self.dir_path / f"input-{which}.html"
                target.write_bytes(source.read_bytes())
                original = target.read_bytes()
                argv = ["--csv", str(target if which == "csv" else self.csv_path),
                        "--config", str(target if which == "config" else self.config_path),
                        "--strategy", "sma-trend", "--output", str(target)]
                stdout, stderr = StringIO(), StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    self.assertEqual(main(argv), 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("same as input", stderr.getvalue())
                self.assertEqual(target.read_bytes(), original)

    def test_argparse_help_and_missing_arguments(self):
        # --help exits with 0
        cmd_help = [sys.executable, "-B", "-m", "catos.research_cli", "--help"]
        proc_help = subprocess.run(cmd_help, capture_output=True, text=True)
        self.assertEqual(proc_help.returncode, 0)
        self.assertIn("--csv", proc_help.stdout)

        # missing required arg exits with 2
        cmd_missing = [sys.executable, "-B", "-m", "catos.research_cli", "--csv", str(self.csv_path)]
        proc_missing = subprocess.run(cmd_missing, capture_output=True, text=True)
        self.assertEqual(proc_missing.returncode, 2)

        # unknown strategy option exits with 2
        cmd_bad_strat = [
            sys.executable, "-B", "-m", "catos.research_cli",
            "--csv", str(self.csv_path),
            "--config", str(self.config_path),
            "--strategy", "invalid-strat",
            "--output", str(self.output_path),
        ]
        proc_bad_strat = subprocess.run(cmd_bad_strat, capture_output=True, text=True)
        self.assertEqual(proc_bad_strat.returncode, 2)


if __name__ == "__main__":
    unittest.main()
