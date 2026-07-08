from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_full_ablation_2026-07-08"


def v39_config() -> base.V35Config:
    return replace(
        base.V35Config(),
        long_vol_min=0.35,
        short_target_atr_pct=0.022,
    )


def v39_flags() -> ab.SignalFlags:
    return ab.SignalFlags(short_use_h1_ema=False)


def v39_ablation_specs(cfg: base.V35Config) -> list[ab.ExpSpec]:
    specs: list[ab.ExpSpec] = [
        ab.ExpSpec(
            "v39_base",
            cfg,
            v39_flags(),
            group="base",
            note="V39 baseline: long_vol_min=0.35, short_target_atr_pct=0.022, no short 1h EMA confirm",
        )
    ]

    def add(
        name: str,
        group: str,
        note: str = "",
        flags: ab.SignalFlags | None = None,
        **changes: Any,
    ) -> None:
        specs.append(
            ab.ExpSpec(
                name,
                replace(cfg, **changes) if changes else cfg,
                flags if flags is not None else v39_flags(),
                group,
                note,
            )
        )

    # V39-specific rollback / equivalence checks.
    add("rollback_long_vol_025", "v39_rollbacks", note="V39 long_vol_min 0.35 -> V35 0.25", long_vol_min=0.25)
    add(
        "rollback_short_target_018",
        "v39_rollbacks",
        note="V39 short_target_atr_pct 0.022 -> V35 0.018",
        short_target_atr_pct=0.018,
    )
    add(
        "restore_short_h1_ema",
        "v39_rollbacks",
        note="恢复 V35 空头 1h EMA 确认",
        flags=replace(v39_flags(), short_use_h1_ema=True),
    )

    # Sizing and target volatility.
    add("target_long_016", "sizing", note="long target 0.020->0.016", long_target_atr_pct=0.016)
    add("target_long_024", "sizing", note="long target 0.020->0.024", long_target_atr_pct=0.024)
    add("target_short_014", "sizing", note="short target 0.022->0.014", short_target_atr_pct=0.014)
    add("target_short_018", "sizing", note="short target 0.022->0.018", short_target_atr_pct=0.018)
    add("target_short_026", "sizing", note="short target 0.022->0.026", short_target_atr_pct=0.026)
    add("cap_20", "sizing", note="max_allocation 3.0->2.0", max_allocation=2.0)
    add("cap_25", "sizing", note="max_allocation 3.0->2.5", max_allocation=2.5)
    add("cap_40", "sizing", note="max_allocation 3.0->4.0", max_allocation=4.0)

    # Feature windows.
    add("ema_fast_64", "windows", ema_fast=64)
    add("ema_fast_128", "windows", ema_fast=128)
    add("ema_slow_256", "windows", ema_slow=256)
    add("ema_slow_512", "windows", ema_slow=512)
    add("adx_window_14", "windows", adx_window=14)
    add("adx_window_21", "windows", adx_window=21)
    add("adx_window_35", "windows", adx_window=35)
    add("volume_window_96", "windows", volume_window=96)
    add("volume_window_288", "windows", volume_window=288)
    add("atr_window_480", "windows", atr_window=480)
    add("atr_window_960", "windows", atr_window=960)
    add("h1_adx_window_14", "windows", h1_adx_window=14)
    add("h1_adx_window_28", "windows", h1_adx_window=28)
    add("h1_ema_fast_12", "windows", h1_ema_fast=12)
    add("h1_ema_fast_36", "windows", h1_ema_fast=36)
    add("h1_ema_slow_72", "windows", h1_ema_slow=72)
    add("h1_ema_slow_144", "windows", h1_ema_slow=144)

    # Entry thresholds and structural filters.
    add("long_adx_24", "entry", long_adx_min=24.0)
    add("long_adx_26", "entry", long_adx_min=26.0)
    add("long_adx_30", "entry", long_adx_min=30.0)
    add("long_adx_32", "entry", long_adx_min=32.0)
    add("short_adx_32", "entry", short_adx_min=32.0)
    add("short_adx_34", "entry", short_adx_min=34.0)
    add("short_adx_40", "entry", short_adx_min=40.0)
    add("long_vol_025", "entry", note="V39 多头量能门槛回退到 0.25", long_vol_min=0.25)
    add("long_vol_045", "entry", long_vol_min=0.45)
    add("no_long_volume", "entry", note="移除多头成交量过滤", long_vol_min=-10.0)
    add("short_vol_035", "entry", short_vol_min=0.35)
    add("short_vol_075", "entry", short_vol_min=0.75)
    add("no_short_volume", "entry", note="移除空头成交量过滤", short_vol_min=-10.0)
    add("h1_long_adx_14", "entry", h1_long_adx_min=14.0)
    add("h1_long_adx_22", "entry", h1_long_adx_min=22.0)
    add("no_h1_long_adx", "entry", note="移除 1h ADX 门槛", h1_long_adx_min=-1.0)
    add("no_h1_di_long", "entry", note="移除 1h +DI>-DI", flags=replace(v39_flags(), long_use_h1_di=False))
    add(
        "no_ema_spread_long",
        "entry",
        note="移除多头 EMA spread>0",
        flags=replace(v39_flags(), long_use_ema_spread=False),
    )
    add(
        "restore_h1_ema_short",
        "entry",
        note="恢复空头 1h EMA 确认",
        flags=replace(v39_flags(), short_use_h1_ema=True),
    )
    add(
        "no_ema_spread_short",
        "entry",
        note="在 V39 已移除空头 1h EMA 后，再移除 15m 空头 EMA spread<0",
        flags=replace(v39_flags(), short_use_ema_spread=False),
    )
    add("long_only", "entry", note="禁用空头", flags=replace(v39_flags(), allow_short=False))
    add("short_only", "entry", note="禁用多头", flags=replace(v39_flags(), allow_long=False))

    # Exit structure.
    add("tp_40", "exit", take_profit_atr=4.0)
    add("tp_45", "exit", take_profit_atr=4.5)
    add("tp_55", "exit", take_profit_atr=5.5)
    add("tp_60", "exit", take_profit_atr=6.0)
    add("sl_50", "exit", hard_stop_atr=5.0)
    add("sl_60", "exit", hard_stop_atr=6.0)
    add("sl_80", "exit", hard_stop_atr=8.0)
    add("sl_90", "exit", hard_stop_atr=9.0)
    add("adx_exit_20", "exit", adx_exit=20.0)
    add("adx_exit_24", "exit", adx_exit=24.0)
    add("adx_exit_26", "exit", adx_exit=26.0)
    add("no_indicator_exit", "exit", note="移除 ADX 指标退出", adx_exit=-1.0)
    add("delayed_2", "exit", delayed_bars=2)
    add("delayed_4", "exit", delayed_bars=4)
    add("disable_mfe_10", "exit", disable_after_mfe_atr=1.0)
    add("disable_mfe_20", "exit", disable_after_mfe_atr=2.0)
    add("never_disable_indicator", "exit", note="指标退出全程有效", disable_after_mfe_atr=1e9)
    add("timeout_192", "exit", max_hold_bars=192)
    add("timeout_96", "exit", max_hold_bars=96)
    add("no_timeout", "exit", note="移除 timeout", max_hold_bars=10**9)

    return specs


