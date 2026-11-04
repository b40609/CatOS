"""Fetch one OKX public research dataset: closed candles, realized funding and the instrument spec.

Public GET endpoints only: no API key, no account endpoint, no order. Every
request is paced at least MIN_INTERVAL_S after the previous one (OKX publishes
20 req/2 s for history candles and 10 req/2 s for funding history), retried with
backoff on HTTP 429/5xx, OKX code 50011 and network errors, and capped by
--max-requests. Pages are checked against the cursor semantics this tool relies
on (``after`` returns strictly older records, newest first); any surprise stops
the run instead of guessing. Files are written last, by
``catos.research_datasets.write_dataset``, which refuses gaps and incomplete funding.

Usage (repo root):
    .venv/Scripts/python.exe -B tools/fetch_okx_candles.py --inst-id BTC-USDT-SWAP --bar 15m --days 90
"""

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from catos import research_datasets as datasets  # noqa: E402

BASE_URL = "https://www.okx.com"
CANDLES_PATH, FUNDING_PATH, INSTRUMENTS_PATH = datasets.ENDPOINTS
MIN_INTERVAL_S = 0.25
PAGE_LIMIT = 100
MAX_RETRIES = 3
DAY_MS = 86_400_000
USER_AGENT = "catOS-research/1.0"


class FetchError(RuntimeError):
    pass


