"""健全度測試：驗證 Python 3.12 執行環境與核心依賴健全度。"""

import asyncio
import sys
import pytest


def test_python_version() -> None:
    """驗證 Python 版本符合 Python 3.12 要求。"""
    assert sys.version_info >= (3, 12), f"需要 Python 3.12+，當前為 {sys.version}"


def test_core_dependencies_importable() -> None:
    """驗證第一階段核心庫皆可正常載入。"""
    import cryptography
    import fastapi
    import httpx
    import pydantic

    assert fastapi.__version__
    assert httpx.__version__
    assert cryptography.__version__
    assert pydantic.__version__


@pytest.mark.asyncio
async def test_async_event_loop() -> None:
    """驗證 pytest-asyncio 與非同步事件迴圈正常運作。"""
    await asyncio.sleep(0.01)
    result = await asyncio.to_thread(lambda: 42)
    assert result == 42
