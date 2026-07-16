from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_post24h_exit_floor as guard_engine
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_slow_start_exit_2026-07-15"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"
EXIT_REASON = "slow_start_next_open_exit"


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def make_guard(
    name: str,
    *,
    hold_hours: int,
    max_mfe_atr: float,
    episode_reset: bool = False,
) -> guard_engine.GuardConfig:
    return guard_engine.GuardConfig(
        name=name,
        mode="next_open",
        min_hold_bars=hold_hours * 4,
        activation_mfe_atr=max_mfe_atr,
        mfe_condition="below",
        next_open_exit_reason=EXIT_REASON,
        block_same_direction_until_signal_reset=episode_reset,
    )


def variants() -> list[guard_engine.GuardConfig]:
    return [
        guard_engine.GuardConfig("v35_base", mode="none"),
        make_guard("exit_h4_mlt15", hold_hours=4, max_mfe_atr=1.5),
        make_guard("exit_h6_mlt10", hold_hours=6, max_mfe_atr=1.0),
        make_guard("exit_h6_mlt15", hold_hours=6, max_mfe_atr=1.5),
        make_guard("exit_h6_mlt20", hold_hours=6, max_mfe_atr=2.0),
        make_guard("exit_h8_mlt10", hold_hours=8, max_mfe_atr=1.0),
        make_guard("exit_h8_mlt15", hold_hours=8, max_mfe_atr=1.5),
        make_guard("exit_h8_mlt20", hold_hours=8, max_mfe_atr=2.0),
        make_guard("exit_h10_mlt15", hold_hours=10, max_mfe_atr=1.5),
        make_guard("exit_h12_mlt15", hold_hours=12, max_mfe_atr=1.5),
        make_guard(
            "exit_h6_mlt10_reset",
            hold_hours=6,
            max_mfe_atr=1.0,
            episode_reset=True,
        ),
        make_guard(
            "exit_h6_mlt15_reset",
            hold_hours=6,
            max_mfe_atr=1.5,
            episode_reset=True,
        ),
        make_guard(
            "exit_h8_mlt15_reset",
            hold_hours=8,
            max_mfe_atr=1.5,
            episode_reset=True,
        ),
    ]


def changed_trade_details(
    run: base.RunResult,
    baseline: base.RunResult,
) -> list[dict[str, Any]]:
    base_trades = baseline.trades.copy()
    base_trades["entry_ts"] = pd.to_datetime(base_trades["entry_ts"], utc=True)
    changed = run.trades.loc[run.trades["exit_reason"] == EXIT_REASON].copy()
    rows: list[dict[str, Any]] = []
    for _, trade in changed.iterrows():
        entry_ts = pd.Timestamp(trade["entry_ts"])
        match = base_trades.loc[
            (base_trades["entry_ts"] == entry_ts)
            & (base_trades["direction"] == trade["direction"])
        ]
        base_trade = match.iloc[0] if len(match) == 1 else None
        row = {
            "entry_ts": entry_ts,
            "direction": int(trade["direction"]),
            "entry_price": float(trade["entry_price"]),
            "activation_ts": trade["guard_activation_ts"],
            "activation_mfe_atr": float(trade["guard_activation_mfe_atr"]),
            "exit_ts": trade["exit_ts"],
            "exit_price": float(trade["exit_price"]),
            "hold_hours": float(trade["hold_bars"] * 0.25),
            "trade_return_pct": round(float(trade["trade_return"] * 100.0), 4),
            "base_match": base_trade is not None,
        }
        if base_trade is not None:
            row.update(
                {
                    "base_exit_ts": base_trade["exit_ts"],
                    "base_exit_reason": base_trade["exit_reason"],
                    "base_hold_hours": float(base_trade["hold_bars"] * 0.25),
                    "base_trade_return_pct": round(
                        float(base_trade["trade_return"] * 100.0),
                        4,
                    ),
                    "trade_return_delta_pp": round(
                        float(
                            (trade["trade_return"] - base_trade["trade_return"]) * 100.0
                        ),
                        4,
                    ),
                }
            )
        rows.append(row)
    return rows


