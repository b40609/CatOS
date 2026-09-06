"""OKX 合約規格與張數換算器測試 (Instrument Specs & Contract Lot Sizer Tests)

驗證：
1. 合約規格查詢與快取（ctVal, minSz, lotSz）
2. 標記價即時查詢 (get_mark_price)
3. 倉位名義價值 (Notional Value in USDT) 精確換算合約張數 (cont)
4. 低於最小下單張數 (minSz) 之拒單防呆
5. 合約張數反向換算倉位名義價值
"""

import httpx
import pytest

from src.core.security import OKXCredentials
from src.exchange.okx_client import (
    InstrumentSpec,
    OKXDemoClient,
    OKXOrderSizeError,
)


@pytest.fixture
def mock_specs_and_market() -> httpx.MockTransport:
    """模擬 OKX SWAP 合約規格與標記價 API 回應。"""
    def handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        params = dict(request.url.params)

        if url_path == "/api/v5/public/instruments":
            inst_id = params.get("instId")
            data = [
                {
                    "instType": "SWAP",
                    "instId": "BTC-USDT-SWAP",
                    "ctVal": "0.01",
                    "ctValCcy": "BTC",
                    "ctType": "linear",
                    "minSz": "1",
                    "lotSz": "1",
                    "tickSz": "0.1",
                    "settleCcy": "USDT",
                    "state": "live",
                },
                {
                    "instType": "SWAP",
                    "instId": "ETH-USDT-SWAP",
                    "ctVal": "0.1",
                    "ctValCcy": "ETH",
                    "ctType": "linear",
                    "minSz": "1",
                    "lotSz": "1",
                    "tickSz": "0.01",
                    "settleCcy": "USDT",
                    "state": "live",
                },
            ]
            if inst_id:
                data = [d for d in data if d["instId"] == inst_id]
            return httpx.Response(status_code=200, json={"code": "0", "data": data, "msg": ""})

        elif url_path == "/api/v5/market/mark-price":
            inst_id = params.get("instId", "BTC-USDT-SWAP")
            price = "50000.0" if inst_id == "BTC-USDT-SWAP" else "3000.0"
            return httpx.Response(
                status_code=200,
                json={"code": "0", "data": [{"instId": inst_id, "markPx": price}], "msg": ""},
            )

        return httpx.Response(status_code=404, json={"code": "404", "msg": "Not found"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_get_instrument_spec_and_cache(mock_specs_and_market: httpx.MockTransport) -> None:
    """驗證獲取合約規格模型與內部快取機制。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_specs_and_market) as client:
        spec = await client.get_instrument_spec("BTC-USDT-SWAP")
        assert isinstance(spec, InstrumentSpec)
        assert spec.inst_id == "BTC-USDT-SWAP"
        assert spec.ct_val == 0.01
        assert spec.min_sz == 1.0
        assert spec.lot_sz == 1.0
        assert spec.ct_val_ccy == "BTC"

        # 二次獲取驗證快取
        spec2 = await client.get_instrument_spec("BTC-USDT-SWAP")
        assert spec is spec2


@pytest.mark.asyncio
async def test_get_mark_price(mock_specs_and_market: httpx.MockTransport) -> None:
    """驗證查詢合約最新標記價。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_specs_and_market) as client:
        mark_price = await client.get_mark_price("BTC-USDT-SWAP")
        assert mark_price == 50000.0


@pytest.mark.asyncio
async def test_notional_to_contracts_calculation(mock_specs_and_market: httpx.MockTransport) -> None:
    """驗證依據倉位名義價值 (Notional Value in USDT) 精確計算合約張數。

    公式：下單張數 = 倉位名義價值 / (當前標記價 * 合約面值)
    例如：
    - BTC-USDT-SWAP (ctVal = 0.01 BTC, markPx = 50,000 USDT)
      1 張 = 500 USDT 名義價值
      輸入名義價值 1000 USDT ➔ 2 張
      輸入名義價值 1250 USDT ➔ 2 張 (向下取整至 lotSz = 1)
    """
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_specs_and_market) as client:
        # 1000 USDT ➔ 2 張
        contracts = await client.notional_to_contracts("BTC-USDT-SWAP", notional_usdt=1000.0, mark_price=50000.0)
        assert contracts == 2.0

        # 1250 USDT ➔ 向下取整為 2 張
        contracts_partial = await client.notional_to_contracts("BTC-USDT-SWAP", notional_usdt=1250.0, mark_price=50000.0)
        assert contracts_partial == 2.0


@pytest.mark.asyncio
async def test_notional_to_contracts_below_min_sz_raises_error(mock_specs_and_market: httpx.MockTransport) -> None:
    """驗證輸入名義價值換算張數小於最小下單張數 (minSz) 時拋出結構化防呆錯誤。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_specs_and_market) as client:
        # 400 USDT 在 markPx 50,000 下換算為 0.8 張，小於 minSz = 1
        with pytest.raises(OKXOrderSizeError) as exc_info:
            await client.notional_to_contracts("BTC-USDT-SWAP", notional_usdt=400.0, mark_price=50000.0)
        assert "未達最小下單張數" in str(exc_info.value)


@pytest.mark.asyncio
async def test_contracts_to_notional_calculation(mock_specs_and_market: httpx.MockTransport) -> None:
    """驗證張數反向換算倉位名義價值。

    2 張 BTC-USDT-SWAP * 0.01 * 50,000 = 1000.0 USDT
    """
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_specs_and_market) as client:
        notional = await client.contracts_to_notional("BTC-USDT-SWAP", sz=2.0, mark_price=50000.0)
        assert notional == 1000.0
