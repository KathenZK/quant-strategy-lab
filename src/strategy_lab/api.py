from __future__ import annotations

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

from strategy_lab.config import load_settings
from strategy_lab.data import DataLakeLayout
from strategy_lab.experiments import RunRegistry


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

_STRATEGY_TEMPLATES = [
    {
        "id": "momentum_breakout",
        "name": "动量突破",
        "category": "trend",
        "description": "用趋势强度、波动过滤和突破确认筛选强势标的。",
        "default_timeframe": "1h",
        "default_universe": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "parameters": [
            {"key": "lookback", "label": "回看周期", "type": "number", "default": 48},
            {"key": "breakout_z", "label": "突破阈值", "type": "number", "default": 1.8},
            {"key": "risk_budget", "label": "风险预算", "type": "number", "default": 0.35},
        ],
    },
    {
        "id": "funding_reversion",
        "name": "资金费率均值回归",
        "category": "carry",
        "description": "观察资金费率、OI 与价格背离，用于衍生品拥挤度实验。",
        "default_timeframe": "4h",
        "default_universe": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
        "parameters": [
            {"key": "funding_window", "label": "资金费率窗口", "type": "number", "default": 21},
            {"key": "oi_filter", "label": "OI 过滤", "type": "number", "default": 0.12},
            {"key": "max_leverage", "label": "最大杠杆", "type": "number", "default": 1.0},
        ],
    },
    {
        "id": "event_reaction",
        "name": "新闻事件反应",
        "category": "event",
        "description": "把新闻时间线映射到资产窗口，验证事件后收益与回撤。",
        "default_timeframe": "15m",
        "default_universe": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "parameters": [
            {"key": "event_window_hours", "label": "事件窗口", "type": "number", "default": 12},
            {"key": "cooldown_hours", "label": "冷却时间", "type": "number", "default": 6},
            {"key": "sentiment_threshold", "label": "情绪阈值", "type": "number", "default": 0.62},
        ],
    },
]


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


def _layout(config_path: str | Path | None = None) -> DataLakeLayout:
    return DataLakeLayout.from_settings(load_settings(config_path))


def _resolve_reports_path(
    reports_dir: Path,
    value: str | Path | None,
    *,
    strict: bool = True,
) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (reports_dir / candidate).resolve()
    reports_root = reports_dir.resolve()
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


def _enrich_run(reports_dir: Path, row: dict) -> dict:
    manifest = {}
    if not row.get("config_hash") or not row.get("git_sha") or not row.get("data_snapshot_id") or not row.get("structured_artifact_paths"):
        manifest = _read_json(reports_dir, row.get("manifest_path"), strict=False)
    metadata = manifest.get("metadata", {})
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
        "structured_artifact_paths": row.get("structured_artifact_paths") or manifest.get("structured_artifacts", {}),
        "generated_at": row.get("generated_at") or manifest.get("generated_at"),
    }