def reentry_audit(run: base.RunResult) -> dict[str, Any]:
    trades = run.trades.reset_index(drop=True).copy()
    active_indices = trades.index[trades["exit_reason"] == EXIT_REASON].tolist()
    details: list[dict[str, Any]] = []
    for index in active_indices:
        if index + 1 >= len(trades):
            continue
        exited = trades.iloc[index]
        following = trades.iloc[index + 1]
        gap_hours = (
            pd.Timestamp(following["entry_ts"]) - pd.Timestamp(exited["exit_ts"])
        ).total_seconds() / 3600.0
        details.append(
            {
                "exit_ts": exited["exit_ts"],
                "exit_direction": int(exited["direction"]),
                "next_entry_ts": following["entry_ts"],
                "next_direction": int(following["direction"]),
                "gap_hours": round(float(gap_hours), 2),
                "same_direction": bool(
                    int(exited["direction"]) == int(following["direction"])
                ),
            }
        )
    return {
        "active_exits": len(active_indices),
        "same_direction_reentry_within_1h": sum(
            detail["same_direction"] and detail["gap_hours"] <= 1.0
            for detail in details
        ),
        "same_direction_reentry_within_4h": sum(
            detail["same_direction"] and detail["gap_hours"] <= 4.0
            for detail in details
        ),
        "details": details,
    }


def summarize(
    guard: guard_engine.GuardConfig,
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    exits = int((run.trades["exit_reason"] == EXIT_REASON).sum())
    return {
        "guard": asdict(guard),
        "metrics": run.metrics,
        "capital_retention_vs_base_pct": round(
            float(run.equity_curve.iloc[-1] / baseline.equity_curve.iloc[-1] * 100.0),
            2,
        ),
        "activations": int(run.trades["guard_activation_ts"].notna().sum()),
        "active_exits": exits,
        "hold_stats": guard_engine.hold_stats(run.trades),
        "standard_slices": run.slices,
        "changed_trade_details": changed_trade_details(run, baseline),
        "reentry_audit": reentry_audit(run),
    }


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    config = base.V35Config()
    features = base.build_features(frame, config)
    guards = variants()
    runs = [
        guard_engine.run_backtest(
            guard=guard,
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        for guard in guards
    ]
    baseline = runs[0]
    canonical = base.run_backtest(
        "canonical",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    expected = canonical.trades.assign(
        guard_mode="none",
        guard_active=False,
        guard_activation_ts=None,
        guard_activation_mfe_atr=None,
        guard_floor_atr=None,
    )
    if baseline.metrics != canonical.metrics or not baseline.trades.equals(expected):
        raise RuntimeError("Custom engine failed canonical V35 parity.")

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB-V35 slow-start next-open exit",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "base_config": asdict(config),
        "execution_model": {
            "activation": (
                "After a closed 15m bar, if elapsed holding time has reached the "
                "configured threshold and historical MFE remains strictly below the "
                "configured ceiling, schedule an exit."
            ),
            "fill": "Exit at the next 15m open before any new intrabar bracket check.",
            "reentry": (
                "Default variants add no cooldown. Variants suffixed reset block same-"
                "direction reentry until the delayed canonical entry signal becomes false."
            ),
            "cost": (
                "V35 canonical 0.00085 per fill, including fee and 4 bps adverse "
                "slippage; Binance funding included."
            ),
        },
        "selection_disclosure": (
            "The 6h/8h and MFE1.5 rule is motivated by a post-hoc descriptive audit. "
            "Adjacent times and MFE ceilings are sensitivity diagnostics."
        ),
        "engine_parity": "PASS: mode=none equals canonical V35 trades and metrics.",
        "rows": [
            summarize(guard, run, baseline)
            for guard, run in zip(guards, runs, strict=True)
        ],
    }
    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"gaps={quality['missing_15m_bars']}"
    )
    for row in payload["rows"]:
        metrics = row["metrics"]
        reentry = row["reentry_audit"]
        print(
            f"{row['guard']['name']:>18} ret={metrics['return_pct']:>8.2f}% "
            f"dd={metrics['max_drawdown_pct']:>7.2f}% sh={metrics['sharpe']:>4.2f} "
            f"wr={metrics['win_rate_pct']:>6.2f}% "
            f"retain={row['capital_retention_vs_base_pct']:>6.2f}% "
            f"exits={row['active_exits']:>2} re1h={reentry['same_direction_reentry_within_1h']:>2}"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
