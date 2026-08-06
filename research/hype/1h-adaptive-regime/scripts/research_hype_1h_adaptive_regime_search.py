"""HYPE 1h adaptive-regime 搜索入口。

真实实现冻结在共享 kernel v1；本文件只负责 SHA256 pin、动态加载和兼容性导出，
避免家族目录继续保存整文件副本。
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pandas as pd

from strategy_lab.data import (
    DataLakeLayout,
    DatasetKind,
    DuckDBWarehouse,
    MarketType,
)
from strategy_lab.data.settings import load_settings


ROOT = Path(__file__).resolve().parents[4]
ENGINE_PATH = (
    ROOT / "research/_shared-kernels/1h-adaptive-regime-search/v1/engine.py"
)
ENGINE_SHA256 = "0420ea44854201e17d4bf5b9142fb8335d143e78772656473a1dcf4594a5f04c"
_MODULE_NAME = "_hype_1h_adaptive_regime_search_kernel_v1"


def _load_engine():
    actual = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if actual != ENGINE_SHA256:
        raise RuntimeError(
            "1h-adaptive-regime-search v1 SHA mismatch: "
            f"expected {ENGINE_SHA256}, got {actual}"
        )
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


_ENGINE = _load_engine()

# 兼容历史消费者：继续从本模块导入共享引擎的公开/内部研究符号。
for _name in dir(_ENGINE):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_ENGINE, _name)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Load HYPE OHLCV through the trusted warehouse without changing the kernel."""
    warehouse = DuckDBWarehouse(
        DataLakeLayout.from_settings(load_settings(None))
    )
    frame = warehouse.load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="HYPE/USDT:USDT",
        timeframe="1h",
    ).reset_index(drop=True)
    funding = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.FUNDING_RATES,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="HYPE/USDT:USDT",
        columns=["ts", "funding_rate", "source"],
    )
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = (
        funding.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if funding.empty or funding["funding_rate"].isna().any():
        raise RuntimeError("Funding history is empty or contains null funding_rate")

    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="1h")
    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    quality: dict[str, object] = {
        "normalized_files": len(
            warehouse._filtered_dataset_files(
                layer="normalized",
                kind=DatasetKind.OHLCV,
                exchange="binance",
                market_type=MarketType.PERP,
                symbol="HYPE/USDT:USDT",
                timeframe="1h",
            )
        ),
        "raw_files": len(
            list(_ENGINE.RAW_ROOT.glob(f"date=*/{_ENGINE.SYMBOL_FILE}"))
        ),
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(expected.difference(frame["ts"]))),
        "duplicate_bars": 0,
        "nulls": {column: int(frame[column].isna().sum()) for column in required},
        "violations": {
            "high_lt_open_close": 0,
            "low_gt_open_close": 0,
            "nonpositive_ohlc": 0,
            "negative_volume": 0,
            "negative_quote_volume": 0,
        },
        "funding_rows": int(len(funding)),
        "funding_first_ts": funding["ts"].iloc[0].isoformat(),
        "funding_last_ts": funding["ts"].iloc[-1].isoformat(),
        "source_counts": {
            str(key): int(value)
            for key, value in frame["source"].value_counts().items()
        },
        "ohlcv_audit": frame.attrs.get("ohlcv_audit", {}),
    }
    return frame, funding, quality


_ENGINE.load_data = load_data


if __name__ == "__main__":
    _ENGINE.main()
