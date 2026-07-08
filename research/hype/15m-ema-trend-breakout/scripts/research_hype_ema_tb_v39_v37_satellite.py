"""V39 + V37 early-long 卫星叠加回测。

主腿：V39（V35 + long_vol_min 0.35 + short_target_atr_pct 0.022；空头 1h EMA 确认
已证明与空头 ema_spread<0 逐字节等价，保留在 build_features 中不影响结果）。

卫星腿（V37 canonical）：只做多小仓位，V35 多头其它条件满足但 ADX28<28 时，
若 ADX14>=35 且上升、+DI14>-DI14，则 K2 open 入场，TP4ATR/SL5ATR、ADX14<22 弱势退出。

三个卫星口径：
- sat_v025 : V37 canonical，volume_surge >= 0.25。
- sat_v035 : 量能与 V39 主腿对齐，volume_surge >= 0.35。
- sat_gap  : canonical 之外，额外覆盖 V39 提高量能门槛后留下的缺口
             （ADX28>=28 但 volume_surge 在 [0.25, 0.35)，其余 V35 多头条件满足，
              且 ADX14>=35 上升、+DI14>-DI14）。

对照：V39、卫星 standalone、V39+卫星、V35+卫星（V37 复现，锚定与主账口径的差异）。
成本 0.00085/fill 含 funding。
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v37_v38_floor as v37


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_ema_tb_v39_v37_satellite_2026-07-08.json"
TRADES_PATH = ARTIFACT_DIR / "hype_ema_tb_v39_v37_satellite_trades_2026-07-08.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_ema_tb_v39_v37_satellite_equity_2026-07-08.csv"
NO_FLOOR = base.ProfitFloorConfig(enabled=False)


def satellite_signal(features: pd.DataFrame, vol_min: float, gap_mode: bool) -> pd.Series:
    common = (
        features["ema_spread"].gt(0.0)
        & features["h1_adx"].gt(18.0)
        & features["h1_plus_di"].gt(features["h1_minus_di"])
        & features["adx14"].ge(35.0)
        & features["adx14_rising"]
        & features["plus_di14"].gt(features["minus_di14"])
    )
    if gap_mode:
        # canonical 卫星区 + V39 量能缺口区（ADX28>=28 且 vol∈[0.25,0.35)）
        canonical = common & features["adx"].lt(28.0) & features["volume_surge"].ge(0.25)
        gap = (
            common
            & features["adx"].ge(28.0)
            & features["volume_surge"].ge(0.25)
            & features["volume_surge"].lt(0.35)
        )
        return canonical | gap
    return common & features["adx"].lt(28.0) & features["volume_surge"].ge(vol_min)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)

    v35_cfg = base.V35Config()
    v39_cfg = replace(v35_cfg, long_vol_min=0.35, short_target_atr_pct=0.022)
    sat_cfg = v37.SatelliteConfig()

    v39_features = v37.add_satellite_features(base.build_features(frame, v39_cfg))
    v35_features = v37.add_satellite_features(base.build_features(frame, v35_cfg))

    v39_main = v37.wrap_main_result(base.run_backtest("v39_main", frame, funding, v39_features, v39_cfg, NO_FLOOR))
    v35_main = v37.wrap_main_result(base.run_backtest("v35_main", frame, funding, v35_features, v35_cfg, NO_FLOOR))

    sat_variants = {
        "sat_v025": (0.25, False),
        "sat_v035": (0.35, False),
        "sat_gap": (0.25, True),
    }
    sat_runs: dict[str, v37.LegResult] = {}
    for name, (vol_min, gap_mode) in sat_variants.items():
        feats = v39_features.copy()
        feats["satellite_long_signal"] = satellite_signal(feats, vol_min, gap_mode)
        sat_runs[name] = v37.run_satellite(name, frame, funding, feats, v39_cfg, sat_cfg)

    v37_repro = v37.combine_legs("v37_repro_v35_plus_sat025", v35_main, sat_runs["sat_v025"])
    combos = {
        f"v39_plus_{name}": v37.combine_legs(f"v39_plus_{name}", v39_main, run)
        for name, run in sat_runs.items()
    }

    runs: list[v37.LegResult] = [v39_main, v35_main, *sat_runs.values(), v37_repro, *combos.values()]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V39 + V37 early-long satellite overlay",
        "source": "data_lake",
        "data_quality": quality,
        "execution_assumptions": {
            "main_leg": "V39 live-realistic K2-open replay (long_vol_min 0.35, short_target_atr_pct 0.022).",
            "satellite_leg": "V37 early-long reconstruction; variants differ only in volume gate / gap coverage.",
            "portfolio": "Main and satellite can overlap; combined equity uses per-bar main return + satellite return before compounding.",
            "cost": "0.00085 per fill; Binance funding aligned to 15m bars.",
        },
        "main_config": asdict(v39_cfg),
        "satellite_config": asdict(sat_cfg),
        "satellite_variants": {
            "sat_v025": "V37 canonical: ADX28<28, volume_surge>=0.25",
            "sat_v035": "V39-aligned volume: ADX28<28, volume_surge>=0.35",
            "sat_gap": "canonical + gap: also ADX28>=28 with volume_surge in [0.25,0.35)",
        },
        "runs": [
            {
                "name": run.name,
                "metrics": run.metrics,
                "slices": run.slices,
                "last_trades": v37.last_trades(run.trades, 6),
            }
            for run in runs
        ],
        "comparison": {
            f"{name}_vs_v39": v37.metric_delta(run, v39_main) for name, run in combos.items()
        }
        | {"v37_repro_vs_v35": v37.metric_delta(v37_repro, v35_main)},
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    equity = pd.concat([run.equity_curve.rename(run.name) for run in runs], axis=1)
    equity.to_csv(EQUITY_PATH, index_label="ts")
    trades = [run.trades.assign(variant=run.name) for run in runs if not run.trades.empty]
    if trades:
        pd.concat(trades, ignore_index=True).to_csv(TRADES_PATH, index=False)
    v37.print_summary(quality, runs)
    print(f"\nsummary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
