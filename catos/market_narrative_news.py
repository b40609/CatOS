"""Public Narrative + News collectors with fixed, credential-free sources.

The module stores only source-explicit facts. It does not infer Yaozi ranking,
importance, narrative scores, symbol tags, or private classification rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import argparse
import calendar
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from catos import ipc


COINGECKO_CATEGORIES_URL = "https://api.coingecko.com/api/v3/coins/categories"
COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
COINDESK_RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"
COINGECKO_SOURCE = "coingecko-categories"
COINGECKO_TRENDING_SOURCE = "coingecko-trending-categories"
COINDESK_SOURCE = "coindesk-rss"
_ALLOWED_HOSTS = frozenset(("api.coingecko.com", "www.coindesk.com"))
_MAX_SOURCE_BYTES = 4 * 1024 * 1024


class PublicContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class NarrativeSnapshot:
    source: str
    narrative_id: str
    name: str
    observed_at_ms: int
    market_cap: Decimal | None
    market_cap_change_24h: Decimal | None
    volume_24h: Decimal | None
    content: str | None
    top_assets: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeBatch:
    source: str
    observed_at_ms: int
    items: tuple[NarrativeSnapshot, ...]
    issues: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NewsEvent:
    news_id: str
    source: str
    observed_at_ms: int
    published_at_ms: int | None
    title: str
    url: str
    summary: str | None
    categories: tuple[str, ...]


@dataclass(frozen=True)
class NewsBatch:
    source: str
    observed_at_ms: int
    items: tuple[NewsEvent, ...]
    issues: tuple[tuple[str, str], ...] = ()


def _validate_observed_at(observed_at_ms: int) -> int:
    return ipc.integer(observed_at_ms, "observed_at_ms")


def _decimal(value, field: str) -> Decimal | None:
    if value is None:
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
    raise PublicContextError(f"invalid_decimal:{field}")


def _required_text(value, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise PublicContextError(f"invalid_text:{field}")
    return value.strip()


def _optional_text(value, field: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise PublicContextError(f"invalid_text:{field}")
    text = value.strip()
    return text or None


def _https_url(value: str, host: str, field: str) -> str:
    text = _required_text(value, field)
    parsed = urlparse(text)
    if parsed.scheme != "https" or parsed.hostname != host:
        raise PublicContextError(f"invalid_url:{field}")
    return text


def _http_get(url: str, timeout: float = 10.0) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise PublicContextError("source_not_allowed")
    request = Request(url, headers={"User-Agent": "catOS-public-context/1.0"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise PublicContextError(f"source_http_{response.status}")
            payload = response.read(_MAX_SOURCE_BYTES + 1)
    except HTTPError as error:
        raise PublicContextError(f"source_http_{error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise PublicContextError("source_unavailable") from None
    if len(payload) > _MAX_SOURCE_BYTES:
        raise PublicContextError("source_too_large")
    return payload


def parse_coingecko_categories(payload: bytes, observed_at_ms: int) -> NarrativeBatch:
    observed_at_ms = _validate_observed_at(observed_at_ms)
    try:
        rows = json.loads(payload.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicContextError("invalid_coingecko_payload") from None
    if type(rows) is not list:
        raise PublicContextError("invalid_coingecko_payload")
    items = []
    issues = []
    for index, row in enumerate(rows):
        if type(row) is not dict:
            issues.append(("invalid_category_row", str(index)))
            continue
        try:
            narrative_id = _required_text(row.get("id"), "category.id")
            name = _required_text(row.get("name"), "category.name")
            top_assets_raw = row.get("top_3_coins_id") or []
            if type(top_assets_raw) is not list or any(type(item) is not str for item in top_assets_raw):
                raise PublicContextError("invalid_top_assets")
            items.append(NarrativeSnapshot(
                source=COINGECKO_SOURCE,
                narrative_id=narrative_id,
                name=name,
                observed_at_ms=observed_at_ms,
                market_cap=_decimal(row.get("market_cap"), "market_cap"),
                market_cap_change_24h=_decimal(
                    row.get("market_cap_change_24h"), "market_cap_change_24h"),
                volume_24h=_decimal(row.get("volume_24h"), "volume_24h"),
                content=_optional_text(row.get("content"), "content"),
                top_assets=tuple(top_assets_raw),
            ))
        except PublicContextError as error:
            issues.append((str(error), str(index)))
    items.sort(key=lambda item: item.narrative_id)
    return NarrativeBatch(COINGECKO_SOURCE, observed_at_ms, tuple(items), tuple(issues))


def parse_coingecko_trending_categories(payload: bytes, observed_at_ms: int) -> NarrativeBatch:
    """Parse public trending-category membership without persisting source rank."""
    observed_at_ms = _validate_observed_at(observed_at_ms)
    try:
        body = json.loads(payload.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicContextError("invalid_coingecko_trending_payload") from None
    if type(body) is not dict or type(body.get("categories")) is not list:
        raise PublicContextError("invalid_coingecko_trending_payload")
    items = []
    issues = []
    for index, row in enumerate(body["categories"]):
        if type(row) is not dict:
            issues.append(("invalid_trending_category_row", str(index)))
            continue
        try:
            narrative_id = _required_text(row.get("slug"), "trending_category.slug")
            name = _required_text(row.get("name"), "trending_category.name")
            data = row.get("data")
            if type(data) is not dict:
                raise PublicContextError("invalid_trending_category_data")
            change = data.get("market_cap_change_percentage_24h")
            if type(change) is not dict:
                raise PublicContextError("invalid_trending_category_change")
            items.append(NarrativeSnapshot(
                source=COINGECKO_TRENDING_SOURCE,
                narrative_id=narrative_id,
                name=name,
                observed_at_ms=observed_at_ms,
                market_cap=_decimal(data.get("market_cap"), "trending.market_cap"),
                market_cap_change_24h=_decimal(
                    change.get("usd"), "trending.market_cap_change_24h.usd"),
                volume_24h=_decimal(data.get("total_volume"), "trending.total_volume"),
                content=None,
                top_assets=(),
            ))
        except PublicContextError as error:
            issues.append((str(error), str(index)))
    return NarrativeBatch(
        COINGECKO_TRENDING_SOURCE, observed_at_ms, tuple(items), tuple(issues))


def _rss_text(item: ET.Element, tag: str) -> str | None:
    node = item.find(tag)
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _published_ms(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return calendar.timegm(parsed.astimezone(timezone.utc).utctimetuple()) * 1000


def parse_coindesk_rss(payload: bytes, observed_at_ms: int, limit: int = 100) -> NewsBatch:
    observed_at_ms = _validate_observed_at(observed_at_ms)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise PublicContextError("invalid_limit")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        raise PublicContextError("invalid_coindesk_rss") from None
    items = []
    issues = []
    for index, row in enumerate(root.findall(".//item")[:limit]):
        try:
            title = _required_text(_rss_text(row, "title"), "news.title")
            link = _https_url(_rss_text(row, "link"), "www.coindesk.com", "news.url")
            published_raw = _rss_text(row, "pubDate")
            summary = _optional_text(_rss_text(row, "description"), "news.summary")
            categories = tuple(sorted({
                node.text.strip() for node in row.findall("category")
                if node.text is not None and node.text.strip()
            }))
            canonical = json.dumps(
                [COINDESK_SOURCE, link, title, published_raw, summary, list(categories)],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            news_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            items.append(NewsEvent(
                news_id=news_id,
                source=COINDESK_SOURCE,
                observed_at_ms=observed_at_ms,
                published_at_ms=_published_ms(published_raw),
                title=title,
                url=link,
                summary=summary,
                categories=categories,
            ))
        except PublicContextError as error:
            issues.append((str(error), str(index)))
    items.sort(key=lambda item: (
        -(item.published_at_ms if item.published_at_ms is not None else -1), item.news_id))
    return NewsBatch(COINDESK_SOURCE, observed_at_ms, tuple(items), tuple(issues))


def fetch_narratives(observed_at_ms: int, *, get_bytes=_http_get) -> NarrativeBatch:
    return parse_coingecko_categories(get_bytes(COINGECKO_CATEGORIES_URL), observed_at_ms)


def fetch_trending_categories(observed_at_ms: int, *, get_bytes=_http_get) -> NarrativeBatch:
    return parse_coingecko_trending_categories(
        get_bytes(COINGECKO_TRENDING_URL), observed_at_ms)


def fetch_news(observed_at_ms: int, *, get_bytes=_http_get, limit: int = 100) -> NewsBatch:
    return parse_coindesk_rss(get_bytes(COINDESK_RSS_URL), observed_at_ms, limit)


def collect_public_context(store, observed_at_ms: int, *, get_bytes=_http_get, news_limit: int = 100):
    """Fetch public context sources independently and persist explicit failure batches."""
    observed_at_ms = _validate_observed_at(observed_at_ms)
    if type(news_limit) is not int or not 1 <= news_limit <= 1000:
        raise PublicContextError("invalid_limit")
    try:
        narratives = fetch_narratives(observed_at_ms, get_bytes=get_bytes)
    except PublicContextError as error:
        narratives = NarrativeBatch(
            COINGECKO_SOURCE, observed_at_ms, (), ((str(error), "fetch"),))
    try:
        attention = fetch_trending_categories(observed_at_ms, get_bytes=get_bytes)
    except PublicContextError as error:
        attention = NarrativeBatch(
            COINGECKO_TRENDING_SOURCE, observed_at_ms, (), ((str(error), "fetch"),))
    try:
        news = fetch_news(observed_at_ms, get_bytes=get_bytes, limit=news_limit)
    except PublicContextError as error:
        news = NewsBatch(COINDESK_SOURCE, observed_at_ms, (), ((str(error), "fetch"),))
    store.record_narrative_batch(narratives)
    store.record_narrative_batch(attention)
    store.record_news_batch(news)
    return narratives, attention, news


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Collect public Narrative + News into market-intel SQLite")
    parser.add_argument("--db", required=True)
    parser.add_argument("--observed-at-ms", required=True, type=int)
    parser.add_argument("--news-limit", type=int, default=100)
    args = parser.parse_args(argv)
    from catos.market_intel import MarketIntelStore
    store = MarketIntelStore(args.db)
    try:
        narratives, attention, news = collect_public_context(
            store,
            args.observed_at_ms,
            news_limit=args.news_limit,
        )
    finally:
        store.close()
    print(json.dumps({
        "contract": "catos_public_context_collection_v1",
        "observed_at_ms": args.observed_at_ms,
        "narrative_count": len(narratives.items),
        "narrative_issues": [list(issue) for issue in narratives.issues],
        "attention_count": len(attention.items),
        "attention_issues": [list(issue) for issue in attention.issues],
        "news_count": len(news.items),
        "news_issues": [list(issue) for issue in news.issues],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
