"""OKX 模擬盤（Demo）連線：讀帳戶、下單、撤單。M1，2026-11-16 使用者授權。

只連模擬盤：每個請求都帶 `x-simulated-trading: 1`，沒有關掉它的參數，也沒有 Live 模式。
實盤金鑰配上這個 header 會被 OKX 拒絕（50101），所以金鑰放錯也送不到實盤。

金鑰檔由使用者自己建立並存在專案外；本模組只在 `load_credentials` 讀它，
錯誤訊息只寫路徑與原因，不含檔案內容。import 本模組不做任何 I/O。

能打的端點是固定白名單；寫入只有下單與撤單，不改槓桿、持倉模式或帳戶設定。
每張委託由 `place_market_order` 強制帶固定 tag，呼叫端不能改。
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import threading
import time
from typing import Callable, Protocol
from urllib.parse import urlencode

# 2026-09 唯讀採集時以這個主機成功完成簽名請求（docs/demo-collection-handoff.md）。
DEMO_HOST = "openapi.okx.com"
TAG = "41cb53c54d6dABDE"
DEFAULT_INST = "BTC-USDT-SWAP"
CREDENTIALS_ENV = "CATOS_OKX_DEMO_CREDENTIALS"
MIN_INTERVAL_S = 0.25
TIMEOUT_S = 10.0
MAX_BODY = 2_000_000

_GET_PATHS = frozenset((
    "/api/v5/public/time",
    "/api/v5/public/instruments",
    "/api/v5/public/mark-price",
    "/api/v5/market/candles",
    "/api/v5/market/ticker",
    "/api/v5/account/config",
    "/api/v5/account/balance",
    "/api/v5/account/positions",
    "/api/v5/trade/order",
    "/api/v5/trade/orders-pending",
    "/api/v5/trade/fills",
    "/api/v5/trade/order-algo",            # P6 disaster stop (2026-11-17): one conditional order
    "/api/v5/trade/orders-algo-pending",   # and the account's pending algo orders (foreign check)
))
_POST_PATHS = frozenset(("/api/v5/trade/order", "/api/v5/trade/cancel-order",
                         "/api/v5/trade/order-algo", "/api/v5/trade/amend-algos", "/api/v5/trade/cancel-algos"))
_PUBLIC_PREFIXES = ("/api/v5/public/", "/api/v5/market/")
_INST = re.compile(r"[A-Z0-9]{1,16}-USDT-SWAP\Z")
_CL_ORD_ID = re.compile(r"[A-Za-z0-9]{1,32}\Z")


class DemoError(Exception):
    """錯誤訊息只含固定說明、OKX 回的代碼與訊息，不含金鑰或請求 header。"""


class OkxApiError(DemoError):
    def __init__(self, code: str, msg: str):
        super().__init__(f"OKX 回應錯誤 {code}：{msg}")
        self.code = code
        self.msg = msg


@dataclass(frozen=True, repr=False)
class Credentials:
    api_key: str
    secret: str
    passphrase: str

    def __post_init__(self):
        for value in (self.api_key, self.secret, self.passphrase):
            if type(value) is not str or not 1 <= len(value) <= 512 or any(not 33 <= ord(c) <= 126 for c in value):
                raise DemoError("金鑰檔內容格式不對（欄位要是非空、不含空白的英數字串）")

    def __repr__(self):
        return "Credentials(<redacted>)"


def credentials_path() -> Path:
    """環境變數優先；否則用 ~/.catos/okx-demo.json，沒有再用桌面的 OKX_API.txt（2026-11-16 使用者指定）。"""
    raw = os.environ.get(CREDENTIALS_ENV)
    if raw:
        return Path(raw)
    primary = Path.home() / ".catos" / "okx-demo.json"
    desktop = Path.home() / "Desktop" / "OKX_API.txt"
    return desktop if not primary.exists() and desktop.exists() else primary


_LABELS = {"apikey": "api_key", "okxapikey": "api_key",
           "secret": "secret", "secretkey": "secret", "apisecret": "secret", "okxsecretkey": "secret",
           "passphrase": "passphrase", "apipassphrase": "passphrase", "okxpassphrase": "passphrase"}
_LINE = re.compile(r"\s*([^:=：]+?)\s*[:=：]\s*(.+?)\s*$")


def _parse_text(text: str, path: Path) -> list[Credentials]:
    """有標籤的文字檔：每組以 apikey 開頭，接 secretkey、passphrase；其他行（標題、ip、備註）略過。"""
    sets: list[dict] = []
    for line in text.splitlines():
        matched = _LINE.match(line)
        if not matched:
            continue
        field = _LABELS.get(re.sub(r"[ _-]", "", matched.group(1)).lower())
        if field is None:
            continue
        value = matched.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if field == "api_key":
            sets.append({})
        elif not sets:
            raise DemoError(f"金鑰檔裡 {field} 出現在 apikey 之前：{path}")
        if field in sets[-1]:
            raise DemoError(f"金鑰檔裡同一組有重複的 {field}：{path}")
        sets[-1][field] = value
    if not sets:
        raise DemoError(f"金鑰檔裡找不到 apikey：{path}")
    for index, entry in enumerate(sets, 1):
        if set(entry) != {"api_key", "secret", "passphrase"}:
            raise DemoError(f"金鑰檔第 {index} 組缺欄位（要有 apikey、secretkey、passphrase）：{path}")
    return [Credentials(e["api_key"], e["secret"], e["passphrase"]) for e in sets]


def load_credential_sets(path: Path | None = None) -> list[Credentials]:
    """讀使用者指定的金鑰檔。JSON（api_key、secret、passphrase）或有標籤的文字檔，可含多組。"""
    path = Path(path) if path is not None else credentials_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise DemoError(f"找不到金鑰檔：{path}") from None
    except OSError:
        raise DemoError(f"讀不到金鑰檔：{path}") from None
    if len(raw) > 16384:
        raise DemoError(f"金鑰檔太大，不像金鑰檔：{path}")
    try:
        text = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DemoError(f"金鑰檔不是 UTF-8 或 UTF-16 文字：{path}") from None
    if text.lstrip().startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            raise DemoError(f"金鑰檔不是有效的 JSON：{path}") from None
        if not isinstance(data, dict) or set(data) != {"api_key", "secret", "passphrase"}:
            raise DemoError(f"金鑰檔要剛好有 api_key、secret、passphrase 三個欄位：{path}")
        return [Credentials(data["api_key"], data["secret"], data["passphrase"])]
    return _parse_text(text, path)


def load_credentials(path: Path | None = None) -> Credentials:
    sets = load_credential_sets(path)
    if len(sets) != 1:
        raise DemoError(f"金鑰檔裡有 {len(sets)} 組金鑰，這個用法只接受一組")
    return sets[0]


def connect(path: Path | None = None, sender: "Sender | None" = None) -> tuple["DemoClient", str]:
    """建立用戶端。檔案有多組金鑰時逐組問 OKX 帳戶設定，剛好一組可用才採用，不猜。

    回傳 (client, 說明)；說明只含第幾組與 OKX 上的金鑰名稱，不含金鑰內容。
    """
    sets = load_credential_sets(path)
    if len(sets) == 1:
        return DemoClient(sets[0], sender), "金鑰檔只有一組"
    usable, failures = [], []
    for index, creds in enumerate(sets, 1):
        client = DemoClient(creds, sender)
        try:
            label = str(client._request("GET", "/api/v5/account/config")[0].get("label", ""))
            usable.append((index, client, label))
        except OkxApiError as exc:
            failures.append(f"第 {index} 組 {exc.code}")
    if len(usable) != 1:
        raise DemoError(f"金鑰檔有 {len(sets)} 組，OKX 模擬盤可用的有 {len(usable)} 組，無法判斷用哪一組"
                        f"（{'、'.join(failures) or '全部可用'}）；請只留一組")
    index, client, label = usable[0]
    return client, f"金鑰檔有 {len(sets)} 組，用第 {index} 組（OKX 名稱 {label}；{'、'.join(failures)} 不可用）"


class Sender(Protocol):
    def send(self, method: str, target: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
        """送一次請求，不重試、不跟轉址。"""


class HttpsSender:
    """直接 TLS 到固定主機，不走環境變數代理，不帶 cookie。"""

    def send(self, method, target, headers, body):
        conn = http.client.HTTPSConnection(DEMO_HOST, 443, timeout=TIMEOUT_S,
                                           context=ssl.create_default_context())
        try:
            conn.request(method, target, body=body or None, headers=headers)
            response = conn.getresponse()
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise DemoError("OKX 回應太大，已中止")
            return response.status, data
        except DemoError:
            raise
        except Exception as exc:
            # 不帶例外內文：可能含請求內容。
            raise DemoError(f"連線 OKX 模擬盤失敗（{type(exc).__name__}）") from None
        finally:
            conn.close()


def _timestamp(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sign(secret: str, timestamp: str, method: str, target: str, body: str) -> str:
    digest = hmac.new(secret.encode("ascii"), (timestamp + method + target + body).encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _dec(row: dict, field: str) -> Decimal | None:
    value = row.get(field)
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise DemoError(f"OKX 回應的 {field} 不是數字") from None
    if not result.is_finite():
        raise DemoError(f"OKX 回應的 {field} 不是有限數字")
    return result


def _positive_text(value) -> bool:
    try:
        number = Decimal(value) if type(value) is str else None
    except InvalidOperation:
        return False
    return number is not None and number.is_finite() and number > 0


def _inst(inst_id: str) -> str:
    if type(inst_id) is not str or not _INST.match(inst_id):
        raise DemoError("只支援 USDT 永續合約（例如 BTC-USDT-SWAP）")
    return inst_id


class DemoClient:
    def __init__(self, credentials: Credentials, sender: Sender | None = None, *,
                 clock_ms: Callable[[], int] | None = None, sleep: Callable[[float], None] | None = None,
                 monotonic: Callable[[], float] | None = None):
        if not isinstance(credentials, Credentials):
            raise DemoError("credentials 型別不對")
        self._credentials = credentials
        self._sender = sender if sender is not None else HttpsSender()
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic
        self._last = None
        # One request at a time: a request the Supervisor stopped waiting for can still be running.
        self._gate = threading.Lock()

    def __repr__(self):
        return "DemoClient(<demo>)"

    def _request(self, method: str, path: str, params: dict | None = None, payload: dict | None = None) -> list:
        allowed = _GET_PATHS if method == "GET" else _POST_PATHS if method == "POST" else frozenset()
        if path not in allowed:
            raise DemoError(f"端點不在白名單：{method} {path}")
        target = path + ("?" + urlencode(params) if params else "")
        body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
        headers = {"Accept": "application/json", "Content-Type": "application/json",
                   "x-simulated-trading": "1"}
        if not path.startswith(_PUBLIC_PREFIXES):
            stamp = _timestamp(self._clock_ms())
            headers.update({"OK-ACCESS-KEY": self._credentials.api_key,
                            "OK-ACCESS-PASSPHRASE": self._credentials.passphrase,
                            "OK-ACCESS-TIMESTAMP": stamp,
                            "OK-ACCESS-SIGN": sign(self._credentials.secret, stamp, method, target, body)})
        with self._gate:
            if self._last is not None:
                wait = MIN_INTERVAL_S - (self._monotonic() - self._last)
                if wait > 0:
                    self._sleep(wait)
            if not path.startswith(_PUBLIC_PREFIXES):
                # Re-stamp after the wait so the signature time is the send time.
                stamp = _timestamp(self._clock_ms())
                headers["OK-ACCESS-TIMESTAMP"] = stamp
                headers["OK-ACCESS-SIGN"] = sign(self._credentials.secret, stamp, method, target, body)
            try:
                status, raw = self._sender.send(method, target, headers, body.encode("utf-8"))
            except DemoError:
                raise
            except Exception as exc:
                # 任何送出層的例外都不往外帶內文：可能含 header 或金鑰。
                raise DemoError(f"連線 OKX 模擬盤失敗（{type(exc).__name__}）") from None
            finally:
                self._last = self._monotonic()
        try:
            doc = json.loads(raw.decode("utf-8"), parse_float=Decimal) if raw else None
        except (UnicodeDecodeError, ValueError):
            doc = None
        if not isinstance(doc, dict):
            raise DemoError(f"OKX 回應不是 JSON（HTTP {status}）")
        code = str(doc.get("code", ""))
        if code != "0":
            # 下單類的失敗原因在 data[].sCode／sMsg。
            data = doc.get("data")
            if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("sCode") not in (None, "", "0"):
                raise OkxApiError(str(data[0]["sCode"]), str(data[0].get("sMsg", "")))
            raise OkxApiError(code or f"HTTP{status}", str(doc.get("msg", "")))
        data = doc.get("data")
        if not isinstance(data, list):
            raise DemoError("OKX 回應缺少 data")
        return data

    # ---- 讀取 ----
    def server_time_ms(self) -> int:
        return int(self._request("GET", "/api/v5/public/time")[0]["ts"])

    def instrument(self, inst_id: str = DEFAULT_INST) -> dict:
        rows = self._request("GET", "/api/v5/public/instruments", {"instType": "SWAP", "instId": _inst(inst_id)})
        if len(rows) != 1:
            raise DemoError(f"找不到合約 {inst_id}")
        row = rows[0]
        return {"inst_id": row["instId"], "ct_val": _dec(row, "ctVal"), "lot_sz": _dec(row, "lotSz"),
                "min_sz": _dec(row, "minSz"), "tick_sz": _dec(row, "tickSz"), "state": row.get("state")}

    def mark_price(self, inst_id: str = DEFAULT_INST) -> Decimal:
        rows = self._request("GET", "/api/v5/public/mark-price", {"instType": "SWAP", "instId": _inst(inst_id)})
        if len(rows) != 1:
            raise DemoError(f"拿不到 {inst_id} 的標記價格")
        return _dec(rows[0], "markPx")

    def account_config(self) -> dict:
        rows = self._request("GET", "/api/v5/account/config")
        if len(rows) != 1:
            raise DemoError("帳戶設定回應筆數不對")
        row = rows[0]
        return {"acct_lv": str(row.get("acctLv", "")), "pos_mode": str(row.get("posMode", "")),
                "perm": str(row.get("perm", "")), "uid": str(row.get("uid", ""))}

    def usdt_balance(self) -> dict:
        rows = self._request("GET", "/api/v5/account/balance", {"ccy": "USDT"})
        if len(rows) != 1:
            raise DemoError("餘額回應筆數不對")
        account = rows[0]
        usdt = next((d for d in account.get("details", []) if d.get("ccy") == "USDT"), {})
        return {"total_eq_usd": _dec(account, "totalEq"), "usdt_eq": _dec(usdt, "eq") or Decimal(0),
                "usdt_avail": _dec(usdt, "availEq") if _dec(usdt, "availEq") is not None else _dec(usdt, "availBal") or Decimal(0)}

    def positions(self, inst_id: str | None = None) -> list[dict]:
        params = {"instType": "SWAP"}
        if inst_id is not None:
            params["instId"] = _inst(inst_id)
        result = []
        for row in self._request("GET", "/api/v5/account/positions", params):
            size = _dec(row, "pos") or Decimal(0)
            if size == 0:
                continue
            result.append({"inst_id": row.get("instId"), "pos": size, "mgn_mode": row.get("mgnMode"),
                           "pos_side": row.get("posSide"), "avg_px": _dec(row, "avgPx"),
                           "upl": _dec(row, "upl"), "lever": row.get("lever")})
        return result

    def pending_orders(self, inst_id: str | None = None) -> list[dict]:
        params = {"instType": "SWAP"}
        if inst_id is not None:
            params["instId"] = _inst(inst_id)
        return [{"inst_id": r.get("instId"), "ord_id": r.get("ordId"), "side": r.get("side"),
                 "sz": _dec(r, "sz"), "state": r.get("state"), "tag": r.get("tag")}
                for r in self._request("GET", "/api/v5/trade/orders-pending", params)]

    def order(self, inst_id: str, ord_id: str) -> dict:
        rows = self._request("GET", "/api/v5/trade/order", {"instId": _inst(inst_id), "ordId": str(ord_id)})
        if len(rows) != 1:
            raise DemoError("查委託回應筆數不對")
        r = rows[0]
        return {"ord_id": r.get("ordId"), "state": r.get("state"), "side": r.get("side"), "sz": _dec(r, "sz"),
                "acc_fill_sz": _dec(r, "accFillSz") or Decimal(0), "avg_px": _dec(r, "avgPx"),
                "fee": _dec(r, "fee") or Decimal(0), "pnl": _dec(r, "pnl") or Decimal(0), "tag": r.get("tag")}

    # ---- 寫入：只有市價下單與撤單 ----
    def place_market_order(self, inst_id: str, side: str, size: Decimal, *, reduce_only: bool = False,
                           cl_ord_id: str | None = None) -> str:
        if side not in ("buy", "sell"):
            raise DemoError("side 只能是 buy 或 sell")
        if not isinstance(size, Decimal) or not size.is_finite() or size <= 0:
            raise DemoError("張數要是大於 0 的 Decimal")
        payload = {"instId": _inst(inst_id), "tdMode": "cross", "side": side, "ordType": "market",
                   "sz": format(size, "f"), "tag": TAG}
        if reduce_only:
            payload["reduceOnly"] = True
        if cl_ord_id is not None:
            if not _CL_ORD_ID.match(cl_ord_id):
                raise DemoError("clOrdId 只能是 1～32 個英數字")
            payload["clOrdId"] = cl_ord_id
        rows = self._request("POST", "/api/v5/trade/order", payload=payload)
        if len(rows) != 1 or rows[0].get("sCode") not in ("0", 0) or not rows[0].get("ordId"):
            row = rows[0] if rows else {}
            raise OkxApiError(str(row.get("sCode", "?")), str(row.get("sMsg", "下單回應不完整")))
        return str(rows[0]["ordId"])

    def cancel_order(self, inst_id: str, ord_id: str) -> None:
        self._request("POST", "/api/v5/trade/cancel-order", payload={"instId": _inst(inst_id), "ordId": str(ord_id)})

    # ---- Bot 用：Supervisor 的委託格式、以 clOrdId 查單 ----
    SUPERVISOR_FIELDS = frozenset(("instId", "tdMode", "posSide", "ordType", "side", "sz", "reduceOnly", "clOrdId", "tag"))

    def submit_supervisor_payload(self, payload: dict) -> str:
        """送出 Supervisor 建好的委託（fake_exchange.build_payload 的欄位），原樣轉送、不增減欄位。"""
        if (type(payload) is not dict or set(payload) != self.SUPERVISOR_FIELDS or payload["tag"] != TAG
                or payload["tdMode"] != "cross" or payload["posSide"] != "net" or payload["ordType"] != "market"
                or payload["side"] not in ("buy", "sell") or type(payload["reduceOnly"]) is not bool
                or not _CL_ORD_ID.match(str(payload["clOrdId"]))):
            raise DemoError("委託欄位不符 Supervisor 格式，拒送")
        _inst(payload["instId"])
        rows = self._request("POST", "/api/v5/trade/order", payload=dict(payload))
        if len(rows) != 1 or rows[0].get("sCode") not in ("0", 0) or not rows[0].get("ordId"):
            row = rows[0] if rows else {}
            raise OkxApiError(str(row.get("sCode", "?")), str(row.get("sMsg", "下單回應不完整")))
        return str(rows[0]["ordId"])

    def order_by_client_id(self, inst_id: str, cl_ord_id: str) -> dict | None:
        """查不到（51603）回 None；其他錯誤照常拋出。"""
        try:
            rows = self._request("GET", "/api/v5/trade/order", {"instId": _inst(inst_id), "clOrdId": cl_ord_id})
        except OkxApiError as exc:
            if exc.code == "51603":
                return None
            raise
        if len(rows) != 1:
            raise DemoError("查委託回應筆數不對")
        r = rows[0]
        return {"ord_id": str(r.get("ordId")), "cl_ord_id": r.get("clOrdId"), "state": r.get("state"),
                "sz": _dec(r, "sz"), "acc_fill_sz": _dec(r, "accFillSz") or Decimal(0),
                "u_time": int(r.get("uTime") or 0), "tag": r.get("tag")}

    def order_fills(self, inst_id: str, ord_id: str) -> list[dict]:
        rows = self._request("GET", "/api/v5/trade/fills", {"instType": "SWAP", "instId": _inst(inst_id),
                                                             "ordId": str(ord_id), "limit": "100"})
        return [{"trade_id": str(r["tradeId"]), "fill_sz": _dec(r, "fillSz"), "fill_px": _dec(r, "fillPx"),
                 "fee": _dec(r, "fee") or Decimal(0), "fee_ccy": str(r.get("feeCcy") or "")} for r in rows if str(r.get("ordId")) == str(ord_id)]

    def cancel_by_client_id(self, inst_id: str, cl_ord_id: str) -> None:
        self._request("POST", "/api/v5/trade/cancel-order", payload={"instId": _inst(inst_id), "clOrdId": cl_ord_id})

    # ---- P6 保底停損：OKX 條件單（2026-11-17 使用者：10%、觸發後停下、啟動參數設定）----
    # Supervisor（catos/protection.py）建好的格式原樣轉送：整倉（closeFraction=1）、只減倉、標記價格觸發、市價執行。
    PROTECTION_BASE = frozenset(("instId", "tdMode", "posSide", "ordType", "closeFraction", "reduceOnly", "tag",
                                 "requestId", "algoClOrdId"))
    PROTECTION_PRICE = frozenset(("side", "slTriggerPx", "slTriggerPxType", "slOrdPx"))
    ALGO_TYPES = ("conditional", "oco", "trigger", "move_order_stop")

    def _protection(self, payload: dict, *, priced: bool) -> dict:
        keys = self.PROTECTION_BASE | (self.PROTECTION_PRICE if priced else frozenset())
        if (type(payload) is not dict or set(payload) != keys or payload["tag"] != TAG
                or payload["tdMode"] != "cross" or payload["posSide"] != "net" or payload["ordType"] != "conditional"
                or payload["closeFraction"] != "1" or payload["reduceOnly"] is not True
                or not _CL_ORD_ID.match(str(payload["algoClOrdId"])) or not _CL_ORD_ID.match(str(payload["requestId"]))
                or (priced and (payload["side"] not in ("buy", "sell") or payload["slOrdPx"] != "-1"
                                or payload["slTriggerPxType"] not in ("mark", "last", "index")
                                or not _positive_text(payload["slTriggerPx"])))):
            raise DemoError("保底停損欄位不符 Supervisor 格式，拒送")
        _inst(payload["instId"])
        return payload

    def place_protection(self, payload: dict) -> str:
        p = self._protection(payload, priced=True)
        body = {k: p[k] for k in ("instId", "tdMode", "side", "posSide", "ordType", "closeFraction", "reduceOnly",
                                  "slTriggerPx", "slTriggerPxType", "slOrdPx", "algoClOrdId", "tag")}
        rows = self._request("POST", "/api/v5/trade/order-algo", payload=body)
        if len(rows) != 1 or rows[0].get("sCode") not in ("0", 0) or not rows[0].get("algoId"):
            row = rows[0] if rows else {}
            raise OkxApiError(str(row.get("sCode", "?")), str(row.get("sMsg", "條件單回應不完整")))
        return str(rows[0]["algoId"])

    def amend_protection(self, payload: dict) -> None:
        p = self._protection(payload, priced=True)
        body = {"instId": p["instId"], "algoClOrdId": p["algoClOrdId"], "reqId": p["requestId"],
                "newSlTriggerPx": p["slTriggerPx"], "newSlOrdPx": p["slOrdPx"], "newSlTriggerPxType": p["slTriggerPxType"]}
        rows = self._request("POST", "/api/v5/trade/amend-algos", payload=body)
        if len(rows) != 1 or rows[0].get("sCode") not in ("0", 0):
            row = rows[0] if rows else {}
            raise OkxApiError(str(row.get("sCode", "?")), str(row.get("sMsg", "改條件單回應不完整")))

    def cancel_protection(self, inst_id: str, algo_id: str) -> None:
        if not re.fullmatch(r"[0-9]{1,32}", str(algo_id)):
            raise DemoError("algoId 格式不對")
        rows = self._request("POST", "/api/v5/trade/cancel-algos", payload=[{"instId": _inst(inst_id), "algoId": str(algo_id)}])
        if len(rows) != 1 or rows[0].get("sCode") not in ("0", 0):
            row = rows[0] if rows else {}
            raise OkxApiError(str(row.get("sCode", "?")), str(row.get("sMsg", "撤條件單回應不完整")))

    @staticmethod
    def _algo_row(r: dict) -> dict:
        return {"inst_id": r.get("instId"), "algo_id": str(r.get("algoId") or ""),
                "algo_cl_ord_id": str(r.get("algoClOrdId") or ""), "ord_type": r.get("ordType"),
                "state": r.get("state"), "side": r.get("side"), "sl_trigger_px": _dec(r, "slTriggerPx"),
                "sl_trigger_px_type": r.get("slTriggerPxType"), "tag": r.get("tag"),
                "u_time": int(r.get("uTime") or 0)}

    def protection_order(self, inst_id: str, algo_cl_ord_id: str) -> dict | None:
        """以 algoClOrdId 查一張條件單；查不到回 None，其他錯誤照常拋出。"""
        if not _CL_ORD_ID.match(str(algo_cl_ord_id)):
            raise DemoError("algoClOrdId 只能是 1～32 個英數字")
        try:
            rows = self._request("GET", "/api/v5/trade/order-algo", {"algoClOrdId": algo_cl_ord_id})
        except OkxApiError as exc:
            if exc.code in ("51603", "51000"):
                return None
            raise
        if not rows:
            return None
        if len(rows) != 1:
            raise DemoError("查條件單回應筆數不對")
        row = self._algo_row(rows[0])
        if row["inst_id"] != _inst(inst_id):
            raise DemoError("條件單的合約不對")
        return row

    def pending_algos(self) -> list[dict]:
        """帳戶裡所有等待中的 SWAP 條件類委託（四種類型），用來找陌生的條件單。"""
        result = []
        for ord_type in self.ALGO_TYPES:
            rows = self._request("GET", "/api/v5/trade/orders-algo-pending", {"ordType": ord_type, "instType": "SWAP"})
            result.extend(self._algo_row(r) for r in rows)
        return result

    BARS = {300_000: "5m", 900_000: "15m", 3_600_000: "1H", 14_400_000: "4H"}

    def closed_candles(self, inst_id: str, timeframe_ms: int, limit: int) -> list[dict]:
        """最近已收盤 K 線，由舊到新（OKX market/candles，最多 300 根；confirm=1 才算收盤）。"""
        if timeframe_ms not in self.BARS or not 1 <= limit <= 299:
            raise DemoError("K 線週期或根數不支援")
        rows = self._request("GET", "/api/v5/market/candles",
                             {"instId": _inst(inst_id), "bar": self.BARS[timeframe_ms], "limit": str(limit + 1)})
        result = []
        for r in rows:
            if not isinstance(r, list) or len(r) < 9:
                raise DemoError("K 線格式不對")
            if r[8] != "1":
                continue
            result.append({"open_time_ms": int(r[0]), "open": Decimal(r[1]), "high": Decimal(r[2]),
                           "low": Decimal(r[3]), "close": Decimal(r[4])})
        result.sort(key=lambda bar: bar["open_time_ms"])
        return result[-limit:]

    def account_snapshot(self) -> dict:
        """風控用：USDT 權益、維持保證金率（無部位時 OKX 回空）。"""
        rows = self._request("GET", "/api/v5/account/balance", {"ccy": "USDT"})
        if len(rows) != 1:
            raise DemoError("餘額回應筆數不對")
        account = rows[0]
        usdt = next((d for d in account.get("details", []) if d.get("ccy") == "USDT"), None)
        if usdt is None or _dec(usdt, "eq") is None:
            raise DemoError("餘額回應沒有 USDT 權益")
        return {"usdt_eq": _dec(usdt, "eq"), "mgn_ratio": _dec(account, "mgnRatio"),
                "u_time": int(account.get("uTime") or 0)}


# ---- 帳戶檢查（第一張單前的簡單核對）----

def account_issues(config: dict) -> list[str]:
    """回傳不適合交易的原因；空清單表示可以下單。"""
    issues = []
    perms = {p.strip() for p in config["perm"].split(",") if p.strip()}
    if "withdraw" in perms:
        issues.append("這把金鑰開了提幣權限，請改建一把不含提幣的模擬盤金鑰")
    if "trade" not in perms:
        issues.append("這把金鑰沒有交易權限：查餘額可以，下單會被拒")
    if config["pos_mode"] != "net_mode":
        issues.append(f"持倉模式是 {config['pos_mode']}，CatOS 只支援單向持倉（net_mode）；請在 OKX 模擬盤的設定裡改成單向持倉")
    if config["acct_lv"] not in ("2", "3", "4"):
        issues.append(f"帳戶模式（acctLv={config['acct_lv']}）不能交易永續合約；請在 OKX 模擬盤改成單幣種或跨幣種保證金模式")
    return issues


def status(client: DemoClient, inst_id: str = DEFAULT_INST) -> dict:
    config = client.account_config()
    return {"config": config, "issues": account_issues(config), "balance": client.usdt_balance(),
            "positions": client.positions(), "pending": client.pending_orders(), "inst_id": inst_id}


class FirstOrderStop(DemoError):
    """第一張單流程在某一步停下；`report` 是停下前已完成的步驟。"""

    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


def _wait_filled(client: DemoClient, inst_id: str, ord_id: str, sleep: Callable[[float], None],
                 attempts: int = 20) -> dict:
    for _ in range(attempts):
        order = client.order(inst_id, ord_id)
        if order["state"] == "filled":
            return order
        if order["state"] in ("canceled", "mmp_canceled"):
            raise DemoError(f"委託 {ord_id} 被取消（state={order['state']}），沒有成交")
        sleep(0.5)
    raise DemoError(f"委託 {ord_id} 等了約 10 秒還沒全部成交，狀態不明；請到 OKX 網頁確認")


def _position_size(client: DemoClient, inst_id: str) -> Decimal:
    rows = client.positions(inst_id)
    if any(p["mgn_mode"] != "cross" for p in rows):
        raise DemoError(f"{inst_id} 有非全倉部位，CatOS 不處理")
    return sum((p["pos"] for p in rows), Decimal(0))


def first_order(client: DemoClient, inst_id: str = DEFAULT_INST, *,
                sleep: Callable[[float], None] = time.sleep, stamp: str | None = None) -> dict:
    """最小單買進，核對部位；再減倉賣出，核對歸零與餘額變化。

    開始前帳戶設定要合格，且這個合約沒有部位、沒有掛單（陌生部位不碰）。
    平倉用 reduceOnly，只會減少部位。中途出錯就停，不重送；已開的部位會試一次平倉。
    """
    report: dict = {"inst_id": inst_id, "steps": []}
    config = client.account_config()
    issues = account_issues(config)
    if issues:
        raise FirstOrderStop("帳戶設定不能下單：" + "；".join(issues), report)
    if _position_size(client, inst_id) != 0:
        raise FirstOrderStop(f"{inst_id} 已經有部位；CatOS 不碰不是自己開的部位，請先在 OKX 網頁平掉", report)
    if client.pending_orders(inst_id):
        raise FirstOrderStop(f"{inst_id} 有掛單；請先在 OKX 網頁撤掉", report)
    spec = client.instrument(inst_id)
    size = spec["min_sz"]
    before = client.usdt_balance()
    report.update({"size": size, "ct_val": spec["ct_val"], "usdt_eq_before": before["usdt_eq"]})
    if before["usdt_avail"] <= 0:
        raise FirstOrderStop("USDT 可用餘額是 0，無法下單", report)

    stamp = stamp or str(time.time_ns() // 1_000_000)
    try:
        open_id = client.place_market_order(inst_id, "buy", size, cl_ord_id=f"catosm1o{stamp}")
    except DemoError as exc:
        raise FirstOrderStop(f"開倉委託被拒：{exc}", report) from None
    report["steps"].append("開倉委託已送出")
    try:
        opened = _wait_filled(client, inst_id, open_id, sleep)
        report["open"] = opened
        held = _position_size(client, inst_id)
        report["position_after_open"] = held
        if held != opened["acc_fill_sz"]:
            raise DemoError(f"部位對不上：成交 {opened['acc_fill_sz']} 張，OKX 部位 {held} 張")
        report["steps"].append("開倉成交，部位核對相符")
    except DemoError as exc:
        _try_close(client, inst_id, report, stamp)
        raise FirstOrderStop(str(exc), report) from None

    try:
        close_id = client.place_market_order(inst_id, "sell", size, reduce_only=True, cl_ord_id=f"catosm1c{stamp}")
        report["steps"].append("平倉委託已送出")
        closed = _wait_filled(client, inst_id, close_id, sleep)
    except DemoError as exc:
        raise FirstOrderStop(f"{exc}；部位可能還在，請到 OKX 網頁確認", report) from None
    report["close"] = closed
    left = _position_size(client, inst_id)
    report["position_after_close"] = left
    if left != 0:
        raise FirstOrderStop(f"平倉後部位應為 0，OKX 顯示 {left} 張", report)
    report["steps"].append("平倉成交，部位歸零")

    after = client.usdt_balance()
    expected = opened["pnl"] + opened["fee"] + closed["pnl"] + closed["fee"]
    report.update({"usdt_eq_after": after["usdt_eq"], "usdt_eq_change": after["usdt_eq"] - before["usdt_eq"],
                   "expected_change": expected})
    # 期間若剛好收資金費，差額會不等於成交損益加手續費；只列出，不擋。
    report["balance_matches"] = report["usdt_eq_change"] == expected
    report["steps"].append("餘額已核對")
    return report


def _try_close(client: DemoClient, inst_id: str, report: dict, stamp: str) -> None:
    try:
        held = _position_size(client, inst_id)
        if held > 0:
            ord_id = client.place_market_order(inst_id, "sell", held, reduce_only=True, cl_ord_id=f"catosm1x{stamp}")
            report["steps"].append(f"出錯後已送出減倉委託 {ord_id}，請到 OKX 網頁確認部位已歸零")
    except DemoError as exc:
        report["steps"].append(f"出錯後試著平倉也失敗（{exc}），請到 OKX 網頁手動平倉")


def render_first_order(report: dict) -> str:
    lines = [f"OKX 模擬盤第一張單：{report['inst_id']}", ""]
    lines.extend(f"  ✓ {s}" for s in report["steps"])
    if "open" in report:
        o = report["open"]
        lines += ["", f"  開倉  買 {_fmt(o['acc_fill_sz'])} 張  均價 {_fmt(o['avg_px'])}  手續費 {_fmt(o['fee'])}  ordId={o['ord_id']}"]
    if "close" in report:
        c = report["close"]
        lines.append(f"  平倉  賣 {_fmt(c['acc_fill_sz'])} 張  均價 {_fmt(c['avg_px'])}  手續費 {_fmt(c['fee'])}  損益 {_fmt(c['pnl'])}  ordId={c['ord_id']}")
    if "usdt_eq_after" in report:
        lines += ["", f"  USDT 權益  {_fmt(report['usdt_eq_before'])} → {_fmt(report['usdt_eq_after'])}（變化 {_fmt(report['usdt_eq_change'])}）",
                  f"  成交損益＋手續費合計 {_fmt(report['expected_change'])}",
                  "  餘額核對：" + ("相符" if report["balance_matches"] else "不相符（期間若剛好收資金費會有差額；請對照 OKX 網頁的帳單）")]
    return "\n".join(lines)


def _fmt(value) -> str:
    return "—" if value is None else format(value, "f")


def render_status(report: dict) -> str:
    bal = report["balance"]
    lines = ["OKX 模擬盤（Demo）帳戶", "",
             f"  總權益（USD）  {_fmt(bal['total_eq_usd'])}",
             f"  USDT 權益      {_fmt(bal['usdt_eq'])}",
             f"  USDT 可用      {_fmt(bal['usdt_avail'])}", ""]
    if report["positions"]:
        lines.append("  部位：")
        for p in report["positions"]:
            lines.append(f"    {p['inst_id']}  {_fmt(p['pos'])} 張  均價 {_fmt(p['avg_px'])}  未實現 {_fmt(p['upl'])}  {p['mgn_mode']}")
    else:
        lines.append("  部位：無")
    lines.append(f"  掛單：{len(report['pending'])} 筆")
    for o in report["pending"]:
        lines.append(f"    {o['inst_id']}  {o['side']} {_fmt(o['sz'])}  {o['state']}  ordId={o['ord_id']}")
    lines.append("")
    if report["issues"]:
        lines.append("  不能下單，原因：")
        lines.extend(f"    - {i}" for i in report["issues"])
    else:
        lines.append("  帳戶設定可以下單（單向持倉、可交易永續、金鑰無提幣權限）")
    return "\n".join(lines)


def cli_main(argv: list[str]) -> int:
    import argparse
    import sys
    if argv and argv[0] == "bot":
        from catos.demo_bot import cli_main as bot_main
        return bot_main(argv[1:])
    if argv and argv[0] == "rearm":
        from catos.demo_bot import rearm_main
        return rearm_main(argv[1:])
    parser = argparse.ArgumentParser(prog="catos.cli demo", description="OKX 模擬盤（只連 Demo）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status", help="讀模擬盤的餘額、部位、掛單")
    p_status.add_argument("--inst", default=DEFAULT_INST)
    p_first = sub.add_parser("first-order", help="下一張最小市價單再平掉，核對部位與餘額")
    p_first.add_argument("--inst", default=DEFAULT_INST, choices=[DEFAULT_INST])  # M1: one contract only
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        # 輸出被導到檔案或管線時，Windows 預設用舊編碼，中文會變亂碼。
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        client, note = connect()
        print(f"金鑰：{credentials_path()}，{note}\n")
        if args.cmd == "status":
            print(render_status(status(client, args.inst)))
            return 0
        if args.cmd == "first-order":
            print(render_first_order(first_order(client, args.inst)))
            return 0
    except FirstOrderStop as exc:
        print(render_first_order(exc.report))
        sys.stderr.write(f"停止：{exc}\n")
        return 1
    except DemoError as exc:
        sys.stderr.write(f"錯誤：{exc}\n")
        if isinstance(exc, OkxApiError) and exc.code == "50101":
            sys.stderr.write("提示：50101 通常是用了實盤金鑰。請在 OKX「模擬交易」裡建立 API 金鑰。\n")
        return 1
    return 2
