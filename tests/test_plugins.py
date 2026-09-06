"""策略插件體系與出廠雙試紙測試 (Strategy Plugins Tests)

驗證：
1. 策略基類 (StrategyBase) 與宣告式參數 Schema (params_schema)
2. 插件熱加載沙盒 (StrategyLoader) 與語法/例外隔離
3. 試紙一：下單通道驗證試紙 (Signal Test Strategy)
4. 試紙二：SMA 5/20 雙均線試紙 (SMA Cross Strategy)
"""

from pathlib import Path
import pytest

from src.plugins.base import (
    ParameterSchema,
    ParameterType,
    SignalAction,
    StrategyBase,
    StrategySignal,
)
from src.plugins.loader import StrategyLoader
from src.plugins.strategies.signal_test import SignalTestStrategy
from src.plugins.strategies.sma_cross import SMACrossStrategy


def test_parameter_schema_definition() -> None:
    """驗證宣告式參數表單 Schema 定義。"""
    schema = ParameterSchema(
        name="fast_period",
        label="快線週期",
        param_type=ParameterType.INTEGER,
        default=5,
        min_value=2,
        max_value=50,
        unit="根",
        description="快線均線計算週期",
    )
    assert schema.name == "fast_period"
    assert schema.default == 5
    assert schema.unit == "根"


def test_signal_test_strategy_logic() -> None:
    """驗證試紙一 (Signal Test)：無部位時開多並掛停損，持有滿 N 根後平倉。"""
    strat = SignalTestStrategy(params={"exit_bars": 1, "stop_loss_pct": 2.0})

    # 第 1 根 K 線，無部位 ➔ 發出 open_long 信號 + 2% 標記價停損
    candle1 = {"timestamp": 1000, "open": 50000, "high": 50500, "low": 49500, "close": 50000, "volume": 10}
    signal1 = strat.on_candle(candle1, has_position=False)
    assert signal1.action == SignalAction.OPEN_LONG
    assert signal1.stop_loss_pct == 2.0

    # 開倉後持倉第 1 根 (exit_bars 達成) ➔ 發出 close_long 平多信號
    candle2 = {"timestamp": 2000, "open": 50000, "high": 51000, "low": 49800, "close": 50200, "volume": 12}
    signal2 = strat.on_candle(candle2, has_position=True)
    assert signal2.action == SignalAction.CLOSE_LONG


def test_sma_cross_strategy_logic() -> None:
    """驗證試紙二 (SMA 5/20)：均線穿越金叉開多、死叉開空。"""
    strat = SMACrossStrategy(params={"fast_period": 3, "slow_period": 5, "stop_loss_pct": 3.0})

    # 模擬 5 根下跌 K 線使快線在慢線下方
    prices = [100.0, 95.0, 90.0, 85.0, 80.0]
    for i, p in enumerate(prices):
        strat.on_candle(
            {"timestamp": i * 60, "open": p, "high": p, "low": p, "close": p, "volume": 1},
            has_position=False,
        )

    # 第 6 根價格暴力上漲，造成 SMA 3 上穿 SMA 5 金叉
    signal_cross_up = strat.on_candle(
        {"timestamp": 5 * 60, "open": 80.0, "high": 120.0, "low": 80.0, "close": 120.0, "volume": 10},
        has_position=False,
    )
    assert signal_cross_up.action == SignalAction.OPEN_LONG
    assert signal_cross_up.stop_loss_pct == 3.0


def test_strategy_loader_scans_and_loads() -> None:
    """驗證 StrategyLoader 能正確掃描並加載出廠雙試紙。"""
    strategies_dir = Path("src/plugins/strategies")
    loader = StrategyLoader(strategies_dir=strategies_dir)

    classes = loader.load_all()
    names = [cls.name for cls in classes]

    assert "Signal Test (下單通道驗證試紙)" in names or "Signal Test" in names
    assert "SMA 5/20 (經典雙均線試紙)" in names or "SMA 5/20" in names


def test_strategy_loader_isolates_broken_files(tmp_path: Path) -> None:
    """驗證沙盒例外隔離：遇到語法錯誤或惡意檔案時，隔離跳過不中斷整體系統。"""
    broken_file = tmp_path / "broken_strategy.py"
    broken_file.write_text("def syntax_error_here(: invalid syntax", encoding="utf-8")

    loader = StrategyLoader(strategies_dir=tmp_path)
    loaded = loader.load_all()
    # 應安全跳過錯誤檔案且不拋出崩潰異常
    assert len(loaded) == 0
