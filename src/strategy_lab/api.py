from __future__ import annotations

from dataclasses import MISSING, fields, is_dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import json
import math
import os
import time
from typing import Any
import uuid

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query
import yaml

from strategy_lab.config import AppSettings, load_settings
from strategy_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType
from strategy_lab.experiments import RunRegistry
from strategy_lab.factors import default_registry
from strategy_lab.features import FeatureBuilder, FeatureStore
from strategy_lab.orchestration import StrategyRunner
from strategy_lab.orchestration.config import load_strategy_workflow_text
from strategy_lab.strategies import strategy_registry


_MARKET_SOURCES = [
    {
        "id": "binance",
        "name": "Binance",
        "type": "crypto_exchange",
        "status": "online",
        "latency_ms": 142,
        "coverage": ["spot", "usdt_perp", "funding", "open_interest", "liquidations"],
        "note": "ccxt OHLCV + 本地数据湖，清算流已接入 Binance。",
    },
    {
        "id": "okx",
        "name": "OKX",
        "type": "crypto_exchange",
        "status": "online",
        "latency_ms": 176,
        "coverage": ["spot", "swap", "funding", "open_interest"],
        "note": "第一阶段作为行情与回测候选数据源，衍生品字段按 adapter 逐步补齐。",
    },
    {
        "id": "data_lake",
        "name": "Local Data Lake",
        "type": "warehouse",
        "status": "ready",
        "latency_ms": 8,
        "coverage": ["ohlcv", "features", "snapshots", "run_registry"],
        "note": "策略回测默认使用可复现的数据快照。",
    },
    {
        "id": "news_events",
        "name": "News/Event Stream",
        "type": "intelligence",
        "status": "planned",
        "latency_ms": None,
        "coverage": ["headlines", "entity_tags", "event_windows"],
        "note": "先做只读聚合和资产标签，后续进入事件因子研究。",
    },
]

_INSTRUMENTS = [
    {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "market_type": "spot", "sources": ["binance", "okx"], "tags": ["majors", "store_of_value"]},
    {"symbol": "ETH/USDT", "base": "ETH", "quote": "USDT", "market_type": "spot", "sources": ["binance", "okx"], "tags": ["majors", "beta"]},
    {"symbol": "SOL/USDT", "base": "SOL", "quote": "USDT", "market_type": "spot", "sources": ["binance", "okx"], "tags": ["l1", "momentum"]},
    {"symbol": "DOGE/USDT", "base": "DOGE", "quote": "USDT", "market_type": "spot", "sources": ["binance", "okx"], "tags": ["meme", "retail"]},
    {"symbol": "ASTER/USDT", "base": "ASTER", "quote": "USDT", "market_type": "spot", "sources": ["binance"], "tags": ["watchlist", "new_listing"]},
    {"symbol": "PAXG/USDT", "base": "PAXG", "quote": "USDT", "market_type": "spot", "sources": ["binance"], "tags": ["gold", "macro"]},
    {"symbol": "BTC/USDT:USDT", "base": "BTC", "quote": "USDT", "market_type": "usdt_perp", "sources": ["binance", "okx"], "tags": ["perp", "funding"]},
    {"symbol": "ETH/USDT:USDT", "base": "ETH", "quote": "USDT", "market_type": "usdt_perp", "sources": ["binance", "okx"], "tags": ["perp", "funding"]},
]

_STRATEGY_TEMPLATE_METADATA = {
    "ma_crossover": {
        "name": "双均线交叉",
        "category": "trend",
        "description": "基于快慢均线距离判断趋势切换，适合做单标的趋势跟随 baseline。",
        "default_timeframe": "1h",
        "default_universe": ["BTC/USDT", "ETH/USDT"],
    },
    "trend_confirmation": {
        "name": "趋势确认",
        "category": "trend",
        "description": "综合动量、突破、OI、基差、成交量和资金费率过滤强趋势机会。",
        "default_timeframe": "4h",
        "default_universe": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT"],
    },
    "crowding_reversal": {
        "name": "拥挤度反转",
        "category": "reversal",
        "description": "观察资金费率、基差、OI 与短期动量背离，验证拥挤交易的反转机会。",
        "default_timeframe": "4h",
        "default_universe": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
    },
    "donchian_breakout": {
        "name": "Donchian 突破",
        "category": "breakout",
        "description": "用 Donchian 通道突破识别趋势启动，并支持止损、追踪止损和金字塔加仓参数。",
        "default_timeframe": "1d",
        "default_universe": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    },
    "momentum_rotation": {
        "name": "动量轮动",
        "category": "momentum",
        "description": "基于价格动量、突破、RSI 和成交量在多标的之间做相对强弱轮动。",
        "default_timeframe": "1h",
        "default_universe": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
    },
    "small_cap_momentum_breakout": {
        "name": "小市值动量突破",
        "category": "momentum",
        "description": "监控小市值币种的突破、短周期动量和放量异动，并用止损、移动止盈和冷却期控制追涨风险。",
        "default_timeframe": "5m",
        "default_universe": ["DOGE/USDT", "PEPE/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT"],
    },
}

