from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import time

from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


JsonRequester = Callable[[str, dict[str, str] | None, float], Any]

BINANCE_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINPAPRIKA_TICKERS_URL = "https://api.coinpaprika.com/v1/tickers"
DEFAULT_MARKET_CAP_THRESHOLD_USD = 30_000_000.0


@dataclass(frozen=True, slots=True)
class ExchangeListing:
    venue: str
    inst_type: str
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AssetMarketCap:
    source: str
    asset_id: str
    symbol: str
    name: str | None
    price_usd: float | None
    market_cap_usd: float | None
    circulating_supply: float | None
    total_supply: float | None
    rank: int | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LowMarketCapMatch:
    listing: ExchangeListing
    market_cap: AssetMarketCap
    match_count: int
    ambiguous_symbol: bool


@dataclass(frozen=True, slots=True)
class SmallCapUniverseSyncResult:
    listings: list[ExchangeListing]
    market_caps: list[AssetMarketCap]
    matches: list[LowMarketCapMatch]
    wrote_to_database: bool


def request_json(url: str, headers: dict[str, str] | None = None, timeout: float = 20.0) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "quant-strategy-lab/0.1",
            **(headers or {}),
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while requesting {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"failed to request {url}: {exc.reason}") from exc
    return json.loads(payload)


def parse_binance_spot_listings(
    payload: dict[str, Any],
    *,
    quote_assets: tuple[str, ...] = ("USDT",),
    include_inactive: bool = False,
) -> list[ExchangeListing]:
    allowed_quotes = {quote.upper() for quote in quote_assets}
    listings: list[ExchangeListing] = []
    for item in payload.get("symbols", []):
        quote_asset = str(item.get("quoteAsset", "")).upper()
        status = str(item.get("status", "")).lower()
        is_spot_allowed = bool(item.get("isSpotTradingAllowed", True))
        if quote_asset not in allowed_quotes:
            continue
        if not include_inactive and (status != "trading" or not is_spot_allowed):
            continue
        listings.append(
            ExchangeListing(
                venue="binance",
                inst_type="SPOT",
                symbol=str(item["symbol"]).upper(),
                base_asset=str(item["baseAsset"]).upper(),
                quote_asset=quote_asset,
                status="active" if status == "trading" else status,
                raw=item,
            )
        )
    return sorted(listings, key=lambda item: item.symbol)


def fetch_binance_spot_listings(
    *,
    quote_assets: tuple[str, ...] = ("USDT",),
    include_inactive: bool = False,
    requester: JsonRequester = request_json,
    timeout: float = 20.0,
) -> list[ExchangeListing]:
    payload = requester(BINANCE_EXCHANGE_INFO_URL, None, timeout)
    return parse_binance_spot_listings(
        payload,
        quote_assets=quote_assets,
        include_inactive=include_inactive,
    )


def parse_coingecko_market_caps(payload: list[dict[str, Any]]) -> list[AssetMarketCap]:
    market_caps: list[AssetMarketCap] = []
    for item in payload:
        asset_id = item.get("id")
        symbol_value = item.get("symbol")
        if not asset_id or not symbol_value:
            continue
        market_caps.append(
            AssetMarketCap(
                source="coingecko",
                asset_id=str(asset_id),
                symbol=str(symbol_value).upper(),
                name=item.get("name"),
                price_usd=_optional_float(item.get("current_price")),
                market_cap_usd=_optional_float(item.get("market_cap")),
                circulating_supply=_optional_float(item.get("circulating_supply")),
                total_supply=_optional_float(item.get("total_supply")),
                rank=_optional_int(item.get("market_cap_rank")),
                raw=item,
            )
        )
    return market_caps


def fetch_coingecko_market_caps(
    *,
    max_pages: int = 10,
    per_page: int = 250,
    page_delay_seconds: float = 2.0,
    requester: JsonRequester = request_json,
    api_key: str | None = None,
    timeout: float = 20.0,
) -> list[AssetMarketCap]:
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if not 1 <= per_page <= 250:
        raise ValueError("per_page must be between 1 and 250")

    headers = {"x-cg-demo-api-key": api_key} if api_key else None
    market_caps: list[AssetMarketCap] = []
    for page in range(1, max_pages + 1):
        query = urlencode(
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "locale": "en",
            }
        )
        payload = requester(f"{COINGECKO_MARKETS_URL}?{query}", headers, timeout)
        if not payload:
            break
        market_caps.extend(parse_coingecko_market_caps(payload))
        if page < max_pages and page_delay_seconds > 0:
            time.sleep(page_delay_seconds)
    return market_caps


