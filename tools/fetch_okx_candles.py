"""Fetch historical closed candles from OKX Public REST API and format for CatOS.

Uses only Python standard library (urllib.request, json, csv, argparse).
Default output follows CatOS Task A CSV specification (open_time_ms,open,high,low,close,closed).
"""

import argparse
import csv
import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error

OKX_HISTORY_CANDLES_URL = "https://www.okx.com/api/v5/market/history-candles"


def fetch_okx_closed_candles(
    inst_id: str = "BTC-USDT-SWAP",
    bar: str = "1H",
    total_count: int = 1000,
    request_limit: int = 100,
) -> list[list[str]]:
    """Fetch closed candles from OKX public history-candles endpoint with pagination.

    Parameters
    ----------
    inst_id : str
        Instrument ID (e.g. 'BTC-USDT-SWAP').
    bar : str
        Bar timeframe (e.g. '1H', '15m').
    total_count : int
        Desired number of closed candles.
    request_limit : int
        Page limit per API request (max 100 for OKX).

    Returns
    -------
    list[list[str]]
        List of closed candles sorted in chronological order (oldest first).
    """
    closed_candles: list[list[str]] = []
    after: str | None = None
    headers = {"User-Agent": "catOS-research/1.0"}

    print(f"開始自 OKX 下載 {inst_id} ({bar})，目標數量: {total_count} 根已收盤 K 線...")

    while len(closed_candles) < total_count:
        params = [
            f"instId={urllib.parse.quote(inst_id)}",
            f"bar={urllib.parse.quote(bar)}",
            f"limit={min(request_limit, 100)}",
        ]
        if after:
            params.append(f"after={after}")

        url = f"{OKX_HISTORY_CANDLES_URL}?{'&'.join(params)}"
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"OKX API HTTP 請求失敗 ({e.code}): {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OKX API 連線失敗: {e.reason}") from e

        code = payload.get("code")
        if code != "0":
            msg = payload.get("msg", "未知錯誤")
            raise RuntimeError(f"OKX API 回傳錯誤碼 {code}: {msg}")

        data = payload.get("data", [])
        if not data:
            print("API 無更多歷史資料可供抓取。")
            break

        # Filter only closed candles (confirm == "1")
        # OKX candle schema: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        for item in data:
            confirm = item[8] if len(item) > 8 else "1"
            if confirm == "1":
                closed_candles.append(item)
                if len(closed_candles) >= total_count:
                    break

        # Next page uses the oldest timestamp in the current batch
        oldest_ts_in_batch = data[-1][0]
        after = oldest_ts_in_batch
        print(f"已獲取 {len(closed_candles)}/{total_count} 根已收盤 K 線 (當前批次時間戳: {oldest_ts_in_batch})...")

        time.sleep(0.05)  # Respect OKX 20 req/2s rate limit

    # Sort in ascending chronological order (oldest first)
    closed_candles.sort(key=lambda x: int(x[0]))
    return closed_candles


def save_candles_to_csv(
    candles: list[list[str]],
    output_path: Path | str,
    output_format: str = "catos",
) -> Path:
    """Save candles into CSV.

    Parameters
    ----------
    candles : list[list[str]]
        Candles sorted chronologically.
    output_path : Path or str
        Destination CSV file path.
    output_format : str
        'catos' for CatOS Task A format (open_time_ms,open,high,low,close,closed)
        'ohlcv' for standard OHLCV format (timestamp,open,high,low,close,volume)

    Returns
    -------
    Path
        Resolved output path.
    """
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if output_format == "catos":
            # CatOS Task A specification: open_time_ms,open,high,low,close,closed
            writer.writerow(["open_time_ms", "open", "high", "low", "close", "closed"])
            for c in candles:
                writer.writerow([c[0], c[1], c[2], c[3], c[4], "1"])
        elif output_format == "ohlcv":
            # Standard OHLCV: timestamp,open,high,low,close,volume
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for c in candles:
                writer.writerow([c[0], c[1], c[2], c[3], c[4], c[5]])
        else:
            raise ValueError(f"不支援的輸出格式: {output_format!r}")

    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch closed candles from OKX and adapt format for CatOS."
    )
    parser.add_argument(
        "--inst-id",
        default="BTC-USDT-SWAP",
        help="OKX 合約代碼 (預設: BTC-USDT-SWAP)",
    )
    parser.add_argument(
        "--bar",
        default="1H",
        help="K 線週期 (預設: 1H)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="抓取 K 線根數 (預設: 1000)",
    )
    parser.add_argument(
        "--output",
        default="data/BTC-USDT-SWAP-1H.csv",
        help="輸出 CSV 路徑 (預設: data/BTC-USDT-SWAP-1H.csv)",
    )
    parser.add_argument(
        "--format",
        choices=["catos", "ohlcv"],
        default="catos",
        help="輸出格式：'catos' (CatOS Task A 格式) 或 'ohlcv' (timestamp,open,high,low,close,volume) (預設: catos)",
    )

    args = parser.parse_args(argv)

    try:
        candles = fetch_okx_closed_candles(
            inst_id=args.inst_id,
            bar=args.bar,
            total_count=args.count,
        )
        saved_path = save_candles_to_csv(
            candles=candles,
            output_path=args.output,
            output_format=args.format,
        )
        print(f"\n成功儲存 {len(candles)} 根 K 線至: {saved_path}")

        # Display first 3 lines of the CSV file
        print("\n=== 前 3 行資料檢視 ===")
        with open(saved_path, mode="r", encoding="utf-8") as f:
            for _ in range(3):
                line = f.readline()
                if not line:
                    break
                print(line.rstrip("\r\n"))

        return 0
    except Exception as err:
        sys.stderr.write(f"\n錯誤: {err}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
