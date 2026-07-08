from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
NO_FLOOR = base.ProfitFloorConfig(enabled=False)

# 特征窗口参数：变化时必须重建特征；其余阈值/退出参数只需重建信号或直接进回测。
FEATURE_FIELDS = (
    "ema_fast",
    "ema_slow",
    "adx_window",
    "volume_window",
    "atr_window",
    "h1_adx_window",
    "h1_ema_fast",
    "h1_ema_slow",
)


@dataclass(frozen=True, slots=True)
class SignalFlags:
    """结构性消融开关；默认全部等价于 V35 原始信号。"""

    long_use_ema_spread: bool = True
    long_use_h1_di: bool = True
    short_use_ema_spread: bool = True
    short_use_h1_ema: bool = True
    allow_long: bool = True
    allow_short: bool = True


@dataclass(frozen=True, slots=True)
class ExpSpec:
    name: str
    config: base.V35Config
    flags: SignalFlags = SignalFlags()
    group: str = ""
    note: str = ""


class FeatureCache:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self._cache: dict[tuple[Any, ...], pd.DataFrame] = {}

    def get(self, config: base.V35Config) -> pd.DataFrame:
        key = tuple(getattr(config, field) for field in FEATURE_FIELDS)
        if key not in self._cache:
            self._cache[key] = base.build_features(self.frame, config)
        return self._cache[key]


def build_signals(features: pd.DataFrame, config: base.V35Config, flags: SignalFlags) -> pd.DataFrame:
    out = features.copy()
    long_signal = (
        out["adx"].ge(config.long_adx_min)
        & out["volume_surge"].ge(config.long_vol_min)
        & out["h1_adx"].gt(config.h1_long_adx_min)
    )
    if flags.long_use_ema_spread:
        long_signal &= out["ema_spread"].gt(0.0)
    if flags.long_use_h1_di:
        long_signal &= out["h1_plus_di"].gt(out["h1_minus_di"])
    short_signal = out["adx"].ge(config.short_adx_min) & out["volume_surge"].ge(config.short_vol_min)
    if flags.short_use_ema_spread:
        short_signal &= out["ema_spread"].lt(0.0)
    if flags.short_use_h1_ema:
        short_signal &= out["h1_ema_spread"].lt(0.0)
    if not flags.allow_long:
        long_signal &= False
    if not flags.allow_short:
        short_signal &= False
    conflict = long_signal & short_signal
    long_signal &= ~conflict
    short_signal &= ~conflict
    out["long_signal"] = long_signal
    out["short_signal"] = short_signal
    return out


def run_spec(
    spec: ExpSpec,
    frame: pd.DataFrame,
    funding: pd.Series,
    cache: FeatureCache,
) -> base.RunResult:
    features = build_signals(cache.get(spec.config), spec.config, spec.flags)
    return base.run_backtest(spec.name, frame, funding, features, spec.config, NO_FLOOR)


def window_stats(run: base.RunResult, days: int | None) -> dict[str, Any]:
    equity = run.equity_curve
    if days is None:
        start = equity.index.min()
    else:
        start = equity.index.max() - pd.Timedelta(days=days)
    sliced = equity.loc[equity.index >= start]
    normalized = sliced / float(sliced.iloc[0])
    drawdown = normalized / normalized.cummax() - 1.0
    trades = run.trades
    if trades.empty:
        wins = 0
        count = 0
        exits: dict[str, int] = {}
    else:
        mask = pd.to_datetime(trades["exit_ts"], utc=True) >= sliced.index.min()
        window_trades = trades.loc[mask]
        count = int(len(window_trades))
        wins = int((window_trades["trade_return"] > 0).sum())
        exits = {str(k): int(v) for k, v in window_trades["exit_reason"].value_counts().items()}
    return {
        "return_pct": round(float(normalized.iloc[-1] - 1.0) * 100.0, 2),
        "max_drawdown_pct": round(float(drawdown.min()) * 100.0, 2),
        "trades": count,
        "wins": wins,
        "win_rate_pct": round(wins / count * 100.0, 2) if count else None,
        "exit_counts": exits,
    }


def summarize(spec: ExpSpec, run: base.RunResult) -> dict[str, Any]:
    return {
        "name": spec.name,
        "group": spec.group,
        "note": spec.note,
        "config": asdict(spec.config),
        "flags": asdict(spec.flags),
        "full": window_stats(run, None),
        "sharpe": run.metrics["sharpe"],
        "d90": window_stats(run, 90),
        "d30": window_stats(run, 30),
    }


def print_row(row: dict[str, Any]) -> None:
    full = row["full"]
    d90 = row["d90"]
    d30 = row["d30"]
    print(
        f"{row['name']:>34} | full {full['return_pct']:>9.2f}% dd {full['max_drawdown_pct']:>7.2f}% "
        f"sh {row['sharpe']:>5.2f} n {full['trades']:>3} win {full['win_rate_pct'] or 0:>6.2f}% "
        f"| 90d {d90['return_pct']:>8.2f}% dd {d90['max_drawdown_pct']:>7.2f}% "
        f"win {d90['win_rate_pct'] or 0:>6.2f}% n {d90['trades']:>3} "
        f"| 30d {d30['return_pct']:>7.2f}%"
    )


