from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import hype_15m_signal_1h_confirm_bidirectional_search as dual15
import hype_new_trend_mechanism_search as base


BASE_RETURN = 2.2282425847426066
BASE_MAX_DRAWDOWN = -0.2002081670125816
BASE_SHARPE = 2.927910262149072
BASE_ENTRIES = 145


def main() -> None:
    m15, funding = base._load_15m()
    h1 = base._resample_ohlcv(m15, "1h")
    features = dual15._build_features(m15, h1)
    configs = _config_grid()
    candidates = _search(m15, funding, features, configs)
    best = candidates[0] if candidates else None
    result = {
        "symbol": base.SYMBOL,
        "strategy_family": "V2I 15m bidirectional 3x parameter tuning",
        "search": {
            "configs_evaluated": len(configs),
            "objective": "Prefer candidates with higher return and lower max drawdown than V2I; fallback score rewards return, Calmar and Sharpe while penalizing drawdown deterioration.",
        },
        "data": {
            "m15": base._coverage(m15),
            "h1_from_15m": base._coverage(h1),
        },
        "v2i_reference": {
            "return": BASE_RETURN,
            "max_drawdown": BASE_MAX_DRAWDOWN,
            "sharpe": BASE_SHARPE,
            "entries": BASE_ENTRIES,
            "config": asdict(_v2i_config()),
        },
        "best": best,
        "best_periods": _periods(m15, funding, features, dual15.Signal15mDualConfig(**best["config"])) if best else None,
        "strict_improvements": [
            row
            for row in candidates
            if row["full"]["return"] > BASE_RETURN and row["full"]["max_drawdown"] > BASE_MAX_DRAWDOWN
        ][:20],
        "higher_return_candidates": [row for row in candidates if row["full"]["return"] > BASE_RETURN][:20],
        "lower_drawdown_candidates": [row for row in candidates if row["full"]["max_drawdown"] > BASE_MAX_DRAWDOWN][:20],
        "top_candidates": candidates[:50],
    }
    out = Path("archive/reports/legacy/hype_v2i_parameter_tuning_search.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def _v2i_config() -> dual15.Signal15mDualConfig:
    return dual15.Signal15mDualConfig(
        ema_fast=96,
        ema_slow=384,
        atr_window=192,
        keltner_multiplier=2.0,
        adx_window=28,
        adx_min=22.0,
        short_adx_boost=4.0,
        adx_exit=22.0,
        volume_window=96,
        min_volume_surge=0.5,
        short_volume_boost=0.5,
        confirm_1h="ema",
        short_confirm_1h="bear_adx_di",
        target_atr_pct=0.012,
        short_target_atr_pct=0.002,
        max_allocation=3.0,
        short_max_allocation=1.0,
        stop_atr=6.0,
        short_stop_atr=2.0,
        take_atr=6.0,
        short_take_atr=4.0,
        trail_atr=10.0,
        short_trail_atr=6.0,
        max_hold_bars=288,
        short_max_hold_bars=48,
        cooldown_bars=8,
    )


def _config_grid() -> list[dual15.Signal15mDualConfig]:
    rng = random.Random(2026052706)
    configs: set[dual15.Signal15mDualConfig] = {_v2i_config()}

    def choice(values: tuple):
        return values[rng.randrange(len(values))]

    ema_pairs = ((48, 192), (64, 256), (96, 384))
    while len(configs) < 5200:
        ema_fast, ema_slow = choice(ema_pairs)
        adx_min = choice((20.0, 22.0, 24.0, 26.0, 28.0, 30.0))
        configs.add(
            dual15.Signal15mDualConfig(
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                atr_window=choice((96, 144, 192, 288)),
                keltner_multiplier=choice((1.5, 1.8, 2.0, 2.2, 2.5)),
                adx_window=choice((21, 28, 48)),
                adx_min=adx_min,
                short_adx_boost=choice((4.0, 6.0, 8.0, 10.0, 12.0)),
                adx_exit=choice((18.0, 20.0, 22.0, 24.0, 26.0)),
                volume_window=choice((48, 96, 192, 288)),
                min_volume_surge=choice((0.25, 0.5, 0.75, 1.0)),
                short_volume_boost=choice((0.25, 0.5, 0.75, 1.0)),
                confirm_1h=choice(("adx_di", "ema", "ema_price", "supertrend")),
                short_confirm_1h=choice(("bear_adx_di", "bear_ema", "bear_ema_price", "bear_supertrend")),
                target_atr_pct=choice((0.010, 0.011, 0.012, 0.013, 0.014)),
                short_target_atr_pct=choice((0.0015, 0.002, 0.0025, 0.003)),
                max_allocation=choice((2.5, 3.0)),
                short_max_allocation=choice((1.0, 1.5, 2.0, 3.0)),
                stop_atr=choice((5.0, 6.0, 7.0, 8.0, 10.0)),
                short_stop_atr=choice((1.5, 2.0, 2.5, 3.0)),
                take_atr=choice((4.0, 5.0, 6.0, 8.0, 10.0)),
                short_take_atr=choice((3.0, 4.0, 5.0, 6.0, 8.0)),
                trail_atr=choice((6.0, 8.0, 10.0, 12.0, 14.0)),
                short_trail_atr=choice((4.0, 6.0, 8.0)),
                max_hold_bars=choice((192, 288, 384)),
                short_max_hold_bars=choice((32, 48, 64, 96)),
                cooldown_bars=choice((8, 16, 24, 32)),
            )
        )
    return list(configs)


def _search(
    m15: pd.DataFrame,
    funding: pd.Series,
    features: dict[str, object],
    configs: list[dual15.Signal15mDualConfig],
) -> list[dict[str, object]]:
    start = 1600
    end = len(m15) - 1
    coarse = []
    for config in configs:
        full = dual15._run(m15, funding, features, config, start, end)
        if (
            full["entries"] >= 40
            and full["long_entries"] >= 20
            and full["short_entries"] >= 2
            and full["return"] > 0.8
            and full["max_drawdown"] > -0.35
        ):
            improvement_bonus = 0.0
            if full["return"] > BASE_RETURN:
                improvement_bonus += float(full["return"] - BASE_RETURN) * 2.0
            if full["max_drawdown"] > BASE_MAX_DRAWDOWN:
                improvement_bonus += float(full["max_drawdown"] - BASE_MAX_DRAWDOWN) * 8.0
            score = (
                base._calmar(full)
                + 0.35 * float(full["return"])
                + 0.15 * float(full["sharpe"])
                - 4.0 * max(0.0, abs(float(full["max_drawdown"])) - abs(BASE_MAX_DRAWDOWN))
                + improvement_bonus
            )
            coarse.append((score, config, full))
    coarse.sort(key=lambda row: (row[0], row[2]["return"]), reverse=True)

    n = len(m15)
    train_end = int(n * 0.55)
    val_end = int(n * 0.78)
    rows = []
    for score, config, full in coarse[:360]:
        train = dual15._run(m15, funding, features, config, start, train_end)
        val = dual15._run(m15, funding, features, config, train_end, val_end)
        test = dual15._run(m15, funding, features, config, val_end, n - 1)
        if (
            min(train["entries"], val["entries"], test["entries"]) >= 2
            and min(train["return"], val["return"], test["return"]) > -0.18
            and max(
                abs(float(train["max_drawdown"])),
                abs(float(val["max_drawdown"])),
                abs(float(test["max_drawdown"])),
            )
            < 0.32
        ):
            split_score = min(base._calmar(train), base._calmar(val), base._calmar(test)) + 0.25 * score
            rows.append(
                {
                    "config": asdict(config),
                    "score": float(score),
                    "split_score": float(split_score),
                    "return_delta": float(full["return"] - BASE_RETURN),
                    "drawdown_delta": float(full["max_drawdown"] - BASE_MAX_DRAWDOWN),
                    "sharpe_delta": float(full["sharpe"] - BASE_SHARPE),
                    "train": train,
                    "val": val,
                    "test": test,
                    "full": full,
                }
            )
    return sorted(rows, key=lambda row: (row["split_score"], row["score"], row["full"]["return"]), reverse=True)


def _periods(
    m15: pd.DataFrame,
    funding: pd.Series,
    features: dict[str, object],
    config: dual15.Signal15mDualConfig,
) -> dict[str, dict[str, float | int | str]]:
    out = {}
    end = len(m15) - 1
    for name, days in (("1w", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365)):
        start_ts = m15.index[-1] - pd.Timedelta(days=days)
        start = max(1600, int(m15.index.searchsorted(start_ts)))
        out[name] = dual15._run(m15, funding, features, config, start, end)
    return out


if __name__ == "__main__":
    main()
