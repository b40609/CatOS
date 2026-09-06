"""實質槓桿硬上限風控引擎 (Risk Engine)

核心職責：
1. 實質槓桿計算：全帳戶持倉名義價值總和 / 帳戶總權益。
2. 開倉前瞻風控硬上限：預估開倉後實質槓桿若超出交易者自訂硬上限（如 2.0x、3.0x），強制拒絕開倉。
3. 平倉與停損豁免：平多、平空、標記價條件停損與市價全平委託 100% 豁免風控，保證交易者隨時可撤退避險。
"""

from __future__ import annotations

from enum import Enum


class RiskLimitExceededError(Exception):
    """超出風控硬上限異常。"""


class RiskAction(str, Enum):
    """交易動作類型。"""

    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    STOP_LOSS = "stop_loss"
    CLOSE_ALL = "close_all"


class RiskEngine:
    """實質槓桿硬上限風控引擎。"""

    def __init__(self, max_effective_leverage: float = 3.0) -> None:
        """初始化風控引擎。

        :param max_effective_leverage: 實質槓桿硬上限倍數 (例如 2.0 代表 2.0x)
        """
        if max_effective_leverage <= 0:
            raise ValueError("實質槓桿硬上限必須大於 0。")
        self.max_effective_leverage = float(max_effective_leverage)

    def calculate_effective_leverage(
        self,
        total_position_notional: float,
        total_equity: float,
    ) -> float:
        """計算當前帳戶實質槓桿。

        計算公式：全帳戶持倉名義價值總和 / 帳戶總權益

        :param total_position_notional: 全帳戶持倉名義價值總和 (USDT)
        :param total_equity: 帳戶總權益 (USDT)
        :return: 實質槓桿倍數
        """
        if total_position_notional < 0:
            total_position_notional = abs(total_position_notional)

        if total_equity <= 0:
            if total_position_notional > 0:
                return float("inf")
            return 0.0

        return round(total_position_notional / total_equity, 4)

    def validate_order(
        self,
        action: RiskAction | str,
        order_notional: float,
        current_positions_notional: float,
        total_equity: float,
    ) -> bool:
        """驗證委託是否合規通過風控硬上限。

        【產品核心紅線】：
        1. 平倉與停損委託 100% 白名單豁免通行，絕不受限。
        2. 開倉委託預估實質槓桿超出硬上限時強制拒單。

        :param action: 交易動作
        :param order_notional: 擬送出之委託名義價值 (USDT)
        :param current_positions_notional: 當前全帳戶持倉名義價值總和 (USDT)
        :param total_equity: 當前帳戶總權益 (USDT)
        :return: True 代表通過風控
        :raises RiskLimitExceededError: 若超出風控上限
        """
        act = action.value if isinstance(action, RiskAction) else str(action).lower()

        # 白名單豁免：平倉、停損、全平一律無條件放行
        exempted_actions = {
            RiskAction.CLOSE_LONG.value,
            RiskAction.CLOSE_SHORT.value,
            RiskAction.STOP_LOSS.value,
            RiskAction.CLOSE_ALL.value,
        }
        if act in exempted_actions:
            return True

        # 開倉委託風控檢查
        if act in {RiskAction.OPEN_LONG.value, RiskAction.OPEN_SHORT.value}:
            if total_equity <= 0:
                raise RiskLimitExceededError("帳戶總權益小於或等於 0，禁止建立新倉位。")

            projected_notional = current_positions_notional + order_notional
            projected_leverage = projected_notional / total_equity

            if projected_leverage > self.max_effective_leverage:
                raise RiskLimitExceededError(
                    f"委託開倉後預估實質槓桿 {projected_leverage:.2f}x "
                    f"超出實質槓桿硬上限 {self.max_effective_leverage:.2f}x，強制拒絕開倉。"
                )
            return True

        raise ValueError(f"未知的風控交易動作: {action}")