def parse_coinpaprika_market_caps(payload: list[dict[str, Any]]) -> list[AssetMarketCap]:
    market_caps: list[AssetMarketCap] = []
    for item in payload:
        asset_id = item.get("id")
        symbol_value = item.get("symbol")
        if not asset_id or not symbol_value:
            continue
        usd_quote = (item.get("quotes") or {}).get("USD") or {}
        market_caps.append(
            AssetMarketCap(
                source="coinpaprika",
                asset_id=str(asset_id),
                symbol=str(symbol_value).upper(),
                name=item.get("name"),
                price_usd=_optional_float(usd_quote.get("price")),
                market_cap_usd=_optional_float(usd_quote.get("market_cap")),
                circulating_supply=_optional_float(item.get("circulating_supply")),
                total_supply=_optional_float(item.get("total_supply")),
                rank=_optional_int(item.get("rank")),
                raw=item,
            )
        )
    return market_caps


def fetch_coinpaprika_market_caps(
    *,
    requester: JsonRequester = request_json,
    timeout: float = 30.0,
) -> list[AssetMarketCap]:
    payload = requester(COINPAPRIKA_TICKERS_URL, None, timeout)
    return parse_coinpaprika_market_caps(payload)


def filter_low_market_cap_listings(
    listings: list[ExchangeListing],
    market_caps: list[AssetMarketCap],
    *,
    threshold_usd: float = DEFAULT_MARKET_CAP_THRESHOLD_USD,
) -> list[LowMarketCapMatch]:
    if threshold_usd <= 0:
        raise ValueError("threshold_usd must be positive")

    caps_by_symbol: dict[str, list[AssetMarketCap]] = {}
    for market_cap in market_caps:
        caps_by_symbol.setdefault(market_cap.symbol.upper(), []).append(market_cap)

    matches: list[LowMarketCapMatch] = []
    for listing in listings:
        candidates = caps_by_symbol.get(listing.base_asset.upper(), [])
        candidates = [item for item in candidates if item.market_cap_usd is not None]
        if not candidates:
            continue

        # Tickers can collide across assets. Choosing the highest market-cap
        # candidate is conservative: it avoids classifying a large asset as
        # small-cap because an unrelated low-cap token shares the same ticker.
        chosen = max(candidates, key=lambda item: item.market_cap_usd or 0.0)
        if chosen.market_cap_usd is not None and chosen.market_cap_usd < threshold_usd:
            matches.append(
                LowMarketCapMatch(
                    listing=listing,
                    market_cap=chosen,
                    match_count=len(candidates),
                    ambiguous_symbol=len(candidates) > 1,
                )
            )
    return sorted(matches, key=lambda item: item.market_cap.market_cap_usd or 0.0)


def sync_small_cap_universe(
    *,
    database_url: str | None,
    schema: str = "qsl",
    threshold_usd: float = DEFAULT_MARKET_CAP_THRESHOLD_USD,
    quote_assets: tuple[str, ...] = ("USDT",),
    include_inactive: bool = False,
    coingecko_max_pages: int = 10,
    coingecko_per_page: int = 250,
    coingecko_page_delay_seconds: float = 2.0,
    coingecko_api_key: str | None = None,
    market_cap_source: str = "coinpaprika",
    dry_run: bool = False,
    requester: JsonRequester = request_json,
) -> SmallCapUniverseSyncResult:
    listings = fetch_binance_spot_listings(
        quote_assets=quote_assets,
        include_inactive=include_inactive,
        requester=requester,
    )
    if market_cap_source == "coinpaprika":
        market_caps = fetch_coinpaprika_market_caps(requester=requester)
    elif market_cap_source == "coingecko":
        market_caps = fetch_coingecko_market_caps(
            max_pages=coingecko_max_pages,
            per_page=coingecko_per_page,
            page_delay_seconds=coingecko_page_delay_seconds,
            requester=requester,
            api_key=coingecko_api_key,
        )
    else:
        raise ValueError("market_cap_source must be one of: coinpaprika, coingecko")
    matches = filter_low_market_cap_listings(
        listings,
        market_caps,
        threshold_usd=threshold_usd,
    )

    wrote_to_database = False
    if not dry_run:
        if not database_url:
            raise ValueError("database_url is required unless dry_run is enabled")
        with Connection.connect(database_url) as connection:
            ensure_market_cap_schema(connection, schema=schema)
            upsert_exchange_listings(connection, listings, schema=schema)
            upsert_asset_market_caps(connection, market_caps, schema=schema)
            replace_low_market_cap_universe(
                connection,
                matches,
                schema=schema,
                source=market_cap_source,
                threshold_usd=threshold_usd,
            )
            wrote_to_database = True

    return SmallCapUniverseSyncResult(
        listings=listings,
        market_caps=market_caps,
        matches=matches,
        wrote_to_database=wrote_to_database,
    )


