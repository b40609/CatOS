"""Credential-free OKX option facts for the local Options/Gamma surface.

Only source-explicit fields are collected. Signed gamma exposure, dealer
positioning and YAOZI aggregation/ranking are deliberately not reconstructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from catos import ipc


OKX_OPTION_SUMMARY_SOURCE = "okx-opt-summary"
OKX_OPEN_INTEREST_SOURCE = "okx-open-interest"
OKX_PUBLIC_HOST = "www.okx.com"
OKX_OPTION_SUMMARY_PATH = "/api/v5/public/opt-summary"
OKX_OPEN_INTEREST_PATH = "/api/v5/public/open-interest"
DERIBIT_BOOK_SUMMARY_SOURCE = "deribit-book-summary"
DERIBIT_PUBLIC_HOST = "www.deribit.com"
DERIBIT_BOOK_SUMMARY_PATH = "/api/v2/public/get_book_summary_by_currency"
_MAX_SOURCE_BYTES = 4 * 1024 * 1024
_FAMILY_RE = re.compile(r"[A-Z0-9]{2,16}-(?:USD|USDC)\Z")
_DERIBIT_INSTRUMENT_RE = re.compile(
    r"(?P<base>[A-Z0-9]{2,16})-(?P<expiry>[0-9]{1,2}[A-Z]{3}[0-9]{2})-"
    r"(?P<strike>[0-9]+(?:\.[0-9]+)?)-(?P<option_type>[CP])\Z"
)


class PublicOptionError(RuntimeError):
    pass


@dataclass(frozen=True)
class OptionSummaryFact:
    inst_family: str
    inst_id: str
    observed_at_ms: int
    source_ms: int | None
    delta_bs: Decimal | None
    delta_pa: Decimal | None
    gamma_bs: Decimal | None
    gamma_pa: Decimal | None
    theta_bs: Decimal | None
    theta_pa: Decimal | None
    vega_bs: Decimal | None
    vega_pa: Decimal | None
    mark_vol: Decimal | None
    bid_vol: Decimal | None
    ask_vol: Decimal | None
    fwd_px: Decimal | None


@dataclass(frozen=True)
class OptionSummaryBatch:
    source: str
    inst_family: str
    observed_at_ms: int
    items: tuple[OptionSummaryFact, ...]
    issues: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OptionOpenInterestFact:
    inst_family: str
    inst_id: str
    observed_at_ms: int
    source_ms: int | None
    oi: Decimal | None
    oi_ccy: Decimal | None


@dataclass(frozen=True)
class OptionOpenInterestBatch:
    source: str
    inst_family: str
    observed_at_ms: int
    items: tuple[OptionOpenInterestFact, ...]
    issues: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DeribitOptionBookFact:
    inst_family: str
    inst_id: str
    observed_at_ms: int
    creation_ms: int | None
    expiry_code: str
    strike: Decimal
    option_type: str
    open_interest_base: Decimal
    mark_iv: Decimal | None
    mark_price: Decimal | None
    underlying_price: Decimal | None
    premium_currency: str


@dataclass(frozen=True)
class DeribitOptionBookBatch:
    source: str
    inst_family: str
    observed_at_ms: int
    items: tuple[DeribitOptionBookFact, ...]
    issues: tuple[tuple[str, str], ...] = ()


def option_family(value: str) -> str:
    if type(value) is not str:
        raise PublicOptionError("invalid_inst_family")
    value = value.strip().upper()
    if _FAMILY_RE.fullmatch(value) is None:
        raise PublicOptionError("invalid_inst_family")
    return value


def _observed(value: int) -> int:
    return ipc.integer(value, "observed_at_ms")


def _decimal(value, field: str) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if type(value) is int:
        return Decimal(value)
    if type(value) is str:
        try:
            return Decimal(value)
        except InvalidOperation:
            pass
    raise PublicOptionError(f"invalid_decimal:{field}")


def _source_ms(value) -> int | None:
    if value is None or value == "":
        return None
    if type(value) is int:
        return value
    if type(value) is Decimal and value == value.to_integral_value():
        return int(value)
    if type(value) is str and value.isdigit():
        return int(value)
    raise PublicOptionError("invalid_source_ms")


def _inst_id(value) -> str:
    if type(value) is not str or not value.strip():
        raise PublicOptionError("invalid_inst_id")
    return value.strip().upper()


def _decode_okx(payload: bytes, error_code: str):
    try:
        document = json.loads(payload.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicOptionError(error_code) from None
    if type(document) is not dict or str(document.get("code")) != "0" or type(document.get("data")) is not list:
        raise PublicOptionError(error_code)
    return document["data"]


def _decode_deribit(payload: bytes):
    try:
        document = json.loads(payload.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicOptionError("invalid_deribit_book_summary_payload") from None
    if (type(document) is not dict or document.get("jsonrpc") != "2.0"
            or type(document.get("result")) is not list or document.get("error") is not None):
        raise PublicOptionError("invalid_deribit_book_summary_payload")
    return document["result"]


def _deribit_family(value: str) -> tuple[str, str]:
    family = option_family(value)
    base, quote = family.rsplit("-", 1)
    if quote != "USD":
        raise PublicOptionError("unsupported_deribit_family")
    return family, base


def _nonnegative_decimal(value, field: str) -> Decimal:
    parsed = _decimal(value, field)
    if parsed is None or not parsed.is_finite() or parsed < 0:
        raise PublicOptionError(f"invalid_decimal:{field}")
    return parsed


def _row_family(row: dict, requested: str) -> str:
    reported = row.get("instFamily")
    if reported in (None, ""):
        reported = row.get("uly")
    if reported in (None, ""):
        return requested
    reported = option_family(reported)
    if reported != requested:
        raise PublicOptionError("scope_mismatch")
    return reported


def parse_option_summary(payload: bytes, inst_family: str, observed_at_ms: int) -> OptionSummaryBatch:
    inst_family = option_family(inst_family)
    observed_at_ms = _observed(observed_at_ms)
    rows = _decode_okx(payload, "invalid_option_summary_payload")
    items = []
    issues = []
    for index, row in enumerate(rows):
        if type(row) is not dict:
            issues.append(("invalid_option_summary_row", str(index)))
            continue
        try:
            family = _row_family(row, inst_family)
            items.append(OptionSummaryFact(
                inst_family=family,
                inst_id=_inst_id(row.get("instId")),
                observed_at_ms=observed_at_ms,
                source_ms=_source_ms(row.get("ts")),
                delta_bs=_decimal(row.get("deltaBS"), "deltaBS"),
                delta_pa=_decimal(row.get("deltaPA"), "deltaPA"),
                gamma_bs=_decimal(row.get("gammaBS"), "gammaBS"),
                gamma_pa=_decimal(row.get("gammaPA"), "gammaPA"),
                theta_bs=_decimal(row.get("thetaBS"), "thetaBS"),
                theta_pa=_decimal(row.get("thetaPA"), "thetaPA"),
                vega_bs=_decimal(row.get("vegaBS"), "vegaBS"),
                vega_pa=_decimal(row.get("vegaPA"), "vegaPA"),
                mark_vol=_decimal(row.get("markVol"), "markVol"),
                bid_vol=_decimal(row.get("bidVol"), "bidVol"),
                ask_vol=_decimal(row.get("askVol"), "askVol"),
                fwd_px=_decimal(row.get("fwdPx"), "fwdPx"),
            ))
        except PublicOptionError as error:
            issues.append((str(error), str(index)))
    items.sort(key=lambda item: item.inst_id)
    return OptionSummaryBatch(
        OKX_OPTION_SUMMARY_SOURCE, inst_family, observed_at_ms, tuple(items), tuple(issues))


def parse_option_open_interest(
        payload: bytes, inst_family: str, observed_at_ms: int) -> OptionOpenInterestBatch:
    inst_family = option_family(inst_family)
    observed_at_ms = _observed(observed_at_ms)
    rows = _decode_okx(payload, "invalid_option_open_interest_payload")
    items = []
    issues = []
    for index, row in enumerate(rows):
        if type(row) is not dict:
            issues.append(("invalid_option_open_interest_row", str(index)))
            continue
        try:
            family = _row_family(row, inst_family)
            items.append(OptionOpenInterestFact(
                inst_family=family,
                inst_id=_inst_id(row.get("instId")),
                observed_at_ms=observed_at_ms,
                source_ms=_source_ms(row.get("ts")),
                oi=_decimal(row.get("oi"), "oi"),
                oi_ccy=_decimal(row.get("oiCcy"), "oiCcy"),
            ))
        except PublicOptionError as error:
            issues.append((str(error), str(index)))
    items.sort(key=lambda item: item.inst_id)
    return OptionOpenInterestBatch(
        OKX_OPEN_INTEREST_SOURCE, inst_family, observed_at_ms, tuple(items), tuple(issues))


def parse_deribit_book_summary(
        payload: bytes, inst_family: str, observed_at_ms: int) -> DeribitOptionBookBatch:
    inst_family, requested_base = _deribit_family(inst_family)
    observed_at_ms = _observed(observed_at_ms)
    rows = _decode_deribit(payload)
    items = []
    issues = []
    for index, row in enumerate(rows):
        if type(row) is not dict:
            issues.append(("invalid_deribit_book_summary_row", str(index)))
            continue
        try:
            inst_id = _inst_id(row.get("instrument_name"))
            match = _DERIBIT_INSTRUMENT_RE.fullmatch(inst_id)
            if match is None or match.group("base") != requested_base:
                raise PublicOptionError("scope_mismatch")
            if row.get("base_currency") != requested_base or row.get("quote_currency") != requested_base:
                raise PublicOptionError("scope_mismatch")
            items.append(DeribitOptionBookFact(
                inst_family=inst_family,
                inst_id=inst_id,
                observed_at_ms=observed_at_ms,
                creation_ms=_source_ms(row.get("creation_timestamp")),
                expiry_code=match.group("expiry"),
                strike=_nonnegative_decimal(match.group("strike"), "strike"),
                option_type=match.group("option_type"),
                open_interest_base=_nonnegative_decimal(row.get("open_interest"), "open_interest"),
                mark_iv=_decimal(row.get("mark_iv"), "mark_iv"),
                mark_price=_decimal(row.get("mark_price"), "mark_price"),
                underlying_price=_decimal(row.get("underlying_price"), "underlying_price"),
                premium_currency=requested_base,
            ))
        except PublicOptionError as error:
            issues.append((str(error), str(index)))
    items.sort(key=lambda item: item.inst_id)
    return DeribitOptionBookBatch(
        DERIBIT_BOOK_SUMMARY_SOURCE, inst_family, observed_at_ms, tuple(items), tuple(issues))


def option_summary_url(inst_family: str) -> str:
    inst_family = option_family(inst_family)
    return f"https://{OKX_PUBLIC_HOST}{OKX_OPTION_SUMMARY_PATH}?{urlencode({'instFamily': inst_family})}"


def option_open_interest_url(inst_family: str) -> str:
    inst_family = option_family(inst_family)
    query = urlencode({"instType": "OPTION", "instFamily": inst_family})
    return f"https://{OKX_PUBLIC_HOST}{OKX_OPEN_INTEREST_PATH}?{query}"


def deribit_book_summary_url(inst_family: str) -> str:
    _, base = _deribit_family(inst_family)
    query = urlencode({"currency": base, "kind": "option"})
    return f"https://{DERIBIT_PUBLIC_HOST}{DERIBIT_BOOK_SUMMARY_PATH}?{query}"


def _http_get(url: str, timeout: float = 10.0) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != OKX_PUBLIC_HOST:
        raise PublicOptionError("source_not_allowed")
    if parsed.path not in (OKX_OPTION_SUMMARY_PATH, OKX_OPEN_INTEREST_PATH):
        raise PublicOptionError("source_not_allowed")
    request = Request(url, headers={"User-Agent": "catOS-public-options/1.0"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise PublicOptionError(f"source_http_{response.status}")
            payload = response.read(_MAX_SOURCE_BYTES + 1)
    except HTTPError as error:
        raise PublicOptionError(f"source_http_{error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise PublicOptionError("source_unavailable") from None
    if len(payload) > _MAX_SOURCE_BYTES:
        raise PublicOptionError("source_too_large")
    return payload


def _deribit_http_get(url: str, timeout: float = 10.0) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != DERIBIT_PUBLIC_HOST:
        raise PublicOptionError("source_not_allowed")
    if parsed.path != DERIBIT_BOOK_SUMMARY_PATH:
        raise PublicOptionError("source_not_allowed")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != {"currency", "kind"} or query.get("kind") != ["option"]:
        raise PublicOptionError("source_not_allowed")
    if len(query.get("currency", ())) != 1 or not query["currency"][0].isalnum():
        raise PublicOptionError("source_not_allowed")
    request = Request(url, headers={"User-Agent": "catOS-public-options/1.0"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise PublicOptionError(f"source_http_{response.status}")
            payload = response.read(_MAX_SOURCE_BYTES + 1)
    except HTTPError as error:
        raise PublicOptionError(f"source_http_{error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise PublicOptionError("source_unavailable") from None
    if len(payload) > _MAX_SOURCE_BYTES:
        raise PublicOptionError("source_too_large")
    return payload


def collect_public_options(store, inst_family: str, observed_at_ms: int, *, get_bytes=_http_get):
    """Collect summary and open-interest independently so one failure does not erase the other."""
    inst_family = option_family(inst_family)
    observed_at_ms = _observed(observed_at_ms)
    try:
        summary = parse_option_summary(
            get_bytes(option_summary_url(inst_family)), inst_family, observed_at_ms)
    except PublicOptionError as error:
        summary = OptionSummaryBatch(
            OKX_OPTION_SUMMARY_SOURCE, inst_family, observed_at_ms, (), ((str(error), "fetch"),))
    try:
        open_interest = parse_option_open_interest(
            get_bytes(option_open_interest_url(inst_family)), inst_family, observed_at_ms)
    except PublicOptionError as error:
        open_interest = OptionOpenInterestBatch(
            OKX_OPEN_INTEREST_SOURCE, inst_family, observed_at_ms, (), ((str(error), "fetch"),))
    store.record_option_summary_batch(summary)
    store.record_option_open_interest_batch(open_interest)
    return summary, open_interest


def collect_deribit_option_source(
        store, inst_family: str, observed_at_ms: int, *, get_bytes=_deribit_http_get):
    """Collect Deribit inverse-option OI/IV facts and persist source-run evidence only.

    Existing option snapshot tables are OKX-shaped and do not contain a source
    column, so Deribit facts are deliberately not mixed into those snapshots.
    """
    inst_family, _ = _deribit_family(inst_family)
    observed_at_ms = _observed(observed_at_ms)
    try:
        batch = parse_deribit_book_summary(
            get_bytes(deribit_book_summary_url(inst_family)), inst_family, observed_at_ms)
    except PublicOptionError as error:
        batch = DeribitOptionBookBatch(
            DERIBIT_BOOK_SUMMARY_SOURCE, inst_family, observed_at_ms, (),
            ((str(error), "fetch"),),
        )
    store.record_option_context_run(
        source=batch.source,
        inst_family=batch.inst_family,
        observed_at_ms=batch.observed_at_ms,
        item_count=len(batch.items),
        issues=batch.issues,
    )
    return batch
