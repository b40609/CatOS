"""OKX 永續合約下單與標記價條件停損單測試 (Perpetual Orders & Stop Loss Tests)

驗證：
1. 逐倉市價開倉與平倉下單（以合約張數送出）
2. 原子化掛出 OKX 交易所端標記價條件停損單 (slTriggerPxType: "mark")
3. 停損留白防呆（None 或 0 時明確跳過不掛條件單）
4. 查詢逐倉持倉部位（張數、均價、標記價、未實現盈虧）
5. 交易對市價全平（撤銷所有條件單 + 市價清倉）
"""

import httpx
import pytest

from src.core.security import OKXCredentials
from src.exchange.okx_client import (
    OKXDemoClient,
    Position,
)


@pytest.fixture
def mock_trading_transport() -> httpx.MockTransport:
    """模擬 OKX 交易、條件單、持倉與撤單 API。"""
    recorded_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        body = {}
        if request.content:
            import json
            body = json.loads(request.content.decode("utf-8"))

        recorded_calls.append({"method": request.method, "path": url_path, "body": body})

        if url_path == "/api/v5/trade/order":
            # 市價下單回應
            return httpx.Response(
                status_code=200,
                json={
                    "code": "0",
                    "data": [{"ordId": "mock-ord-12345", "clOrdId": "", "sCode": "0", "sMsg": ""}],
                    "msg": "",
                },
            )
        elif url_path == "/api/v5/trade/order-algo":
            # 條件單掛單回應
            return httpx.Response(
                status_code=200,
                json={
                    "code": "0",
                    "data": [{"algoId": "mock-algo-99999", "sCode": "0", "sMsg": ""}],
                    "msg": "",
                },
            )
        elif url_path == "/api/v5/account/positions":
            # 查詢持倉回應
            return httpx.Response(
                status_code=200,
                json={
                    "code": "0",
                    "data": [
                        {
                            "instId": "BTC-USDT-SWAP",
                            "posSide": "net",
                            "pos": "2",
                            "avgPx": "50000.0",
                            "markPx": "51000.0",
                            "upl": "20.0",
                            "uplRatio": "0.02",
                            "lever": "10",
                            "mgnRatio": "0.15",
                        }
                    ],
                    "msg": "",
                },
            )
        elif url_path == "/api/v5/trade/orders-algo-pending":
            # 查詢未完成條件單
            return httpx.Response(
                status_code=200,
                json={
                    "code": "0",
                    "data": [{"algoId": "mock-algo-99999", "instId": "BTC-USDT-SWAP"}],
                    "msg": "",
                },
            )
        elif url_path == "/api/v5/trade/cancel-algos":
            # 撤銷條件單
            return httpx.Response(
                status_code=200,
                json={"code": "0", "data": [{"algoId": "mock-algo-99999", "sCode": "0"}], "msg": ""},
            )
        elif url_path == "/api/v5/trade/close-position":
            # 市價全平部位
            return httpx.Response(
                status_code=200,
                json={"code": "0", "data": [{"instId": "BTC-USDT-SWAP"}], "msg": ""},
            )

        return httpx.Response(status_code=404, json={"code": "404", "msg": "Not found"})

    transport = httpx.MockTransport(handler)
    transport.recorded_calls = recorded_calls  # type: ignore
    return transport


@pytest.mark.asyncio
async def test_place_market_order(mock_trading_transport: httpx.MockTransport) -> None:
    """驗證市價下單 Payload 符合 OKX V5 規範（逐倉 isolated、單向持倉 net）。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_trading_transport) as client:
        result = await client.place_market_order(
            inst_id="BTC-USDT-SWAP",
            side="buy",
            sz=2.0,
        )
        assert result["ordId"] == "mock-ord-12345"

    calls = mock_trading_transport.recorded_calls  # type: ignore
    order_call = next(c for c in calls if c["path"] == "/api/v5/trade/order")
    assert order_call["body"]["instId"] == "BTC-USDT-SWAP"
    assert order_call["body"]["tdMode"] == "isolated"
    assert order_call["body"]["side"] == "buy"
    assert order_call["body"]["posSide"] == "net"
    assert order_call["body"]["ordType"] == "market"
    assert order_call["body"]["sz"] == "2"


@pytest.mark.asyncio
async def test_place_mark_stop_loss_order(mock_trading_transport: httpx.MockTransport) -> None:
    """驗證 OKX 交易所端標記價條件停損單 (slTriggerPxType: mark, ordType: conditional)。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_trading_transport) as client:
        # 多頭部位停損：side 為 sell，標記價觸發市價平倉
        result = await client.place_mark_stop_loss(
            inst_id="BTC-USDT-SWAP",
            side="sell",
            sz=2.0,
            trigger_price=48000.0,
        )
        assert result is not None
        assert result["algoId"] == "mock-algo-99999"

    calls = mock_trading_transport.recorded_calls  # type: ignore
    algo_call = next(c for c in calls if c["path"] == "/api/v5/trade/order-algo")
    body = algo_call["body"]
    assert body["instId"] == "BTC-USDT-SWAP"
    assert body["tdMode"] == "isolated"
    assert body["side"] == "sell"
    assert body["posSide"] == "net"
    assert body["ordType"] == "conditional"
    assert body["slTriggerPx"] == "48000.0"
    assert body["slTriggerPxType"] == "mark"
    assert body["slOrdPx"] == "-1"
    assert body["sz"] == "2"


@pytest.mark.asyncio
async def test_stop_loss_blank_does_not_place_order(mock_trading_transport: httpx.MockTransport) -> None:
    """驗證停損參數留白 (trigger_price 為 None 或 <= 0) 時明確跳過不掛單。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_trading_transport) as client:
        result = await client.place_mark_stop_loss(
            inst_id="BTC-USDT-SWAP",
            side="sell",
            sz=2.0,
            trigger_price=None,
        )
        assert result is None

    calls = mock_trading_transport.recorded_calls  # type: ignore
    algo_calls = [c for c in calls if c["path"] == "/api/v5/trade/order-algo"]
    assert len(algo_calls) == 0


@pytest.mark.asyncio
async def test_get_positions(mock_trading_transport: httpx.MockTransport) -> None:
    """驗證獲取逐倉持倉部位對象與欄位映射。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_trading_transport) as client:
        positions = await client.get_positions(inst_id="BTC-USDT-SWAP")
        assert len(positions) == 1
        pos = positions[0]
        assert isinstance(pos, Position)
        assert pos.inst_id == "BTC-USDT-SWAP"
        assert pos.pos == 2.0
        assert pos.avg_px == 50000.0
        assert pos.mark_px == 51000.0
        assert pos.upl == 20.0


@pytest.mark.asyncio
async def test_close_position_market_cancels_algos_and_closes(mock_trading_transport: httpx.MockTransport) -> None:
    """驗證市價全平流程：撤銷該交易對的所有條件單，再送出市價全平委託。"""
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")
    async with OKXDemoClient(credentials=creds, transport=mock_trading_transport) as client:
        await client.close_position_market("BTC-USDT-SWAP")

    calls = mock_trading_transport.recorded_calls  # type: ignore
    paths = [c["path"] for c in calls]
    assert "/api/v5/trade/orders-algo-pending" in paths
    assert "/api/v5/trade/cancel-algos" in paths
    assert "/api/v5/trade/close-position" in paths
