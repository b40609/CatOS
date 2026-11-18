"""One-off P6 check on OKX Demo: what OKX actually does with the disaster stop (2026-11-18).

Waiting for the Donchian Bot to trade can take days, so this opens the minimum size once
and walks the disaster stop through the same adapter the Bot uses (``OkxDemoExchange``:
``submit`` with the Supervisor order format, ``protection`` with the Supervisor
conditional-order format, fixed tag), then closes. Like ``demo first-order`` it is a
one-off check under the M1 Demo authorization (orders and cancels on Demo), not a second
trading path: no journal, no strategy, minimum size, and it refuses to run while the Bot
is running or the contract has any position, order or conditional order.

It records the evidence the code was written without (all "unverified" until now):
- the fields OKX returns for ``order-algo`` and ``orders-algo-history``;
- whether OKX cancels the whole-position stop by itself once the position is closed;
- which code ``order-algo`` answers for a finished stop (51603 or a row);
- whether the adapter then settles through the history endpoint.
Only field names, states, prices and codes are recorded; never credentials.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import time
from types import SimpleNamespace

from catos.fake_exchange import TAG, build_payload
from catos.okx_demo import DemoClient, DemoError, OkxApiError, account_issues
from catos.okx_demo_exchange import OkxDemoExchange
from catos import protection

D = Decimal
WATCH_SECONDS = 10
HISTORY_STATES = ("effective", "canceled", "order_failed")
ALGO_FIELDS = ("instId", "algoId", "algoClOrdId", "ordType", "state", "side", "slTriggerPx", "slTriggerPxType",
               "slOrdPx", "closeFraction", "reduceOnly", "sz", "tag", "cTime", "uTime")


class CheckStopped(DemoError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def bot_running(root: Path, now: float | None = None, fresh_seconds: int = 1200) -> str | None:
    """Run id of a Bot whose status says running and was updated recently, else None."""
    now = time.time() if now is None else now
    if not root.is_dir():
        return None
    for run in root.iterdir():
        try:
            status = json.loads((run / "status.json").read_text(encoding="utf-8"))
            updated = datetime.fromisoformat(status["updated_at"]).timestamp()
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if status.get("state") == "running" and now - updated < fresh_seconds:
            return run.name
    return None


def _probe(client, path, params):
    """One raw GET; returns the code and the algo rows reduced to known fields (never headers)."""
    try:
        rows = client._request("GET", path, params)
    except OkxApiError as exc:
        return dict(code=exc.code, rows=[])
    return dict(code="0", keys=sorted(rows[0]) if rows else [],
                rows=[{k: r.get(k) for k in ALGO_FIELDS if k in r} for r in rows])


def _probe_algo(client, inst, algo_cl):
    found = _probe(client, "/api/v5/trade/order-algo", {"algoClOrdId": algo_cl})
    found["rows"] = [r for r in found["rows"] if r.get("algoClOrdId") == algo_cl]
    return found


def _probe_history(client, inst, algo_cl):
    result = {}
    for state in HISTORY_STATES:
        found = _probe(client, "/api/v5/trade/orders-algo-history",
                       {"ordType": "conditional", "state": state, "instType": "SWAP", "instId": inst})
        mine = [r for r in found["rows"] if r.get("algoClOrdId") == algo_cl]
        result[state] = dict(code=found["code"], listed=len(found["rows"]), mine=mine,
                             keys=found.get("keys", []))
    return result


def _report_dict(report):
    return {k: getattr(report, k) for k in ("status", "price", "side", "trigger", "complete", "algo_id")
            if hasattr(report, k)}


def _position(client, inst):
    rows = client.positions(inst)
    if any(p["mgn_mode"] != "cross" for p in rows):
        raise DemoError(f"{inst} 有非全倉部位，CatOS 不處理")
    return sum((p["pos"] for p in rows), D(0))


async def run_check(client: DemoClient, inst: str, *, sleep=asyncio.sleep, stamp: str | None = None,
                    ratio: Decimal = D("0.1"), watch_seconds: int = WATCH_SECONDS) -> dict:
    report: dict = dict(inst_id=inst, steps=[], findings={})
    issues = account_issues(client.account_config())
    if issues:
        raise CheckStopped("帳戶設定不能下單：" + "；".join(issues), report)
    if _position(client, inst) != 0:
        raise CheckStopped(f"{inst} 有部位；這個檢查只在空倉時跑", report)
    if client.pending_orders(inst):
        raise CheckStopped(f"{inst} 有掛單；請先處理", report)
    if any(a["inst_id"] == inst for a in client.pending_algos()):
        raise CheckStopped(f"{inst} 有等待中的條件單；請先處理", report)
    spec = client.instrument(inst)
    size, tick = spec["min_sz"], spec["tick_sz"]
    contract = SimpleNamespace(inst_id=inst)
    stamp = stamp or str(time.time_ns() // 1_000_000)
    exchange = OkxDemoExchange(client, f"protcheck{stamp}", inst, sleep=sleep)
    algo_cl = f"catospc1{stamp}"
    base = dict(instId=inst, tdMode="cross", posSide="net", ordType="conditional", closeFraction="1",
                reduceOnly=True, tag=TAG, algoClOrdId=algo_cl)

    def priced(request_id, price):
        return dict(base, requestId=request_id, side="sell", slTriggerPx=str(price), slTriggerPxType="mark",
                    slOrdPx="-1")

    opened = False
    try:
        fill = await exchange.submit(build_payload(contract, f"catospco{stamp}", size, False))
        if fill.status != "FILLED" or not fill.complete:
            raise DemoError(f"開倉沒有完整成交（{fill.status}）")
        opened = True
        quantity = sum((f.quantity for f in fill.fills), D(0))
        average = sum((f.quantity * f.price for f in fill.fills), D(0)) / quantity
        report.update(size=str(size), tick=str(tick), average=str(average))
        report["steps"].append(f"開倉 {size} 張，均價 {average}")

        stop1 = protection.stop_price(average, size, tick, protection.Config(ratio=ratio))
        created = await exchange.protection("algo_create", priced(algo_cl, stop1))
        report["create"] = dict(expected=str(stop1), adapter=_report_dict(created),
                                raw=_probe_algo(client, inst, algo_cl))
        if created.status != "LIVE" or created.price != stop1:
            raise DemoError(f"掛停損後查到的不是預期的 {stop1}：{_report_dict(created)}")
        report["steps"].append(f"保底停損已掛：賣出整倉，標記價格 {stop1} 觸發")

        stop2 = protection.stop_price(average, size, tick, protection.Config(ratio=ratio + D("0.02")))
        amended = await exchange.protection("algo_amend", priced(f"catospc2{stamp}", stop2))
        report["amend"] = dict(expected=str(stop2), adapter=_report_dict(amended),
                               raw=_probe_algo(client, inst, algo_cl))
        if amended.status != "LIVE" or amended.price != stop2:
            raise DemoError(f"改價後查到的不是預期的 {stop2}：{_report_dict(amended)}")
        report["steps"].append(f"保底停損已改到 {stop2}")

        closed = await exchange.submit(build_payload(contract, f"catospcc{stamp}", -size, True))
        if closed.status != "FILLED" or not closed.complete:
            raise DemoError(f"平倉沒有完整成交（{closed.status}）")
        opened = False
        report["steps"].append("平倉成交")
        if _position(client, inst) != 0:
            raise DemoError("平倉後 OKX 部位不是 0")

        watch = []
        for _ in range(watch_seconds):
            found = _probe_algo(client, inst, algo_cl)
            watch.append(dict(code=found["code"], states=[r.get("state") for r in found["rows"]]))
            if found["code"] != "0" or any(r.get("state") != "live" for r in found["rows"]):
                break
            await sleep(1)
        report["after_close_order_algo"] = watch
        report["after_close_history"] = _probe_history(client, inst, algo_cl)
        queried = await exchange.protection("algo_query", dict(base, requestId=f"catospc3{stamp}"))
        report["after_close_adapter_query"] = _report_dict(queried)
        auto = queried.status != "LIVE"
        report["findings"]["auto_cancel_on_flat"] = auto
        report["steps"].append("平倉後 OKX " + ("已自動結束條件單" if auto else f"沒有撤條件單（觀察 {len(watch)} 秒）"))

        if not auto:
            canceled = await exchange.protection("algo_cancel", dict(base, requestId=f"catospc4{stamp}"))
            report["cancel_adapter"] = _report_dict(canceled)
            if canceled.status == "LIVE":
                raise DemoError("撤條件單後還是 LIVE")
            report["steps"].append(f"撤條件單完成（{canceled.status}）")
        report["finished_order_algo"] = _probe_algo(client, inst, algo_cl)
        report["finished_history"] = _probe_history(client, inst, algo_cl)
        final = await exchange.protection("algo_query", dict(base, requestId=f"catospc5{stamp}"))
        report["finished_adapter_query"] = _report_dict(final)
        report["findings"]["finished_order_algo_code"] = report["finished_order_algo"]["code"]
        report["findings"]["history_has_it"] = [s for s, v in report["finished_history"].items() if v["mine"]]
        report["findings"]["adapter_final_status"] = final.status
        left = [a for a in client.pending_algos() if a["inst_id"] == inst]
        if left or _position(client, inst) != 0:
            raise DemoError(f"結束時還有部位或條件單（條件單 {len(left)} 張）")
        report["steps"].append("結束：空倉、沒有條件單")
        return report
    except Exception as exc:  # noqa: BLE001 - always try to leave the account clean
        _cleanup(client, exchange, contract, inst, size, stamp, algo_cl, opened, report)
        if isinstance(exc, CheckStopped):
            raise
        raise CheckStopped(f"{type(exc).__name__}: {exc}", report) from None


def _cleanup(client, exchange, contract, inst, size, stamp, algo_cl, opened, report):
    try:
        held = _position(client, inst)
        if held > 0:
            client.submit_supervisor_payload(build_payload(contract, f"catospcx{stamp}", -held, True))
            report["steps"].append(f"出錯後已送出只減倉的平倉單（{held} 張），請到 OKX 網頁確認")
    except Exception as exc:  # noqa: BLE001
        report["steps"].append(f"出錯後平倉失敗（{type(exc).__name__}），請到 OKX 網頁手動平倉")
    try:
        mine = client.protection_order(inst, algo_cl)
        if mine is not None and mine["state"] in ("live", "pause"):
            client.cancel_protection(inst, mine["algo_id"])
            report["steps"].append("出錯後已撤掉這次掛的條件單")
    except Exception as exc:  # noqa: BLE001
        report["steps"].append(f"出錯後撤條件單失敗（{type(exc).__name__}），請到 OKX 網頁確認")


def render(report: dict) -> str:
    lines = [f"OKX 模擬盤保底停損實測：{report['inst_id']}", ""]
    lines += [f"  - {s}" for s in report["steps"]]
    f = report.get("findings", {})
    if f:
        lines += ["", "  OKX 實際行為："]
        if "auto_cancel_on_flat" in f:
            lines.append(f"    平倉後自動結束條件單：{'是' if f['auto_cancel_on_flat'] else '否'}")
        if "finished_order_algo_code" in f:
            lines.append(f"    已結束的條件單用 order-algo 查：code {f['finished_order_algo_code']}")
            lines.append(f"    orders-algo-history 查得到：{', '.join(f['history_has_it']) or '查不到'}")
            lines.append(f"    Bot 的轉接層最後判定：{f['adapter_final_status']}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import argparse
    import sys
    from catos.okx_demo import DEFAULT_INST, connect, credentials_path
    parser = argparse.ArgumentParser(prog="catos.cli demo protection-check",
                                     description="在模擬盤開最小張數，實測保底停損的掛、改、平倉後狀態，再全部收掉")
    parser.add_argument("--inst", default=DEFAULT_INST, choices=[DEFAULT_INST])
    parser.add_argument("--out", type=Path, default=Path("reports") / "okx-demo-protection-check")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    running = bot_running(Path("outputs") / "okx-demo-bot")
    if running:
        sys.stderr.write(f"停止：模擬盤 Bot 還在跑（run {running}）。先在 Bot 視窗按 Ctrl+C 或在 run 資料夾建 stop.request。\n")
        return 1
    stamp = str(time.time_ns() // 1_000_000)
    try:
        client, note = connect()
        print(f"金鑰：{credentials_path()}，{note}\n")
        report = asyncio.run(run_check(client, args.inst, stamp=stamp))
        code = 0
    except CheckStopped as exc:
        report, code = exc.report, 1
        report["stopped"] = str(exc)
    except DemoError as exc:
        sys.stderr.write(f"錯誤：{exc}\n")
        return 1
    report["time"] = datetime.now(timezone.utc).isoformat()
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(render(report))
    if code:
        sys.stderr.write(f"停止：{report['stopped']}\n")
    print(f"\n完整紀錄：{path}")
    return code