def ablation_specs(cfg: base.V35Config) -> list[ExpSpec]:
    specs: list[ExpSpec] = [ExpSpec("v35_base", cfg, group="base", note="V35 冻结参数基准")]

    def add(name: str, group: str, note: str = "", flags: SignalFlags = SignalFlags(), **changes: Any) -> None:
        specs.append(ExpSpec(name, replace(cfg, **changes) if changes else cfg, flags, group, note))

    # 仓位与目标波动
    add("target_long_016", "sizing", note="long target 0.020->0.016", long_target_atr_pct=0.016)
    add("target_long_024", "sizing", note="long target 0.020->0.024", long_target_atr_pct=0.024)
    add("target_short_014", "sizing", note="short target 0.018->0.014", short_target_atr_pct=0.014)
    add("target_short_022", "sizing", note="short target 0.018->0.022", short_target_atr_pct=0.022)
    add("cap_20", "sizing", note="max_allocation 3.0->2.0", max_allocation=2.0)
    add("cap_25", "sizing", note="max_allocation 3.0->2.5", max_allocation=2.5)
    add("cap_40", "sizing", note="max_allocation 3.0->4.0", max_allocation=4.0)

    # 特征窗口
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

    # 入场阈值与过滤器移除
    add("long_adx_24", "entry", long_adx_min=24.0)
    add("long_adx_26", "entry", long_adx_min=26.0)
    add("long_adx_30", "entry", long_adx_min=30.0)
    add("long_adx_32", "entry", long_adx_min=32.0)
    add("short_adx_32", "entry", short_adx_min=32.0)
    add("short_adx_40", "entry", short_adx_min=40.0)
    add("long_vol_015", "entry", long_vol_min=0.15)
    add("long_vol_035", "entry", long_vol_min=0.35)
    add("no_long_volume", "entry", note="移除多头成交量过滤", long_vol_min=-10.0)
    add("short_vol_075", "entry", short_vol_min=0.75)
    add("no_short_volume", "entry", note="移除空头成交量过滤", short_vol_min=-10.0)
    add("h1_long_adx_14", "entry", h1_long_adx_min=14.0)
    add("h1_long_adx_22", "entry", h1_long_adx_min=22.0)
    add("no_h1_long_adx", "entry", note="移除 1h ADX 门槛", h1_long_adx_min=-1.0)
    add("no_h1_di_long", "entry", note="移除 1h +DI>-DI", flags=SignalFlags(long_use_h1_di=False))
    add("no_ema_spread_long", "entry", note="移除多头 EMA spread>0", flags=SignalFlags(long_use_ema_spread=False))
    add("no_h1_ema_short", "entry", note="移除空头 1h EMA 确认", flags=SignalFlags(short_use_h1_ema=False))
    add("no_ema_spread_short", "entry", note="移除空头 EMA spread<0", flags=SignalFlags(short_use_ema_spread=False))
    add("long_only", "entry", note="禁用空头", flags=SignalFlags(allow_short=False))

    # 退出结构
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


def tune_specs(cfg: base.V35Config) -> list[ExpSpec]:
    """微调网格：只组合消融中对最近 90 天正贡献的方向。

    消融结论（2026-07-08）：adx_window=28、long_adx_min=28、adx_exit=22、
    hard_stop_atr=7、atr_window=672、disable_after_mfe=1.5 均为峰值，不再扫描。
    第一轮教训：空头 ema_spread<0 与 1h EMA 确认互为备份，只能移除其一；
    本轮精简基线只移除 1h EMA 确认（单独移除时与 base 完全一致）。
    """
    pruned_flags = SignalFlags(short_use_h1_ema=False)
    specs: list[ExpSpec] = [
        ExpSpec("v35_base", cfg, group="base"),
        ExpSpec("v35_pruned_baseline", cfg, pruned_flags, group="base", note="仅移除空头 1h EMA 确认，应与 base 完全一致"),
    ]
    grid = product(
        [0.25, 0.35],        # long_vol_min
        [5.0, 5.5],          # take_profit_atr
        [3.0, 2.5],          # max_allocation
        [0.018, 0.022],      # short_target_atr_pct
        [384, 512],          # ema_slow
        [True, False],       # long_use_ema_spread
    )
    for vol, tp, cap, short_target, ema_slow, use_spread in grid:
        name = (
            f"t_v{str(vol).replace('.', '')}_tp{str(tp).replace('.', '')}"
            f"_c{str(cap).replace('.', '')}_st{str(short_target).replace('.', '')}"
            f"_es{ema_slow}_sp{int(use_spread)}"
        )
        specs.append(
            ExpSpec(
                name,
                replace(
                    cfg,
                    long_vol_min=vol,
                    take_profit_atr=tp,
                    max_allocation=cap,
                    short_target_atr_pct=short_target,
                    ema_slow=ema_slow,
                ),
                SignalFlags(
                    long_use_ema_spread=use_spread,
                    short_use_h1_ema=False,
                ),
                group="tune",
            )
        )
    return specs


