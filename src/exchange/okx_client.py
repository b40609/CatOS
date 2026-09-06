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
from decimal import Decimal
import hashlib
import hmac
import json
import random
from typing import Any

import httpx
from pydantic import BaseModel, Field

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


class OKXOrderSizeError(OKXError):
    """下單張數換算異常（低於最小下單張數或計算非法）。"""


class InstrumentSpec(BaseModel):
    """OKX 合約產品規格模型。"""

    inst_id: str = Field(..., description="合約代碼 (例如 BTC-USDT-SWAP)")
    ct_val: float = Field(..., description="合約面值")
    ct_val_ccy: str = Field(..., description="合約面值計價單位")
    ct_type: str = Field(..., description="合約類型 (linear / inverse)")
    min_sz: float = Field(..., description="最小下單張數")
    lot_sz: float = Field(..., description="下單張數步進單位")
    tick_sz: float = Field(..., description="價格最小跳動單位")
    settle_ccy: str = Field(..., description="結算資產單位")


class Position(BaseModel):
    """OKX 永續合約持倉部位模型。"""

    inst_id: str = Field(..., description="合約代碼 (例如 BTC-USDT-SWAP)")
    pos_side: str = Field(..., description="持倉方向 (net / long / short)")
    pos: float = Field(..., description="持倉張數")
    avg_px: float = Field(..., description="開倉均價")
    mark_px: float = Field(..., description="當前標記價")
    upl: float = Field(..., description="未實現盈虧 (USDT)")
    upl_ratio: float = Field(..., description="未實現盈虧率")
    lever: float = Field(..., description="逐倉槓桿倍數")
    mgn_ratio: float = Field(..., description="保證金率")


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
        self._instruments_cache: dict[str, InstrumentSpec] = {}

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

    async def get_instrument_spec(self, inst_id: str) -> InstrumentSpec:
        """獲取合約產品規格（支援記憶體快取）。

        :param inst_id: 合約代碼 (例如 BTC-USDT-SWAP)
        :return: InstrumentSpec 實例
        """
        if inst_id in self._instruments_cache:
            return self._instruments_cache[inst_id]

        response = await self.request(
            method="GET",
            path="/api/v5/public/instruments",
            is_auth=False,
            params={"instType": "SWAP", "instId": inst_id},
        )
        data = response.get("data", [])
        if not data:
            raise OKXAPIError(code="404", msg=f"未找到該合約規格: {inst_id}")

        row = data[0]
        spec = InstrumentSpec(
            inst_id=row["instId"],
            ct_val=float(row["ctVal"]),
            ct_val_ccy=row.get("ctValCcy", ""),
            ct_type=row.get("ctType", "linear"),
            min_sz=float(row.get("minSz", "1")),
            lot_sz=float(row.get("lotSz", "1")),
            tick_sz=float(row.get("tickSz", "0.1")),
            settle_ccy=row.get("settleCcy", "USDT"),
        )
        self._instruments_cache[inst_id] = spec
        return spec

    async def get_mark_price(self, inst_id: str) -> float:
        """查詢永續合約最新標記價。

        :param inst_id: 合約代碼 (例如 BTC-USDT-SWAP)
        :return: 當前標記價 (浮點數)
        """
        response = await self.request(
            method="GET",
            path="/api/v5/market/mark-price",
            is_auth=False,
            params={"instType": "SWAP", "instId": inst_id},
        )
        data = response.get("data", [])
        if not data or "markPx" not in data[0]:
            raise OKXAPIError(code="404", msg=f"無法獲取標記價: {inst_id}")
        return float(data[0]["markPx"])

    async def notional_to_contracts(
        self,
        inst_id: str,
        notional_usdt: float,
        mark_price: float | None = None,
    ) -> float:
        """依據【倉位名義價值 (Notional Value in USDT)】計算下單合約張數 (cont)。

        【交易核心原則】：
        交易者輸入金額一律為「倉位名義價值」，絕非保證金！
        計算公式：下單張數 = 倉位名義價值 / (當前標記價 * 合約面值)
        向下取整至合約步進單位 (lotSz)。若未達最小下單張數 (minSz)，強制拒單。

        :param inst_id: 合約代碼
        :param notional_usdt: 倉位名義價值（USDT）
        :param mark_price: 標記價（若為 None 則自動非同步查詢）
        :return: 合法之合約張數
        """
        if notional_usdt <= 0:
            raise ValueError("倉位名義價值必須大於 0。")

        if mark_price is None:
            mark_price = await self.get_mark_price(inst_id)
        if mark_price <= 0:
            raise ValueError("標記價必須大於 0。")

        spec = await self.get_instrument_spec(inst_id)
        one_contract_notional = Decimal(str(mark_price)) * Decimal(str(spec.ct_val))
        raw_sz = Decimal(str(notional_usdt)) / one_contract_notional

        # 向下取整至 lot_sz 步進
        lot_step = Decimal(str(spec.lot_sz))
        stepped_sz = (raw_sz // lot_step) * lot_step
        final_contracts = float(stepped_sz)

        if final_contracts < spec.min_sz:
            raise OKXOrderSizeError(
                f"倉位名義價值 {notional_usdt} USDT 換算之合約張數 {final_contracts} "
                f"未達最小下單張數 {spec.min_sz} 張 ({inst_id})。"
            )

        return final_contracts

    async def contracts_to_notional(
        self,
        inst_id: str,
        sz: float,
        mark_price: float | None = None,
    ) -> float:
        """將合約張數反向換算為倉位名義價值 (Notional Value in USDT)。

        :param inst_id: 合約代碼
        :param sz: 合約張數
        :param mark_price: 標記價（若為 None 則自動非同步查詢）
        :return: 倉位名義價值（USDT）
        """
        if sz <= 0:
            return 0.0

        if mark_price is None:
            mark_price = await self.get_mark_price(inst_id)

        spec = await self.get_instrument_spec(inst_id)
        notional = Decimal(str(sz)) * Decimal(str(spec.ct_val)) * Decimal(str(mark_price))
        return float(round(notional, 4))

    async def place_market_order(
        self,
        inst_id: str,
        side: str,
        sz: float,
        td_mode: str = "isolated",
        pos_side: str = "net",
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """送出永續合約市價委託單（開多、開空、平多、平空）。

        :param inst_id: 合約代碼 (例如 BTC-USDT-SWAP)
        :param side: 委託方向 ("buy" 或 "sell")
        :param sz: 合約張數 (cont)
        :param td_mode: 保證金模式，預設 "isolated"（逐倉）
        :param pos_side: 持倉方向，預設 "net"（單向持倉）
        :param client_order_id: 客戶端自訂訂單 ID
        :return: OKX 回傳之訂單資料字典 (含 ordId, sCode 等)
        """
        sz_str = str(int(sz)) if sz == int(sz) else str(sz)
        payload: dict[str, Any] = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side.lower(),
            "posSide": pos_side.lower(),
            "ordType": "market",
            "sz": sz_str,
        }
        if client_order_id:
            payload["clOrdId"] = client_order_id

        res = await self.request(
            method="POST",
            path="/api/v5/trade/order",
            is_auth=True,
            json_data=payload,
        )
        return res.get("data", [{}])[0]

    async def place_mark_stop_loss(
        self,
        inst_id: str,
        side: str,
        sz: float,
        trigger_price: float | None,
        td_mode: str = "isolated",
        pos_side: str = "net",
    ) -> dict[str, Any] | None:
        """原子化掛出 OKX 交易所端標記價條件停損單 (Mark Price Stop Loss)。

        【產品核心紅線】：
        1. 停損單必須掛在交易所端（OKX 標記價觸發市價平倉，slTriggerPxType: "mark"）。
        2. 停損參數留白（None 或 <= 0）代表交易者不設停損，明確略過不掛單。

        :param inst_id: 合約代碼
        :param side: 平倉方向（多頭部位停損為 "sell"，空頭部位停損為 "buy"）
        :param sz: 停損平倉張數 (cont)
        :param trigger_price: 標記價停損觸發價（若為 None 則不掛單）
        :param td_mode: 保證金模式，預設 "isolated"
        :param pos_side: 持倉方向，預設 "net"
        :return: 條件單資料字典 (含 algoId)，留白時回傳 None
        """
        if trigger_price is None or trigger_price <= 0:
            return None

        sz_str = str(int(sz)) if sz == int(sz) else str(sz)
        payload: dict[str, Any] = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side.lower(),
            "posSide": pos_side.lower(),
            "ordType": "conditional",
            "sz": sz_str,
            "slTriggerPx": str(trigger_price),
            "slTriggerPxType": "mark",
            "slOrdPx": "-1",  # 市價委託平倉
        }

        res = await self.request(
            method="POST",
            path="/api/v5/trade/order-algo",
            is_auth=True,
            json_data=payload,
        )
        return res.get("data", [{}])[0]

    async def get_positions(self, inst_id: str | None = None) -> list[Position]:
        """查詢逐倉持倉部位。

        :param inst_id: 合約代碼（可選，若未指定則查詢全帳戶 SWAP 持倉）
        :return: Position 部位物件清單
        """
        params = {"instType": "SWAP"}
        if inst_id:
            params["instId"] = inst_id

        res = await self.request(
            method="GET",
            path="/api/v5/account/positions",
            is_auth=True,
            params=params,
        )

        positions: list[Position] = []
        for row in res.get("data", []):
            positions.append(
                Position(
                    inst_id=row["instId"],
                    pos_side=row.get("posSide", "net"),
                    pos=float(row.get("pos", "0")),
                    avg_px=float(row.get("avgPx", "0")),
                    mark_px=float(row.get("markPx", "0")),
                    upl=float(row.get("upl", "0")),
                    upl_ratio=float(row.get("uplRatio", "0")),
                    lever=float(row.get("lever", "1")),
                    mgn_ratio=float(row.get("mgnRatio", "0")),
                )
            )
        return positions

    async def cancel_algo_orders(
        self,
        inst_id: str,
        algo_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """撤銷指定交易對的條件委託單。

        :param inst_id: 合約代碼
        :param algo_ids: 指定撤銷的 algoId 清單；若為 None 則自動查詢並撤銷所有未完成條件單
        :return: 撤單回應清單
        """
        if algo_ids is None:
            pending_res = await self.request(
                method="GET",
                path="/api/v5/trade/orders-algo-pending",
                is_auth=True,
                params={"instType": "SWAP", "instId": inst_id},
            )
            algo_ids = [
                row["algoId"]
                for row in pending_res.get("data", [])
                if "algoId" in row
            ]

        if not algo_ids:
            return []

        payload = [{"algoId": aid, "instId": inst_id} for aid in algo_ids]
        res = await self.request(
            method="POST",
            path="/api/v5/trade/cancel-algos",
            is_auth=True,
            json_data=payload,
        )
        return res.get("data", [])

    async def close_position_market(
        self,
        inst_id: str,
        mgn_mode: str = "isolated",
    ) -> dict[str, Any]:
        """市價全平特定交易對之所有持倉，並自動撤銷所有殘留條件單。

        :param inst_id: 合約代碼
        :param mgn_mode: 保證金模式，預設 "isolated"
        :return: OKX 全平回應資料字典
        """
        # 第一步：撤銷所有未觸發條件單，避免殘留掛單在平倉後被意外觸發
        await self.cancel_algo_orders(inst_id)

        # 第二步：原子化送出 OKX 市價全平部位請求
        payload = {"instId": inst_id, "mgnMode": mgn_mode}
        res = await self.request(
            method="POST",
            path="/api/v5/trade/close-position",
            is_auth=True,
            json_data=payload,
        )
        return res.get("data", [{}])[0]


