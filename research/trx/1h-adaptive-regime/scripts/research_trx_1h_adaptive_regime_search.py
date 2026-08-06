from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
import random
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse, MarketType
from strategy_lab.data.settings import load_settings

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
ENGINE_PATH = ROOT / "research/_shared-kernels/1h-adaptive-regime-search/v1/engine.py"
ENGINE_SHA256 = "0420ea44854201e17d4bf5b9142fb8335d143e78772656473a1dcf4594a5f04c"
FRAME_START = pd.Timestamp("2024-07-03T06:00:00Z")
FRAME_END = pd.Timestamp("2026-07-03T06:00:00Z")
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=trx_usdt_usdt/funding.parquet"
)
DATE_TAG = "2026-07-03"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_adaptive_regime_search_{DATE_TAG}.json"
PREFIT_CSV = ARTIFACT_DIR / f"trx_1h_adaptive_regime_prefit_{DATE_TAG}.csv"
RANKING_CSV = ARTIFACT_DIR / f"trx_1h_adaptive_regime_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_adaptive_regime_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"trx_1h_adaptive_regime_top_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"trx-1h-adaptive-regime-search-{DATE_TAG}.md"

TARGET_ANNUAL_MULTIPLE = 10.0
TARGET_WIN_RATE = 0.50
TARGET_MAX_DD = -0.20
WARMUP_DAYS = 45
LOCKED_OOS_MONTHS = 3

_WORK_ENGINE: Any | None = None
_WORK_FRAME: pd.DataFrame | None = None
_WORK_FUNDING_TIMES: np.ndarray | None = None
_WORK_FUNDING_CUMULATIVE: np.ndarray | None = None
_WORK_TRAIN_START: pd.Timestamp | None = None
_WORK_TRAIN_END: pd.Timestamp | None = None
_WORK_OOS_START: pd.Timestamp | None = None


def load_engine() -> Any:
    actual_hash = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if actual_hash != ENGINE_SHA256:
        raise RuntimeError(
            f"Search engine drift: expected {ENGINE_SHA256}, got {actual_hash}"
        )
    spec = importlib.util.spec_from_file_location("trx_1h_search_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load search engine: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.TARGET_ANNUAL_MULTIPLE = TARGET_ANNUAL_MULTIPLE
    module.TARGET_WIN_RATE = TARGET_WIN_RATE
    module.TARGET_MAX_DD = TARGET_MAX_DD
    module.MIN_PREFIT_TRADES = 40
    module.MIN_VALIDATION_TRADES = 10
    module.MIN_HOLDOUT_TRADES = 12
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Broad locked-three-month-OOS TRXUSDT 1h adaptive-regime search."
    )
    parser.add_argument("--random-configs", type=int, default=300_000)
    parser.add_argument("--seed", type=int, default=20260703)
    parser.add_argument("--prefit-keep", type=int, default=600)
    parser.add_argument("--holdout-keep", type=int, default=250)
    parser.add_argument("--progress-every", type=int, default=5_000)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--no-ensembles", action="store_true")
    return parser.parse_args()