def ensure_market_cap_schema(connection: Connection, *, schema: str = "qsl") -> None:
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {}.exchange_listings (
                  venue text NOT NULL,
                  inst_type text NOT NULL,
                  symbol text NOT NULL,
                  base_asset text NOT NULL,
                  quote_asset text NOT NULL,
                  status text,
                  raw jsonb,
                  updated_at timestamptz NOT NULL DEFAULT now(),
                  PRIMARY KEY (venue, inst_type, symbol)
                )
                """
            ).format(sql.Identifier(schema))
        )
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {}.asset_market_caps (
                  source text NOT NULL,
                  asset_id text NOT NULL,
                  symbol text NOT NULL,
                  name text,
                  price_usd double precision,
                  market_cap_usd double precision,
                  circulating_supply double precision,
                  total_supply double precision,
                  rank integer,
                  raw jsonb,
                  updated_at timestamptz NOT NULL DEFAULT now(),
                  PRIMARY KEY (source, asset_id)
                )
                """
            ).format(sql.Identifier(schema))
        )
        cursor.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS asset_market_caps_symbol_idx
                ON {}.asset_market_caps (symbol)
                """
            ).format(sql.Identifier(schema))
        )
        cursor.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS asset_market_caps_market_cap_idx
                ON {}.asset_market_caps (market_cap_usd)
                """
            ).format(sql.Identifier(schema))
        )
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {}.low_market_cap_universe (
                  venue text NOT NULL,
                  inst_type text NOT NULL,
                  symbol text NOT NULL,
                  base_asset text NOT NULL,
                  quote_asset text NOT NULL,
                  source text NOT NULL,
                  asset_id text NOT NULL,
                  asset_name text,
                  price_usd double precision,
                  market_cap_usd double precision,
                  rank integer,
                  threshold_usd double precision NOT NULL,
                  match_count integer NOT NULL,
                  ambiguous_symbol boolean NOT NULL,
                  updated_at timestamptz NOT NULL DEFAULT now(),
                  PRIMARY KEY (venue, inst_type, symbol, source, threshold_usd)
                )
                """
            ).format(sql.Identifier(schema))
        )
        cursor.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS low_market_cap_universe_market_cap_idx
                ON {}.low_market_cap_universe (market_cap_usd)
                """
            ).format(sql.Identifier(schema))
        )


def upsert_exchange_listings(
    connection: Connection,
    listings: list[ExchangeListing],
    *,
    schema: str = "qsl",
) -> None:
    if not listings:
        return
    query = sql.SQL(
        """
        INSERT INTO {}.exchange_listings (
          venue, inst_type, symbol, base_asset, quote_asset, status, raw, updated_at
        )
        VALUES (
          %(venue)s, %(inst_type)s, %(symbol)s, %(base_asset)s, %(quote_asset)s,
          %(status)s, %(raw)s, now()
        )
        ON CONFLICT (venue, inst_type, symbol)
        DO UPDATE SET
          base_asset = EXCLUDED.base_asset,
          quote_asset = EXCLUDED.quote_asset,
          status = EXCLUDED.status,
          raw = EXCLUDED.raw,
          updated_at = now()
        """
    ).format(sql.Identifier(schema))
    payload = [
        {
            **asdict(listing),
            "raw": Jsonb(listing.raw),
        }
        for listing in listings
    ]
    with connection.cursor() as cursor:
        cursor.executemany(query, payload)


