"""V39 空头专项结构微调。

背景：V39 空头入场要求 15m EMA96/384 spread < 0（慢速趋势过滤，约等于 24h/96h 均线），
导致"连续明显下跌但均线尚未翻空"的区间完全不开空。上一轮只放宽
short_adx_min / short_vol_min 已被否决；本轮改为替换或叠加更快的空头趋势确认结构：

- fast   : 用 15m EMA24/96 spread < 0（约 6h/24h）替换慢速过滤。
- di     : 用 15m -DI28 > +DI28 动能条件替换慢速过滤。
- fast_di: 快速 spread 与 DI 同时成立才替换。
- or_path: 保留原慢速过滤，同时允许 (fast & di) 作为额外空头路径（增量式）。

多头侧全部冻结在 V39（long_vol_min=0.35，其余同 V35）。
每个变体跑组合腿与空头 standalone 腿；成本 0.00085/fill 含 funding。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as tune
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
FAST_EMA = 24
SLOW_EMA = 96  # 与 V35 ema_fast 相同，直接复用 features["ema_fast"]


@dataclass(frozen=True, slots=True)
class ShortSpec:
    name: str
    mode: str  # v39 / fast / di / fast_di / or_path
    short_adx_min: float
    short_vol_min: float
    note: str = ""


def build_signals(
    features: pd.DataFrame,
    config: base.V35Config,
    spec: ShortSpec,
    allow_long: bool,
) -> pd.DataFrame:
    out = features.copy()
    long_signal = (
        out["ema_spread"].gt(0.0)
        & out["adx"].ge(config.long_adx_min)
        & out["volume_surge"].ge(config.long_vol_min)
        & out["h1_adx"].gt(config.h1_long_adx_min)
        & out["h1_plus_di"].gt(out["h1_minus_di"])
    )
    base_short = out["adx"].ge(spec.short_adx_min) & out["volume_surge"].ge(spec.short_vol_min)
    slow_bear = out["ema_spread"].lt(0.0)
    fast_bear = out["fast_spread"].lt(0.0)
    di_bear = out["minus_di"].gt(out["plus_di"])
    if spec.mode == "v39":
        short_signal = base_short & slow_bear
    elif spec.mode == "fast":
        short_signal = base_short & fast_bear
    elif spec.mode == "di":
        short_signal = base_short & di_bear
    elif spec.mode == "fast_di":
        short_signal = base_short & fast_bear & di_bear
    elif spec.mode == "or_path":
        short_signal = base_short & (slow_bear | (fast_bear & di_bear))
    else:
        raise ValueError(f"unknown short mode: {spec.mode}")
    if not allow_long:
        long_signal &= False
    conflict = long_signal & short_signal
    out["long_signal"] = long_signal & ~conflict
    out["short_signal"] = short_signal & ~conflict
    return out


def run_variant(
    spec: ShortSpec,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
    allow_long: bool,
) -> base.RunResult:
    cfg = replace(config, short_adx_min=spec.short_adx_min, short_vol_min=spec.short_vol_min)
    suffix = "" if allow_long else "_short_leg"
    signals = build_signals(features, cfg, spec, allow_long)
    return base.run_backtest(spec.name + suffix, frame, funding, signals, cfg, tune.NO_FLOOR)


def print_variant(row: dict[str, Any]) -> None:
    full = row["combined"]["full"]
    d90 = row["combined"]["d90"]
    short = row["combined"]["short_side"]
    leg = row["short_leg"]["full"]
    print(
        f"{row['name']:>22} | full {full['return_pct']:>9.2f}% dd {full['max_drawdown_pct']:>7.2f}% "
        f"sh {row['combined']['sharpe']:>5.2f} "
        f"| 90d {d90['return_pct']:>8.2f}% dd {d90['max_drawdown_pct']:>7.2f}% "
        f"| shorts n {short['trades']:>3} win {short['win_rate_pct'] or 0:>6.2f}% "
        f"avg {short['avg_trade_return_pct'] or 0:>6.2f}% "
        f"| leg {leg['return_pct']:>8.2f}% dd {leg['max_drawdown_pct']:>7.2f}%"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)

    v39_cfg = replace(base.V35Config(), long_vol_min=0.35, short_target_atr_pct=0.022)
    features = base.build_features(frame, v39_cfg)
    ema_fast24 = features["close"].ewm(span=FAST_EMA, adjust=False, min_periods=FAST_EMA).mean()
    features["fast_spread"] = ema_fast24 / features["ema_fast"] - 1.0

    specs: list[ShortSpec] = [ShortSpec("v39", "v39", 36.0, 0.50, note="V39 注册基线")]
    for mode in ["fast", "di", "fast_di", "or_path"]:
        for adx in [32.0, 34.0, 36.0]:
            for vol in [0.35, 0.50]:
                vol_tag = str(vol).replace(".", "")
                specs.append(ShortSpec(f"{mode}_adx{int(adx)}_v{vol_tag}", mode, adx, vol))

    rows: list[dict[str, Any]] = []
    combined_runs: dict[str, base.RunResult] = {}
    for spec in specs:
        combined = run_variant(spec, frame, funding, features, v39_cfg, allow_long=True)
        short_leg = run_variant(spec, frame, funding, features, v39_cfg, allow_long=False)
        combined_runs[spec.name] = combined
        row = {
            "name": spec.name,
            "mode": spec.mode,
            "short_adx_min": spec.short_adx_min,
            "short_vol_min": spec.short_vol_min,
            "note": spec.note,
            "combined": {
                "full": tune.window_stats(combined, None),
                "sharpe": combined.metrics["sharpe"],
                "d90": tune.window_stats(combined, 90),
                "d30": tune.window_stats(combined, 30),
                "short_side": tune.side_stats(combined, -1),
                "long_side": tune.side_stats(combined, 1),
            },
            "short_leg": {
                "full": tune.window_stats(short_leg, None),
                "sharpe": short_leg.metrics["sharpe"],
                "d90": tune.window_stats(short_leg, 90),
            },
        }
        rows.append(row)
        print_variant(row)

    baseline = rows[0]
    base_full = baseline["combined"]["full"]
    candidates = []
    for row in rows[1:]:
        full = row["combined"]["full"]
        short = row["combined"]["short_side"]
        row["passes_constraints"] = bool(
            full["max_drawdown_pct"] >= base_full["max_drawdown_pct"] - 0.5
            and full["return_pct"] >= base_full["return_pct"] * 0.85
            and short["trades"] > baseline["combined"]["short_side"]["trades"]
            and (short["avg_trade_return_pct"] or -99.0) >= 3.0
        )
        candidates.append(row)
    candidates.sort(
        key=lambda r: (
            r["passes_constraints"],
            r["combined"]["full"]["return_pct"],
        ),
        reverse=True,
    )
    print("\n=== ranked (constraints: dd/-return/short count/short avg) ===")
    for row in candidates[:10]:
        marker = "PASS" if row["passes_constraints"] else "----"
        print(f"[{marker}]", end=" ")
        print_variant(row)

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V39 short-side structure tune",
        "data_quality": quality,
        "cost_model": "Binance perp, 0.00085 per fill (fee + 4bps slippage combined, V35/V39 canonical), funding included.",
        "selection_disclosure": "全窗口与最近 90 天均参与本轮空头结构选参；标准分片仅对最终候选复核。",
        "base_config": asdict(v39_cfg),
        "fast_spread_definition": f"15m EMA{FAST_EMA}/EMA{SLOW_EMA} - 1，快速空头趋势确认。",
        "rows": rows,
        "standard_slices": {
            name: run.slices
            for name, run in combined_runs.items()
            if name == "v39" or any(r["name"] == name and r.get("passes_constraints") for r in rows)
        },
    }
    out_path = ARTIFACT_DIR / "hype_ema_tb_v39_short_structure_tune_2026-07-08.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nsummary -> {out_path}")


if __name__ == "__main__":
    main()
