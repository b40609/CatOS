"""自寫情境：直接餵 OKX 餘額回應給 account_snapshot，再套 demo_bot.py:479 的同一條判斷。

不連 OKX：DemoClient._request 換成回固定資料的函式。
"""
import sys
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from catos.okx_demo import DemoClient, DemoError  # noqa: E402


def margin_ok(position, ratio):  # demo_bot.py:479 原文
    return position == 0 or (ratio is not None and ratio >= 3)


def run(label, top, details):
    client = DemoClient.__new__(DemoClient)
    client._request = lambda method, path, params=None, **kw: [dict({"totalEq": "5000", "uTime": "1"},
                                                                     **({} if top is None else {"mgnRatio": top}),
                                                                     details=details)]
    try:
        ratio = client.account_snapshot()["mgn_ratio"]
        verdict = f"mgn_ratio={ratio!s:<6} margin_ok(持倉)={margin_ok(D(1), ratio)}"
    except DemoError as exc:
        verdict = f"DemoError: {exc}"
    print(f"{label:<44} {verdict}")


U = lambda **kw: dict({"ccy": "USDT", "eq": "5000"}, **kw)  # noqa: E731
run("S1 Futures：頂層空、USDT details 50", "", [U(mgnRatio="50")])
run("S2 兩處都空", "", [U(mgnRatio="")])
run("S3 兩處都沒有欄位", None, [U()])
run("S4 頂層空、details 0", "", [U(mgnRatio="0")])
run("S5 頂層空、details 負值 -1", "", [U(mgnRatio="-1")])
run("S6 頂層空、details 2.99（低於門檻）", "", [U(mgnRatio="2.99")])
run("S7 頂層空、details 3（剛好門檻）", "", [U(mgnRatio="3")])
run("S8 頂層空、details 非數字 abc", "", [U(mgnRatio="abc")])
run("S9 頂層空、details NaN", "", [U(mgnRatio="NaN")])
run("S10 頂層空、details Infinity", "", [U(mgnRatio="Infinity")])
run("S11 只有 BTC details 有值、USDT 空", "", [dict(ccy="BTC", eq="1", mgnRatio="50"), U(mgnRatio="")])
run("S12 BTC 在前且有值、USDT 2", "", [dict(ccy="BTC", eq="1", mgnRatio="50"), U(mgnRatio="2")])
run("S13 多幣種：頂層 2、details 50（並存）", "2", [U(mgnRatio="50")])
run("S14 頂層 0、details 50", "0", [U(mgnRatio="50")])
run("S15 頂層 abc、details 50", "abc", [U(mgnRatio="50")])
run("S16 頂層 50、details abc（不會讀到）", "50", [U(mgnRatio="abc")])
run("S17 頂層空白字串 ' '、details 50", " ", [U(mgnRatio="50")])
run("S18 頂層 null（JSON null）、details 50", None, [U(mgnRatio="50")])
run("S19 details 數字型別 50（非字串）", "", [U(mgnRatio=50)])