def evaluate_config(cfg: Any) -> tuple[bool, Any | None, Any]:
    if (
        _WORK_ENGINE is None
        or _WORK_FRAME is None
        or _WORK_FUNDING_TIMES is None
        or _WORK_FUNDING_CUMULATIVE is None
        or _WORK_TRAIN_START is None
        or _WORK_TRAIN_END is None
        or _WORK_OOS_START is None
    ):
        raise RuntimeError("Search worker state was not initialized")
    signal = _WORK_ENGINE.build_signal(_WORK_FRAME, cfg)
    if int(np.count_nonzero(signal)) < 6:
        return False, None, cfg
    trades = _WORK_ENGINE.simulate_trades(
        _WORK_FRAME,
        signal,
        cfg,
        _WORK_FUNDING_TIMES,
        _WORK_FUNDING_CUMULATIVE,
    )
    candidate = _WORK_ENGINE.candidate_from_config(
        cfg,
        trades,
        _WORK_TRAIN_START,
        _WORK_TRAIN_END,
        _WORK_OOS_START,
    )
    return True, candidate, cfg


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _load_funding() -> pd.DataFrame:
    if not FUNDING_PATH.exists():
        raise FileNotFoundError(
            "TRX funding history is missing from the normalized data lake."
        )
    funding = pd.read_parquet(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = (
        funding.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if funding.empty or funding["funding_rate"].isna().any():
        raise RuntimeError("TRX funding history is empty or contains null rates")
    return funding


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    warehouse = DuckDBWarehouse(
        DataLakeLayout.from_settings(load_settings(None))
    )
    frame = warehouse.load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="TRX/USDT:USDT",
        timeframe="1h",
        start=FRAME_START,
        end=FRAME_END,
    )
    trusted_audit = frame.attrs.get("ohlcv_audit", {})
    frame = frame.reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="1h")
    missing = expected.difference(pd.DatetimeIndex(frame["ts"]))
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
    nulls = {column: int(frame[column].isna().sum()) for column in required}
    violations = {
        "high_lt_open_close": int(
            (frame["high"] < frame[["open", "close"]].max(axis=1)).sum()
        ),
        "low_gt_open_close": int(
            (frame["low"] > frame[["open", "close"]].min(axis=1)).sum()
        ),
        "nonpositive_ohlc": int(
            ((frame[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
        ),
        "negative_volume": int((frame["volume"] < 0).sum()),
        "negative_quote_volume": int((frame["quote_volume"] < 0).sum()),
    }
    blockers = (
        len(missing)
        + sum(nulls.values())
        + sum(violations.values())
        + int(set(frame["is_closed"].unique()) != {True})
    )
    if blockers:
        raise RuntimeError(
            f"TRXUSDT 1h exact research frame has data-quality blockers: "
            f"missing={len(missing)} nulls={nulls} violations={violations}"
        )
    funding = _load_funding()
    metadata = {
        "source": "trusted_normalized_data_lake",
        "ohlcv_audit": trusted_audit,
    }
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "missing_bars": int(len(missing)),
        "duplicate_bars": 0,
        "critical_nulls": nulls,
        "ohlcv_violations": violations,
        "funding_rows": int(len(funding)),
        "funding_first_ts": funding["ts"].iloc[0].isoformat(),
        "funding_last_ts": funding["ts"].iloc[-1].isoformat(),
        "source_counts": {
            str(key): int(value)
            for key, value in frame["source"].value_counts().items()
        },
        "fetch_metadata": metadata,
    }
    return frame, funding, quality


def trx_name(name: str) -> str:
    return name.replace("HYPE_1H_AR", "TRX_1H_AR")


def pct(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def make_report(
    engine: Any,
    *,
    quality: dict[str, Any],
    split: dict[str, str],
    search_counts: dict[str, int],
    finalists: list[Any],
    best: Any,
    slices: list[dict[str, Any]],
) -> str:
    holdout = best.holdout or engine.empty_metrics(1.0)
    full = best.full or engine.empty_metrics(1.0)
    target_hits = sum(candidate.target_pass for candidate in finalists)
    prefit_hits = sum(candidate.prefit_pass for candidate in finalists)
    lines = [
        "# TRX-1H-Adaptive-Regime 广泛搜索 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            "至少一个冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛；这只允许进入稳健性和 live-executable 审计，不代表已可实盘。"
            if target_hits
            else "没有任何冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛，当前结论为 `NO-GO / not promoted / not live-ready`。"
        ),
        "",
        f"- finalists：`{len(finalists)}`；prefit pass：`{prefit_hits}`；locked target pass：`{target_hits}`。",
        "- 目标：年化权益倍率 `>=10.0x`（annual return `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。",
        "",
        "## 数据质量",
        "",
        f"- Binance USD-M Futures `TRXUSDT` perpetual `1h`：`{quality['rows']}` 根闭合 K。",
        f"- UTC：`{quality['first_ts']}` 至 `{quality['last_ts']}`。",
        f"- missing=`{quality['missing_bars']}`，duplicate=`{quality['duplicate_bars']}`，funding rows=`{quality['funding_rows']}`。",
        "",
        "## 防泄漏时间切分",
        "",
        f"- warmup/raw start：`{split['raw_start']}` / `{split['train_start']}`。",
        f"- train：`{split['train_start']}` 至 `{split['train_end']}`。",
        f"- validation：`{split['train_end']}` 至 `{split['validation_end']}`。",
        f"- locked OOS（固定最近三个月）：`{split['oos_start']}` 至 `{split['full_end']}`。",
        "- 参数生成、打分、保留和 ensemble 仅使用 train + validation；OOS 只对冻结 finalists 解锁一次。",
        "",
        "## 执行与成本",
        "",
        "- 闭合 `1h` K 生成信号，下一根 open 市价入场；单仓、不加仓。",
        "- 入场后立即具备 ATR stop/TP；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。",
        "- trailing 仅在完整 K 结束后更新，更新后的 stop 从下一根 K 生效。",
        f"- fee `{engine.FEE_PER_FILL:.4%}/fill`，slippage `{engine.SLIPPAGE_PER_FILL:.4%}/fill`，另逐笔计入真实 Binance funding。",
        "",
        "## 搜索覆盖",
        "",
    ]
    lines.extend(f"- {key}：`{value}`。" for key, value in search_counts.items())
    lines.extend(
        [
            "- 机制：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d regime、funding filter、fixed/risk sizing、fixed/trailing exit。",
            "",
            "## 最佳冻结 finalist",
            "",
            f"- id：`{best.name}`；kind/style：`{best.kind}` / `{best.styles}`。",
            f"- full：annual `{mult(full['annual_multiple'])}`，return `{pct(full['total_return'])}`，DD `{pct(full['max_dd'])}`，win `{pct(full['win_rate'])}`，trades `{int(full['trades'])}`，PF `{full['profit_factor']:.3f}`。",
            f"- locked OOS：annual `{mult(holdout['annual_multiple'])}`，return `{pct(holdout['total_return'])}`，DD `{pct(holdout['max_dd'])}`，win `{pct(holdout['win_rate'])}`，trades `{int(holdout['trades'])}`，PF `{holdout['profit_factor']:.3f}`。",
            f"- hard gate：`{best.target_pass}`。",
            "",
            "## 时间切片",
            "",
            "| Window | Annual | Return | DD | Win | Trades | PF |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | `{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | `{pct(row['win_rate'])}` | `{int(row['trades'])}` | `{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## Promotion 边界",
            "",
            (
                "硬门槛命中只进入延迟、成本、邻域、时间稳定性与生产状态机审计；审计前禁止标记为 candidate/paper-live/live。"
                if target_hits
                else "locked hard gate 未通过，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。"
            ),
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{PREFIT_CSV.relative_to(ROOT)}`",
            f"- `{RANKING_CSV.relative_to(ROOT)}`",
            f"- `{SLICES_CSV.relative_to(ROOT)}`",
            f"- `{TRADES_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    engine = load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=WARMUP_DAYS)
    oos_start = full_end - pd.DateOffset(months=LOCKED_OOS_MONTHS)
    if not train_start < oos_start < full_end:
        raise RuntimeError("Invalid train/OOS split")
    prefit_span = oos_start - train_start
    train_end = train_start + prefit_span * 0.65
    split = {
        "raw_start": raw_start.isoformat(),
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "validation_end": oos_start.isoformat(),
        "oos_start": oos_start.isoformat(),
        "full_end": full_end.isoformat(),
    }
    print(f"data rows={len(frame)} split={split}", flush=True)

    rng = random.Random(args.seed)
    configs = [
        replace(cfg, name=trx_name(cfg.name)) for cfg in engine.curated_configs()
    ]
    random_offset = len(configs)
    configs.extend(
        replace(
            engine.random_config(rng, index + random_offset),
            name=f"TRX_1H_AR_R{index + random_offset:06d}",
        )
        for index in range(args.random_configs)
    )

    global _WORK_ENGINE
    global _WORK_FRAME
    global _WORK_FUNDING_TIMES
    global _WORK_FUNDING_CUMULATIVE
    global _WORK_TRAIN_START
    global _WORK_TRAIN_END
    global _WORK_OOS_START
    _WORK_ENGINE = engine
    _WORK_FRAME = frame
    _WORK_FUNDING_TIMES = funding_times
    _WORK_FUNDING_CUMULATIVE = funding_cumulative
    _WORK_TRAIN_START = train_start
    _WORK_TRAIN_END = train_end
    _WORK_OOS_START = oos_start

    retained: list[tuple[Any, Any]] = []
    evaluated = 0
    eligible = 0
    prefit_passes = 0
    workers = max(1, args.workers)
    if workers == 1:
        results = map(evaluate_config, configs)
        pool = None
    else:
        pool = mp.get_context("fork").Pool(processes=workers)
        results = pool.imap(evaluate_config, configs, chunksize=64)
    try:
        for index, (was_evaluated, candidate, cfg) in enumerate(results, start=1):
            evaluated += int(was_evaluated)
            if candidate is not None:
                eligible += 1
                prefit_passes += int(candidate.prefit_pass)
                retained = engine.retain_candidate(
                    retained, (candidate, cfg), args.prefit_keep
                )
            if index % args.progress_every == 0 and retained:
                current = max(
                    retained, key=lambda item: engine.candidate_sort_key(item[0])
                )[0]
                print(
                    f"search {index}/{len(configs)} evaluated={evaluated} "
                    f"eligible={eligible} prefit_pass={prefit_passes} "
                    f"retained={len(retained)} best={current.name} "
                    f"score={current.prefit_score:.3f} "
                    f"ann={current.prefit['annual_multiple']:.3f} "
                    f"dd={current.prefit['max_dd']:.3f}",
                    flush=True,
                )
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    retained = sorted(
        retained,
        key=lambda item: engine.candidate_sort_key(item[0]),
        reverse=True,
    )[: args.prefit_keep]
    if not retained:
        raise RuntimeError("No eligible TRX configs survived the prefit gates")
    config_map = {cfg.name: cfg for _candidate, cfg in retained}
    pd.DataFrame(
        [
            engine.candidate_row(candidate, config_map)
            for candidate, _cfg in retained
        ]
    ).to_csv(PREFIT_CSV, index=False)
    print(
        f"single search done generated={len(configs)} evaluated={evaluated} "
        f"eligible={eligible} prefit_pass={prefit_passes} "
        f"retained={len(retained)}",
        flush=True,
    )

    ensembles: list[tuple[Any, tuple[Any, Any], list[Any]]] = []
    if not args.no_ensembles:
        ensembles = engine.make_ensembles(
            retained,
            frame,
            funding_times,
            funding_cumulative,
            train_start,
            train_end,
            oos_start,
        )
        print(f"ensembles retained={len(ensembles)}", flush=True)

    finalists: list[tuple[Any, list[Any]]] = []
    for candidate, cfg in retained[: args.holdout_keep]:
        trades = engine.simulate_trades(
            frame,
            engine.build_signal(frame, cfg),
            cfg,
            funding_times,
            funding_cumulative,
        )
        finalists.append(
            (
                engine.finalize_candidate(
                    candidate, trades, train_start, oos_start, full_end
                ),
                trades,
            )
        )
    for candidate, _cfg_pair, trades in ensembles[: args.holdout_keep]:
        finalists.append(
            (
                engine.finalize_candidate(
                    candidate, trades, train_start, oos_start, full_end
                ),
                trades,
            )
        )
    # The locked OOS may validate a candidate, but must never choose the champion.
    # Preserve the prefit ordering after all finalists are evaluated.
    finalists.sort(
        key=lambda item: engine.candidate_sort_key(item[0]), reverse=True
    )
    best, best_trades = finalists[0]
    ranking = pd.DataFrame(
        [
            engine.candidate_row(candidate, config_map)
            for candidate, _trades in finalists
        ]
    )
    ranking.to_csv(RANKING_CSV, index=False)
    slices = engine.diagnostic_slices(
        best_trades, train_start, train_end, oos_start, full_end
    )
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(best_trades)).to_csv(TRADES_CSV, index=False)

    search_counts = {
        "curated_configs": len(configs) - args.random_configs,
        "random_configs": args.random_configs,
        "generated_configs": len(configs),
        "evaluated_configs": evaluated,
        "prefit_eligible": eligible,
        "prefit_pass_observations": prefit_passes,
        "retained_single": len(retained),
        "retained_ensembles": len(ensembles),
        "locked_finalists": len(finalists),
        "locked_target_pass": sum(
            candidate.target_pass for candidate, _trades in finalists
        ),
    }
    used_names = set(best.config_names.split("+"))
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "family_id": "TRX-1H-AR",
        "status": (
            "hard_gate_hit_pending_robustness_not_promoted"
            if any(candidate.target_pass for candidate, _ in finalists)
            else "no_go_not_promoted"
        ),
        "targets": {
            "annual_multiple": TARGET_ANNUAL_MULTIPLE,
            "annual_return": TARGET_ANNUAL_MULTIPLE - 1.0,
            "win_rate": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "split": split,
        "quality": quality,
        "search_counts": search_counts,
        "best": engine.candidate_row(best, config_map),
        "best_configs": {
            name: asdict(config_map[name])
            for name in used_names
            if name in config_map
        },
        "top_20": [
            engine.candidate_row(candidate, config_map)
            for candidate, _trades in finalists[:20]
        ],
        "slices": slices,
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(
        make_report(
            engine,
            quality=quality,
            split=split,
            search_counts=search_counts,
            finalists=[candidate for candidate, _trades in finalists],
            best=best,
            slices=slices,
        ),
        encoding="utf-8",
    )
    best_full = best.full or engine.empty_metrics(1.0)
    best_oos = best.holdout or engine.empty_metrics(1.0)
    print(
        f"best={best.name} target_pass={best.target_pass} "
        f"full_ann={best_full['annual_multiple']:.3f} "
        f"full_dd={best_full['max_dd']:.3f} "
        f"oos_ann={best_oos['annual_multiple']:.3f} "
        f"oos_dd={best_oos['max_dd']:.3f}",
        flush=True,
    )
    print(f"wrote {SUMMARY_JSON}", flush=True)
    print(f"wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
