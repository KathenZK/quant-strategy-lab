from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.models import DatasetKind
from strategy_lab.fs import atomic_write_path


BINANCE_SQUARE_FEED_URL = "https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list"


def _safe_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _collect_symbols(item: dict[str, Any]) -> str:
    values: set[str] = set()
    for key in ("tradingPairs", "tradingPairsV2", "userInputTradingPairs"):
        for entry in item.get(key) or []:
            if isinstance(entry, str):
                values.add(entry.upper())
            elif isinstance(entry, dict):
                symbol = entry.get("symbol") or entry.get("pair") or entry.get("name") or entry.get("baseAsset")
                if symbol:
                    values.add(str(symbol).upper())
    return ",".join(sorted(values))


def _collect_hashtags(item: dict[str, Any]) -> str:
    values: set[str] = set()
    for key in ("hashtagList", "hashtagIdentifyList"):
        for entry in item.get(key) or []:
            if isinstance(entry, str):
                values.add(entry)
            elif isinstance(entry, dict):
                tag = entry.get("hashtag") or entry.get("name") or entry.get("tag") or entry.get("topic")
                if tag:
                    values.add(str(tag))
    return ",".join(sorted(values))


def normalize_square_posts(items: list[dict[str, Any]], *, fetched_at: pd.Timestamp | None = None) -> pd.DataFrame:
    fetched_ts = pd.Timestamp.now(tz="UTC") if fetched_at is None else pd.to_datetime(fetched_at, utc=True)
    rows: list[dict[str, object]] = []
    for item in items:
        post_id = item.get("id")
        if post_id is None:
            continue
        ts_value = item.get("date")
        ts = pd.to_datetime(ts_value, unit="s", utc=True) if ts_value is not None else fetched_ts
        rows.append(
            {
                "ts": ts,
                "post_id": str(post_id),
                "author_name": item.get("authorName") or "",
                "username": item.get("username") or "",
                "square_author_id": item.get("squareAuthorId") or "",
                "author_is_verified": bool(item.get("authorIsVerified")),
                "author_role": _safe_int(item.get("authorRole")),
                "content": item.get("content") or "",
                "title": item.get("title") or "",
                "detected_language": item.get("detectedLanguage") or "",
                "web_link": item.get("webLink") or "",
                "share_link": item.get("shareLink") or "",
                "symbols": _collect_symbols(item),
                "hashtags": _collect_hashtags(item),
                "like_count": _safe_int(item.get("likeCount")),
                "view_count": _safe_int(item.get("viewCount")),
                "comment_count": _safe_int(item.get("commentCount")),
                "share_count": _safe_int(item.get("shareCount")),
                "quote_count": _safe_int(item.get("quoteCount")),
                "reply_count": _safe_int(item.get("replyCount")),
                "total_reaction_count": _safe_int(item.get("totalReactionCount")),
                "content_type": _safe_int(item.get("contentType")),
                "card_type": item.get("cardType") or "",
                "source_type": _safe_int(item.get("sourceType")),
                "is_created_by_ai": bool(item.get("isCreatedByAI")),
                "is_reply_post": bool(item.get("isReplyPost")),
                "fetched_at": fetched_ts,
                "source": "binance_square",
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["fetched_at"] = pd.to_datetime(frame["fetched_at"], utc=True)
    frame["date"] = frame["ts"].dt.date.astype("string")
    return frame.drop_duplicates(subset=["post_id"], keep="last").sort_values(["ts", "post_id"]).reset_index(drop=True)


@dataclass(slots=True)
class BinanceSquareClient:
    base_url: str = BINANCE_SQUARE_FEED_URL
    timeout_seconds: float = 20.0
    user_agent: str = "Mozilla/5.0 (compatible; quant-strategy-lab/0.1)"

    def fetch_article_page(self, *, page_index: int = 1, page_size: int = 20, feed_type: int | None = 0) -> dict[str, Any]:
        params = {"pageIndex": page_index, "pageSize": page_size}
        if feed_type is not None:
            params["type"] = feed_type
        query = urlencode(params)
        request = Request(
            f"{self.base_url}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        data = json.loads(payload)
        if data.get("code") != "000000":
            raise RuntimeError(f"Binance Square API error: {data.get('code')} {data.get('message')}")
        return data

    def fetch_latest_posts(
        self,
        *,
        pages: int = 1,
        page_size: int = 20,
        sleep_seconds: float = 1.0,
        feed_type: int | None = 0,
    ) -> pd.DataFrame:
        items: list[dict[str, Any]] = []
        fetched_at = pd.Timestamp.now(tz="UTC")
        for page_index in range(1, pages + 1):
            response = self.fetch_article_page(page_index=page_index, page_size=page_size, feed_type=feed_type)
            page_items = response.get("data", {}).get("vos") or []
            items.extend(item for item in page_items if isinstance(item, dict))
            if page_index < pages and sleep_seconds > 0.0:
                time.sleep(sleep_seconds)
        return normalize_square_posts(items, fetched_at=fetched_at)

    def fetch_posts_since(
        self,
        *,
        since: pd.Timestamp,
        page_size: int = 20,
        max_pages: int = 100,
        sleep_seconds: float = 1.0,
        feed_type: int | None = 0,
    ) -> pd.DataFrame:
        cutoff = pd.to_datetime(since, utc=True)
        items: list[dict[str, Any]] = []
        fetched_at = pd.Timestamp.now(tz="UTC")
        for page_index in range(1, max_pages + 1):
            response = self.fetch_article_page(page_index=page_index, page_size=page_size, feed_type=feed_type)
            page_items = [item for item in response.get("data", {}).get("vos") or [] if isinstance(item, dict)]
            if not page_items:
                break
            items.extend(page_items)
            page_dates = [item.get("date") for item in page_items if item.get("date") is not None]
            if page_dates and pd.to_datetime(min(page_dates), unit="s", utc=True) < cutoff:
                break
            if page_index < max_pages and sleep_seconds > 0.0:
                time.sleep(sleep_seconds)

        frame = normalize_square_posts(items, fetched_at=fetched_at)
        if frame.empty:
            return frame
        return frame[frame["ts"] >= cutoff].reset_index(drop=True)


def write_square_posts(layout: DataLakeLayout, frame: pd.DataFrame) -> list[Path]:
    if frame.empty:
        return []
    root = layout.dataset_root("normalized", DatasetKind.SQUARE_POSTS) / "source=binance_square"
    paths: list[Path] = []
    for partition, group in frame.groupby("date", sort=True):
        partition_date = date.fromisoformat(str(partition))
        path = root / f"date={partition_date.isoformat()}" / "part-000000.parquet"
        output_frame = group
        if path.exists():
            output_frame = pd.concat([pd.read_parquet(path), group], ignore_index=True)
            output_frame = output_frame.drop_duplicates(subset=["post_id"], keep="last")
            output_frame = output_frame.sort_values(["ts", "post_id"]).reset_index(drop=True)
        output = atomic_write_path(path, lambda temp_path, data=output_frame: data.reset_index(drop=True).to_parquet(temp_path, index=False))
        paths.append(output)
    return paths
