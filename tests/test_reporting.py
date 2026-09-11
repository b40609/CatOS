"""Dedicated unit tests for catos.reporting pure-function HTML report generator."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext, Inexact
from pathlib import Path
import tempfile
import re
import unittest

from catos.reporting import render_report
from catos.research import (
    AccountView,
    BacktestConfig,
    BacktestResult,
    ContractSpec,
    FundingPayment,
    Intent,
    Performance,
    Trade,
)

D = Decimal


def make_sample_result(**overrides) -> BacktestResult:
    spec = ContractSpec(
        inst_id="BTC-USDT-SWAP",
        base_per_contract=D("0.01"),
        tick_size=D("0.25"),
        lot_size=D("1"),
        min_size=D("1"),
    )
    config = BacktestConfig(
        contract=spec,
        timeframe_ms=900_000,
        initial_balance=D("10000"),
        fee_rate=D("0.0005"),
        slippage_bps=D("1"),
        funding_events=(),
    )
    trade1 = Trade(
        time_ms=900_000,
        decision_time_ms=0,
        quantity=D("2"),
        price=D("100.25"),
        fee=D("0.0010025"),
        realized_pnl=D("0"),
        position_after=D("2"),
    )
    trade2 = Trade(
        time_ms=1_800_000,
        decision_time_ms=900_000,
        quantity=D("-2"),
        price=D("105.00"),
        fee=D("0.00105"),
        realized_pnl=D("0.095"),
        position_after=D("0"),
    )
    funding_payment = FundingPayment(
        time_ms=900_000,
        position=D("2"),
        rate=D("0.0001"),
        mark_price=D("100.25"),
        amount_paid=D("0.0002005"),
    )
    view0 = AccountView(
        time_ms=0,
        position=D("0"),
        average_entry=D("0"),
        balance=D("10000"),
        realized_pnl=D("0"),
        unrealized_pnl=D("0"),
        equity=D("10000"),
        fees=D("0"),
        funding_paid=D("0"),
    )
    view1 = AccountView(
        time_ms=900_000,
        position=D("2"),
        average_entry=D("100.25"),
        balance=D("9999.998797"),
        realized_pnl=D("0"),
        unrealized_pnl=D("0.04"),
        equity=D("10000.038797"),
        fees=D("0.0010025"),
        funding_paid=D("0.0002005"),
    )
    view2 = AccountView(
        time_ms=1_800_000,
        position=D("0"),
        average_entry=D("0"),
        balance=D("10000.0927475"),
        realized_pnl=D("0.095"),
        unrealized_pnl=D("0"),
        equity=D("10000.0927475"),
        fees=D("0.0020525"),
        funding_paid=D("0.0002005"),
    )
    perf = Performance(
        initial_equity=D("10000"),
        final_equity=D("10000.0927475"),
        net_pnl=D("0.0927475"),
        return_pct=D("0.000927475"),
        realized_pnl=D("0.095"),
        unrealized_pnl=D("0"),
        fees=D("0.0020525"),
        funding_paid=D("0.0002005"),
        max_drawdown_pct=D("0"),
        trade_count=2,
    )
    base = BacktestResult(
        config=config,
        warmup_bars=1,
        evaluation_start_ms=900_000,
        evaluation_end_ms=1_800_000,
        trades=(trade1, trade2),
        funding=(funding_payment,),
        equity_curve=(view0, view1, view2),
        performance=perf,
        pending_intent=None,
        assumptions=(
            "Research only: no margin, liquidation, Guardian, or live order state machine.",
            "Closed bars at the requested timeframe; no finer data or intrabar path replay.",
        ),
    )
    if overrides:
        for k, v in overrides.items():
            base = getattr(base, "__class__")(**{**base.__dict__, k: v})
    return base


class ReportingTests(unittest.TestCase):
    def test_chart_preserves_tiny_equity_and_empty_position_unknown(self):
        result = make_sample_result()
        for values in (("1E-18", "2E-18"), ("1E-18", "1E-18")):
            with self.subTest(values=values):
                curve = tuple(replace(result.equity_curve[i], equity=D(value)) for i, value in enumerate(values))
                output = render_report(replace(result, equity_curve=curve))
                svg = output[output.index("<svg"):output.index("</svg>")]
                for value in values:
                    self.assertIn(f">{D(value):f}</text>", svg)
        output = render_report(replace(result, equity_curve=()))
        self.assertEqual(output.count('<div class="card-value">無資料</div>'), 2)

    def test_caller_decimal_context_unchanged(self):
        result = make_sample_result()
        expected = render_report(result)
        with localcontext() as context:
            context.prec = 3
            context.traps[Inexact] = True
            context.clear_flags()
            self.assertEqual(render_report(result), expected)
            self.assertFalse(any(context.flags.values()))

    def test_csv_backtest_report_integration(self):
        from catos.data_io import load_candles_csv
        from catos.research import backtest
        from examples.closed_bar_demo import SMATrend

        config = make_sample_result().config
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.csv"
            path.write_text("open_time_ms,open,high,low,close,closed\n" + "".join(
                f"{i * config.timeframe_ms},{price},{price},{price},{price},1\n"
                for i, price in enumerate((100, 101, 103, 102, 99))
            ), encoding="utf-8")
            bars = load_candles_csv(path, config=config)
        result = backtest(strategy=SMATrend, candles=bars, config=config, warmup_bars=2)
        self.assertTrue(result.trades)
        output = render_report(result)
        self.assertIn(f'<div class="card-value">{result.performance.final_equity:f}</div>', output)
        self.assertIn(f"{result.evaluation_start_ms} ~ {result.evaluation_end_ms}", output)
        for trade in result.trades:
            self.assertIn(f"<td>{trade.price:f}</td>", output)

    def test_normal_result(self):
        result = make_sample_result()
        html_out = render_report(result)

        self.assertIsInstance(html_out, str)
        self.assertTrue(html_out.startswith("<!DOCTYPE html>"))
        self.assertIn('<html lang="zh-Hant">', html_out)

        # Basic metadata
        self.assertIn("BTC-USDT-SWAP", html_out)
        self.assertIn("900000 ms", html_out)
        self.assertIn("warmup_bars", html_out)
        self.assertIn("900000 ~ 1800000", html_out)

        # Performance values
        self.assertIn("10000.0927475", html_out)
        self.assertIn("0.0927475", html_out)
        self.assertIn("0.0020525", html_out)
        self.assertIn("0.0002005", html_out)

        # Boundary disclaimer and trade count clarification
        self.assertIn("研究結果，非 Demo／Live 執行器", html_out)
        self.assertIn("交易筆數指模擬成交筆數，不宣稱往返交易數", html_out)

        # Trades and funding records
        self.assertIn("100.25", html_out)
        self.assertIn("105.00", html_out)
        self.assertIn("0.0001", html_out)

        # SVG present
        self.assertIn("<svg", html_out)
        self.assertIn("<polyline", html_out)

        # Assumptions
        self.assertIn("Research only: no margin", html_out)

    def test_no_trades_and_no_funding(self):
        view = AccountView(
            time_ms=0,
            position=D("0"),
            average_entry=D("0"),
            balance=D("1000"),
            realized_pnl=D("0"),
            unrealized_pnl=D("0"),
            equity=D("1000"),
            fees=D("0"),
            funding_paid=D("0"),
        )
        perf = Performance(
            initial_equity=D("1000"),
            final_equity=D("1000"),
            net_pnl=D("0"),
            return_pct=D("0"),
            realized_pnl=D("0"),
            unrealized_pnl=D("0"),
            fees=D("0"),
            funding_paid=D("0"),
            max_drawdown_pct=D("0"),
            trade_count=0,
        )
        result = make_sample_result(
            trades=(),
            funding=(),
            equity_curve=(view,),
            performance=perf,
            pending_intent=None,
        )
        html_out = render_report(result)
        self.assertIn("無模擬成交紀錄", html_out)
        self.assertIn("無資金費紀錄", html_out)
        self.assertIn("<svg", html_out)

    def test_open_position_and_pending_intent(self):
        view = AccountView(
            time_ms=900_000,
            position=D("5"),
            average_entry=D("101.50"),
            balance=D("9900"),
            realized_pnl=D("0"),
            unrealized_pnl=D("10"),
            equity=D("9910"),
            fees=D("1"),
            funding_paid=D("0"),
        )
        intent = Intent(decision_time_ms=900_000, target_position=D("10"))
        result = make_sample_result(
            equity_curve=(view,),
            pending_intent=intent,
        )
        html_out = render_report(result)
        self.assertIn("期末持倉張數", html_out)
        self.assertIn("5", html_out)
        self.assertIn("101.50", html_out)
        self.assertIn("末根未成交意圖 (pending_intent)", html_out)
        self.assertIn("目標張數: 10", html_out)
        self.assertIn("決策時間: 900000", html_out)

    def test_single_point_horizontal_curve_and_negative_equity(self):
        # 1. Empty curve
        result_empty = make_sample_result(equity_curve=())
        html_empty = render_report(result_empty)
        self.assertIn("無權益曲線資料", html_empty)

        # 2. Single point
        view_single = AccountView(
            time_ms=0,
            position=D("0"),
            average_entry=D("0"),
            balance=D("500"),
            realized_pnl=D("0"),
            unrealized_pnl=D("0"),
            equity=D("500"),
            fees=D("0"),
            funding_paid=D("0"),
        )
        result_single = make_sample_result(equity_curve=(view_single,))
        html_single = render_report(result_single)
        self.assertIn("<circle", html_single)
        self.assertIn("500", html_single)

        # 3. Horizontal curve (constant equity)
        view_flat1 = AccountView(0, D("0"), D("0"), D("1000"), D("0"), D("0"), D("1000"), D("0"), D("0"))
        view_flat2 = AccountView(900_000, D("0"), D("0"), D("1000"), D("0"), D("0"), D("1000"), D("0"), D("0"))
        view_flat3 = AccountView(1_800_000, D("0"), D("0"), D("1000"), D("0"), D("0"), D("1000"), D("0"), D("0"))
        result_flat = make_sample_result(equity_curve=(view_flat1, view_flat2, view_flat3))
        html_flat = render_report(result_flat)
        self.assertIn("<polyline", html_flat)
        self.assertIn("1000", html_flat)

        # 4. Negative equity & crossing zero
        view_neg1 = AccountView(0, D("0"), D("0"), D("100"), D("0"), D("0"), D("100"), D("0"), D("0"))
        view_neg2 = AccountView(900_000, D("0"), D("0"), D("-50"), D("0"), D("0"), D("-50"), D("0"), D("0"))
        view_neg3 = AccountView(1_800_000, D("0"), D("0"), D("-200"), D("0"), D("0"), D("-200"), D("0"), D("0"))
        result_neg = make_sample_result(equity_curve=(view_neg1, view_neg2, view_neg3))
        html_neg = render_report(result_neg)
        self.assertIn("<polyline", html_neg)
        # Check zero reference line is present when curve crosses zero
        self.assertIn('stroke="#f85149" stroke-dasharray="3,3"', html_neg)

    def test_html_escaping(self):
        malicious_id = '<script>alert("xss")</script>-USDT-SWAP'
        malicious_spec = ContractSpec(
            inst_id=malicious_id,
            base_per_contract=D("0.01"),
            tick_size=D("0.25"),
            lot_size=D("1"),
            min_size=D("1"),
        )
        malicious_cfg = BacktestConfig(
            contract=malicious_spec,
            timeframe_ms=900_000,
            initial_balance=D("1000"),
            fee_rate=D("0"),
            slippage_bps=D("0"),
            funding_events=(),
        )
        malicious_assumptions = (
            'Assumption with <img src="x" onerror="alert(1)"> test & special symbols " \' < >',
        )
        result = make_sample_result(
            config=malicious_cfg,
            assumptions=malicious_assumptions,
        )
        html_out = render_report(result)
        # Raw tags must not exist
        self.assertNotIn('<script>alert("xss")</script>', html_out)
        self.assertNotIn('<img src="x"', html_out)
        # Must be escaped
        self.assertIn("&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;", html_out)
        self.assertIn("&lt;img src=&quot;x&quot; onerror=&quot;alert(1)&quot;&gt;", html_out)

    def test_decimal_exact_representation(self):
        high_prec_fee = D("0.000000000000000001")
        perf = Performance(
            initial_equity=D("1000.123456789012345678"),
            final_equity=D("1000.123456789012345679"),
            net_pnl=D("0.000000000000000001"),
            return_pct=D("0.0000000000000001"),
            realized_pnl=D("0"),
            unrealized_pnl=D("0"),
            fees=high_prec_fee,
            funding_paid=D("0"),
            max_drawdown_pct=D("0"),
            trade_count=1,
        )
        result = make_sample_result(performance=perf)
        html_out = render_report(result)
        # Verify exact decimal string preserved without scientific notation or float truncation
        self.assertIn("1000.123456789012345678", html_out)
        self.assertIn("0.000000000000000001", html_out)

    def test_no_external_resources(self):
        result = make_sample_result()
        html_out = render_report(result)

        # Disallow http:// or https:// URLs
        urls = re.findall(r'https?://[^\s"\'<>]+', html_out)
        # Note: XML namespaces like xmlns="http://www.w3.org/2000/svg" are standard SVG declarations, not network resource fetches.
        # Check that no external links, scripts, stylesheets, or images exist
        for url in urls:
            self.assertEqual(url, "http://www.w3.org/2000/svg", f"Found disallowed external URL: {url}")

        self.assertNotIn("<script src=", html_out.lower())
        self.assertNotIn('<link rel="stylesheet"', html_out.lower())
        self.assertNotIn("<img src=", html_out.lower())

    def test_input_result_immutability(self):
        original = make_sample_result()
        cloned = deepcopy(original)

        _ = render_report(original)

        self.assertEqual(original.config, cloned.config)
        self.assertEqual(original.warmup_bars, cloned.warmup_bars)
        self.assertEqual(original.evaluation_start_ms, cloned.evaluation_start_ms)
        self.assertEqual(original.evaluation_end_ms, cloned.evaluation_end_ms)
        self.assertEqual(original.trades, cloned.trades)
        self.assertEqual(original.funding, cloned.funding)
        self.assertEqual(original.equity_curve, cloned.equity_curve)
        self.assertEqual(original.performance, cloned.performance)
        self.assertEqual(original.pending_intent, cloned.pending_intent)
        self.assertEqual(original.assumptions, cloned.assumptions)

    def test_invalid_type_raises(self):
        with self.assertRaisesRegex(TypeError, "result must be BacktestResult"):
            render_report("not_a_result")


if __name__ == "__main__":
    unittest.main()
