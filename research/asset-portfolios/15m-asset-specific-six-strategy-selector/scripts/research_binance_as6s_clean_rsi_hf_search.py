from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
OUTPUT_DIR = FAMILY_DIR / "artifacts/per_asset_clean_rsi_hf"
MII_SCRIPTS = ROOT / "research/hype/15m-multi-indicator-intraday/scripts"
AS6S_SCRIPTS = FAMILY_DIR / "scripts"
sys.path.insert(0, str(MII_SCRIPTS))
sys.path.insert(0, str(AS6S_SCRIPTS))

import research_hype_15m_mii_clean_evolution as evolution  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
import research_hype_15m_mii_search as mii  # noqa: E402
from as6s_engine import REUSED_END, STARTS, load_symbol_frame  # noqa: E402
from research_binance_as6s_per_asset_hf_discovery import (  # noqa: E402
    HISTORICAL_OOS_END,
    PREFIT_END,
)
from research_binance_as6s_per_asset_hf_filter_tune import (  # noqa: E402
    finite_pf,
    window_metric,
)


@dataclass(frozen=True, slots=True)
class Config:
    rsi_window: int
    rsi_low: float
    rsi_high: float
    min_atr_pct96: float
    min_rvol96: float
    h1_confirm: bool
    rsi14_band: bool
    take_profit_pct: float
    stop_pct: float
    max_hold_bars: int

    @property
    def signal(self) -> mii.SignalSpec:
        return mii.SignalSpec(
            name=(
                f"rsi_reversal_w{self.rsi_window}_lo{self.rsi_low:g}_hi{self.rsi_high:g}"
            ),
            kind="rsi_reversal",
            window=self.rsi_window,
            low=self.rsi_low,
            high=self.rsi_high,
        )

    @property
    def exit(self) -> mii.ExitSpec:
        return mii.ExitSpec(
            kind="fixed",
            take_profit_pct=self.take_profit_pct,
            stop_pct=self.stop_pct,
            max_hold_bars=self.max_hold_bars,
        )

    @property
    def filter(self) -> mii.FilterSpec:
        return mii.FilterSpec(
            min_rvol96=self.min_rvol96,
            min_h1_dir_spread=0.0 if self.h1_confirm else -99.0,
            min_dir_macd=0.0,
            min_dir_rsi14=48.0 if self.rsi14_band else 0.0,
            max_dir_rsi14=78.0 if self.rsi14_band else 100.0,
            min_atr_pct96=self.min_atr_pct96,
            max_atr_pct96=0.028,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Per-asset clean RSI high-frequency search.")
    parser.add_argument("--symbol", choices=tuple(STARTS), required=True)
    parser.add_argument("--top", type=int, default=300)
    return parser.parse_args()


def atr_grid(symbol: str) -> tuple[float, ...]:
    # Asset-specific absolute levels derived from each symbol's ATR96 distribution.
    # They deliberately overlap neighboring quantiles instead of using a single
    # HYPE-sized volatility threshold for every asset.
    return {
        "BTCUSDT": (0.0015, 0.0020, 0.0025, 0.0030, 0.0040),
        "ETHUSDT": (0.0025, 0.0035, 0.0045, 0.0060, 0.0075),
        "SOLUSDT": (0.0035, 0.0045, 0.0055, 0.0070, 0.0090),
        "BNBUSDT": (0.0018, 0.0025, 0.0035, 0.0045, 0.0060),
        "TRXUSDT": (0.0012, 0.0015, 0.0020, 0.0030, 0.0040),
        "HYPEUSDT": (0.0045, 0.0060, 0.0075, 0.0090, 0.0105),
    }[symbol]


def config_space(symbol: str) -> list[Config]:
    configs: list[Config] = []
    for values in itertools.product(
        (5, 7, 9),
        (35.0, 40.0),
        (55.0, 60.0),
        atr_grid(symbol),
        (0.0, 0.5, 0.75, 1.0),
        (False, True),
        (False, True),
        (0.006, 0.009, 0.0105, 0.012),
        (0.028, 0.032, 0.036, 0.045),
        (16, 24, 32, 48),
    ):
        config = Config(*values)
        if config.rsi_high - config.rsi_low >= 15.0:
            configs.append(config)
    return configs


def candidate_score(row: dict[str, Any]) -> float:
    metrics = [
        row[delay][window]
        for delay in ("k1", "k2")
        for window in ("prefit", "historical_oos", "current_3m")
    ]
    if min(metric["trades"] for metric in metrics) < 8:
        return -1e9
    min_win = min(metric["win_rate"] for metric in metrics)
    worst_dd = min(metric["max_dd"] for metric in metrics)
    min_pf = min(finite_pf(metric["profit_factor"]) for metric in metrics)
    positive = sum(metric["total_return"] > 0.0 for metric in metrics)
    k1_frequency = np.mean(
        [row["k1"][window]["trades_per_day"] for window in ("prefit", "historical_oos", "current_3m")]
    )
    log_annual = sum(
        weight * math.log(max(row[delay][window]["annual_multiple"], 1e-9))
        for delay, window, weight in (
            ("k1", "prefit", 1.0),
            ("k1", "historical_oos", 1.1),
            ("k1", "current_3m", 0.9),
            ("k2", "prefit", 0.6),
            ("k2", "historical_oos", 0.8),
            ("k2", "current_3m", 0.7),
        )
    )
    return float(
        log_annual
        + 3.0 * min_win
        + 0.55 * math.log(min_pf)
        + 1.5 * worst_dd
        + 0.7 * positive
        + 10.0 * min(0.0, min_win - 0.78)
        + 12.0 * min(0.0, worst_dd + 0.20)
        + 5.0 * min(0.0, k1_frequency - 0.35)
        + 2.0 * min(0.0, 2.0 - k1_frequency)
    )


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_symbol_frame(args.symbol, end=REUSED_END)[
        ["ts", "open", "high", "low", "close", "volume"]
    ].copy()
    features = evolution.add_rsi_features(evolution.add_features(raw, []))
    market = mii.build_market_arrays(features)
    configs = config_space(args.symbol)

    grouped: dict[tuple[str, str], list[Config]] = {}
    for config in configs:
        grouped.setdefault((config.signal.name, config.exit.name), []).append(config)
    states: dict[str, mii.SignalState] = {}
    ranking: list[dict[str, Any]] = []
    simulated = 0
    evaluated = 0
    for pair_no, ((signal_name, _exit_name), pair_configs) in enumerate(grouped.items(), start=1):
        seed = pair_configs[0]
        state = states.setdefault(signal_name, mii.signal_state(features, seed.signal))
        trades_k1 = v1.simulate_trades_live(market, state, seed.exit, entry_delay_bars=1)
        trades_k2 = v1.simulate_trades_live(market, state, seed.exit, entry_delay_bars=2)
        simulated += 2
        for config in pair_configs:
            evaluated += 1
            picked_k1 = v1.selected_trades_live(trades_k1, config.filter)
            picked_k2 = v1.selected_trades_live(trades_k2, config.filter)
            row = {
                "config": asdict(config),
                "signal_name": signal_name,
                "exit_name": config.exit.name,
                "filter_name": config.filter.name,
                "k1": {
                    "prefit": window_metric(
                        picked_k1, STARTS[args.symbol], PREFIT_END
                    ),
                    "historical_oos": window_metric(
                        picked_k1, PREFIT_END, HISTORICAL_OOS_END
                    ),
                    "current_3m": window_metric(
                        picked_k1, HISTORICAL_OOS_END, REUSED_END
                    ),
                    "through_current": window_metric(
                        picked_k1, STARTS[args.symbol], REUSED_END
                    ),
                },
                "k2": {
                    "prefit": window_metric(
                        picked_k2, STARTS[args.symbol], PREFIT_END
                    ),
                    "historical_oos": window_metric(
                        picked_k2, PREFIT_END, HISTORICAL_OOS_END
                    ),
                    "current_3m": window_metric(
                        picked_k2, HISTORICAL_OOS_END, REUSED_END
                    ),
                    "through_current": window_metric(
                        picked_k2, STARTS[args.symbol], REUSED_END
                    ),
                },
            }
            row["score"] = candidate_score(row)
            if row["score"] <= -1e8:
                continue
            ranking.append(row)
        if len(ranking) > max(args.top * 30, 6000):
            ranking.sort(key=lambda row: row["score"], reverse=True)
            del ranking[max(args.top * 10, 3000) :]
        if pair_no % 50 == 0:
            print(
                f"{args.symbol} pairs={pair_no}/{len(grouped)} "
                f"simulated={simulated} evaluated={evaluated} kept={len(ranking)}",
                flush=True,
            )

    ranking.sort(key=lambda row: row["score"], reverse=True)
    hard80 = [
        row
        for row in ranking
        if all(
            row[delay][window]["trades"] >= 8
            and row[delay][window]["win_rate"] >= 0.80
            and row[delay][window]["total_return"] > 0.0
            and row[delay][window]["max_dd"] > -0.20
            for delay in ("k1", "k2")
            for window in ("prefit", "historical_oos", "current_3m")
        )
    ]
    output = OUTPUT_DIR / f"{args.symbol.lower()}_clean_rsi_hf_2026-07-14.json"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "clean_rsi_hf_gap_safe_discovery_not_live_ready",
        "symbol": args.symbol,
        "execution": (
            "closed 15m signal; next-open K+1/K+2; gap-safe stop; stop-first same bar; "
            "timeout open before intrabar; one position; fee+4bps slippage; funding pending"
        ),
        "search_space": {
            "configs": len(configs),
            "asset_specific_atr_grid": atr_grid(args.symbol),
            "signal_exit_pairs": len(grouped),
            "simulated": simulated,
            "evaluated": evaluated,
        },
        "hard80_count_before_funding": len(hard80),
        "disclosure": (
            "Current 3m participates in ranking. Actual funding and 8bps remain mandatory. "
            "Future final OOS is [2026-07-14T09:00Z, 2026-10-14T09:00Z)."
        ),
        "ranking": ranking[: args.top],
        "hard80": hard80[: args.top],
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "symbol": args.symbol,
                "output": str(output),
                "hard80": len(hard80),
                "best": ranking[0] if ranking else None,
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
