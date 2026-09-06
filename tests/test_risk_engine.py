"""實質槓桿硬上限風控引擎測試 (Risk Engine Tests)

驗證：
1. 實質槓桿計算：全帳戶持倉名義價值總和 / 帳戶總權益
2. 預估開倉後槓桿超出硬上限時強制拒單
3. 帳戶權益為零或負數時拒絕開倉
4. 平倉委託 (close_long, close_short) 與條件停損 (stop_loss) 100% 白名單豁免放行
"""

import pytest

from src.core.risk_engine import (
    RiskAction,
    RiskEngine,
    RiskLimitExceededError,
)


def test_calculate_effective_leverage() -> None:
    """驗證實質槓桿計算公式準確性。"""
    engine = RiskEngine(max_effective_leverage=3.0)

    # 持倉名義價值 2000 USDT，總權益 1000 USDT ➔ 實質槓桿 2.0x
    leverage = engine.calculate_effective_leverage(
        total_position_notional=2000.0,
        total_equity=1000.0,
    )
    assert leverage == 2.0

    # 無持倉 ➔ 0.0x
    assert engine.calculate_effective_leverage(0.0, 1000.0) == 0.0

    # 權益 <= 0 ➔ 無窮大
    assert engine.calculate_effective_leverage(500.0, 0.0) == float("inf")
    assert engine.calculate_effective_leverage(500.0, -100.0) == float("inf")


def test_open_order_within_risk_limit_allowed() -> None:
    """驗證在風控硬上限內的開倉委託正常放行。"""
    engine = RiskEngine(max_effective_leverage=2.0)

    # 當前持倉 500 USDT，擬開倉 1000 USDT，總權益 1000 USDT ➔ 預估槓桿 1.5x <= 2.0x
    allowed = engine.validate_order(
        action=RiskAction.OPEN_LONG,
        order_notional=1000.0,
        current_positions_notional=500.0,
        total_equity=1000.0,
    )
    assert allowed is True


def test_open_order_exceeding_risk_limit_rejected() -> None:
    """驗證預估槓桿超出硬上限時拋出 RiskLimitExceededError。"""
    engine = RiskEngine(max_effective_leverage=2.0)

    # 當前持倉 1500 USDT，擬開倉 1000 USDT，總權益 1000 USDT ➔ 預估槓桿 2.5x > 2.0x
    with pytest.raises(RiskLimitExceededError) as exc_info:
        engine.validate_order(
            action=RiskAction.OPEN_SHORT,
            order_notional=1000.0,
            current_positions_notional=1500.0,
            total_equity=1000.0,
        )

    assert "超出實質槓桿硬上限" in str(exc_info.value)
    assert "2.50x" in str(exc_info.value)
    assert "2.00x" in str(exc_info.value)


def test_closing_and_stop_loss_orders_100_percent_exempted() -> None:
    """驗證平倉、停損與全平委託 100% 享有白名單豁免，即便實質槓桿已超標仍絕對放行。"""
    engine = RiskEngine(max_effective_leverage=1.0)

    # 當前槓桿已達 5.0x (持倉 5000，權益 1000)
    # 平多委託
    assert (
        engine.validate_order(
            action=RiskAction.CLOSE_LONG,
            order_notional=2000.0,
            current_positions_notional=5000.0,
            total_equity=1000.0,
        )
        is True
    )

    # 平空委託
    assert (
        engine.validate_order(
            action=RiskAction.CLOSE_SHORT,
            order_notional=2000.0,
            current_positions_notional=5000.0,
            total_equity=1000.0,
        )
        is True
    )

    # 標記價條件停損單
    assert (
        engine.validate_order(
            action=RiskAction.STOP_LOSS,
            order_notional=5000.0,
            current_positions_notional=5000.0,
            total_equity=1000.0,
        )
        is True
    )

    # 市價全平
    assert (
        engine.validate_order(
            action=RiskAction.CLOSE_ALL,
            order_notional=5000.0,
            current_positions_notional=5000.0,
            total_equity=1000.0,
        )
        is True
    )


def test_zero_equity_blocks_new_positions() -> None:
    """驗證帳戶總權益小於等於 0 時強制拒絕新開倉。"""
    engine = RiskEngine(max_effective_leverage=3.0)

    with pytest.raises(RiskLimitExceededError) as exc_info:
        engine.validate_order(
            action=RiskAction.OPEN_LONG,
            order_notional=100.0,
            current_positions_notional=0.0,
            total_equity=0.0,
        )
    assert "帳戶總權益小於或等於 0" in str(exc_info.value)