def create_app(config_path: str | Path | None = None) -> FastAPI:
    resolved_config = config_path or os.environ.get("STRATEGY_LAB_CONFIG")
    layout = _layout(resolved_config)
    registry = RunRegistry(layout.reports_dir, db_path=layout.run_registry_db_path)
    app = FastAPI(title="Quant Strategy Lab API", version="0.1.0")
    lab_jobs: dict[str, dict[str, Any]] = {}
    lab_jobs_dir = layout.reports_dir / "lab_jobs"

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "reports_dir": str(layout.reports_dir)}

    @app.get("/api/markets/sources")
    def market_sources() -> dict[str, list[dict[str, Any]]]:
        return {"sources": _MARKET_SOURCES}

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
        instruments = [
            instrument
            for instrument in _INSTRUMENTS
            if source in instrument["sources"] and (market_type is None or instrument["market_type"] == market_type)
        ]
        now = time.time()
        tickers = [_market_ticker(source, instrument, now) for instrument in instruments[:limit]]
        tickers.sort(key=lambda row: abs(row["change_24h"]), reverse=True)
        return {"source": source, "tickers": tickers, "updated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat()}

    @app.get("/api/markets/ohlcv")
    def market_ohlcv(
        source: str = Query("binance"),
        symbol: str = Query("BTC/USDT"),
        timeframe: str = Query("1h"),
        limit: int = Query(120, ge=20, le=500),
    ) -> dict[str, Any]:
        return {
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": _ohlcv_rows(source, symbol, timeframe, limit),
        }

    @app.get("/api/lab/strategy-templates")
    def strategy_templates() -> dict[str, list[dict[str, Any]]]:
        return {"templates": _STRATEGY_TEMPLATES}

    @app.post("/api/lab/backtests")
    def create_backtest_job(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        request_payload = payload or {}
        template_id = str(request_payload.get("template_id") or "momentum_breakout")
        template = next((item for item in _STRATEGY_TEMPLATES if item["id"] == template_id), _STRATEGY_TEMPLATES[0])
        job_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        snapshot_id = f"web-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{job_id[:6]}"
        job = {
            "id": job_id,
            "status": "queued",
            "created_at": created_at,
            "updated_at": created_at,
            "template_id": template["id"],
            "template_name": template["name"],
            "source": request_payload.get("source") or "binance",
            "timeframe": request_payload.get("timeframe") or template["default_timeframe"],
            "universe": request_payload.get("universe") or template["default_universe"],
            "parameters": request_payload.get("parameters") or {item["key"]: item["default"] for item in template["parameters"]},
            "data_snapshot_id": snapshot_id,
            "result_sink": {
                "registry_db": str(layout.run_registry_db_path),
                "reports_dir": str(layout.reports_dir),
            },
            "next_step": "已创建 Web 回测任务。接入 worker 后将调用 StrategyRunner，并把结果写入 RunRegistry。",
        }
        lab_jobs[job_id] = job
        lab_jobs_dir.mkdir(parents=True, exist_ok=True)
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
        now = datetime.now(timezone.utc).replace(microsecond=0)
        events = [
            {
                "id": "event-etf-flow",
                "published_at": (now - timedelta(minutes=28)).isoformat(),
                "source": "ETF flow monitor",
                "title": "BTC ETF 净流入重新转正，衍生品资金费率同步降温",
                "summary": "现货买盘恢复但永续未明显拥挤，适合观察趋势延续与回撤买点。",
                "assets": ["BTC", "ETH"],
                "sentiment": 0.66,
                "event_type": "macro_flow",
            },
            {
                "id": "event-sol-ecosystem",
                "published_at": (now - timedelta(hours=1, minutes=12)).isoformat(),
                "source": "ecosystem radar",
                "title": "Solana 生态交易量回升，链上活跃地址连续三日增长",
                "summary": "事件窗口可用于验证 SOL 高 beta 资产的动量跟随和反转风险。",
                "assets": ["SOL"],
                "sentiment": 0.61,
                "event_type": "onchain_activity",
            },
            {
                "id": "event-okx-listing",
                "published_at": (now - timedelta(hours=3, minutes=8)).isoformat(),
                "source": "listing watch",
                "title": "OKX 新增热门资产交易对，短线成交量出现脉冲",
                "summary": "上市事件优先进入观察列表，不直接进入自动交易。",
                "assets": ["ASTER", "DOGE"],
                "sentiment": 0.54,
                "event_type": "listing",
            },
            {
                "id": "event-gold-macro",
                "published_at": (now - timedelta(hours=5, minutes=40)).isoformat(),
                "source": "macro desk",
                "title": "避险资产波动抬升，PAXG 与 BTC 相关性短暂下降",
                "summary": "可作为跨资产因子研究样本，后续扩展到股票和预测市场。",
                "assets": ["PAXG", "BTC"],
                "sentiment": 0.48,
                "event_type": "macro",
            },
        ]
        return {"events": events[:limit]}

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
        rows = [
            _enrich_run(layout.reports_dir, row)
            for row in registry.load(
                kind=kind,
                search=search,
                strategy_type=strategy_type,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
            )
        ]
        return {"runs": rows}

    @app.get("/api/run-detail")
    def run_detail(
        manifest_path: str = Query(...),
        limit: int = Query(1000, ge=1, le=5000),
    ) -> dict:
        run_row = registry.load_run(manifest_path)
        manifest = registry.load_manifest(manifest_path) or _load_manifest(layout.reports_dir, manifest_path)
        artifacts = manifest.get("structured_artifacts", {})
        metrics = None
        if run_row and (run_row.get("backtest_metrics") or run_row.get("backtest_attribution")):
            metrics = {
                "backtest_metrics": run_row.get("backtest_metrics", {}),
                "backtest_attribution": run_row.get("backtest_attribution", {}),
            }
        equity_curve = registry.load_series(manifest_path, "equity_curve", limit=limit)
        period_returns = registry.load_series(manifest_path, "period_returns", limit=limit)
        trades = registry.load_trades(manifest_path, limit=limit)
        return {
            "run": _enrich_run(layout.reports_dir, run_row) if run_row else None,
            "manifest": manifest,
            "artifacts": {
                "prices": _jsonable_frame(layout.reports_dir, artifacts.get("prices"), row_limit=limit),
                "signals": _jsonable_frame(layout.reports_dir, artifacts.get("signals"), row_limit=limit),
                "weights": _jsonable_frame(layout.reports_dir, artifacts.get("weights"), row_limit=limit),
                "trades": trades or _jsonable_frame(layout.reports_dir, artifacts.get("trades"), row_limit=limit),
                "equity_curve": equity_curve or _jsonable_frame(layout.reports_dir, artifacts.get("equity_curve"), row_limit=limit),
                "period_returns": period_returns or _jsonable_frame(layout.reports_dir, artifacts.get("period_returns"), row_limit=limit),
            },
            "metrics": metrics or _read_json(layout.reports_dir, artifacts.get("metrics")),
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