_PARAMETER_LABELS = {
    "fast_ma_factor": "快均线因子",
    "slow_ma_factor": "慢均线因子",
    "long_allocation": "多头仓位",
    "short_allocation": "空头仓位",
    "stop_loss_pct": "止损比例",
    "take_profit_pct": "止盈比例",
    "cooldown_bars": "冷却 bar 数",
    "min_ma_gap_ratio": "最小均线差",
    "min_slow_ma_slope": "最小慢线斜率",
    "slope_lookback": "斜率窗口",
    "exit_on_choppy": "震荡退出",
    "momentum_factor": "动量因子",
    "primary_momentum_factor": "主动量因子",
    "short_momentum_factor": "短周期动量因子",
    "fast_momentum_factor": "快速动量因子",
    "confirmation_momentum_factor": "确认动量因子",
    "breakout_factor": "突破因子",
    "rsi_factor": "RSI 因子",
    "volume_factor": "成交量因子",
    "illiquidity_factor": "流动性惩罚因子",
    "funding_zscore_factor": "资金费率 zscore",
    "min_momentum": "最小动量",
    "min_fast_momentum": "最小快速动量",
    "min_confirmation_momentum": "最小确认动量",
    "breakout_floor": "突破下限",
    "min_breakout_signal": "最小突破信号",
    "min_volume_surge": "最小放量",
    "min_rsi": "RSI 下限",
    "max_rsi": "RSI 上限",
    "min_long_rsi": "做多 RSI 下限",
    "max_long_rsi": "做多 RSI 上限",
    "min_short_rsi": "做空 RSI 下限",
    "max_short_rsi": "做空 RSI 上限",
    "max_amihud_illiquidity": "最大 Amihud 非流动性",
    "max_long_positions": "最大多头数",
    "max_short_positions": "最大空头数",
    "max_positions": "最大持仓数",
    "position_weight": "单币仓位",
    "trailing_stop_pct": "移动止盈回撤",
    "max_hold_bars": "最长持仓 bar 数",
    "market_neutral": "市场中性",
    "risk_budget_pct": "风险预算",
    "max_pyramids": "最大加仓次数",
}

_MARKET_DATASETS = (
    DatasetKind.OHLCV,
    DatasetKind.FUNDING_RATES,
    DatasetKind.OPEN_INTEREST,
    DatasetKind.BASIS,
    DatasetKind.LIQUIDATIONS,
)


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:10], 16)


def _base_price(symbol: str) -> float:
    base = symbol.split("/")[0]
    defaults = {
        "BTC": 78000.0,
        "ETH": 3300.0,
        "SOL": 146.0,
        "DOGE": 0.19,
        "ASTER": 0.65,
        "PAXG": 3920.0,
    }
    return defaults.get(base, 10.0)


def _market_ticker(source: str, instrument: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    current_time = now or time.time()
    seed = _stable_seed(source, instrument["symbol"])
    wave = math.sin(current_time / 3600 + seed % 360) * 0.018
    drift = ((seed % 180) - 90) / 10000
    price = _base_price(instrument["symbol"]) * (1 + wave + drift)
    change = wave * 1.8 + drift
    volume = (seed % 9000 + 1200) * (1 + abs(wave) * 8)
    funding = None
    open_interest = None
    if instrument["market_type"].endswith("perp"):
        funding = round(((seed % 90) - 45) / 100000, 6)
        open_interest = round(volume * price * 22, 2)
    return {
        **instrument,
        "source": source,
        "last": round(price, 6 if price < 1 else 2),
        "change_24h": round(change, 4),
        "volume_24h": round(volume, 2),
        "quote_volume_24h": round(volume * price, 2),
        "funding_rate": funding,
        "open_interest": open_interest,
        "updated_at": datetime.fromtimestamp(current_time, tz=timezone.utc).isoformat(),
    }


def _ohlcv_rows(source: str, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
    step_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}.get(timeframe, 60)
    seed = _stable_seed(source, symbol, timeframe)
    current = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    base = _base_price(symbol)
    rows: list[dict[str, Any]] = []
    for index in range(limit):
        age = limit - index - 1
        ts = current - timedelta(minutes=step_minutes * age)
        wave = math.sin((index + seed % 40) / 7) * 0.018
        trend = (index - limit / 2) / max(limit, 1) * ((seed % 12) - 5) / 100
        close = base * (1 + wave + trend)
        open_ = close * (1 - math.sin((index + seed % 20) / 5) * 0.004)
        high = max(open_, close) * (1 + 0.006 + (seed % 8) / 10000)
        low = min(open_, close) * (1 - 0.006 - (seed % 6) / 10000)
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "open": round(open_, 6 if close < 1 else 2),
                "high": round(high, 6 if close < 1 else 2),
                "low": round(low, 6 if close < 1 else 2),
                "close": round(close, 6 if close < 1 else 2),
                "volume": round((seed % 5000 + 500) * (1 + abs(wave) * 10), 2),
            }
        )
    return rows


def _humanize_parameter_key(key: str) -> str:
    return _PARAMETER_LABELS.get(key, key.replace("_", " "))


def _parameter_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "text"