def add_deltas(rows: list[dict[str, Any]]) -> None:
    base_row = next(row for row in rows if row["name"] == "v39_base")
    for row in rows:
        row["delta_vs_v39"] = {
            "full_return_pp": round(row["full"]["return_pct"] - base_row["full"]["return_pct"], 2),
            "full_maxdd_pp": round(row["full"]["max_drawdown_pct"] - base_row["full"]["max_drawdown_pct"], 2),
            "sharpe": round(row["sharpe"] - base_row["sharpe"], 4),
            "trades": row["full"]["trades"] - base_row["full"]["trades"],
            "win_rate_pp": (
                round((row["full"]["win_rate_pct"] or 0.0) - (base_row["full"]["win_rate_pct"] or 0.0), 2)
                if row["full"]["win_rate_pct"] is not None
                else None
            ),
            "d90_return_pp": round(row["d90"]["return_pct"] - base_row["d90"]["return_pct"], 2),
            "d90_maxdd_pp": round(row["d90"]["max_drawdown_pct"] - base_row["d90"]["max_drawdown_pct"], 2),
            "d90_win_rate_pp": (
                round((row["d90"]["win_rate_pct"] or 0.0) - (base_row["d90"]["win_rate_pct"] or 0.0), 2)
                if row["d90"]["win_rate_pct"] is not None
                else None
            ),
        }


def print_rankings(rows: list[dict[str, Any]]) -> None:
    print("\n=== worst full-return deltas ===")
    for row in sorted(rows, key=lambda item: item["delta_vs_v39"]["full_return_pp"])[:15]:
        ab.print_row(row)
    print("\n=== best full-return deltas ===")
    for row in sorted(rows, key=lambda item: item["delta_vs_v39"]["full_return_pp"], reverse=True)[:15]:
        ab.print_row(row)
    print("\n=== best recent-90d with maxDD no worse than V39 ===")
    eligible = [
        row
        for row in rows
        if row["name"] != "v39_base"
        and row["d90"]["max_drawdown_pct"] >= rows[0]["d90"]["max_drawdown_pct"]
        and row["d90"]["trades"] >= 15
    ]
    for row in sorted(eligible, key=lambda item: item["d90"]["return_pct"], reverse=True)[:15]:
        ab.print_row(row)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)
    cfg = v39_config()
    cache = ab.FeatureCache(frame)
    specs = v39_ablation_specs(cfg)

    rows: list[dict[str, Any]] = []
    runs: list[base.RunResult] = []
    for spec in specs:
        run = ab.run_spec(spec, frame, funding, cache)
        runs.append(run)
        row = ab.summarize(spec, run)
        row["standard_slices"] = run.slices
        rows.append(row)
        ab.print_row(row)

    add_deltas(rows)
    print_rankings(rows)

    payload: dict[str, Any] = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V39 full parameter ablation",
        "baseline": "HYPE-EMA-TB-V39",
        "data_quality": quality,
        "selection_disclosure": "本轮为 V39 逐项消融诊断；标准分片用于审计与呈现，未用于登记新版本。",
        "cost_model": "Binance USD-M perp, 0.00085 per fill (fee + 4bps slippage combined), funding included.",
        "baseline_config": asdict(cfg),
        "baseline_flags": asdict(v39_flags()),
        "rows": rows,
    }
    out_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    trades = pd.concat(
        [run.trades.assign(variant=run.name) for run in runs if not run.trades.empty],
        ignore_index=True,
    )
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    trades.to_csv(trades_path, index=False)
    print(f"\nsummary -> {out_path}")
    print(f"trades  -> {trades_path}")


if __name__ == "__main__":
    main()
