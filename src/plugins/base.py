"""策略插件抽象基礎介面 (Strategy Plugin Base)

對齊 Jesse 策略風格語法，具備宣告式參數表單 Schema (params_schema)
與統一信號資料結構。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ParameterType(str, Enum):
    """參數資料型別。"""

    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"


class ParameterSchema(BaseModel):
    """宣告式策略參數定義，用於前端動態渲染表單。"""

    name: str = Field(..., description="參數鍵名")
    label: str = Field(..., description="顯示名稱 (中文)")
    param_type: ParameterType = Field(..., description="型別")
    default: Any = Field(..., description="預設值")
    min_value: float | int | None = Field(default=None, description="最小值")
    max_value: float | int | None = Field(default=None, description="最大值")
    step: float | int | None = Field(default=None, description="步進")
    unit: str = Field(default="", description="單位 (如 %、根、天)")
    description: str = Field(default="", description="詳細說明")


class SignalAction(str, Enum):
    """策略信號動作。"""

    NONE = "none"
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


class StrategySignal(BaseModel):
    """策略運算產出之交易信號。"""

    action: SignalAction = Field(default=SignalAction.NONE, description="信號動作")
    stop_loss_pct: float | None = Field(default=None, description="標記價條件停損百分比 (例如 2.0 代表 2%)")
    message: str = Field(default="", description="信號觸發原因備註")


class StrategyBase(ABC):
    """策略插件抽象基類。"""

    name: str = "Base Strategy"
    description: str = ""
    version: str = "1.0.0"
    params_schema: list[ParameterSchema] = []

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        """初始化策略插件並帶入自訂參數。"""
        self.params: dict[str, Any] = {}
        # 先以 Schema 預設值初始化
        for p in self.params_schema:
            self.params[p.name] = p.default
        # 覆蓋用戶自訂參數
        if params:
            self.params.update(params)

    def should_long(self) -> bool:
        """對齊 Jesse：判斷當前是否滿足開多條件。"""
        return False

    def should_short(self) -> bool:
        """對齊 Jesse：判斷當前是否滿足開空條件。"""
        return False

    def go_long(self) -> StrategySignal:
        """對齊 Jesse：執行開多信號生成。"""
        return StrategySignal(action=SignalAction.OPEN_LONG)

    def go_short(self) -> StrategySignal:
        """對齊 Jesse：執行開空信號生成。"""
        return StrategySignal(action=SignalAction.OPEN_SHORT)

    @abstractmethod
    def on_candle(self, candle: dict[str, Any], has_position: bool) -> StrategySignal:
        """當新 K 線收盤時觸發策略運算。

        :param candle: K 線資料 (包含 open, high, low, close, volume, timestamp)
        :param has_position: 當前是否已持有部位
        :return: StrategySignal 交易信號
        """
        raise NotImplementedError
