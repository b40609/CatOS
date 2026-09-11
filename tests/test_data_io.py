"""Dedicated unit tests for catos.data_io CSV candle loader."""

import codecs
from dataclasses import replace
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
import tempfile
import unittest

from catos.data_io import REQUIRED_COLUMNS, load_candles_csv
from catos.research import (
    BacktestConfig,
    Candle,
    ContractSpec,
    Strategy,
    backtest,
)

D = Decimal
STEP = 900_000  # 15-minute bars


def make_config(**changes) -> BacktestConfig:
    base = BacktestConfig(
        contract=ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.25"), D("1"), D("1")),
        timeframe_ms=STEP,
        initial_balance=D("1000"),
        fee_rate=D("0.0005"),
        slippage_bps=D("1"),
        funding_events=(),
    )
    return replace(base, **changes)


class MockTrendStrategy(Strategy):
    """Simple deterministic strategy for integration testing."""

    def __init__(self):
        self.bars = []

    def update_indicators(self, bar: Candle) -> None:
        self.bars.append(bar)

    @property
    def ready(self) -> bool:
        return len(self.bars) >= 1

    def on_bar(self, bar: Candle, account) -> Decimal | None:
        if len(self.bars) == 2:
            return D("2")  # Buy 2 contracts
        if len(self.bars) == 3:
            return D("0")  # Flatten
        return None


class DataIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.tmp_dir.name)
        self.cfg = make_config()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _write_csv(self, filename: str, content: str, encoding: str = "utf-8", prefix_bytes: bytes = b"") -> Path:
        file_path = self.dir_path / filename
        data = prefix_bytes + content.encode(encoding)
        file_path.write_bytes(data)
        return file_path

    def test_normal_file_and_bom(self):
        csv_content = (
            "open_time_ms,open,high,low,close,closed\n"
            "0,100.00,105.00,99.50,102.25,1\n"
            "900000,102.25,108.50,101.00,107.75,1\n"
        )
        # 1. Plain UTF-8 without BOM
        path_plain = self._write_csv("normal_plain.csv", csv_content)
        bars_plain = load_candles_csv(path_plain, config=self.cfg)
        self.assertEqual(len(bars_plain), 2)
        self.assertEqual(bars_plain[0], Candle(0, D("100.00"), D("105.00"), D("99.50"), D("102.25"), True))
        self.assertEqual(bars_plain[1], Candle(900000, D("102.25"), D("108.50"), D("101.00"), D("107.75"), True))

        # 2. UTF-8 with BOM
        path_bom = self._write_csv("normal_bom.csv", csv_content, prefix_bytes=codecs.BOM_UTF8)
        bars_bom = load_candles_csv(path_bom, config=self.cfg)
        self.assertEqual(bars_plain, bars_bom)

    def test_decimal_precision_not_lost(self):
        # Precise tick size supporting fine decimals
        fine_cfg = make_config(
            contract=ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.000000000000000001"), D("1"), D("1"))
        )
        high_prec_str = "100.123456789012345678"
        csv_content = (
            "open_time_ms,open,high,low,close,closed\n"
            f"0,{high_prec_str},{high_prec_str},{high_prec_str},{high_prec_str},1\n"
        )
        path = self._write_csv("high_prec.csv", csv_content)
        bars = load_candles_csv(path, config=fine_cfg)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].open, D(high_prec_str))
        # Ensure it was not rounded to float64 representation
        self.assertEqual(str(bars[0].open), high_prec_str)
        self.assertEqual(bars[0].open.as_tuple().exponent, -18)

    def test_unclosed_candle_rejected(self):
        cases = [
            ("closed_zero.csv", "0"),
            ("closed_true.csv", "true"),
            ("closed_True.csv", "True"),
            ("closed_empty.csv", ""),
            ("closed_two.csv", "2"),
        ]
        for fname, val in cases:
            with self.subTest(val=val):
                csv_content = (
                    "open_time_ms,open,high,low,close,closed\n"
                    f"0,100.00,105.00,99.50,102.25,{val}\n"
                )
                path = self._write_csv(fname, csv_content)
                with self.assertRaisesRegex(ValueError, r"row 2, column 'closed': expected '1'"):
                    load_candles_csv(path, config=self.cfg)

    def test_empty_file_and_header_only(self):
        # 1. 0-byte file
        path_empty = self._write_csv("empty.csv", "")
        with self.assertRaisesRegex(ValueError, "CSV file is empty"):
            load_candles_csv(path_empty, config=self.cfg)

        # 2. Header only
        path_header_only = self._write_csv("header_only.csv", "open_time_ms,open,high,low,close,closed\n")
        with self.assertRaisesRegex(ValueError, "candles must include warm-up and at least one evaluation bar"):
            load_candles_csv(path_header_only, config=self.cfg)

    def test_header_validation(self):
        # Missing column
        path_missing = self._write_csv("missing_col.csv", "open_time_ms,open,high,low,close\n0,1,1,1,1\n")
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            load_candles_csv(path_missing, config=self.cfg)

        # Duplicate column
        path_dup = self._write_csv(
            "dup_col.csv",
            "open_time_ms,open,open,low,close,closed\n0,100,100,100,100,1\n",
        )
        with self.assertRaisesRegex(ValueError, "duplicate columns"):
            load_candles_csv(path_dup, config=self.cfg)

        # Extra column
        path_extra = self._write_csv(
            "extra_col.csv",
            "open_time_ms,open,high,low,close,closed,volume\n0,100,100,100,100,1,50\n",
        )
        with self.assertRaisesRegex(ValueError, "unexpected columns"):
            load_candles_csv(path_extra, config=self.cfg)

        # Out of order
        path_order = self._write_csv(
            "order.csv",
            "open,open_time_ms,high,low,close,closed\n100,0,100,100,100,1\n",
        )
        with self.assertRaisesRegex(ValueError, "out of order"):
            load_candles_csv(path_order, config=self.cfg)

    def test_row_column_count_mismatch(self):
        # Too few columns
        path_few = self._write_csv(
            "few_cols.csv",
            "open_time_ms,open,high,low,close,closed\n0,100,105,95,102\n",
        )
        with self.assertRaisesRegex(ValueError, r"row 2: expected 6 columns, got 5"):
            load_candles_csv(path_few, config=self.cfg)

        # Too many columns
        path_many = self._write_csv(
            "many_cols.csv",
            "open_time_ms,open,high,low,close,closed\n0,100,105,95,102,1,extra\n",
        )
        with self.assertRaisesRegex(ValueError, r"row 2: expected 6 columns, got 7"):
            load_candles_csv(path_many, config=self.cfg)

    def test_invalid_time_parsing(self):
        cases = [
            ("time_float.csv", "100.5"),
            ("time_alpha.csv", "abc"),
            ("time_empty.csv", ""),
        ]
        for fname, val in cases:
            with self.subTest(val=val):
                csv_content = (
                    "open_time_ms,open,high,low,close,closed\n"
                    f"{val},100.00,105.00,99.50,102.25,1\n"
                )
                path = self._write_csv(fname, csv_content)
                with self.assertRaisesRegex(ValueError, r"row 2, column 'open_time_ms': invalid integer"):
                    load_candles_csv(path, config=self.cfg)

    def test_nan_and_infinity_rejected(self):
        # Core validation catches non-finite decimals
        cases = [
            ("nan.csv", "open", "NaN", "open must be finite"),
            ("inf.csv", "high", "Infinity", "high must be finite"),
            ("neg_inf.csv", "low", "-Infinity", "low must be finite"),
        ]
        for fname, col, val, err in cases:
            with self.subTest(col=col, val=val):
                p = {"open": "100.00", "high": "105.00", "low": "99.50", "close": "102.25"}
                p[col] = val
                csv_content = (
                    "open_time_ms,open,high,low,close,closed\n"
                    f"0,{p['open']},{p['high']},{p['low']},{p['close']},1\n"
                )
                path = self._write_csv(fname, csv_content)
                with self.assertRaisesRegex(ValueError, err):
                    load_candles_csv(path, config=self.cfg)

    def test_out_of_order_duplicate_and_gaps(self):
        # Out of order
        path_order = self._write_csv(
            "reverse_order.csv",
            "open_time_ms,open,high,low,close,closed\n"
            "900000,100.00,105.00,99.50,102.25,1\n"
            "0,100.00,105.00,99.50,102.25,1\n",
        )
        with self.assertRaisesRegex(ValueError, "candles must be ordered and contiguous; gaps are not filled"):
            load_candles_csv(path_order, config=self.cfg)

        # Duplicate timestamp
        path_dup = self._write_csv(
            "duplicate_time.csv",
            "open_time_ms,open,high,low,close,closed\n"
            "0,100.00,105.00,99.50,102.25,1\n"
            "0,100.00,105.00,99.50,102.25,1\n",
        )
        with self.assertRaisesRegex(ValueError, "candles must be ordered and contiguous; gaps are not filled"):
            load_candles_csv(path_dup, config=self.cfg)

        # Gap in timeframe (0 to 1800000 instead of 900000)
        path_gap = self._write_csv(
            "gap.csv",
            "open_time_ms,open,high,low,close,closed\n"
            "0,100.00,105.00,99.50,102.25,1\n"
            "1800000,100.00,105.00,99.50,102.25,1\n",
        )
        with self.assertRaisesRegex(ValueError, "candles must be ordered and contiguous; gaps are not filled"):
            load_candles_csv(path_gap, config=self.cfg)

    def test_illegal_tick_and_invalid_ohlc(self):
        # Illegal tick (0.10 is not multiple of 0.25)
        path_tick = self._write_csv(
            "bad_tick.csv",
            "open_time_ms,open,high,low,close,closed\n"
            "0,100.10,105.00,99.50,102.25,1\n",
        )
        with self.assertRaisesRegex(ValueError, "open must be a multiple of 0.25"):
            load_candles_csv(path_tick, config=self.cfg)

        # Invalid OHLC bounds (high < open)
        path_ohlc = self._write_csv(
            "bad_ohlc.csv",
            "open_time_ms,open,high,low,close,closed\n"
            "0,100.00,95.00,90.00,92.50,1\n",
        )
        with self.assertRaisesRegex(ValueError, "invalid OHLC bounds"):
            load_candles_csv(path_ohlc, config=self.cfg)

    def test_empty_string_not_treated_as_zero(self):
        # Empty string in price column
        path_empty_price = self._write_csv(
            "empty_price.csv",
            "open_time_ms,open,high,low,close,closed\n"
            "0,,105.00,99.50,102.25,1\n",
        )
        with self.assertRaisesRegex(ValueError, r"row 2, column 'open': invalid decimal ''"):
            load_candles_csv(path_empty_price, config=self.cfg)

    def test_csv_load_then_backtest_integration(self):
        csv_content = (
            "open_time_ms,open,high,low,close,closed\n"
            "0,100.00,105.00,99.50,102.00,1\n"
            "900000,102.00,108.00,101.50,107.00,1\n"
            "1800000,107.00,112.00,106.50,110.00,1\n"
            "2700000,110.00,115.00,109.00,114.00,1\n"
        )
        path = self._write_csv("integration.csv", csv_content)
        candles = load_candles_csv(path, config=self.cfg)
        self.assertEqual(len(candles), 4)

        result = backtest(
            strategy=MockTrendStrategy,
            candles=candles,
            config=self.cfg,
            warmup_bars=1,
        )
        self.assertEqual(result.warmup_bars, 1)
        self.assertEqual(result.evaluation_start_ms, 900000)
        self.assertEqual(result.evaluation_end_ms, 3600000)
        self.assertEqual(len(result.trades), 2)
        # Trade 1: buy 2 contracts on bar at index 2 (1800000)
        self.assertEqual(result.trades[0].quantity, D("2"))
        self.assertEqual(result.trades[0].time_ms, 1800000)
        # Trade 2: sell 2 contracts to flatten on bar at index 3 (2700000)
        self.assertEqual(result.trades[1].quantity, D("-2"))
        self.assertEqual(result.trades[1].time_ms, 2700000)
        self.assertEqual(result.performance.trade_count, 2)
        self.assertGreater(result.performance.final_equity, self.cfg.initial_balance)

    def test_invalid_config_type_and_nonexistent_file(self):
        # Nonexistent file
        with self.assertRaises(FileNotFoundError):
            load_candles_csv(self.dir_path / "nonexistent.csv", config=self.cfg)

        # Invalid config
        dummy_file = self._write_csv("dummy.csv", "open_time_ms,open,high,low,close,closed\n0,100,100,100,100,1\n")
        with self.assertRaisesRegex(TypeError, "config must be BacktestConfig"):
            load_candles_csv(dummy_file, config="invalid_config")

    def test_malformed_quotes_rejected(self):
        for row in ('0,100,105,95,102,"1', '0,100,105,95,102,"1"junk\n'):
            with self.subTest(row=row):
                path = self._write_csv("quotes.csv", ",".join(REQUIRED_COLUMNS) + "\n" + row)
                with self.assertRaisesRegex(ValueError, "row 2: invalid CSV"):
                    load_candles_csv(path, config=self.cfg)

    def test_decimal_error_independent_of_caller_context(self):
        path = self._write_csv("bad_decimal.csv", ",".join(REQUIRED_COLUMNS) + "\n0,abc,105,95,102,1\n")
        with localcontext() as context:
            context.traps[InvalidOperation] = False
            context.clear_flags()
            with self.assertRaisesRegex(ValueError, "row 2, column 'open': invalid decimal"):
                load_candles_csv(path, config=self.cfg)
            self.assertFalse(context.flags[InvalidOperation])

    def test_error_reports_physical_line_after_multiline_field(self):
        path = self._write_csv("multiline.csv", ",".join(REQUIRED_COLUMNS) + '\n0,"100\n",105,95,102,1\n900000,abc,105,95,102,1\n')
        with self.assertRaisesRegex(ValueError, "row 4, column 'open': invalid decimal"):
            load_candles_csv(path, config=self.cfg)


if __name__ == "__main__":
    unittest.main()