def upsert_asset_market_caps(
    connection: Connection,
    market_caps: list[AssetMarketCap],
    *,
    schema: str = "qsl",
) -> None:
    if not market_caps:
        return
    query = sql.SQL(
        """
        INSERT INTO {}.asset_market_caps (
          source, asset_id, symbol, name, price_usd, market_cap_usd,
          circulating_supply, total_supply, rank, raw, updated_at
        )
        VALUES (
          %(source)s, %(asset_id)s, %(symbol)s, %(name)s, %(price_usd)s,
          %(market_cap_usd)s, %(circulating_supply)s, %(total_supply)s,
          %(rank)s, %(raw)s, now()
        )
        ON CONFLICT (source, asset_id)
        DO UPDATE SET
          symbol = EXCLUDED.symbol,
          name = EXCLUDED.name,
          price_usd = EXCLUDED.price_usd,
          market_cap_usd = EXCLUDED.market_cap_usd,
          circulating_supply = EXCLUDED.circulating_supply,
          total_supply = EXCLUDED.total_supply,
          rank = EXCLUDED.rank,
          raw = EXCLUDED.raw,
          updated_at = now()
        """
    ).format(sql.Identifier(schema))
    payload = [
        {
            **asdict(market_cap),
            "raw": Jsonb(market_cap.raw),
        }
        for market_cap in market_caps
    ]
    with connection.cursor() as cursor:
        cursor.executemany(query, payload)


def replace_low_market_cap_universe(
    connection: Connection,
    matches: list[LowMarketCapMatch],
    *,
    schema: str = "qsl",
    source: str,
    threshold_usd: float,
) -> None:
    delete_query = sql.SQL(
        """
        DELETE FROM {}.low_market_cap_universe
        WHERE source = %(source)s AND threshold_usd = %(threshold_usd)s
        """
    ).format(sql.Identifier(schema))
    insert_query = sql.SQL(
        """
        INSERT INTO {}.low_market_cap_universe (
          venue, inst_type, symbol, base_asset, quote_asset, source, asset_id,
          asset_name, price_usd, market_cap_usd, rank, threshold_usd,
          match_count, ambiguous_symbol, updated_at
        )
        VALUES (
          %(venue)s, %(inst_type)s, %(symbol)s, %(base_asset)s, %(quote_asset)s,
          %(source)s, %(asset_id)s, %(asset_name)s, %(price_usd)s,
          %(market_cap_usd)s, %(rank)s, %(threshold_usd)s, %(match_count)s,
          %(ambiguous_symbol)s, now()
        )
        """
    ).format(sql.Identifier(schema))
    payload = [
        {
            "venue": item.listing.venue,
            "inst_type": item.listing.inst_type,
            "symbol": item.listing.symbol,
            "base_asset": item.listing.base_asset,
            "quote_asset": item.listing.quote_asset,
            "source": source,
            "asset_id": item.market_cap.asset_id,
            "asset_name": item.market_cap.name,
            "price_usd": item.market_cap.price_usd,
            "market_cap_usd": item.market_cap.market_cap_usd,
            "rank": item.market_cap.rank,
            "threshold_usd": threshold_usd,
            "match_count": item.match_count,
            "ambiguous_symbol": item.ambiguous_symbol,
        }
        for item in matches
    ]
    with connection.cursor() as cursor:
        cursor.execute(delete_query, {"source": source, "threshold_usd": threshold_usd})
        if payload:
            cursor.executemany(insert_query, payload)


def load_low_market_cap_rows(
    connection: Connection,
    *,
    schema: str = "qsl",
    threshold_usd: float = DEFAULT_MARKET_CAP_THRESHOLD_USD,
    quote_asset: str = "USDT",
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = sql.SQL(
        """
        SELECT
          venue,
          symbol AS exchange_symbol,
          base_asset,
          quote_asset,
          asset_id,
          asset_name AS name,
          price_usd,
          market_cap_usd,
          rank,
          updated_at AS market_cap_updated_at
        FROM {}.low_market_cap_universe
        WHERE quote_asset = %(quote_asset)s
          AND threshold_usd = %(threshold_usd)s
        ORDER BY market_cap_usd ASC
        LIMIT %(limit)s
        """
    ).format(sql.Identifier(schema))
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            query,
            {
                "quote_asset": quote_asset.upper(),
                "threshold_usd": threshold_usd,
                "limit": limit,
            },
        )
        return list(cursor.fetchall())


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
