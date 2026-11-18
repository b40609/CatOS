"""One-off Demo probe (M1 scope: place/cancel on BTC-USDT-SWAP demo): does OKX honor expTime?"""
import json, sys, time
from decimal import Decimal as D
sys.path.insert(0, r"C:\dev\CatOS")
from catos.okx_demo import connect, OkxApiError
from catos.fake_exchange import TAG
INST = "BTC-USDT-SWAP"
client, note = connect()
out = {"note": note}
def pos():
    return sum((p["pos"] for p in client.positions(INST)), D(0))
assert pos() == 0 and not client.pending_orders(INST), "not flat"
stamp = str(time.time_ns() // 1_000_000)
def order(cl, side, reduce):
    return {"instId": INST, "tdMode": "cross", "posSide": "net", "ordType": "market", "side": side,
            "sz": "0.01", "reduceOnly": reduce, "clOrdId": cl, "tag": TAG}
server = client.server_time_ms()
out["skew_ms"] = server - time.time_ns() // 1_000_000
# 1. expired deadline: must not be processed
cl1 = "catosexp1" + stamp
p1 = order(cl1, "buy", False)
try:
    client._request("POST", "/api/v5/trade/order", payload=p1, exp_time_ms=server - 60_000)
    out["expired"] = "ACCEPTED"
except OkxApiError as exc:
    out["expired"] = {"code": exc.code, "msg": exc.message if hasattr(exc, "message") else str(exc)}
time.sleep(2)
out["expired_query"] = client.order_by_client_id(INST, cl1)
out["pos_after_expired"] = str(pos())
# 2. valid deadline: normal fill, and the tag OKX reports on an ordinary order
cl2 = "catosexp2" + stamp
if pos() == 0:
    client._request("POST", "/api/v5/trade/order", payload=order(cl2, "buy", False),
                    exp_time_ms=client.server_time_ms() + 5_000)
    t0 = time.time()
    got = client.order_by_client_id(INST, cl2)
    out["valid_first_query_s"] = round(time.time() - t0, 3)
    out["valid_order"] = {k: str(v) for k, v in (got or {}).items()}
# close whatever is open
if pos() != 0:
    side = "sell" if pos() > 0 else "buy"
    cl3 = "catosexp3" + stamp
    client._request("POST", "/api/v5/trade/order", payload=dict(order(cl3, side, True), sz=str(abs(pos()))),
                    exp_time_ms=client.server_time_ms() + 5_000)
    time.sleep(1)
    out["close_order"] = {k: str(v) for k, v in (client.order_by_client_id(INST, cl3) or {}).items()}
out["final_pos"] = str(pos())
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