def _strategy_template_parameters(strategy_cls: type) -> list[dict[str, Any]]:
    try:
        strategy = strategy_cls.from_options({})
    except Exception:
        return []
    config = getattr(strategy, "config", None)
    if config is None or not is_dataclass(config):
        return []

    parameters: list[dict[str, Any]] = []
    for field in fields(config):
        if field.default is not MISSING:
            default = field.default
        elif field.default_factory is not MISSING:  # type: ignore[attr-defined]
            default = field.default_factory()  # type: ignore[misc]
        else:
            default = None
        parameters.append(
            {
                "key": field.name,
                "label": _humanize_parameter_key(field.name),
                "type": _parameter_type(default),
                "default": default,
                "required": default is None,
            }
        )
    return parameters


def _strategy_template(strategy_type: str, strategy_cls: type) -> dict[str, Any]:
    metadata = _STRATEGY_TEMPLATE_METADATA.get(strategy_type, {})
    return {
        "id": strategy_type,
        "strategy_type": strategy_type,
        "name": metadata.get("name") or strategy_type.replace("_", " ").title(),
        "category": metadata.get("category") or "strategy",
        "description": metadata.get("description") or f"{strategy_type} registered in strategy_lab.strategies.",
        "default_timeframe": metadata.get("default_timeframe") or "1h",
        "default_universe": metadata.get("default_universe") or ["BTC/USDT", "ETH/USDT"],
        "parameters": _strategy_template_parameters(strategy_cls),
    }


def _workflow_templates_dir() -> Path:
    current = Path.cwd()
    module_path = Path(__file__).resolve()
    for candidate in (current, *module_path.parents):
        templates_dir = candidate / "configs" / "workflows" / "strategies"
        if templates_dir.exists():
            return templates_dir
    return current / "configs" / "workflows" / "strategies"


def _read_workflow_template(path: Path, templates_dir: Path) -> dict[str, Any] | None:
    try:
        workflow_yaml = path.read_text(encoding="utf-8")
        payload = yaml.safe_load(workflow_yaml) or {}
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    strategy = payload.get("strategy") or {}
    refresh = payload.get("refresh") or {}
    metadata = payload.get("metadata") or {}
    if not isinstance(strategy, dict) or not isinstance(refresh, dict) or not isinstance(metadata, dict):
        return None

    relative_path = path.relative_to(templates_dir).as_posix()
    strategy_name = strategy.get("name") or path.stem
    strategy_type = strategy.get("strategy_type") or strategy.get("signal_type") or "factor"
    template_metadata = _STRATEGY_TEMPLATE_METADATA.get(str(strategy_type), {})
    exchange = strategy.get("exchange") or ""
    market_type = strategy.get("market_type") or ""
    symbols = strategy.get("symbols") or []
    return {
        "id": relative_path,
        "path": f"configs/workflows/strategies/{relative_path}",
        "name": template_metadata.get("name") or str(strategy_name),
        "category": template_metadata.get("category") or str(strategy_type),
        "description": metadata.get("description")
        or template_metadata.get("description")
        or f"{exchange} {market_type} workflow from {path.name}".strip(),
        "strategy_type": str(strategy_type),
        "default_timeframe": refresh.get("timeframe") or "1h",
        "default_universe": symbols if isinstance(symbols, list) else [],
        "workflow_yaml": workflow_yaml,
        "workflow": payload,
    }


def _canonical_template_rank(template: dict[str, Any]) -> tuple[int, str]:
    path = str(template.get("id") or "")
    strategy_type = str(template.get("strategy_type") or "")
    score = 100

    if path.startswith(f"{strategy_type}.") and "binance" in path and "recent1y" in path and ".daily." not in path:
        score = 0
    elif path == f"{strategy_type}.mvp.yaml":
        score = 10
    elif path.startswith(f"{strategy_type}.") and "binance" in path and "recent1y" in path:
        score = 20
    elif path.startswith(f"{strategy_type}.") and "binance" in path and "recent3m" in path:
        score = 30
    elif path.startswith(f"{strategy_type}."):
        score = 40

    if "shared-baseline" in path:
        score += 100
    if "baseline" in path:
        score += 80
    if "no_liq" in path or "filtered" in path:
        score += 60
    return (score, path)