def final_specs(cfg: base.V35Config) -> list[ExpSpec]:
    """最终候选对照：base、温和微调版、最近 90 天优化版。"""
    return [
        ExpSpec("v35_base", cfg, group="base"),
        ExpSpec(
            "v35_tuned_mild",
            replace(cfg, long_vol_min=0.35, short_target_atr_pct=0.022),
            SignalFlags(short_use_h1_ema=False),
            group="final",
            note="仅提高 long_vol_min 0.25->0.35、short target 0.018->0.022，移除冗余空头 1h EMA 确认",
        ),
        ExpSpec(
            "v35_tuned_recent3m",
            replace(cfg, long_vol_min=0.35, short_target_atr_pct=0.022, max_allocation=2.5, ema_slow=512),
            SignalFlags(long_use_ema_spread=False, short_use_h1_ema=False),
            group="final",
            note="最近90天优化版：另移除多头 EMA spread 过滤、cap 2.5、ema_slow 512",
        ),
    ]


def rank_tune(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_row = next(row for row in rows if row["name"] == "v35_base")
    b90 = base_row["d90"]
    candidates = []
    for row in rows:
        if row["name"] == "v35_base":
            continue
        d90 = row["d90"]
        full = row["full"]
        if d90["win_rate_pct"] is None or d90["trades"] < 15:
            continue
        constraints = (
            d90["return_pct"] >= b90["return_pct"]
            and d90["max_drawdown_pct"] >= b90["max_drawdown_pct"]
            and (d90["win_rate_pct"] or 0.0) >= (b90["win_rate_pct"] or 0.0)
            and full["return_pct"] >= 3000.0
            and full["max_drawdown_pct"] >= -26.0
        )
        row["passes_constraints"] = constraints
        candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["passes_constraints"],
            row["d90"]["return_pct"] + 2.0 * (row["d90"]["win_rate_pct"] or 0.0) + 3.0 * row["d90"]["max_drawdown_pct"],
        ),
        reverse=True,
    )
    return candidates


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--stage", choices=["ablation", "tune", "final"], default="ablation")
    args = parser.parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)
    cfg = base.V35Config()
    cache = FeatureCache(frame)
    if args.stage == "ablation":
        specs = ablation_specs(cfg)
    elif args.stage == "tune":
        specs = tune_specs(cfg)
    else:
        specs = final_specs(cfg)

    rows: list[dict[str, Any]] = []
    runs: list[base.RunResult] = []
    for spec in specs:
        run = run_spec(spec, frame, funding, cache)
        runs.append(run)
        row = summarize(spec, run)
        rows.append(row)
        print_row(row)

    payload: dict[str, Any] = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": f"HYPE-EMA-TB-V35 full ablation & recent-3m tune ({args.stage})",
        "data_quality": quality,
        "selection_disclosure": "最近 90/30 天窗口在 tune 阶段直接参与选参；ablation 阶段仅作诊断观察。",
        "cost_model": "Binance perp, 0.00085 per fill (fee + 4bps slippage combined, V35 canonical), funding included.",
        "rows": rows,
    }
    if args.stage == "tune":
        ranked = rank_tune(rows)
        payload["ranked_top"] = ranked[:20]
        print("\n=== top candidates (constraints first, then 90d composite) ===")
        for row in ranked[:15]:
            marker = "PASS" if row.get("passes_constraints") else "----"
            print(f"[{marker}]", end=" ")
            print_row(row)

    if args.stage == "final":
        payload["standard_slices"] = {run.name: run.slices for run in runs}
        trades = pd.concat(
            [run.trades.assign(variant=run.name) for run in runs if not run.trades.empty],
            ignore_index=True,
        )
        trades_path = ARTIFACT_DIR / "hype_ema_tb_v35_final_candidates_trades_2026-07-08.csv"
        trades.to_csv(trades_path, index=False)
        equity = pd.concat([run.equity_curve.rename(run.name) for run in runs], axis=1)
        equity_path = ARTIFACT_DIR / "hype_ema_tb_v35_final_candidates_equity_2026-07-08.csv"
        equity.to_csv(equity_path, index_label="ts")
        print("\n=== standard slices ===")
        for run in runs:
            for item in run.slices:
                print(
                    f"{run.name:>24} {item['window']:>5} ret {item['return_pct']:>10.2f}% "
                    f"dd {item['max_drawdown_pct']:>8.2f}% trades {item['closed_trades']:>4}"
                )

    out_path = ARTIFACT_DIR / f"hype_ema_tb_v35_{args.stage}_recent_tune_2026-07-08.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nsummary -> {out_path}")


if __name__ == "__main__":
    main()
