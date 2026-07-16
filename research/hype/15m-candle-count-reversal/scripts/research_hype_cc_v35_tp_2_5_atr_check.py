from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-candle-count-reversal"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_hype_cc_v35_dual_ema_filter.py"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CSV_PATH = ARTIFACT_DIR / "hype_cc_v35_tp_2_5_atr_slices_2026-07-16.csv"
JSON_PATH = ARTIFACT_DIR / "hype_cc_v35_tp_2_5_atr_summary_2026-07-16.json"


def load_base_module():
    spec = importlib.util.spec_from_file_location("hype_cc_v35_tp25_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base module: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hype_cc_v35_tp25_base"] = module
    spec.loader.exec_module(module)
    return module


def enriched_metrics(base, run) -> dict[str, Any]:
    metrics = base.compact_metrics(run)
    trades = run.trades
    closed_trades = int(len(trades))
    wins = int((trades["trade_return"] > 0.0).sum()) if closed_trades else 0
    metrics.update(
        {
            "closed_trades": closed_trades,
            "wins": wins,
            "win_rate_pct": (
                round(100.0 * wins / closed_trades, 4) if closed_trades else None
            ),
            "avg_take_profit_pct": (
                round(100.0 * float(trades["take_profit_pct"].mean()), 4)
                if closed_trades
                else None
            ),
            "min_take_profit_pct": (
                round(100.0 * float(trades["take_profit_pct"].min()), 4)
                if closed_trades
                else None
            ),
            "max_take_profit_pct": (
                round(100.0 * float(trades["take_profit_pct"].max()), 4)
                if closed_trades
                else None
            ),
        }
    )
    return metrics


def main() -> None:
    base = load_base_module()
    replay = base._load_replay_module()
    frame, quality = base.load_and_audit_frame()
    v35 = replay.hype_v35_config()
    tp25 = replace(v35, take_profit_atr_multiplier=2.5)
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
        "full": None,
    }
    variants = {
        "V35 TP5.5 baseline": v35,
        "V35 TP2.5 diagnostic": tp25,
    }

    rows: list[dict[str, Any]] = []
    for window_name, delta in windows.items():
        start = (
            frame.index[0]
            if delta is None
            else max(frame.index[0], frame.index[-1] - delta)
        )
        for variant_name, config in variants.items():
            run = base.run_next_open(
                replay,
                frame,
                config,
                trade_start=start,
                trade_end=frame.index[-1],
            )
            rows.append(
                {
                    "window": window_name,
                    "variant": variant_name,
                    "start": start.isoformat(),
                    "end": frame.index[-1].isoformat(),
                    "take_profit_atr_multiplier": (
                        config.take_profit_atr_multiplier
                    ),
                    "min_take_profit_pct_config": config.min_take_profit_pct,
                    "max_take_profit_pct_config": config.max_take_profit_pct,
                    "fee_rate": config.fee_rate,
                    "slippage_rate": config.slippage_rate,
                    **enriched_metrics(base, run),
                }
            )
    slices = pd.DataFrame(rows)
    month = slices.loc[slices["window"].eq("1m")].set_index("variant")
    baseline_month = month.loc["V35 TP5.5 baseline"]
    tp25_month = month.loc["V35 TP2.5 diagnostic"]
    decision = (
        "reject TP2.5; 30d return remains negative"
        if float(tp25_month["return_pct"]) <= 0.0
        else "30d turns positive; further validation still required"
    )
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": "HYPE-Candle-Count-Reversal-V35 TP2.5 ATR diagnostic",
        "status": decision,
        "data_quality": quality,
        "change_contract": {
            "only_changed_field": "take_profit_atr_multiplier",
            "baseline": 5.5,
            "diagnostic": 2.5,
            "take_profit_atr_window": tp25.take_profit_atr_window,
            "min_take_profit_pct": tp25.min_take_profit_pct,
            "max_take_profit_pct": tp25.max_take_profit_pct,
            "all_other_v35_fields": "unchanged",
            "execution": "closed signal bar; next bar open entry",
        },
        "recent_30d": {
            "start": tp25_month["start"],
            "end": tp25_month["end"],
            "baseline": {
                "return_pct": float(baseline_month["return_pct"]),
                "max_drawdown_pct": float(
                    baseline_month["max_drawdown_pct"]
                ),
                "sharpe": float(baseline_month["sharpe"]),
                "win_rate_pct": float(baseline_month["win_rate_pct"]),
                "entries": int(baseline_month["entries"]),
            },
            "tp_2_5": {
                "return_pct": float(tp25_month["return_pct"]),
                "max_drawdown_pct": float(tp25_month["max_drawdown_pct"]),
                "sharpe": float(tp25_month["sharpe"]),
                "win_rate_pct": float(tp25_month["win_rate_pct"]),
                "entries": int(tp25_month["entries"]),
            },
        },
        "artifact": str(CSV_PATH.relative_to(ROOT)),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    slices.to_csv(CSV_PATH, index=False)
    JSON_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {JSON_PATH}")


if __name__ == "__main__":
    main()
