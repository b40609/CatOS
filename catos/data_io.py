"""CSV closed-bar reader for catOS research.

Uses only the Python standard library.
Parses UTF-8 (with or without BOM) CSV files into Candle tuples.
All prices are parsed directly as Decimal from strings without float conversion.
Validates market data by reusing research._validate.
"""

import csv
from decimal import Decimal, InvalidOperation, localcontext
import os

from catos import research
from catos.research import BacktestConfig, Candle

REQUIRED_COLUMNS: tuple[str, ...] = (
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "closed",
)


def load_candles_csv(
    path: str | os.PathLike[str],
    *,
    config: BacktestConfig,
) -> tuple[Candle, ...]:
    """Load and validate closed bars from a CSV file.

    Parameters
    ----------
    path : str or PathLike
        Path to the CSV file.
    config : BacktestConfig
        Backtest configuration used to validate tick size, timeframe, and continuity.

    Returns
    -------
    tuple[Candle, ...]
        Validated tuple of Candle instances.
    """
    if not isinstance(config, BacktestConfig):
        raise TypeError("config must be BacktestConfig")

    with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, strict=True)

        def rows():
            while True:
                start_line = reader.line_num + 1
                try:
                    row = next(reader)
                except StopIteration:
                    return
                except csv.Error as e:
                    raise ValueError(f"row {start_line}: invalid CSV: {e}") from e
                yield start_line, row

        records = rows()
        try:
            _, header = next(records)
        except StopIteration:
            raise ValueError(f"CSV file is empty: {path}")

        if len(header) != len(set(header)):
            raise ValueError(f"CSV header contains duplicate columns: {header}")

        if tuple(header) != REQUIRED_COLUMNS:
            missing = [col for col in REQUIRED_COLUMNS if col not in header]
            extra = [col for col in header if col not in REQUIRED_COLUMNS]
            if missing:
                raise ValueError(f"CSV header is missing required columns: {missing}")
            if extra:
                raise ValueError(f"CSV header contains unexpected columns: {extra}")
            raise ValueError(
                f"CSV header columns are out of order: expected {list(REQUIRED_COLUMNS)}, got {header}"
            )

        bars: list[Candle] = []
        for row_index, row in records:
            if len(row) != len(REQUIRED_COLUMNS):
                raise ValueError(
                    f"row {row_index}: expected {len(REQUIRED_COLUMNS)} columns, got {len(row)}"
                )

            time_str, open_str, high_str, low_str, close_str, closed_str = row

            try:
                open_time_ms = int(time_str)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"row {row_index}, column 'open_time_ms': invalid integer {time_str!r}"
                ) from e

            prices: dict[str, Decimal] = {}
            for col_name, val_str in (
                ("open", open_str),
                ("high", high_str),
                ("low", low_str),
                ("close", close_str),
            ):
                try:
                    with localcontext() as context:
                        context.traps[InvalidOperation] = True
                        prices[col_name] = Decimal(val_str)
                except InvalidOperation as e:
                    raise ValueError(
                        f"row {row_index}, column '{col_name}': invalid decimal {val_str!r}"
                    ) from e

            if closed_str != "1":
                raise ValueError(
                    f"row {row_index}, column 'closed': expected '1', got {closed_str!r}"
                )

            bars.append(
                Candle(
                    open_time_ms=open_time_ms,
                    open=prices["open"],
                    high=prices["high"],
                    low=prices["low"],
                    close=prices["close"],
                    closed=True,
                )
            )

    bars_tuple = tuple(bars)
    research._call(research._validate, config, bars_tuple, 0)
    return bars_tuple
