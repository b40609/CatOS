"""機器人生命週期狀態機與 App 平倉同步測試 (Bot State Machine Tests)

驗證：
1. 標準 6 大狀態命名與合法狀態轉移
2. 非法狀態轉移阻絕 (InvalidStateTransitionError)
3. 同一交易對排他性防呆 (ContractExclusivityError)
4. OKX App 手動平倉自動同步轉為「停機 · App 已平倉」並鎖死開倉
"""

import pytest

from src.core.state_machine import (
    BotManager,
    BotState,
    BotStateMachine,
    ContractExclusivityError,
    InvalidStateTransitionError,
)


def test_standard_state_names() -> None:
    """驗證標準 6 大狀態嚴格對齊 CONTEXT.md 定義。"""
    assert BotState.STANDBY.value == "待機"
    assert BotState.LOADING.value == "載入中"
    assert BotState.RUNNING.value == "運行中"
    assert BotState.ERROR_DISCONNECTED.value == "異常 · 連線中斷"
    assert BotState.STOPPED_STRATEGY_ERROR.value == "停機 · 策略運算錯誤"
    assert BotState.STOPPED_APP_MANUAL_CLOSED.value == "停機 · App 已平倉"


def test_valid_lifecycle_transitions() -> None:
    """驗證正常的機器人生命週期狀態轉換流。"""
    sm = BotStateMachine(bot_id="bot-1", inst_id="BTC-USDT-SWAP")
    assert sm.state == BotState.STANDBY

    # 待機 ➔ 載入中
    sm.transition_to(BotState.LOADING)
    assert sm.state == BotState.LOADING

    # 載入中 ➔ 運行中
    sm.transition_to(BotState.RUNNING)
    assert sm.state == BotState.RUNNING

    # 運行中 ➔ 異常 · 連線中斷
    sm.transition_to(BotState.ERROR_DISCONNECTED)
    assert sm.state == BotState.ERROR_DISCONNECTED

    # 異常恢復 ➔ 運行中
    sm.transition_to(BotState.RUNNING)
    assert sm.state == BotState.RUNNING

    # 用戶手動停止 ➔ 待機
    sm.transition_to(BotState.STANDBY)
    assert sm.state == BotState.STANDBY


def test_invalid_transition_raises_error() -> None:
    """驗證非法狀態直接躍遷時拋出 InvalidStateTransitionError。"""
    sm = BotStateMachine(bot_id="bot-1", inst_id="BTC-USDT-SWAP")
    assert sm.state == BotState.STANDBY

    # 待機不能直接跳轉為「停機 · App 已平倉」
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(BotState.STOPPED_APP_MANUAL_CLOSED)


def test_contract_exclusivity_prevent_multiple_bots_on_same_contract() -> None:
    """驗證同一交易對排他性防呆：同一合約在同一時間只允許一台機器人處於運行中。"""
    manager = BotManager()

    # 啟動第 1 台 BTC-USDT-SWAP 機器人
    bot1 = manager.create_bot(bot_id="btc_bot_alpha", inst_id="BTC-USDT-SWAP")
    bot1.transition_to(BotState.LOADING)
    bot1.transition_to(BotState.RUNNING)

    # 嘗試為相同合約創建/啟動第 2 台機器人
    bot2 = manager.create_bot(bot_id="btc_bot_beta", inst_id="BTC-USDT-SWAP")

    with pytest.raises(ContractExclusivityError) as exc_info:
        manager.start_bot("btc_bot_beta")

    assert "同一合約代碼 [BTC-USDT-SWAP] 同一時間只允許一台機器人處於運行中" in str(exc_info.value)

    # 其他不同合約（如 ETH-USDT-SWAP）可正常啟動
    bot_eth = manager.create_bot(bot_id="eth_bot", inst_id="ETH-USDT-SWAP")
    manager.start_bot("eth_bot")
    assert bot_eth.state == BotState.LOADING


def test_okx_app_manual_close_sync_stops_bot_and_locks_open() -> None:
    """驗證交易者在手機 OKX App 手動平倉後，狀態機自動轉為「停機 · App 已平倉」並鎖死開倉。"""
    sm = BotStateMachine(bot_id="bot-1", inst_id="BTC-USDT-SWAP")
    sm.transition_to(BotState.LOADING)
    sm.transition_to(BotState.RUNNING)

    # 標記當前持倉為開倉狀態
    sm.notify_position_opened(pos_size=2.0)
    assert sm.has_position is True
    assert sm.can_open_position is False  # 已有部位不允許重疊開倉

    # 模擬持倉對帳：偵測到 OKX 交易所持倉變為 0 (交易者在手機 App 手動平倉)
    sm.sync_exchange_position(current_pos_size=0.0)

    # 驗證狀態自動轉移為「停機 · App 已平倉」
    assert sm.state == BotState.STOPPED_APP_MANUAL_CLOSED
    assert sm.has_position is False
    # 驗證防二次開倉：在該狀態下嚴禁開倉
    assert sm.can_open_position is False
