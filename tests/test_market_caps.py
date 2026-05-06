from strategy_lab.data.ingest.market_caps import (
    BINANCE_EXCHANGE_INFO_URL,
    COINGECKO_MARKETS_URL,
    COINPAPRIKA_TICKERS_URL,
    fetch_binance_spot_listings,
    fetch_coinpaprika_market_caps,
    fetch_coingecko_market_caps,
    filter_low_market_cap_listings,
    parse_binance_spot_listings,
)


def test_parse_binance_spot_listings_filters_active_usdt_symbols() -> None:
    payload = {
        "symbols": [
            {
                "symbol": "ABCUSDT",
                "baseAsset": "ABC",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "isSpotTradingAllowed": True,
            },
            {
                "symbol": "DEFUSDT",
                "baseAsset": "DEF",
                "quoteAsset": "USDT",
                "status": "BREAK",
                "isSpotTradingAllowed": True,
            },
            {
                "symbol": "ABCBTC",
                "baseAsset": "ABC",
                "quoteAsset": "BTC",
                "status": "TRADING",
                "isSpotTradingAllowed": True,
            },
        ]
    }

    listings = parse_binance_spot_listings(payload)

    assert [item.symbol for item in listings] == ["ABCUSDT"]
    assert listings[0].base_asset == "ABC"
    assert listings[0].status == "active"


def test_low_market_cap_filter_uses_highest_market_cap_for_duplicate_ticker() -> None:
    listings = parse_binance_spot_listings(
        {
            "symbols": [
                {
                    "symbol": "ABCUSDT",
                    "baseAsset": "ABC",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "isSpotTradingAllowed": True,
                },
                {
                    "symbol": "XYZUSDT",
                    "baseAsset": "XYZ",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "isSpotTradingAllowed": True,
                },
            ]
        }
    )
    market_caps = fetch_coingecko_market_caps(
        requester=lambda url, headers, timeout: [
            {
                "id": "abc-small",
                "symbol": "abc",
                "name": "ABC Small",
                "current_price": 0.1,
                "market_cap": 5_000_000,
                "circulating_supply": 50_000_000,
                "total_supply": 100_000_000,
                "market_cap_rank": 3000,
            },
            {
                "id": "abc-large",
                "symbol": "abc",
                "name": "ABC Large",
                "current_price": 10.0,
                "market_cap": 100_000_000,
                "circulating_supply": 10_000_000,
                "total_supply": 10_000_000,
                "market_cap_rank": 500,
            },
            {
                "id": "xyz",
                "symbol": "xyz",
                "name": "XYZ",
                "current_price": 0.2,
                "market_cap": 20_000_000,
                "circulating_supply": 100_000_000,
                "total_supply": 100_000_000,
                "market_cap_rank": 2500,
            },
        ],
        max_pages=1,
    )

    matches = filter_low_market_cap_listings(listings, market_caps, threshold_usd=30_000_000)

    assert [item.listing.symbol for item in matches] == ["XYZUSDT"]
    assert matches[0].market_cap.asset_id == "xyz"


def test_fetchers_use_expected_external_endpoints() -> None:
    requested_urls: list[str] = []

    def requester(url, headers, timeout):
        requested_urls.append(url)
        if url == BINANCE_EXCHANGE_INFO_URL:
            return {
                "symbols": [
                    {
                        "symbol": "ABCUSDT",
                        "baseAsset": "ABC",
                        "quoteAsset": "USDT",
                        "status": "TRADING",
                        "isSpotTradingAllowed": True,
                    }
                ]
            }
        assert url.startswith(COINGECKO_MARKETS_URL)
        return [
            {
                "id": "abc",
                "symbol": "abc",
                "name": "ABC",
                "current_price": 0.1,
                "market_cap": 5_000_000,
                "circulating_supply": 50_000_000,
                "total_supply": 100_000_000,
                "market_cap_rank": 3000,
            }
        ]

    listings = fetch_binance_spot_listings(requester=requester)
    market_caps = fetch_coingecko_market_caps(requester=requester, max_pages=1)

    assert listings[0].symbol == "ABCUSDT"
    assert market_caps[0].asset_id == "abc"
    assert requested_urls[0] == BINANCE_EXCHANGE_INFO_URL
    assert requested_urls[1].startswith(COINGECKO_MARKETS_URL)


def test_coinpaprika_market_cap_parser_reads_usd_quote() -> None:
    requested_urls: list[str] = []

    def requester(url, headers, timeout):
        requested_urls.append(url)
        assert headers is None
        assert timeout == 30.0
        return [
            {
                "id": "abc-abc",
                "symbol": "ABC",
                "name": "ABC",
                "rank": 2500,
                "circulating_supply": 100_000_000,
                "total_supply": 200_000_000,
                "quotes": {
                    "USD": {
                        "price": 0.2,
                        "market_cap": 20_000_000,
                    }
                },
            }
        ]

    market_caps = fetch_coinpaprika_market_caps(
        requester=requester,
    )

    assert requested_urls == [COINPAPRIKA_TICKERS_URL]
    assert market_caps[0].source == "coinpaprika"
    assert market_caps[0].asset_id == "abc-abc"
    assert market_caps[0].market_cap_usd == 20_000_000
