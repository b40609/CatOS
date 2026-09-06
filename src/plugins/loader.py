"""策略插件熱加載沙盒 (Strategy Plugin Loader & Sandbox)

支援動態掃描目錄、熱加載插件模組，並具備語法與執行期例外隔離沙盒。
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Type

from src.plugins.base import StrategyBase

logger = logging.getLogger("catOS.plugins.loader")


class StrategyLoader:
    """策略插件動態加載器與例外隔離沙盒。"""

    def __init__(self, strategies_dir: Path | str) -> None:
        self.strategies_dir = Path(strategies_dir)

    def load_all(self) -> list[Type[StrategyBase]]:
        """掃描目錄並動態加載所有合法的策略插件類別。

        若特定插件檔案存在語法錯誤或執行期異常，進行沙盒隔離並記錄日誌，絕不中斷主進程。
        """
        loaded_strategies: list[Type[StrategyBase]] = []

        if not self.strategies_dir.exists() or not self.strategies_dir.is_dir():
            return loaded_strategies

        for py_file in self.strategies_dir.glob("*.py"):
            if py_file.name.startswith(("_", ".")):
                continue

            try:
                module_name = f"catos_plugin_{py_file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 檢索模組內繼承自 StrategyBase 的具體策略類別
                for _, attr in inspect.getmembers(module, inspect.isclass):
                    if issubclass(attr, StrategyBase) and attr is not StrategyBase:
                        loaded_strategies.append(attr)

            except Exception as e:
                # 沙盒例外隔離：記錄日誌並略過破損插件
                logger.warning(f"策略插件 [{py_file.name}] 載入失敗已隔離: {e}")
                continue

        return loaded_strategies
