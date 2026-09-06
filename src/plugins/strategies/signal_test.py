"""試紙一：下單通道驗證試紙 (Signal Test Strategy)

【目的】：檢驗 OKX 模擬盤開倉、掛標記價條件停損、查詢持倉與平倉全生命週期。
【邏輯】：
- 無部位時：下一根收盤立即市價開多，同時掛出交易所標記價條件停損單。
- 有部位時：持倉滿 N 根（預設 1 根）收盤無條件市價平倉。
"""

from typing import Any

from src.plugins.base import (
    ParameterSchema,
    ParameterType,
    SignalAction,
    StrategyBase,
    StrategySignal,
)


class SignalTestStrategy(StrategyBase):
    """下單通道驗證試紙。"""

    name = "Signal Test (下單通道驗證試紙)"
    description = "用於檢驗 OKX 模擬盤下單通道與全生命週期：無部位時開多並掛標記價條件停損，持倉滿 N 根 K 線無條件市價平倉。"
    version = "1.0.0"

    params_schema = [
        ParameterSchema(
            name="exit_bars",
            label="出場 K 線數",
            param_type=ParameterType.INTEGER,
            default=1,
            min_value=1,
            max_value=20,
            unit="根",
            description="持倉收盤多少根 K 線後執行市價平倉",
        ),
        ParameterSchema(
            name="stop_loss_pct",
            label="停損百分比",
            param_type=ParameterType.FLOAT,
            default=2.0,
            min_value=0.1,
            max_value=20.0,
            unit="%",
            description="交易所標記價條件停損百分比",
        ),
    ]

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._bars_held: int = 0

    def on_candle(self, candle: dict[str, Any], has_position: bool) -> StrategySignal:
        if not has_position:
            self._bars_held = 0
            return StrategySignal(
                action=SignalAction.OPEN_LONG,
                stop_loss_pct=float(self.params["stop_loss_pct"]),
                message="通道驗證：無部位立即開多，並掛出交易所標記價條件停損",
            )

        self._bars_held += 1
        exit_bars = int(self.params["exit_bars"])

        if self._bars_held >= exit_bars:
            self._bars_held = 0
            return StrategySignal(
                action=SignalAction.CLOSE_LONG,
                message=f"通道驗證：持倉已達 {exit_bars} 根 K 線，執行市價平倉",
            )

        return StrategySignal(action=SignalAction.NONE)
