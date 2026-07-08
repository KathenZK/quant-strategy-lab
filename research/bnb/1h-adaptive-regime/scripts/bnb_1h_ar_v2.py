"""BNB-1H-Adaptive-Regime-V2: clean-parameter version of V1.

V2 keeps only the parameters that affect the V1 trade path; every removed
no-op field is pinned to the neutral replacement value that the V1 full
ablation verified as trade-path invariant. Running this module as a script
verifies trade-path equality against the frozen V1 primary and writes the
multi-window backtest evidence.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_bnb_1h_adaptive_regime_search.py"
FREEZE_JSON = (
    ARTIFACT_DIR / "bnb_1h_ar_cap3_highwin_frozen_primary_2026-07-06-cap3-highwin.json"
)
DATE_TAG = "2026-07-07"
MULTIWINDOW_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v2_multiwindow_{DATE_TAG}.csv"
VERIFICATION_JSON = ARTIFACT_DIR / f"bnb_1h_ar_v2_verification_{DATE_TAG}.json"
REPORT_MD = NOTES_DIR / f"bnb-1h-ar-v2-multiwindow-backtest-{DATE_TAG}.md"

MAX_LEVERAGE = 3.0
PRIORITIES = (2.1431344645719372, 1.8729418183646944)

# Active parameters (documented in the clean version spec). Removed no-op
# fields are set to ablation-verified neutral values below.
EMA_PULLBACK_V2: dict[str, Any] = {
    "name": "BNB_1H_AR_V2_EMA_PULLBACK",
    "style": "ema_pullback",
    "side_mode": "both",
    "ema_fast": 55,
    "ema_slow": 89,
    "ema_htf": 377,
    "indicator_window": 14,
    "threshold_low": 0.0,
    "threshold_high": 100.0,
    "band_k": 0.0,
    "pullback_atr": -0.25,
    "roc_window": 12,
    "roc_threshold_bps": 0.0,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "min_adx": 0.0,
    "max_adx": 100.0,
    "min_rvol": 1.0,
    "min_atr_bps": 50.0,
    "max_atr_bps": 10_000.0,
    "min_dir_roc_bps": -10_000.0,
    "max_dist_ema_bps": 300.0,
    "htf_mode": "none",
    "require_macd_turn": False,
    "require_body_dir": False,
    "max_aligned_funding_bps": 10_000.0,
    "exit_kind": "fixed",
    "tp_atr": 3.0,
    "sl_atr": 5.0,
    "trail_activation_atr": 100_000.0,
    "trail_atr": 100_000.0,
    "max_hold_bars": 168,
    "cooldown_bars": 6,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 2.0,
    "risk_fraction": 0.01,
    "max_leverage": 1.0,
}

WICK_REJECT_V2: dict[str, Any] = {
    "name": "BNB_1H_AR_V2_WICK_REJECT",
    "style": "wick_reject",
    "side_mode": "both",
    "ema_fast": 21,
    "ema_slow": 144,
    "ema_htf": 55,
    "indicator_window": 14,
    "threshold_low": 0.35,
    "threshold_high": 0.85,
    "band_k": 0.5,
    "pullback_atr": 0.0,
    "roc_window": 12,
    "roc_threshold_bps": 0.0,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "min_adx": 24.0,
    "max_adx": 100.0,
    "min_rvol": 2.0,
    "min_atr_bps": 0.0,
    "max_atr_bps": 10_000.0,
    "min_dir_roc_bps": -10_000.0,
    "max_dist_ema_bps": 100_000.0,
    "htf_mode": "h12",
    "require_macd_turn": False,
    "require_body_dir": False,
    "max_aligned_funding_bps": 10_000.0,
    "exit_kind": "fixed",
    "tp_atr": 1.0,
    "sl_atr": 5.0,
    "trail_activation_atr": 100_000.0,
    "trail_atr": 100_000.0,
    "max_hold_bars": 72,
    "cooldown_bars": 24,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 0.75,
    "risk_fraction": 0.01,
    "max_leverage": 1.0,
}

# Fields the V2 spec treats as active/behavioral per component.
ACTIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "ema_pullback": (
        "side_mode",
        "ema_fast",
        "ema_slow",
        "ema_htf",
        "pullback_atr",
        "min_rvol",
        "min_atr_bps",
        "max_dist_ema_bps",
        "exit_kind",
        "tp_atr",
        "sl_atr",
        "max_hold_bars",
        "cooldown_bars",
        "fixed_leverage",
    ),
    "wick_reject": (
        "side_mode",
        "threshold_low",
        "threshold_high",
        "band_k",
        "min_adx",
        "min_rvol",
        "htf_mode",
        "exit_kind",
        "tp_atr",
        "sl_atr",
        "max_hold_bars",
        "cooldown_bars",
        "fixed_leverage",
    ),
}


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("bnb_1h_base_search", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load base search script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def load_context() -> dict[str, Any]:
    base = load_base()
    engine = base.load_engine()
    raw_frame, funding, quality = base.load_data()
    frame = engine.add_features(raw_frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    split = {
        key: pd.Timestamp(value)
        for key, value in freeze["split"].items()
        if key
        in {"train_start", "train_end", "validation_end", "oos_start", "full_end"}
    }
    return {
        "base": base,
        "engine": engine,
        "frame": frame,
        "funding_times": funding_times,
        "funding_cumulative": funding_cumulative,
        "quality": quality,
        "freeze": freeze,
        "split": split,
    }


def v1_configs(engine: Any, freeze: dict[str, Any]) -> tuple[Any, ...]:
    configs = []
    for cfg_dict in freeze["configs"]:
        cfg = engine.StrategyConfig(**cfg_dict)
        configs.append(
            replace(
                cfg,
                fixed_leverage=min(float(cfg.fixed_leverage), MAX_LEVERAGE),
                max_leverage=min(float(cfg.max_leverage), MAX_LEVERAGE),
                entry_delay_bars=1,
            )
        )
    return tuple(configs)


def v2_configs(engine: Any) -> tuple[Any, ...]:
    return (
        engine.StrategyConfig(**EMA_PULLBACK_V2),
        engine.StrategyConfig(**WICK_REJECT_V2),
    )


def simulate_component(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    cfg: Any,
    *,
    start: pd.Timestamp | None = None,
) -> list[Any]:
    signal = engine.build_signal(frame, cfg)
    if start is not None:
        allowed = frame["ts"] + pd.Timedelta(hours=cfg.entry_delay_bars) >= start
        signal = signal.copy()
        signal[~allowed.to_numpy()] = 0
    return engine.simulate_trades(frame, signal, cfg, funding_times, funding_cumulative)


def simulate_strategy(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    configs: tuple[Any, ...],
    priorities: tuple[float, ...] = PRIORITIES,
    *,
    start: pd.Timestamp | None = None,
) -> list[Any]:
    parts = [
        simulate_component(
            engine, frame, funding_times, funding_cumulative, cfg, start=start
        )
        for cfg in configs
    ]
    if len(parts) == 1:
        return parts[0]
    return engine.merge_trade_sets(parts[0], parts[1], priorities[0], priorities[1])


def trade_signature(trades: list[Any]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            trade.style,
            trade.signal_i,
            trade.entry_i,
            trade.exit_i,
            trade.side,
            trade.exit_reason,
            round(float(trade.entry_price), 8),
            round(float(trade.exit_price), 8),
            round(float(trade.exposure), 8),
            round(float(trade.equity_ret), 12),
        )
        for trade in trades
    )


def metric_bundle(
    engine: Any,
    trades: list[Any],
    oos_trades: list[Any],
    split: dict[str, pd.Timestamp],
) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, split["train_start"], split["train_end"]),
        "validation": engine.metrics(trades, split["train_end"], split["oos_start"]),
        "prefit": engine.metrics(trades, split["train_start"], split["oos_start"]),
        "holdout": engine.metrics(oos_trades, split["oos_start"], split["full_end"]),
        "full": engine.metrics(trades, split["train_start"], split["full_end"]),
    }


def multiwindow_rows(
    engine: Any,
    trades: list[Any],
    oos_trades: list[Any],
    split: dict[str, pd.Timestamp],
) -> list[dict[str, Any]]:
    full_end = split["full_end"]
    oos_start = split["oos_start"]
    windows: list[tuple[str, pd.Timestamp, pd.Timestamp]] = [
        ("train", split["train_start"], split["train_end"]),
        ("validation", split["train_end"], oos_start),
        ("prefit", split["train_start"], oos_start),
        ("locked_oos", oos_start, full_end),
        ("full", split["train_start"], full_end),
    ]
    cursor = split["train_start"]
    block = 1
    while cursor < full_end:
        right = min(full_end, cursor + pd.Timedelta(days=90))
        windows.append((f"block_90d_{block:02d}", cursor, right))
        cursor = right
        block += 1
    recent: list[tuple[str, Any]] = [
        ("last_1d", pd.Timedelta(days=1)),
        ("last_7d", pd.Timedelta(days=7)),
        ("last_1m", pd.DateOffset(months=1)),
        ("last_3m", pd.DateOffset(months=3)),
        ("last_6m", pd.DateOffset(months=6)),
        ("last_1y", pd.DateOffset(years=1)),
    ]
    for name, delta in recent:
        windows.append((name, max(split["train_start"], full_end - delta), full_end))
    rows = []
    for name, left, right in windows:
        source = oos_trades if left >= oos_start else trades
        rows.append(
            {"window": name, "start": left, "end": right, **engine.metrics(source, left, right)}
        )
    return rows


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2f}x"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    ctx = load_context()
    engine = ctx["engine"]
    frame = ctx["frame"]
    funding_times = ctx["funding_times"]
    funding_cumulative = ctx["funding_cumulative"]
    split = ctx["split"]

    v1 = v1_configs(engine, ctx["freeze"])
    v2 = v2_configs(engine)
    v1_trades = simulate_strategy(engine, frame, funding_times, funding_cumulative, v1)
    v2_trades = simulate_strategy(engine, frame, funding_times, funding_cumulative, v2)
    if trade_signature(v1_trades) != trade_signature(v2_trades):
        raise RuntimeError("V2 clean config drifted from the V1 trade path")
    v2_oos_trades = simulate_strategy(
        engine, frame, funding_times, funding_cumulative, v2, start=split["oos_start"]
    )

    bundle = metric_bundle(engine, v2_trades, v2_oos_trades, split)
    rows = multiwindow_rows(engine, v2_trades, v2_oos_trades, split)
    pd.DataFrame(rows).to_csv(MULTIWINDOW_CSV, index=False)

    payload = {
        "family": "BNB-1H-Adaptive-Regime",
        "version": "BNB-1H-Adaptive-Regime-V2",
        "status": "clean_equivalent_verified_not_promoted",
        "trade_path_equals_v1": True,
        "trades": len(v2_trades),
        "data_quality": ctx["quality"],
        "split": ctx["freeze"]["split"],
        "priorities": PRIORITIES,
        "metrics": bundle,
        "configs": [EMA_PULLBACK_V2, WICK_REJECT_V2],
    }
    VERIFICATION_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# BNB-1H-Adaptive-Regime-V2 多时间窗口回测 - 2026-07-07",
        "",
        "## 结论",
        "",
        "`BNB-1H-Adaptive-Regime-V2` 是 V1 的 clean 参数版本；本次逐笔重放确认 V2 与 V1 交易路径完全一致（trade signature 相等，共 `"
        + str(len(v2_trades))
        + "` 笔）。V2 状态仍为 `diagnostic observation / not promoted / not live-ready`；本报告的分片仅作冻结后审计，不参与选参。",
        "",
        "## 口径",
        "",
        "- Market：Binance USD-M Futures `BNBUSDT` perpetual `1h`。",
        f"- 数据：UTC `{ctx['quality']['first_ts']}` 至 `{ctx['quality']['last_ts']}`；`{ctx['quality']['rows']}` 根闭合 K；missing/duplicate=`0/0`。数据集与 V1 冻结时一致，未重新刷新；所有窗口锚定数据集末端。",
        "- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，逐笔计入 Binance 历史 funding。",
        "- 执行：闭合 K 信号，下一根 open 成交；bracket 立即生效；同 K 双触发 stop-first；open 穿 stop 按 open 成交。",
        f"- 杠杆：component 固定 `2.0x` / `0.75x`，硬上限 `<= {MAX_LEVERAGE:.0f}x`。",
        "",
        "## 分片结果",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | `{pct(row['total_return'])}` | "
            f"`{pct(row['max_dd'])}` | `{pct(row['win_rate'])}` | `{int(row['trades'])}` | "
            f"`{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## Promotion 边界",
            "",
            "V2 与 V1 交易路径等价，locked OOS 失败结论不变（`0.64x / -22.86% DD / 68.42% win`）。禁止 candidate、paper-live、dry-run、handoff 或 live。",
            "",
            "## 产物",
            "",
            f"- `{VERIFICATION_JSON.relative_to(ROOT)}`",
            f"- `{MULTIWINDOW_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            json_safe(
                {
                    "trade_path_equals_v1": True,
                    "trades": len(v2_trades),
                    "prefit": bundle["prefit"],
                    "holdout": bundle["holdout"],
                    "full": bundle["full"],
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
