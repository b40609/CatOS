"""機器人生命週期狀態機與排他性管理 (Bot State Machine & Exclusivity)

核心特點：
1. 嚴格對齊 CONTEXT.md 標準 6 大狀態：
   待機、載入中、運行中、異常 · 連線中斷、停機 · 策略運算錯誤、停機 · App 已平倉。
2. 同一交易對排他性防呆：同一合約（如 BTC-USDT-SWAP）同一時間僅允許一台機器人處於運行中。
3. OKX App 手動平倉自動同步轉為「停機 · App 已平倉」，並徹底鎖死開倉權限，嚴禁二次反向開倉。
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class InvalidStateTransitionError(Exception):
    """非法狀態轉移異常。"""


class ContractExclusivityError(Exception):
    """同一交易對排他性衝突異常。"""


class BotState(str, Enum):
    """機器人生命週期標準狀態。"""

    STANDBY = "待機"
    LOADING = "載入中"
    RUNNING = "運行中"
    ERROR_DISCONNECTED = "異常 · 連線中斷"
    STOPPED_STRATEGY_ERROR = "停機 · 策略運算錯誤"
    STOPPED_APP_MANUAL_CLOSED = "停機 · App 已平倉"


# 合法狀態跳轉路徑表
VALID_TRANSITIONS: dict[BotState, set[BotState]] = {
    BotState.STANDBY: {BotState.LOADING},
    BotState.LOADING: {
        BotState.RUNNING,
        BotState.ERROR_DISCONNECTED,
        BotState.STANDBY,
    },
    BotState.RUNNING: {
        BotState.ERROR_DISCONNECTED,
        BotState.STOPPED_STRATEGY_ERROR,
        BotState.STOPPED_APP_MANUAL_CLOSED,
        BotState.STANDBY,
    },
    BotState.ERROR_DISCONNECTED: {
        BotState.RUNNING,
        BotState.STANDBY,
    },
    BotState.STOPPED_STRATEGY_ERROR: {
        BotState.STANDBY,
    },
    BotState.STOPPED_APP_MANUAL_CLOSED: {
        BotState.STANDBY,
    },
}


class BotStateMachine:
    """單一量化機器人生命週期狀態機。"""

    def __init__(self, bot_id: str, inst_id: str) -> None:
        self.bot_id = bot_id
        self.inst_id = inst_id
        self._state = BotState.STANDBY
        self._has_position: bool = False
        self._pos_size: float = 0.0

    @property
    def state(self) -> BotState:
        """當前生命週期狀態。"""
        return self._state

    @property
    def has_position(self) -> bool:
        """當前是否持有合約部位。"""
        return self._has_position

    @property
    def pos_size(self) -> float:
        """持倉張數。"""
        return self._pos_size

    @property
    def can_open_position(self) -> bool:
        """是否允許開新倉位（僅限於運行中且當前無部位時）。"""
        return self._state == BotState.RUNNING and not self._has_position

    def transition_to(self, new_state: BotState) -> None:
        """安全跳轉至目標狀態。若非合法轉換路徑則拋出 InvalidStateTransitionError。"""
        allowed = VALID_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"非法狀態跳轉：無法從 [{self._state.value}] 直接跳轉至 [{new_state.value}]。"
            )
        self._state = new_state

    def notify_position_opened(self, pos_size: float) -> None:
        """記錄部位已成功建立。"""
        self._has_position = True
        self._pos_size = float(pos_size)

    def notify_position_closed(self) -> None:
        """記錄部位已平倉。"""
        self._has_position = False
        self._pos_size = 0.0

    def sync_exchange_position(self, current_pos_size: float) -> None:
        """與交易所最新持倉對帳。

        【產品核心紅線】：
        若原先持有部位，但交易所回傳持倉為 0（交易者在手機 OKX App 手動平倉），
        機器人自動同步轉為「停機 · App 已平倉」，鎖死開倉權限，絕不二次反向開倉。
        """
        if self._state == BotState.RUNNING and self._has_position and current_pos_size == 0.0:
            self._has_position = False
            self._pos_size = 0.0
            self.transition_to(BotState.STOPPED_APP_MANUAL_CLOSED)


class BotManager:
    """機器人實例排他性與全局生命週期管理器。"""

    def __init__(self) -> None:
        self._bots: dict[str, BotStateMachine] = {}

    def create_bot(self, bot_id: str, inst_id: str) -> BotStateMachine:
        """創建新機器人狀態機實例。"""
        sm = BotStateMachine(bot_id=bot_id, inst_id=inst_id)
        self._bots[bot_id] = sm
        return sm

    def get_bot(self, bot_id: str) -> BotStateMachine:
        """獲取指定機器人實例。"""
        if bot_id not in self._bots:
            raise KeyError(f"未找到機器人: {bot_id}")
        return self._bots[bot_id]

    def start_bot(self, bot_id: str) -> None:
        """啟動機器人（強制實施同一交易對排他性防呆）。"""
        target_bot = self.get_bot(bot_id)

        # 檢驗排他性：同一合約代碼同一時間只允許一台機器人處於運行中或載入中
        for other_id, other_bot in self._bots.items():
            if other_id != bot_id and other_bot.inst_id == target_bot.inst_id:
                if other_bot.state in {BotState.LOADING, BotState.RUNNING}:
                    raise ContractExclusivityError(
                        f"同一合約代碼 [{target_bot.inst_id}] 同一時間只允許一台機器人處於運行中。"
                    )

        target_bot.transition_to(BotState.LOADING)
