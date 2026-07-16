from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict
from pathlib import Path
from typing import Any

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_post24h_exit_floor as guard_engine
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v35_slow_start_exit as slow_exit
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_slow_start_exit_2026-07-15"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"


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
        next_open_exit_reason=slow_exit.EXIT_REASON,
        block_same_direction_until_signal_reset=episode_reset,
    )


def variants() -> list[guard_engine.GuardConfig]:
    return [
        guard_engine.GuardConfig("v39_base", mode="none"),
        make_guard("v39_exit_h6_mlt10", hold_hours=6, max_mfe_atr=1.0),
        make_guard("v39_exit_h6_mlt15", hold_hours=6, max_mfe_atr=1.5),
        make_guard("v39_exit_h8_mlt10", hold_hours=8, max_mfe_atr=1.0),
        make_guard("v39_exit_h8_mlt15", hold_hours=8, max_mfe_atr=1.5),
        make_guard("v39_exit_h10_mlt15", hold_hours=10, max_mfe_atr=1.5),
        make_guard("v39_exit_h12_mlt15", hold_hours=12, max_mfe_atr=1.5),
        make_guard(
            "v39_exit_h6_mlt15_reset",
            hold_hours=6,
            max_mfe_atr=1.5,
            episode_reset=True,
        ),
        make_guard(
            "v39_exit_h8_mlt15_reset",
            hold_hours=8,
            max_mfe_atr=1.5,
            episode_reset=True,
        ),
    ]


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    config = v39.v39_config()
    flags = v39.v39_flags()
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )
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
        "v39_canonical",
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
        raise RuntimeError("Custom engine failed canonical V39 parity.")

    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "version": "HYPE-EMA-TB-V39",
        "diagnostic_id": "V39 slow-start next-open exit",
        "dry_run_boundary": (
            "Standalone parent V39 remains registered/not promoted in its family ledger. "
            "V39 is currently active as the priority trend leg inside "
            "HYPE-15M-TB-MII-ENS-V2 production dry-run."
        ),
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "v39_config": asdict(config),
        "v39_signal_flags": asdict(flags),
        "execution_model": {
            "activation": (
                "After a closed 15m bar, if elapsed holding time has reached the "
                "configured threshold and historical MFE remains strictly below the "
                "configured ceiling, schedule an exit."
            ),
            "fill": "Exit at the next 15m open before any new intrabar bracket check.",
            "reset_variants": (
                "Variants suffixed reset block same-direction reentry until the delayed "
                "canonical V39 entry signal becomes false."
            ),
            "cost": (
                "V39 canonical 0.00085 per fill, including fee and 4 bps adverse "
                "slippage; Binance funding included."
            ),
        },
        "selection_disclosure": (
            "The 6h/8h and MFE1.5 rule was proposed after inspecting V35. Applying it "
            "to V39 is a post-hoc transfer diagnostic."
        ),
        "engine_parity": "PASS: mode=none equals canonical V39 trades and metrics.",
        "rows": [
            slow_exit.summarize(guard, run, baseline)
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
        print(
            f"{row['guard']['name']:>26} ret={metrics['return_pct']:>8.2f}% "
            f"dd={metrics['max_drawdown_pct']:>7.2f}% sh={metrics['sharpe']:>4.2f} "
            f"wr={metrics['win_rate_pct']:>6.2f}% "
            f"retain={row['capital_retention_vs_base_pct']:>6.2f}% "
            f"exits={row['active_exits']:>2} "
            f"re1h={row['reentry_audit']['same_direction_reentry_within_1h']:>2}"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
