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
from research_hype_state_machine_v12 import V12Spec, add_structure_features, run_v12
from research_hype_state_machine_v12_hard_exit import spec as focused_spec


CSV_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_main_result_backfill_v13.csv")
JSON_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_main_result_backfill_v13.json")


WINDOWS = {
    "1W": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "6M": pd.Timedelta(days=180),
    "1Y": pd.Timedelta(days=365),
}


def v13_spec() -> V12Spec:
    return focused_spec(
        "V13_age128_dist08",
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=0.35,
        entry_max_regime_age=128,
        entry_max_dist_ema96=0.08,
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
    spec = v13_spec()
    results = {
        label: run_v12(frame, spec, start_ts=end_ts - delta)
        for label, delta in WINDOWS.items()
    }
    row = row_from_results("V13", results)

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
                "spec": asdict(spec),
                "windows": results,
                "main_table_row": row,
                "notes": [
                    "V13 records V12.4 age128 plus entry_max_dist_ema96 <= 8%.",
                    "Window backtests start from flat position at each window start.",
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
