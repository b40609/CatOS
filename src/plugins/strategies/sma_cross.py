"""試紙二：經典雙均線試紙 (SMA 5/20 Strategy)

【目的】：經典雙均線趨勢策略範本，驗證多指標交叉運算與狀態維持。
【邏輯】：
- 快線 (預設 5) 上穿慢線 (預設 20) 金叉 ➔ 開多
- 快線下穿慢線死叉 ➔ 開空
- 等穿越、不重複加倉
"""

from typing import Any

from src.plugins.base import (
    ParameterSchema,
    ParameterType,
    SignalAction,
    StrategyBase,
    StrategySignal,
)


class SMACrossStrategy(StrategyBase):
    """經典雙均線策略試紙。"""

    name = "SMA 5/20 (經典雙均線試紙)"
    description = "快線 SMA 5 上穿慢線 SMA 20 金叉開多，下穿死叉開空；等穿越、不加倉，作為趨勢策略基準範本。"
    version = "1.0.0"

    params_schema = [
        ParameterSchema(
            name="fast_period",
            label="快線週期",
            param_type=ParameterType.INTEGER,
            default=5,
            min_value=2,
            max_value=100,
            unit="根",
            description="快線均線計算週期 (SMA)",
        ),
        ParameterSchema(
            name="slow_period",
            label="慢線週期",
            param_type=ParameterType.INTEGER,
            default=20,
            min_value=5,
            max_value=300,
            unit="根",
            description="慢線均線計算週期 (SMA)",
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
        self._close_prices: list[float] = []
        self._prev_fast: float | None = None
        self._prev_slow: float | None = None

    def on_candle(self, candle: dict[str, Any], has_position: bool) -> StrategySignal:
        close_px = float(candle["close"])
        self._close_prices.append(close_px)

        fast_p = int(self.params["fast_period"])
        slow_p = int(self.params["slow_period"])

        if len(self._close_prices) < slow_p:
            return StrategySignal(action=SignalAction.NONE)

        fast_sma = sum(self._close_prices[-fast_p:]) / fast_p
        slow_sma = sum(self._close_prices[-slow_p:]) / slow_p

        signal = StrategySignal(action=SignalAction.NONE)

        if self._prev_fast is not None and self._prev_slow is not None:
            # 金叉上穿 (快線向上穿過慢線)
            if self._prev_fast <= self._prev_slow and fast_sma > slow_sma:
                if not has_position:
                    signal = StrategySignal(
                        action=SignalAction.OPEN_LONG,
                        stop_loss_pct=float(self.params["stop_loss_pct"]),
                        message=f"均線金叉：SMA {fast_p} ({fast_sma:.2f}) 上穿 SMA {slow_p} ({slow_sma:.2f})，發出開多信號",
                    )
            # 死叉下穿 (快線向下穿過慢線)
            elif self._prev_fast >= self._prev_slow and fast_sma < slow_sma:
                if not has_position:
                    signal = StrategySignal(
                        action=SignalAction.OPEN_SHORT,
                        stop_loss_pct=float(self.params["stop_loss_pct"]),
                        message=f"均線死叉：SMA {fast_p} ({fast_sma:.2f}) 下穿 SMA {slow_p} ({slow_sma:.2f})，發出開空信號",
                    )

        self._prev_fast = fast_sma
        self._prev_slow = slow_sma
        return signal
