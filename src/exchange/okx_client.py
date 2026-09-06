"""OKX 模擬盤非同步客戶端 (OKX Demo Async Client)

核心特點：
1. 唯一通道硬防呆：所有請求強制注入 `x-simulated-trading: 1` 標頭，杜絕實盤操作。
2. 原廠 V5 HMAC-SHA256 簽名與 ISO 8601 UTC 時間戳校準。
3. 指數退避重試（針對 HTTP 429 速率限制與連線抖動）。
4. 支援注入自定義 httpx.AsyncBaseTransport 測試 Seam，達成純記憶體高速單元測試。
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import random
from typing import Any

import httpx

from src.core.security import OKXCredentials


class OKXError(Exception):
    """OKX 客戶端基礎異常。"""


class OKXAPIError(OKXError):
    """OKX 伺服器端業務錯誤異常。"""

    def __init__(self, code: str, msg: str, data: Any = None) -> None:
        super().__init__(f"OKX API 錯誤 [代碼 {code}]: {msg}")
        self.code = str(code)
        self.msg = str(msg)
        self.data = data


class OKXRateLimitError(OKXAPIError):
    """OKX 頻率限制異常 (HTTP 429 / 50004)。"""


class OKXNetworkError(OKXError):
    """OKX 網路連線異常。"""


def generate_okx_signature(
    timestamp: str,
    method: str,
    request_path: str,
    body: str,
    secret: str,
) -> str:
    """計算符合 OKX V5 規範之 HMAC-SHA256 簽名。

    :param timestamp: ISO 8601 UTC 時間戳 (例如: 2020-12-08T09:08:57.715Z)
    :param method: HTTP 方法 (GET, POST 等，將自動轉為大寫)
    :param request_path: 請求路徑（含 Query string，例如: /api/v5/account/balance?ccy=BTC）
    :param body: 請求主體 JSON 字串（無主體則為空字串）
    :param secret: API Secret Key
    :return: Base64 編碼的簽名字串
    """
    prehash = f"{timestamp}{method.upper()}{request_path}{body or ''}"
    signature = hmac.new(
        secret.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def get_okx_iso_timestamp() -> str:
    """生成符合 OKX V5 規範的 ISO 8601 UTC 毫秒時間戳。"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class OKXDemoClient:
    """OKX 模擬盤非同步客戶端。

    【產品核心紅線】：
    本客戶端連線唯一綁定 OKX 模擬盤，所有外發請求均強制攜帶 `x-simulated-trading: 1` 標頭。
    """

    SIMULATED_HEADER = {"x-simulated-trading": "1"}

    def __init__(
        self,
        credentials: OKXCredentials | None = None,
        base_url: str = "https://www.okx.com",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        initial_retry_delay: float = 0.5,
    ) -> None:
        """初始化 OKX 模擬盤非同步客戶端。

        :param credentials: 身分憑證模型，若僅執行公共查詢可為 None
        :param base_url: API 基礎網址，預設為 https://www.okx.com
        :param transport: 自定義 HTTP Transport（用於單元測試隔離）
        :param timeout: 請求逾時秒數
        :param max_retries: 指數退避重試上限次數
        :param initial_retry_delay: 初始重試延遲秒數
        """
        self._credentials = credentials
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._initial_retry_delay = initial_retry_delay

        # 配置內部非同步客戶端
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            transport=transport,
            timeout=httpx.Timeout(timeout),
            headers={"Content-Type": "application/json"},
        )

    async def __aenter__(self) -> OKXDemoClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """關閉底層 HTTP 連線池。"""
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        is_auth: bool = False,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any]:
        """向 OKX 發送 HTTP 請求（含強制標頭、簽名校驗與指數退避）。

        :param method: GET, POST, DELETE 等
        :param path: API 路徑，例如 `/api/v5/market/tickers`
        :param is_auth: 是否需要私有簽名
        :param params: URL Query 參數
        :param json_data: 請求體 JSON 物件
        :return: OKX 解析後之回應字典 (含 code, data, msg)
        """
        method = method.upper()
        # 組合包含 Query 參數的完整 request_path
        query_string = ""
        if params:
            query_string = "?" + httpx.QueryParams(params).__str__()
        request_path = path + query_string

        body_str = ""
        if json_data is not None:
            body_str = json.dumps(json_data, separators=(",", ":"))

        # 基礎標頭：強制帶入模擬盤唯一定位標頭
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            **self.SIMULATED_HEADER,
        }

        if is_auth:
            if not self._credentials:
                raise ValueError("私有 API 請求需要提供有效的 OKXCredentials 憑證。")

            timestamp = get_okx_iso_timestamp()
            signature = generate_okx_signature(
                timestamp=timestamp,
                method=method,
                request_path=request_path,
                body=body_str,
                secret=self._credentials.api_secret,
            )

            headers.update(
                {
                    "OK-ACCESS-KEY": self._credentials.api_key,
                    "OK-ACCESS-SIGN": signature,
                    "OK-ACCESS-TIMESTAMP": timestamp,
                    "OK-ACCESS-PASSPHRASE": self._credentials.passphrase,
                }
            )

        # 雙重防呆：確保模擬盤標頭絕對存在
        headers["x-simulated-trading"] = "1"

        # 指數退避重試循環
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=request_path,
                    headers=headers,
                    content=body_str.encode("utf-8") if body_str else None,
                )

                # 遇到 429 速率限制
                if response.status_code == 429:
                    if attempt < self._max_retries:
                        delay = self._initial_retry_delay * (2**attempt) + random.uniform(
                            0, 0.1
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise OKXRateLimitError(
                            code="50004",
                            msg=f"OKX API 請求頻率受限 (HTTP 429)，已達重試上限 {self._max_retries} 次。",
                        )

                # HTTP 4xx / 5xx 檢查
                if response.status_code >= 400:
                    try:
                        err_payload = response.json()
                        code = err_payload.get("code", str(response.status_code))
                        msg = err_payload.get("msg", response.text)
                        if code == "50004":
                            raise OKXRateLimitError(code, msg)
                        raise OKXAPIError(code=code, msg=msg)
                    except (json.JSONDecodeError, KeyError):
                        response.raise_for_status()

                # 解析業務回應
                payload: dict[str, Any] = response.json()
                code = payload.get("code", "0")
                if code != "0":
                    msg = payload.get("msg", "未知 OKX 業務異常")
                    if code == "50004":
                        if attempt < self._max_retries:
                            delay = self._initial_retry_delay * (2**attempt) + random.uniform(
                                0, 0.1
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise OKXRateLimitError(code=code, msg=msg, data=payload.get("data"))
                    raise OKXAPIError(code=code, msg=msg, data=payload.get("data"))

                return payload

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < self._max_retries:
                    delay = self._initial_retry_delay * (2**attempt) + random.uniform(0, 0.1)
                    await asyncio.sleep(delay)
                    continue
                raise OKXNetworkError(
                    f"OKX 網路連線異常，重試 {self._max_retries} 次後失敗: {e}"
                ) from e
