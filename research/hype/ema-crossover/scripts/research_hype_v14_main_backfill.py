from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_state_machine_v12 import add_structure_features
from research_hype_v13_late_reentry import LateReentrySpec, base_v13_spec, run_late_reentry


CSV_PATH = Path("research/hype/ema-crossover/artifacts/hype_main_result_backfill_v14.csv")
JSON_PATH = Path("research/hype/ema-crossover/artifacts/hype_main_result_backfill_v14.json")


WINDOWS = {
    "1W": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "6M": pd.Timedelta(days=180),
    "1Y": pd.Timedelta(days=365),
}


def v14_spec() -> LateReentrySpec:
    return LateReentrySpec(
        "V14_age256_dist06_cd16",
        base_v13_spec("V14_base"),
        late_max_age=256,
        late_dist_ema96=0.06,
        cooldown_bars=16,
        min_prev_pnl=0.0,
        min_prev_mfe_atr=4.0,
    )


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def row_from_results(label: str, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    one_year = results["1Y"]
    exit_reasons = dict(one_year["exit_reasons"])
    stop_loss = int(exit_reasons.get("stop_loss", 0))
    take_profit = int(exit_reasons.get("take_profit", 0))
    other_exit = int(one_year["trades"] - stop_loss - take_profit)
    return {
        "version": label,
        "1W_return": pct(results["1W"]["return"]),
        "1W_max_dd": pct(results["1W"]["max_dd"]),
        "1M_return": pct(results["1M"]["return"]),
        "1M_max_dd": pct(results["1M"]["max_dd"]),
        "3M_return": pct(results["3M"]["return"]),
        "3M_max_dd": pct(results["3M"]["max_dd"]),
        "6M_return": pct(results["6M"]["return"]),
        "6M_max_dd": pct(results["6M"]["max_dd"]),
        "1Y_return": pct(one_year["return"]),
        "1Y_max_dd": pct(one_year["max_dd"]),
        "trades": int(one_year["trades"]),
        "late_trades": int(one_year["late_trades"]),
        "win_rate": pct(one_year["win_rate"]),
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "other_exit": other_exit,
        "sharpe": float(one_year["sharpe"]),
        "exit_reasons": exit_reasons,
    }


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    spec = v14_spec()
    results = {
        label: run_late_reentry(frame, spec, start_ts=end_ts - delta)
        for label, delta in WINDOWS.items()
    }
    row = row_from_results("V14", results)

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(CSV_PATH, index=False)
    JSON_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "start": str(pd.Timestamp(frame.ts.iloc[0])),
                    "end": str(end_ts),
                    "bars": int(len(frame)),
                },
                "spec": {
                    "name": spec.name,
                    "v12": asdict(spec.v12),
                    "late_max_age": spec.late_max_age,
                    "late_dist_ema96": spec.late_dist_ema96,
                    "cooldown_bars": spec.cooldown_bars,
                    "min_prev_pnl": spec.min_prev_pnl,
                    "min_prev_mfe_atr": spec.min_prev_mfe_atr,
                    "require_pullback": spec.require_pullback,
                },
                "windows": results,
                "main_table_row": row,
                "notes": [
                    "V14 records the best V13.1 late re-entry candidate.",
                    "Normal first entry keeps V13 filters: age <= 128 and dist_ema96 <= 8%.",
                    "Late re-entry allows same-regime profitable continuation until age <= 256, dist_ema96 <= 6%, cooldown 16 bars.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={CSV_PATH}")
    print(f"wrote={JSON_PATH}")
    print(pd.DataFrame([row]).to_string(index=False))


if __name__ == "__main__":
    main()