def urlopen_json(url):
    """(HTTP status, body bytes) for one public GET; HTTP errors are returned, not raised."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class Client:
    """Paced, budgeted public GET client. opener/clock/sleep are injectable for offline tests."""

    def __init__(self, *, max_requests, opener=urlopen_json, clock=time.monotonic, sleep=time.sleep,
                 base_url=BASE_URL):
        self.max_requests = max_requests
        self.opener = opener
        self.clock = clock
        self.sleep = sleep
        self.base_url = base_url
        self.requests = 0
        self._last = None

    def get(self, path, params):
        if path not in datasets.ENDPOINTS:
            raise FetchError(f"endpoint_not_allowed: {path}")
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        for attempt in range(MAX_RETRIES + 1):
            if self.requests >= self.max_requests:
                raise FetchError(f"request_budget_exhausted: {self.max_requests}")
            if self._last is not None:
                wait = MIN_INTERVAL_S - (self.clock() - self._last)
                if wait > 0:
                    self.sleep(wait)
            self._last = self.clock()
            self.requests += 1
            try:
                status, body = self.opener(url)
            except (urllib.error.URLError, OSError) as error:
                failure = f"network: {error}"
            else:
                if status == 200:
                    payload = json.loads(body)
                    if payload.get("code") == "0":
                        return payload.get("data")
                    if payload.get("code") != "50011":
                        raise FetchError(f"okx_error {payload.get('code')}: {payload.get('msg')}")
                    failure = "okx_rate_limited"
                elif status == 429 or status >= 500:
                    failure = f"http_{status}"
                else:
                    raise FetchError(f"http_{status}")
            if attempt == MAX_RETRIES:
                raise FetchError(f"retries_exhausted: {failure}")
            self.sleep(2 ** attempt)
        raise AssertionError("unreachable")


def _price(value, name):
    try:
        number = Decimal(value) if type(value) is str else None
    except InvalidOperation:
        number = None
    if number is None or not number.is_finite() or number <= 0:
        raise FetchError(f"invalid_{name}: {value!r}")
    return value


def _rate(value, name):
    try:
        number = Decimal(value) if type(value) is str else None
    except InvalidOperation:
        number = None
    if number is None or not number.is_finite() or not -1 < number < 1:
        raise FetchError(f"invalid_{name}: {value!r}")
    return value


def _check_page(times, cursor):
    """Newest first, unique and strictly older than the cursor, at most PAGE_LIMIT rows."""
    if (len(times) > PAGE_LIMIT or any(ms >= cursor for ms in times)
            or times != sorted(set(times), reverse=True)):
        raise FetchError("pagination_unexpected")


def fetch_instrument(client, inst_id):
    data = client.get(INSTRUMENTS_PATH, {"instType": "SWAP", "instId": inst_id})
    if type(data) is not list or len(data) != 1 or type(data[0]) is not dict:
        raise FetchError("instrument_not_found")
    return data[0]


def fetch_candles(client, inst_id, bar, start_ms, end_ms):
    """Closed bars with open time in [start, end), ascending, as (ms, open, high, low, close)."""
    rows = {}
    cursor = end_ms
    while cursor > start_ms:
        page = client.get(CANDLES_PATH, {"instId": inst_id, "bar": bar, "after": str(cursor),
                                         "limit": str(PAGE_LIMIT)})
        if not page:
            break
        if any(type(item) is not list or len(item) < 9 or not str(item[0]).isdigit() for item in page):
            raise FetchError("candle_row_shape_unexpected")
        times = [int(item[0]) for item in page]
        _check_page(times, cursor)
        for ms, item in zip(times, page):
            if ms < start_ms:
                continue
            if item[8] != "1":
                raise FetchError(f"unclosed_candle_in_range: {ms}")
            o, h, low, c = (_price(item[i], name) for i, name in ((1, "open"), (2, "high"), (3, "low"), (4, "close")))
            if not Decimal(low) <= min(Decimal(o), Decimal(c)) <= max(Decimal(o), Decimal(c)) <= Decimal(h):
                raise FetchError(f"invalid_ohlc_bounds: {ms}")
            rows[ms] = (ms, o, h, low, c)
        cursor = times[-1]
    return [rows[ms] for ms in sorted(rows)]


def fetch_funding(client, inst_id, start_ms, end_ms):
    """Settled funding in [start, end), ascending, as (ms, realized_rate, funding_rate)."""
    rows = {}
    cursor = end_ms
    while cursor > start_ms:
        page = client.get(FUNDING_PATH, {"instId": inst_id, "after": str(cursor), "limit": str(PAGE_LIMIT)})
        if not page:
            break
        if any(type(item) is not dict or item.get("instId") != inst_id
               or not str(item.get("fundingTime", "")).isdigit() for item in page):
            raise FetchError("funding_row_shape_unexpected")
        times = [int(item["fundingTime"]) for item in page]
        _check_page(times, cursor)
        for ms, item in zip(times, page):
            if ms < start_ms:
                continue
            rows[ms] = (ms, _rate(item.get(datasets.RATE_FIELD), "realized_rate"),
                        _rate(item.get("fundingRate"), "funding_rate"))
        cursor = times[-1]
    return [rows[ms] for ms in sorted(rows)]


def main(argv=None, *, client=None, now_ms=None, root=None):
    parser = argparse.ArgumentParser(description="Fetch one OKX public research dataset (no API key).")
    parser.add_argument("--inst-id", default="BTC-USDT-SWAP")
    parser.add_argument("--bar", default="15m", choices=sorted(datasets.BAR_MS))
    parser.add_argument("--days", type=int, required=True, help="whole days ending at the last closed bar")
    parser.add_argument("--end-ms", type=int, help="exclusive end (bar-aligned) to re-fetch a known range")
    parser.add_argument("--max-requests", type=int, default=150)
    args = parser.parse_args(argv)
    if not datasets.INST_ID.fullmatch(args.inst_id) or not 1 <= args.days <= 365:
        parser.error("inst-id must be <BASE>-USDT-SWAP and days in [1, 365]")
    timeframe = datasets.BAR_MS[args.bar]
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    end_ms = args.end_ms if args.end_ms is not None else now_ms // timeframe * timeframe
    if end_ms % timeframe or end_ms > now_ms:
        parser.error("end-ms must be bar-aligned and not in the future")
    start_ms = end_ms - args.days * DAY_MS
    client = client or Client(max_requests=args.max_requests)
    try:
        instrument = fetch_instrument(client, args.inst_id)
        datasets.contract_from_instrument(instrument, args.inst_id)  # fail before paging candles
        candles = fetch_candles(client, args.inst_id, args.bar, start_ms, end_ms)
        funding = fetch_funding(client, args.inst_id, start_ms, end_ms)
        target = datasets.write_dataset(
            root, inst_id=args.inst_id, bar=args.bar, start_ms=start_ms, end_ms=end_ms,
            candles=candles, funding=funding, instrument=instrument,
            fetched_at_ms=now_ms, requests=client.requests,
        )
        dataset = datasets.load_manifest(target / datasets.MANIFEST, root)
    except (FetchError, ValueError, FileExistsError) as error:
        print(f"stopped after {client.requests} requests: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"dataset_id": dataset.dataset_id, "path": datasets.rel_path(target),
                      "bars": dataset.bars, "funding_events": len(funding),
                      "requests": client.requests, "files": dict(dataset.files)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
