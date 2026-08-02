"""V35.3 空头侧关闭 ADX 指标退出诊断（long-only indicator exit）。

动机：V35.3 全历史空头 `indicator_exit` 仅 2 笔（2025-12-05、2026-07-28），
事后都劣于继续持有——前者本可打 TP，后者本可被 4.4ATR 空头分批锁定。
多头侧指标退出此前反事实已证明净正贡献（全关更差）。本脚本只对空头
关闭 ADX22 delayed3 指标退出，多头保留，其余 V35.3 规则（TP5、
多 SL6.75/空 SL5.7、空头 4.4ATR 平 75%、timeout384）全部不变。

实现说明：为避免修改被多个历史诊断 import 的
research_hype_ema_tb_v35_2_short_partial_stop_scan 引擎文件，本脚本读取
该引擎源码，对唯一的 can_indicator_exit 代码块做方向门控替换后 exec 成
独立模块。若引擎源码发生漂移，断言会显式失败而不是静默错测。

状态：diagnostic only。样本仅 2 笔空头指标退出、且由已知事件启发，
无论结果如何都不构成热改依据，最多冻结为 shadow candidate 等待
时间前推 OOS。不修改冻结版、不修改 runner。
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_short_indicator_exit_off_2026-08-01"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"

ENGINE_FILENAME = "research_hype_ema_tb_v35_2_short_partial_stop_scan.py"

OLD_BLOCK = (
    "                    can_indicator_exit = (\n"
    "                        position.mfe_atr\n"
    "                        < config.disable_after_mfe_atr\n"
    "                    )\n"
)
LONG_ONLY_BLOCK = (
    "                    can_indicator_exit = (\n"
    "                        position.direction == 1\n"
    "                        and position.mfe_atr\n"
    "                        < config.disable_after_mfe_atr\n"
    "                    )\n"
)
ALL_OFF_BLOCK = (
    "                    can_indicator_exit = (\n"
    "                        False\n"
    "                        and position.mfe_atr\n"
    "                        < config.disable_after_mfe_atr\n"
    "                    )\n"
)


def load_patched_engine(module_name: str, new_block: str) -> types.ModuleType:
    source_path = SCRIPT_DIR / ENGINE_FILENAME
    source = source_path.read_text(encoding="utf-8")
    if source.count(OLD_BLOCK) != 1:
        raise RuntimeError(
            "stop engine source drifted: expected exactly one "
            f"can_indicator_exit block in {ENGINE_FILENAME}; "
            "re-audit this patch before trusting results"
        )
    patched = source.replace(OLD_BLOCK, new_block)
    module = types.ModuleType(module_name)
    module.__file__ = str(source_path)
    # dataclasses resolves cls.__module__ via sys.modules; register first.
    sys.modules[module.__name__] = module
    exec(compile(patched, str(source_path), "exec"), module.__dict__)
    return module


def v35_3_spec(engine: types.ModuleType, name: str) -> Any:
    return engine.StopPartialSpec(
        name=name,
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
        directional_stop_replaces_hard_stop=True,
    )


def exit_mix_by_direction(trades: pd.DataFrame) -> dict[str, dict[str, int]]:
    mix: dict[str, dict[str, int]] = {}
    for direction, label in ((1, "long"), (-1, "short")):
        subset = trades[trades["direction"] == direction]
        mix[label] = {
            str(k): int(v)
            for k, v in subset["exit_reason"].value_counts().items()
        }
        mix[label]["_trades"] = int(len(subset))
        wins = subset[subset["trade_return"] > 0]
        mix[label]["_wins"] = int(len(wins))
    return mix


def trade_brief(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "mfe_atr",
        "mae_atr",
        "exit_reason",
        "trade_return",
        "profit_partial_taken",
        "profit_partial_ts",
        "profit_partial_price",
    )
    return {k: row[k] for k in keys if k in row}


def remap_short_indicator_exits(
    baseline_trades: pd.DataFrame,
    variant_trades: pd.DataFrame,
    variant_open: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    shorts = baseline_trades[
        (baseline_trades["direction"] == -1)
        & (baseline_trades["exit_reason"] == "indicator_exit")
    ]
    rows: list[dict[str, Any]] = []
    for _, trade in shorts.iterrows():
        entry_ts = pd.Timestamp(trade["entry_ts"])
        matched = variant_trades[
            pd.to_datetime(variant_trades["entry_ts"]) == entry_ts
        ]
        if not matched.empty:
            variant_outcome: dict[str, Any] = trade_brief(
                matched.iloc[0].to_dict()
            )
        elif variant_open is not None and (
            pd.Timestamp(str(variant_open.get("entry_ts"))) == entry_ts
        ):
            variant_outcome = {"still_open_at_data_end": variant_open}
        else:
            variant_outcome = {"error": "entry not found in variant path"}
        rows.append(
            {
                "baseline": trade_brief(trade.to_dict()),
                "variant": variant_outcome,
            }
        )
    return rows


def entry_set_overlap(
    baseline_trades: pd.DataFrame, variant_trades: pd.DataFrame
) -> dict[str, Any]:
    base_set = set(pd.to_datetime(baseline_trades["entry_ts"]))
    var_set = set(pd.to_datetime(variant_trades["entry_ts"]))
    return {
        "baseline_trades": len(base_set),
        "variant_trades": len(var_set),
        "shared_entries": len(base_set & var_set),
        "baseline_only": sorted(str(ts) for ts in base_set - var_set),
        "variant_only": sorted(str(ts) for ts in var_set - base_set),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    features = signal_engine.build_signals(
        base.build_features(frame, config), config, flags
    )

    baseline_run, baseline_audit = stop_engine.run_backtest(
        spec=v35_3_spec(stop_engine, "v35_3_base"),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )

    patched_engine = load_patched_engine(
        "stop_engine_long_only_indicator_exit", LONG_ONLY_BLOCK
    )
    variant_run, variant_audit = patched_engine.run_backtest(
        spec=v35_3_spec(patched_engine, "v35_3_short_ind_exit_off"),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )

    all_off_engine = load_patched_engine(
        "stop_engine_all_indicator_exit_off", ALL_OFF_BLOCK
    )
    all_off_run, all_off_audit = all_off_engine.run_backtest(
        spec=v35_3_spec(all_off_engine, "v35_3_all_ind_exit_off"),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )

    summary = {
        "diagnostic": OUT_STEM,
        "status": "diagnostic only / not promoted / not live-ready",
        "market": "Binance USD-M Futures HYPEUSDT perp 15m",
        "cost_model": {
            "trade_fee_rate": 0.001,
            "slippage_bps": 4,
            "funding": "8h realized funding applied per bar",
        },
        "data": {
            "start": str(frame.index[0]),
            "end": str(frame.index[-1]),
            "rows": int(len(frame)),
            "quality_gate": quality_gate,
        },
        "slices_role": "audit only, not used for selection",
        "mechanism": (
            "variant: identical to V35.3 except ADX22-delayed3 indicator "
            "exit is gated to long positions only; shorts keep TP5 / SL5.7 "
            "/ 4.4ATR 75% partial / timeout384. all_off reference: "
            "indicator exit disabled for both directions"
        ),
        "runs": [
            {
                "name": run.name,
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "exit_mix_by_direction": exit_mix_by_direction(run.trades),
                "open_position": run.open_position,
                "audit": audit,
            }
            for run, audit in (
                (baseline_run, baseline_audit),
                (variant_run, variant_audit),
                (all_off_run, all_off_audit),
            )
        ],
        "short_indicator_exit_remap": remap_short_indicator_exits(
            baseline_run.trades,
            variant_run.trades,
            variant_run.open_position,
        ),
        "entry_set_overlap": entry_set_overlap(
            baseline_run.trades, variant_run.trades
        ),
        "sample_size_warning": (
            "only 2 short indicator exits in full history, both informed "
            "this test post hoc; shadow candidate at best, requires "
            "forward OOS before any promotion discussion"
        ),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    all_runs = (baseline_run, variant_run, all_off_run)
    pd.concat(
        [run.trades.assign(variant=run.name) for run in all_runs],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name).to_frame() for run in all_runs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(f"data: {summary['data']['start']} ~ {summary['data']['end']}")
    print(f"quality gate: {quality_gate}")
    for run in all_runs:
        m = run.metrics
        print(
            f"{run.name:>28}  ret {m['return_pct']:>10.2f}%  "
            f"dd {m['max_drawdown_pct']:>7.2f}%  sharpe {m['sharpe']:>5.2f}  "
            f"trades {m['trades']:>4}  win {m['win_rate_pct']:>6.2f}%"
        )
    print()
    print("slice returns (window: base | short_off | all_off):")
    for slices in zip(*(run.slices for run in all_runs), strict=True):
        cells = "  ".join(f"{s['return_pct']:>12.2f}" for s in slices)
        print(f"{slices[0]['window']:>6}  {cells}")
    print()
    print("short indicator exits remap:")
    print(
        json.dumps(
            summary["short_indicator_exit_remap"],
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    print()
    print("entry overlap:", json.dumps(summary["entry_set_overlap"], default=str))
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
