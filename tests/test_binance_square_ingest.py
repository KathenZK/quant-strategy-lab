from __future__ import annotations

import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind
from strategy_lab.data.ingest.binance_square import BinanceSquareClient, normalize_square_posts, write_square_posts


def test_normalize_square_posts_extracts_public_feed_fields() -> None:
    frame = normalize_square_posts(
        [
            {
                "id": 123,
                "date": 1_778_104_494,
                "authorName": "Creator",
                "username": "creator_handle",
                "squareAuthorId": "author-1",
                "authorIsVerified": True,
                "content": "BTC breakout",
                "webLink": "https://www.binance.com/en/square/post/123",
                "tradingPairsV2": [{"symbol": "BTC"}],
                "userInputTradingPairs": [{"baseAsset": "ETH"}],
                "hashtagList": [{"hashtag": "BTC"}],
                "likeCount": "7",
                "viewCount": 100,
                "commentCount": None,
                "shareCount": 2,
                "quoteCount": 1,
                "totalReactionCount": 9,
            },
            {
                "id": 123,
                "date": 1_778_104_494,
                "authorName": "Creator",
                "content": "duplicate should win",
            },
        ],
        fetched_at=pd.Timestamp("2026-05-07T00:00:00Z"),
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["post_id"] == "123"
    assert row["content"] == "duplicate should win"
    assert row["source"] == "binance_square"
    assert row["ts"].tzinfo is not None
    assert row["date"] == "2026-05-06"


def test_write_square_posts_partitions_by_publish_date(tmp_path) -> None:
    layout = DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )
    layout.ensure_directories()
    frame = normalize_square_posts(
        [
            {"id": "1", "date": 1_778_104_494, "authorName": "A", "content": "first"},
            {"id": "2", "date": 1_778_190_894, "authorName": "B", "content": "second"},
        ]
    )

    paths = write_square_posts(layout, frame)

    assert len(paths) == 2
    assert all(path.exists() for path in paths)
    assert str(paths[0]).startswith(str(layout.dataset_root("normalized", DatasetKind.SQUARE_POSTS)))
    persisted = pd.concat(pd.read_parquet(path) for path in paths)
    assert set(persisted["post_id"]) == {"1", "2"}


def test_write_square_posts_merges_existing_partition(tmp_path) -> None:
    layout = DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )
    layout.ensure_directories()
    first = normalize_square_posts([{"id": "1", "date": 1_778_104_494, "authorName": "A", "content": "first"}])
    second = normalize_square_posts(
        [
            {"id": "1", "date": 1_778_104_494, "authorName": "A", "content": "updated"},
            {"id": "2", "date": 1_778_104_500, "authorName": "B", "content": "second"},
        ]
    )

    paths = write_square_posts(layout, first)
    write_square_posts(layout, second)

    persisted = pd.read_parquet(paths[0]).sort_values("post_id")
    assert list(persisted["post_id"]) == ["1", "2"]
    assert persisted.loc[persisted["post_id"] == "1", "content"].item() == "updated"


def test_fetch_posts_since_stops_after_window_boundary(monkeypatch) -> None:
    calls: list[int] = []
    pages = {
        1: [
            {"id": "new-1", "date": 1_778_140_000, "authorName": "A", "content": "BTC"},
            {"id": "new-2", "date": 1_778_136_000, "authorName": "B", "content": "ETH"},
        ],
        2: [
            {"id": "old-1", "date": 1_778_132_000, "authorName": "C", "content": "SOL"},
            {"id": "old-2", "date": 1_778_120_000, "authorName": "D", "content": "XRP"},
        ],
        3: [
            {"id": "too-far", "date": 1_778_100_000, "authorName": "E", "content": "BNB"},
        ],
    }

    def fake_fetch_article_page(self, *, page_index: int = 1, page_size: int = 20, feed_type: int | None = 0):
        calls.append(page_index)
        return {"code": "000000", "success": True, "data": {"vos": pages[page_index]}}

    monkeypatch.setattr(BinanceSquareClient, "fetch_article_page", fake_fetch_article_page)

    frame = BinanceSquareClient().fetch_posts_since(
        since=pd.Timestamp(1_778_133_000, unit="s", tz="UTC"),
        page_size=2,
        max_pages=10,
        sleep_seconds=0.0,
    )

    assert calls == [1, 2]
    assert set(frame["post_id"]) == {"new-1", "new-2"}
