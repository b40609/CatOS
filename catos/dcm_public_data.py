"""Explicitly invoked, bounded PUBLIC OKX research snapshot collector.

Not a Worker adapter, background collector, credential reader or arbitrary URL
proxy. Only BTC-USDT-SWAP and a fixed GET allowlist are supported in this slice.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import time
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from catos.dcm import DAY, HOUR, D
from catos.data_io import REQUIRED_COLUMNS, load_candles_csv
from catos.research import BacktestConfig, ContractSpec, FundingEvent

BASE = "https://www.okx.com"
SYMBOL = "BTC-USDT-SWAP"
TIMEFRAMES = {"15m": 900_000, "1H": HOUR, "4H": 4 * HOUR}
ENDPOINTS = {
    "time": "/api/v5/public/time",
    "instrument": "/api/v5/public/instruments",
    "candles": "/api/v5/market/history-candles",
    "marks": "/api/v5/market/history-mark-price-candles",
    "funding": "/api/v5/public/funding-rate-history",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def public_get(endpoint, params):
    if endpoint not in ENDPOINTS.values():
        raise ValueError("endpoint is not on the public research allowlist")
    if set(params) - {"instType", "instId", "bar", "after", "limit"}:
        raise ValueError("unsupported public query parameter")
    if "instId" in params and params["instId"] != SYMBOL:
        raise ValueError("this collection authorization is single-market")
    request = Request(BASE + endpoint + ("?" + urlencode(params) if params else ""),
                      headers={"User-Agent": "CatOS-offline-research/1.0"}, method="GET")
    with urlopen(request, timeout=25) as response:
        if urlsplit(response.geturl()).hostname != "www.okx.com":
            raise ValueError("unexpected public endpoint redirect")
        return json.loads(response.read(8_000_001).decode("utf-8"))


class Collector:
    def __init__(self, output, transport=public_get, pause=time.sleep, progress=print):
        self.output = Path(output)
        self.transport, self.pause, self.progress = transport, pause, progress
        self.requests = []

    def request(self, kind, **params):
        for attempt in range(3):
            try:
                value = self.transport(ENDPOINTS[kind], params)
                if value.get("code") != "0" or not isinstance(value.get("data"), list):
                    raise ValueError("public API returned an unsuccessful envelope: " + str(value.get("code")))
                break
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise
                self.pause(attempt + 1)
        name = f"raw/{len(self.requests):04d}-{kind}.json"
        write_json(self.output / name, {"endpoint": ENDPOINTS[kind], "query": params,
                                       "retrieved_at_ms": time.time_ns() // 1_000_000,
                                       "response": value})
        self.requests.append(name)
        self.pause(0.22)
        return value["data"]

    def history(self, kind, start, end, bar=None):
        rows, cursor = {}, end + 1
        for page in range(180):
            params = {"instId": SYMBOL, "after": str(cursor), "limit": "100"}
            if bar:
                params["bar"] = bar
            data = self.request(kind, **params)
            if not data:
                raise ValueError(f"{kind}/{bar}: history ended before requested start")
            stamps = []
            for row in data:
                stamp = int(row["fundingTime"] if kind == "funding" else row[0])
                if stamp >= cursor:
                    raise ValueError("public pagination did not return older records")
                stamps.append(stamp)
                if stamp in rows and rows[stamp] != row:
                    raise ValueError("conflicting duplicate public record")
                rows[stamp] = row
            oldest = min(stamps)
            if oldest <= start:
                return [rows[stamp] for stamp in sorted(rows) if start <= stamp <= end]
            cursor = oldest
            if page % 10 == 0:
                self.progress(f"collect {kind}/{bar or '-'} page={page + 1}", flush=True)
        raise ValueError("bounded public pagination limit exhausted")

    def collect(self, days=85):
        if type(days) is not int or not 70 <= days <= 88:
            raise ValueError("days must be an integer in [70,88]")
        self.output.mkdir(parents=True, exist_ok=False)
        (self.output / "raw").mkdir()
        try:
            server_ms = int(self.request("time")[0]["ts"])
            # Leave a full completed day behind the current day, so settlement
            # timestamp mark candles are also confirmed, including the end edge.
            end = server_ms // DAY * DAY - DAY
            start = end - days * DAY
            instruments = self.request("instrument", instType="SWAP", instId=SYMBOL)
            if len(instruments) != 1:
                raise ValueError("expected exactly one public instrument")
            meta = instruments[0]
            if (meta["instId"] != SYMBOL or meta["ctType"] != "linear"
                    or meta["settleCcy"] != "USDT" or meta["ctValCcy"] != "BTC"):
                raise ValueError("unexpected public contract specification")
            contract = {"inst_id": SYMBOL, "base_per_contract": str(D(meta["ctVal"]) * D(meta["ctMult"])),
                        "tick_size": meta["tickSz"], "lot_size": meta["lotSz"], "min_size": meta["minSz"]}
            marks = self.history("marks", start, end, "1H")
            mark_map = {}
            for row in marks:
                if len(row) != 6 or row[-1] != "1":
                    raise ValueError("unconfirmed or malformed historical mark candle")
                mark_map[int(row[0])] = row[1]
            funding = self.history("funding", start, end)
            events = []
            for row in funding:
                if row["instId"] != SYMBOL or not row.get("realizedRate"):
                    raise ValueError("missing realized funding rate or wrong instrument")
                stamp = int(row["fundingTime"])
                if stamp not in mark_map:
                    raise ValueError("funding event lacks a matching historical mark-price open")
                events.append({"time_ms": stamp, "rate": row["realizedRate"], "mark_price": mark_map[stamp]})
            times = [start] + [item["time_ms"] for item in events] + [end]
            if not events or max(b - a for a, b in zip(times, times[1:])) > DAY:
                raise ValueError("funding coverage has an unexplained gap >24h")
            spec = ContractSpec(**{key: D(value) if key != "inst_id" else value for key, value in contract.items()})
            datasets = []
            for bar, step in TIMEFRAMES.items():
                data = self.history("candles", start, end - step, bar)
                if [int(row[0]) for row in data] != list(range(start, end, step)):
                    raise ValueError(f"{bar}: missing, duplicate or misaligned closed candle")
                path = self.output / f"{bar}.csv"
                with path.open("x", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(REQUIRED_COLUMNS)
                    for row in data:
                        if len(row) != 9 or row[-1] != "1":
                            raise ValueError("unconfirmed or malformed historical trade candle")
                        writer.writerow([row[0], *row[1:5], "1"])
                cfg = BacktestConfig(spec, step, D("10000"), D("0.0005"), D("2"),
                                     tuple(FundingEvent(item["time_ms"], D(item["rate"]), D(item["mark_price"])) for item in events))
                load_candles_csv(path, config=cfg)
                datasets.append({"bar": bar, "timeframe_ms": step, "file": path.name, "bars": len(data)})
                self.progress(f"validated {bar}: {len(data)} closed bars", flush=True)
            write_json(self.output / "funding.json", events)
            manifest = {"version": "dcm-public-snapshot-v1", "kind": "public-market",
                        "symbol": SYMBOL, "server_time_ms": server_ms,
                        "start_ms": start, "end_ms": end, "days": days,
                        "contract": contract, "datasets": datasets, "funding_file": "funding.json",
                        "funding_events": len(events), "requests": len(self.requests),
                        "funding_mark_model": "historical 1H mark-price candle OPEN at settlement timestamp; proxy, not exact settlement mark",
                        "volume_model": "original volumes retained in raw API pages; not used by this OHLC strategy",
                        "metadata_model": "current public specification; historical specification changes not independently verified",
                        "public_docs": "https://www.okx.com/docs-v5/en/",
                        "files": {str(path.relative_to(self.output)).replace("\\", "/"): digest(path)
                                  for path in sorted(self.output.rglob("*")) if path.is_file()}}
            write_json(self.output / "manifest.json", manifest)
            return manifest
        except Exception as error:
            write_json(self.output / "collection-failed.json", {"error": str(error), "requests": len(self.requests)})
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--days", type=int, default=85)
    args = parser.parse_args()
    result = Collector(args.output).collect(args.days)
    print(json.dumps({"output": str(args.output.resolve()), "days": result["days"],
                      "requests": result["requests"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