def _canonical_strategy_templates(templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_strategy_type: dict[str, dict[str, Any]] = {}
    for template in templates:
        strategy_type = str(template.get("strategy_type") or "")
        if not strategy_type:
            continue
        current = by_strategy_type.get(strategy_type)
        if current is None or _canonical_template_rank(template) < _canonical_template_rank(current):
            by_strategy_type[strategy_type] = template

    metadata_order = {strategy_type: index for index, strategy_type in enumerate(_STRATEGY_TEMPLATE_METADATA)}
    return sorted(
        by_strategy_type.values(),
        key=lambda template: (
            metadata_order.get(str(template.get("strategy_type") or ""), len(metadata_order)),
            str(template.get("strategy_type") or ""),
        ),
    )


def _strategy_templates() -> list[dict[str, Any]]:
    templates_dir = _workflow_templates_dir()
    if not templates_dir.exists():
        return []
    templates = [
        template
        for path in sorted(templates_dir.glob("*.y*ml"))
        if (template := _read_workflow_template(path, templates_dir)) is not None
    ]
    return _canonical_strategy_templates(templates)


def _layout(config_path: str | Path | None = None) -> DataLakeLayout:
    return DataLakeLayout.from_settings(load_settings(config_path))


def _dataset_frame(layout: DataLakeLayout, kind: DatasetKind) -> pd.DataFrame:
    try:
        return DuckDBWarehouse(layout).load_dataset(layer="normalized", kind=kind)
    except Exception:
        return pd.DataFrame()


def _iso_or_none(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.isoformat()


def _market_type_from_query(value: str | None) -> MarketType | None:
    if not value:
        return None
    normalized = value.lower()
    if normalized in {"perp", "swap", "usdt_perp"}:
        return MarketType.PERP
    if normalized == "spot":
        return MarketType.SPOT
    return None


def _real_market_sources(layout: DataLakeLayout, settings: AppSettings) -> list[dict[str, Any]]:
    exchange_rows: dict[str, dict[str, Any]] = {
        exchange.name.lower(): {
            "coverage": set(),
            "file_count": 0,
            "row_count": 0,
            "symbols": set(),
            "start_ts": None,
            "end_ts": None,
        }
        for exchange in settings.exchanges
    }
    lake_coverage: set[str] = set()
    lake_file_count = 0
    lake_row_count = 0
    lake_symbols: set[str] = set()
    lake_start = None
    lake_end = None

    warehouse = DuckDBWarehouse(layout)
    for kind in _MARKET_DATASETS:
        files = warehouse.dataset_files(layer="normalized", kind=kind)
        if files:
            lake_coverage.add(kind.value)
            lake_file_count += len(files)
        frame = _dataset_frame(layout, kind)
        if frame.empty:
            continue

        lake_row_count += len(frame)
        if "symbol" in frame.columns:
            lake_symbols.update(str(symbol) for symbol in frame["symbol"].dropna().unique())
        if "ts" in frame.columns:
            start_ts = frame["ts"].min()
            end_ts = frame["ts"].max()
            lake_start = start_ts if lake_start is None or start_ts < lake_start else lake_start
            lake_end = end_ts if lake_end is None or end_ts > lake_end else lake_end

        if "exchange" not in frame.columns:
            continue
        for exchange_name, group in frame.groupby("exchange"):
            key = str(exchange_name).lower()
            summary = exchange_rows.setdefault(
                key,
                {
                    "coverage": set(),
                    "file_count": 0,
                    "row_count": 0,
                    "symbols": set(),
                    "start_ts": None,
                    "end_ts": None,
                },
            )
            summary["coverage"].add(kind.value)
            summary["file_count"] += len([file for file in files if f"exchange={key}" in file])
            summary["row_count"] += len(group)
            if "symbol" in group.columns:
                summary["symbols"].update(str(symbol) for symbol in group["symbol"].dropna().unique())
            if "ts" in group.columns:
                start_ts = group["ts"].min()
                end_ts = group["ts"].max()
                summary["start_ts"] = start_ts if summary["start_ts"] is None or start_ts < summary["start_ts"] else summary["start_ts"]
                summary["end_ts"] = end_ts if summary["end_ts"] is None or end_ts > summary["end_ts"] else summary["end_ts"]

    sources: list[dict[str, Any]] = []
    for exchange in settings.exchanges:
        key = exchange.name.lower()
        summary = exchange_rows.get(key, {})
        coverage = sorted(summary.get("coverage", set()))
        sources.append(
            {
                "id": key,
                "name": exchange.name.upper() if exchange.name.lower() != "binance" else "Binance",
                "type": "crypto_exchange",
                "status": "ready" if summary.get("row_count", 0) > 0 else "configured",
                "latency_ms": None,
                "coverage": coverage,
                "file_count": int(summary.get("file_count", 0)),
                "row_count": int(summary.get("row_count", 0)),
                "symbol_count": len(summary.get("symbols", set())),
                "from": _iso_or_none(summary.get("start_ts")),
                "to": _iso_or_none(summary.get("end_ts")),
                "note": "当前配置的数据湖中检测到真实行情快照。" if coverage else "已配置，但当前数据湖未检测到 normalized 行情文件。",
            }
        )

    sources.append(
        {
            "id": "data_lake",
            "name": "Local Data Lake",
            "type": "warehouse",
            "status": "ready" if lake_file_count > 0 else "empty",
            "latency_ms": None,
            "coverage": sorted(lake_coverage),
            "file_count": lake_file_count,
            "row_count": lake_row_count,
            "symbol_count": len(lake_symbols),
            "from": _iso_or_none(lake_start),
            "to": _iso_or_none(lake_end),
            "note": "从 normalized parquet 和 SQLite run registry 读取真实研究数据。",
        }
    )
    sources.append(
        {
            "id": "news_events",
            "name": "News/Event Stream",
            "type": "intelligence",
            "status": "not_configured",
            "latency_ms": None,
            "coverage": [],
            "file_count": 0,
            "row_count": 0,
            "symbol_count": 0,
            "from": None,
            "to": None,
            "note": "未检测到真实新闻/事件数据源，总览页不会展示模拟快讯。",
        }
    )
    return sources


def _real_market_tickers(
    layout: DataLakeLayout,
    *,
    source: str,
    market_type: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    selected_market_type = _market_type_from_query(market_type)
    frame = DuckDBWarehouse(layout).load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=source,
        market_type=selected_market_type,
    )
    if frame.empty:
        return []

    frame = frame.sort_values(["exchange", "symbol", "market_type", "ts"])
    tickers: list[dict[str, Any]] = []
    for (_, symbol, kind), group in frame.groupby(["exchange", "symbol", "market_type"], sort=False):
        latest = group.iloc[-1]
        latest_ts = pd.Timestamp(latest["ts"])
        comparison = group[group["ts"] <= latest_ts - pd.Timedelta(hours=24)]
        previous = comparison.iloc[-1] if not comparison.empty else group.iloc[0]
        previous_close = float(previous["close"])
        latest_close = float(latest["close"])
        change_24h = latest_close / previous_close - 1.0 if previous_close else None
        recent = group[group["ts"] > latest_ts - pd.Timedelta(hours=24)]
        volume_24h = float(recent["volume"].sum()) if "volume" in recent else None
        tickers.append(
            {
                "source": source,
                "symbol": str(symbol),
                "base": latest.get("base_asset"),
                "quote": latest.get("quote_asset"),
                "market_type": str(kind),
                "last": latest_close,
                "change_24h": change_24h,
                "volume_24h": volume_24h,
                "quote_volume_24h": volume_24h * latest_close if volume_24h is not None else None,
                "updated_at": _iso_or_none(latest_ts),
            }
        )
    tickers.sort(key=lambda row: abs(row["change_24h"] or 0), reverse=True)
    return tickers[:limit]


def _resolve_reports_path(
    reports_dir: Path,
    value: str | Path | None,
    *,
    strict: bool = True,
) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    reports_root = reports_dir.resolve()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        direct = candidate.resolve()
        try:
            direct.relative_to(reports_root)
        except ValueError:
            resolved = (reports_dir / candidate).resolve()
        else:
            resolved = direct
    try:
        resolved.relative_to(reports_root)
    except ValueError:
        if strict:
            raise HTTPException(status_code=400, detail=f"path escapes reports dir: {value}")
        return None
    return resolved


def _jsonable_frame(
    reports_dir: Path,
    path: str | None,
    *,
    row_limit: int,
    strict: bool = True,
) -> list[dict[str, object]]:
    artifact_path = _resolve_reports_path(reports_dir, path, strict=strict)
    if artifact_path is None:
        return []
    if not artifact_path.exists():
        return []
    frame = pd.read_parquet(artifact_path)
    if row_limit > 0 and len(frame) > row_limit:
        frame = frame.tail(row_limit).reset_index(drop=True)
    for column in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = pd.to_datetime(frame[column], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def _read_json(reports_dir: Path, path: str | None, *, strict: bool = True) -> dict:
    target = _resolve_reports_path(reports_dir, path, strict=strict)
    if target is None:
        return {}
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _load_manifest(reports_dir: Path, manifest_path: str, *, strict: bool = True) -> dict:
    target = _resolve_reports_path(reports_dir, manifest_path, strict=strict)
    if target is None:
        raise HTTPException(status_code=400, detail=f"path escapes reports dir: {manifest_path}")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"manifest not found: {manifest_path}")
    return json.loads(target.read_text(encoding="utf-8"))


def _backfill_benchmark_metrics(reports_dir: Path, manifest: dict, metrics: dict[str, Any]) -> dict[str, Any]:
    if "buy_hold_return" in metrics and "excess_return_vs_buy_hold" in metrics:
        return metrics

    artifacts = manifest.get("structured_artifacts", {})
    prices_path = _resolve_reports_path(reports_dir, artifacts.get("prices"), strict=False)
    if prices_path is None or not prices_path.exists():
        return metrics

    try:
        prices = pd.read_parquet(prices_path)
    except Exception:
        return metrics

    strategy = manifest.get("strategy", {})
    benchmark_symbol = strategy.get("benchmark_symbol") or (strategy.get("symbols") or [None])[0]
    benchmark_column = benchmark_symbol if benchmark_symbol in prices.columns else None
    if benchmark_column is None:
        benchmark_column = next((column for column in prices.columns if column != "ts"), None)
    if benchmark_column is None:
        return metrics

    benchmark_price = pd.to_numeric(prices[benchmark_column], errors="coerce").dropna()
    if len(benchmark_price) < 2 or benchmark_price.iloc[0] == 0:
        return metrics

    next_metrics = dict(metrics)
    buy_hold_return = float(benchmark_price.iloc[-1] / benchmark_price.iloc[0] - 1.0)
    next_metrics.setdefault("buy_hold_return", buy_hold_return)
    cumulative_return = next_metrics.get("cumulative_return")
    if cumulative_return is not None:
        next_metrics.setdefault("excess_return_vs_buy_hold", float(cumulative_return) - buy_hold_return)
    return next_metrics


def _enrich_run(reports_dir: Path, row: dict) -> dict:
    manifest = _read_json(reports_dir, row.get("manifest_path"), strict=False)
    metadata = manifest.get("metadata", {})
    strategy = manifest.get("strategy", {})
    refresh = manifest.get("refresh", {})
    execution = manifest.get("execution", {})
    backtest_metrics = _backfill_benchmark_metrics(
        reports_dir,
        manifest,
        row.get("backtest_metrics") or manifest.get("backtest_metrics", {}),
    )
    strategy_type = (
        row.get("strategy_type")
        or manifest.get("strategy_type")
        or row.get("signal_type")
        or manifest.get("signal_type")
    )
    return {
        **row,
        "variant_id": row.get("variant_id") or metadata.get("variant_id"),
        "config_hash": row.get("config_hash") or manifest.get("config_hash"),
        "git_sha": row.get("git_sha") or manifest.get("git_sha"),
        "data_snapshot_id": row.get("data_snapshot_id") or manifest.get("data_snapshot_id"),
        "strategy_type": strategy_type,
        "strategy_params": strategy.get("strategy_params", {}),
        "exchange": strategy.get("exchange"),
        "market_type": strategy.get("market_type"),
        "symbols": strategy.get("symbols", []),
        "benchmark_symbol": strategy.get("benchmark_symbol") or (strategy.get("symbols") or [None])[0],
        "timeframe": refresh.get("timeframe"),
        "execution_assumptions": execution,
        "metadata": metadata,
        "backtest_metrics": backtest_metrics,
        "backtest_attribution": row.get("backtest_attribution") or manifest.get("backtest_attribution", {}),
        "structured_artifact_paths": row.get("structured_artifact_paths") or manifest.get("structured_artifacts", {}),
        "generated_at": row.get("generated_at") or manifest.get("generated_at"),
    }


def _run_registry_dirs(reports_dir: Path) -> list[Path]:
    candidates = [reports_dir]
    parent = reports_dir.parent
    if parent.exists():
        candidates.extend(
            candidate
            for candidate in sorted(parent.iterdir())
            if candidate.is_dir() and (candidate / "_registry" / "runs.sqlite").exists()
        )
    if reports_dir.exists():
        candidates.extend(
            candidate
            for candidate in sorted(reports_dir.iterdir())
            if candidate.is_dir() and (candidate / "_registry" / "runs.sqlite").exists()
        )

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        key = candidate.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _registry_profile(reports_dir: Path) -> str:
    return reports_dir.name if reports_dir.name != "reports" else "default"


def _sort_run_value(row: dict[str, Any], sort_by: str, *, descending: bool) -> object:
    metrics = row.get("backtest_metrics") or {}
    if sort_by in metrics:
        value = metrics.get(sort_by)
        return value if value is not None else (float("-inf") if descending else float("inf"))
    if sort_by == "final_equity":
        value = (row.get("paper_summary") or {}).get("final_equity")
        return value if value is not None else (float("-inf") if descending else float("inf"))
    value = row.get(sort_by)
    return value if value is not None else ""


def _load_runs_across_registries(
    reports_dir: Path,
    *,
    kind: str | None,
    search: str | None,
    strategy_type: str | None,
    sort_by: str,
    sort_order: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_manifest_paths: set[str] = set()
    for registry_dir in _run_registry_dirs(reports_dir):
        registry = RunRegistry(registry_dir, db_path=registry_dir / "_registry" / "runs.sqlite")
        try:
            registry_rows = registry.load(
                kind=kind,
                search=search,
                strategy_type=strategy_type,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=None,
                offset=0,
            )
        except Exception:
            continue
        for row in registry_rows:
            manifest_path = str(row.get("manifest_path") or "")
            if not manifest_path or manifest_path in seen_manifest_paths:
                continue
            seen_manifest_paths.add(manifest_path)
            rows.append(
                {
                    **_enrich_run(registry_dir, row),
                    "registry_profile": _registry_profile(registry_dir),
                    "registry_reports_dir": str(registry_dir),
                }
            )

    descending = sort_order.lower() != "asc"
    rows.sort(key=lambda row: _sort_run_value(row, sort_by, descending=descending), reverse=descending)
    if offset:
        rows = rows[offset:]
    return rows[:limit]


def _find_registry_for_run(reports_dir: Path, manifest_path: str) -> tuple[Path, RunRegistry, dict[str, Any] | None]:
    for registry_dir in _run_registry_dirs(reports_dir):
        registry = RunRegistry(registry_dir, db_path=registry_dir / "_registry" / "runs.sqlite")
        try:
            row = registry.load_run(manifest_path)
        except Exception:
            row = None
        if row is not None:
            return registry_dir, registry, row
    return reports_dir, RunRegistry(reports_dir, db_path=reports_dir / "_registry" / "runs.sqlite"), None


def create_app(config_path: str | Path | None = None) -> FastAPI:
    resolved_config = config_path or os.environ.get("STRATEGY_LAB_CONFIG")
    settings = load_settings(resolved_config)
    layout = DataLakeLayout.from_settings(settings)
    layout.ensure_directories()
    warehouse = DuckDBWarehouse(layout)
    builder = FeatureBuilder(warehouse=warehouse, store=FeatureStore(layout), registry=default_registry())
    registry = RunRegistry(layout.reports_dir, db_path=layout.run_registry_db_path)
    app = FastAPI(title="Quant Strategy Lab API", version="0.1.0")
    lab_jobs: dict[str, dict[str, Any]] = {}
    lab_jobs_dir = layout.reports_dir / "lab_jobs"

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "reports_dir": str(layout.reports_dir)}

    @app.get("/api/markets/sources")
    def market_sources() -> dict[str, list[dict[str, Any]]]:
        return {"sources": _real_market_sources(layout, settings)}

    @app.get("/api/markets/instruments")
    def market_instruments(
        source: str | None = Query(None),
        market_type: str | None = Query(None),
    ) -> dict[str, list[dict[str, Any]]]:
        instruments = _INSTRUMENTS
        if source:
            instruments = [instrument for instrument in instruments if source in instrument["sources"]]
        if market_type:
            instruments = [instrument for instrument in instruments if instrument["market_type"] == market_type]
        return {"instruments": instruments}

    @app.get("/api/markets/tickers")
    def market_tickers(
        source: str = Query("binance"),
        market_type: str | None = Query(None),
        limit: int = Query(80, ge=1, le=500),
    ) -> dict[str, Any]:
        tickers = _real_market_tickers(layout, source=source, market_type=market_type, limit=limit)
        updated_at = max((ticker["updated_at"] for ticker in tickers if ticker.get("updated_at")), default=None)
        return {"source": source, "tickers": tickers, "updated_at": updated_at, "source_type": "normalized_data_lake"}

    @app.get("/api/markets/ohlcv")
    def market_ohlcv(
        source: str = Query("binance"),
        symbol: str = Query("BTC/USDT"),
        timeframe: str = Query("1h"),
        limit: int = Query(120, ge=20, le=500),
    ) -> dict[str, Any]:
        selected_market_type = MarketType.PERP if ":" in symbol else None
        frame = DuckDBWarehouse(layout).load_dataset(
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange=source,
            market_type=selected_market_type,
            symbol=symbol,
        )
        if frame.empty:
            bars: list[dict[str, Any]] = []
        else:
            frame = frame.sort_values("ts").tail(limit)
            bars = [
                {
                    "timestamp": _iso_or_none(row["ts"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
                for row in frame.to_dict(orient="records")
            ]
        return {
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": bars,
            "source_type": "normalized_data_lake",
        }

    @app.get("/api/lab/strategy-templates")
    def strategy_templates() -> dict[str, list[dict[str, Any]]]:
        return {"templates": _strategy_templates()}

    @app.post("/api/lab/backtests")
    def create_backtest_job(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        request_payload = payload or {}
        templates = _strategy_templates()
        workflow_yaml = request_payload.get("workflow_yaml")
        template_id = str(request_payload.get("template_id") or (templates[0]["id"] if templates else ""))
        template = next((item for item in templates if item["id"] == template_id), templates[0] if templates else None)
        if not workflow_yaml:
            if template is None:
                raise HTTPException(status_code=400, detail="workflow_yaml is required when no YAML templates are available")
            workflow_yaml = template["workflow_yaml"]
        if not isinstance(workflow_yaml, str) or not workflow_yaml.strip():
            raise HTTPException(status_code=400, detail="workflow_yaml must be a non-empty YAML string")
        try:
            workflow_config = load_strategy_workflow_text(workflow_yaml)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid workflow_yaml: {exc}") from exc

        job_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        snapshot_id = f"web-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{job_id[:6]}"
        lab_jobs_dir.mkdir(parents=True, exist_ok=True)
        submitted_workflows_dir = lab_jobs_dir / "workflows"
        submitted_workflows_dir.mkdir(parents=True, exist_ok=True)
        workflow_yaml_path = submitted_workflows_dir / f"{job_id}.yaml"
        workflow_yaml_path.write_text(workflow_yaml, encoding="utf-8")
        job = {
            "id": job_id,
            "status": "running",
            "created_at": created_at,
            "updated_at": created_at,
            "template_id": template_id or workflow_config.strategy.name,
            "template_name": workflow_config.strategy.name,
            "source": workflow_config.strategy.exchange,
            "timeframe": workflow_config.refresh.timeframe,
            "universe": workflow_config.strategy.symbols,
            "parameters": workflow_config.strategy.strategy_params,
            "workflow_yaml_path": str(workflow_yaml_path),
            "data_snapshot_id": snapshot_id,
            "result_sink": {
                "registry_db": str(layout.run_registry_db_path),
                "reports_dir": str(layout.reports_dir),
            },
            "next_step": "已保存编辑后的 YAML workflow，正在运行回测并写入 RunRegistry。",
        }
        lab_jobs[job_id] = job
        (lab_jobs_dir / f"{job_id}.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            artifacts = StrategyRunner(layout=layout, builder=builder).run(workflow_config)
            manifest_payload = _read_json(layout.reports_dir, artifacts.manifest_path, strict=False)
            job.update(
                {
                    "status": "completed",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "run_id": artifacts.run_id,
                    "manifest_path": artifacts.manifest_path,
                    "factor_report_path": artifacts.factor_report_path,
                    "backtest_report_path": artifacts.backtest_report_path,
                    "paper_report_path": artifacts.paper_report_path,
                    "backtest_metrics": artifacts.backtest_metrics,
                    "paper_summary": artifacts.paper_summary,
                    "data_snapshot_id": manifest_payload.get("data_snapshot_id") or snapshot_id,
                    "next_step": "回测已完成，结果已写入 RunRegistry，可在回测记录页面查看。",
                }
            )
        except Exception as exc:
            job.update(
                {
                    "status": "failed",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                    "next_step": "回测执行失败，请检查 YAML、数据快照和因子配置。",
                }
            )

        lab_jobs[job_id] = job
        (lab_jobs_dir / f"{job_id}.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"job": job}

    @app.get("/api/lab/jobs/{job_id}")
    def lab_job(job_id: str) -> dict[str, Any]:
        job = lab_jobs.get(job_id)
        if not job:
            job_path = lab_jobs_dir / f"{job_id}.json"
            if job_path.exists():
                job = json.loads(job_path.read_text(encoding="utf-8"))
        if not job:
            raise HTTPException(status_code=404, detail=f"lab job not found: {job_id}")
        return {"job": job}

    @app.get("/api/news/events")
    def news_events(limit: int = Query(30, ge=1, le=100)) -> dict[str, list[dict[str, Any]]]:
        return {"events": [], "source_status": "not_configured", "message": "未配置真实新闻/事件数据源。"}

    @app.get("/api/runs")
    def runs(
        kind: str | None = Query(None),
        search: str | None = Query(None),
        strategy_type: str | None = Query(None),
        sort_by: str = Query("generated_at"),
        sort_order: str = Query("desc"),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, list[dict]]:
        rows = _load_runs_across_registries(
            layout.reports_dir,
            kind=kind,
            search=search,
            strategy_type=strategy_type,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
        return {"runs": rows}

    @app.get("/api/run-detail")
    def run_detail(
        manifest_path: str = Query(...),
        limit: int = Query(1000, ge=1, le=5000),
    ) -> dict:
        registry_reports_dir, selected_registry, run_row = _find_registry_for_run(layout.reports_dir, manifest_path)
        manifest = selected_registry.load_manifest(manifest_path) or _load_manifest(registry_reports_dir, manifest_path)
        artifacts = manifest.get("structured_artifacts", {})
        metrics = None
        if run_row and (run_row.get("backtest_metrics") or run_row.get("backtest_attribution")):
            metrics = {
                "backtest_metrics": run_row.get("backtest_metrics", {}),
                "backtest_attribution": run_row.get("backtest_attribution", {}),
            }
        equity_curve = selected_registry.load_series(manifest_path, "equity_curve", limit=limit)
        period_returns = selected_registry.load_series(manifest_path, "period_returns", limit=limit)
        trades = selected_registry.load_trades(manifest_path, limit=limit)
        return {
            "run": _enrich_run(registry_reports_dir, run_row) if run_row else None,
            "manifest": manifest,
            "artifacts": {
                "prices": _jsonable_frame(registry_reports_dir, artifacts.get("prices"), row_limit=limit),
                "signals": _jsonable_frame(registry_reports_dir, artifacts.get("signals"), row_limit=limit),
                "weights": _jsonable_frame(registry_reports_dir, artifacts.get("weights"), row_limit=limit),
                "trades": trades or _jsonable_frame(registry_reports_dir, artifacts.get("trades"), row_limit=limit),
                "equity_curve": equity_curve or _jsonable_frame(registry_reports_dir, artifacts.get("equity_curve"), row_limit=limit),
                "period_returns": period_returns or _jsonable_frame(registry_reports_dir, artifacts.get("period_returns"), row_limit=limit),
            },
            "metrics": metrics or _read_json(registry_reports_dir, artifacts.get("metrics")),
            "row_limit": limit,
        }

    @app.get("/api/experiment-detail")
    def experiment_detail(manifest_path: str = Query(...)) -> dict:
        run_row = registry.load_run(manifest_path)
        manifest = registry.load_manifest(manifest_path) or _load_manifest(layout.reports_dir, manifest_path)
        children = [_enrich_run(layout.reports_dir, child) for child in registry.load_child_runs(manifest_path)]
        return {
            "run": _enrich_run(layout.reports_dir, run_row) if run_row else None,
            "manifest": manifest,
            "children": children,
        }

    @app.get("/api/comparison-detail")
    def comparison_detail(manifest_path: str = Query(...)) -> dict:
        run_row = registry.load_run(manifest_path)
        manifest = registry.load_manifest(manifest_path) or _load_manifest(layout.reports_dir, manifest_path)
        children = [_enrich_run(layout.reports_dir, child) for child in registry.load_child_runs(manifest_path)]
        return {
            "run": _enrich_run(layout.reports_dir, run_row) if run_row else None,
            "manifest": manifest,
            "children": children,
        }

    return app


app = create_app()
