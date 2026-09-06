"""OKX 模擬盤客戶端身分驗證與通訊層測試 (OKX Client Auth & Transport Tests)

驗證：
1. 強制注入 x-simulated-trading: 1 模擬盤唯一通道標頭
2. OKX V5 HMAC-SHA256 簽名與 ISO 8601 UTC 時間戳
3. 指數退避重試（HTTP 429 與暫態網路錯誤）
4. OKX V5 業務錯誤碼映射與異常處理
"""

import hashlib
import hmac
import base64
import json
import httpx
import pytest

from src.core.security import OKXCredentials
from src.exchange.okx_client import (
    OKXAPIError,
    OKXDemoClient,
    OKXRateLimitError,
    generate_okx_signature,
)


def test_okx_v5_signature_vector() -> None:
    """驗證 OKX V5 HMAC-SHA256 簽名演算法契約。"""
    timestamp = "2020-12-08T09:08:57.715Z"
    method = "GET"
    request_path = "/api/v5/account/balance?ccy=BTC"
    body = ""
    secret = "E6571BE662057F3A5A6D5E99D8F6B7E1"

    expected_prehash = f"{timestamp}{method}{request_path}"
    expected_sign = base64.b64encode(
        hmac.new(secret.encode("utf-8"), expected_prehash.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    calculated_sign = generate_okx_signature(
        timestamp=timestamp,
        method=method,
        request_path=request_path,
        body=body,
        secret=secret,
    )

    assert calculated_sign == expected_sign


@pytest.mark.asyncio
async def test_simulated_trading_header_always_present() -> None:
    """驗證所有外發請求無條件強制攜帶 x-simulated-trading: 1 模擬盤標頭。"""
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={"code": "0", "data": [{"status": "live"}], "msg": ""},
        )

    mock_transport = httpx.MockTransport(handler)
    creds = OKXCredentials(
        api_key="demo-key",
        api_secret="demo-secret",
        passphrase="demo-passphrase",
    )

    async with OKXDemoClient(credentials=creds, transport=mock_transport) as client:
        # 公開請求
        await client.request("GET", "/api/v5/public/instruments?instType=SWAP", is_auth=False)
        # 私有請求
        await client.request("GET", "/api/v5/account/balance", is_auth=True)

    assert len(captured_requests) == 2
    for req in captured_requests:
        assert "x-simulated-trading" in req.headers
        assert req.headers["x-simulated-trading"] == "1"


@pytest.mark.asyncio
async def test_private_request_has_full_auth_headers() -> None:
    """驗證私有請求包含完整的 OKX 認證標頭。"""
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(status_code=200, json={"code": "0", "data": [], "msg": ""})

    mock_transport = httpx.MockTransport(handler)
    creds = OKXCredentials(
        api_key="my-demo-key",
        api_secret="my-demo-secret",
        passphrase="my-demo-passphrase",
    )

    async with OKXDemoClient(credentials=creds, transport=mock_transport) as client:
        await client.request("POST", "/api/v5/trade/order", is_auth=True, json_data={"instId": "BTC-USDT-SWAP"})

    req = captured_requests[0]
    assert req.headers["OK-ACCESS-KEY"] == "my-demo-key"
    assert req.headers["OK-ACCESS-PASSPHRASE"] == "my-demo-passphrase"
    assert "OK-ACCESS-SIGN" in req.headers
    assert "OK-ACCESS-TIMESTAMP" in req.headers
    assert req.headers["x-simulated-trading"] == "1"


@pytest.mark.asyncio
async def test_exponential_backoff_on_429() -> None:
    """驗證遇 429 速率限制時自動以指數退避重試並在成功後返回結果。"""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(status_code=429, json={"code": "50004", "msg": "Rate limit exceeded"})
        return httpx.Response(status_code=200, json={"code": "0", "data": [{"ok": True}], "msg": ""})

    mock_transport = httpx.MockTransport(handler)
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")

    # 設定極短退避時間以加速測試
    async with OKXDemoClient(
        credentials=creds,
        transport=mock_transport,
        initial_retry_delay=0.01,
        max_retries=3,
    ) as client:
        res = await client.request("GET", "/api/v5/market/tickers?instType=SWAP", is_auth=False)
        assert res["code"] == "0"
        assert res["data"][0]["ok"] is True
        assert call_count == 3


@pytest.mark.asyncio
async def test_max_retries_exceeded_raises_rate_limit_error() -> None:
    """驗證持續 429 超過重試上限時拋出 OKXRateLimitError。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=429, json={"code": "50004", "msg": "Rate limit exceeded"})

    mock_transport = httpx.MockTransport(handler)
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")

    async with OKXDemoClient(
        credentials=creds,
        transport=mock_transport,
        initial_retry_delay=0.01,
        max_retries=2,
    ) as client:
        with pytest.raises(OKXRateLimitError) as exc_info:
            await client.request("GET", "/api/v5/market/tickers", is_auth=False)
        assert exc_info.value.code == "50004"


@pytest.mark.asyncio
async def test_okx_business_error_raises_api_error() -> None:
    """驗證 OKX 回傳 code != 0 業務錯誤時拋出結構化 OKXAPIError。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"code": "51000", "data": [], "msg": "帳戶餘額不足以開倉"},
        )

    mock_transport = httpx.MockTransport(handler)
    creds = OKXCredentials(api_key="k", api_secret="s", passphrase="p")

    async with OKXDemoClient(credentials=creds, transport=mock_transport) as client:
        with pytest.raises(OKXAPIError) as exc_info:
            await client.request("POST", "/api/v5/trade/order", is_auth=True, json_data={})
        assert exc_info.value.code == "51000"
        assert "帳戶餘額不足" in exc_info.value.msg
