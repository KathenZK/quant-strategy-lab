from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_trx_1h_adaptive_regime_search as search  # noqa: E402


base = search.load_engine()
FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
DATE_TAG = "2026-07-03"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_persistent_regime_boundary_{DATE_TAG}.json"
RANKING_CSV = ARTIFACT_DIR / f"trx_1h_persistent_regime_boundary_{DATE_TAG}.csv"
REPORT_MD = (
    DIAGNOSTIC_DIR / f"trx-1h-persistent-regime-boundary-{DATE_TAG}.md"
)

LEVERAGES = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
MIN_PREFIT_TRADES = 40
MIN_VALIDATION_TRADES = 10
MIN_OOS_TRADES = 12


def state_machine(
    long_entry: np.ndarray,
    short_entry: np.ndarray,
    long_exit: np.ndarray,
    short_exit: np.ndarray,
) -> np.ndarray:
    state = np.zeros(len(long_entry), dtype=np.int8)
    current = 0
    for index in range(len(state)):
        if current > 0 and bool(long_exit[index]):
            current = 0
        elif current < 0 and bool(short_exit[index]):
            current = 0
        if current == 0:
            if bool(long_entry[index]):
                current = 1
            elif bool(short_entry[index]):
                current = -1
        state[index] = current
    return state


def build_states(frame: pd.DataFrame) -> list[tuple[str, np.ndarray]]:
    close = frame["close"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    states: list[tuple[str, np.ndarray]] = []
    for fast in base.EMA_VALUES[:-1]:
        for slow in base.EMA_VALUES:
            if slow <= fast * 1.35:
                continue
            spread = (
                frame[f"ema{fast}"].to_numpy("float64")
                / frame[f"ema{slow}"].to_numpy("float64")
                - 1.0
            )
            for threshold_bps in (0.0, 5.0, 10.0, 20.0, 40.0, 80.0):
                threshold = threshold_bps / 10_000.0
                state = np.where(
                    spread > threshold,
                    1,
                    np.where(spread < -threshold, -1, 0),
                ).astype(np.int8)
                states.append(
                    (f"ema_state_{fast}_{slow}_t{threshold_bps:g}", state)
                )
    for window in (21, 34, 55, 89, 144, 233, 377):
        spread = close / frame[f"ema{window}"].to_numpy("float64") - 1.0
        for threshold_bps in (0.0, 5.0, 10.0, 20.0, 40.0, 80.0):
            threshold = threshold_bps / 10_000.0
            state = np.where(
                spread > threshold,
                1,
                np.where(spread < -threshold, -1, 0),
            ).astype(np.int8)
            states.append((f"price_ema_state_{window}_t{threshold_bps:g}", state))
    for fast, slow, signal in base.MACD_SETS:
        values = frame[f"macd_{fast}_{slow}_{signal}"].to_numpy("float64")
        state = np.where(np.isfinite(values), np.sign(values), 0).astype(np.int8)
        states.append((f"macd_state_{fast}_{slow}_{signal}", state))
    for window in base.DONCHIAN_WINDOWS + (336,):
        upper = pd.Series(high).shift(1).rolling(window, min_periods=window).max().to_numpy()
        lower = pd.Series(low).shift(1).rolling(window, min_periods=window).min().to_numpy()
        state = state_machine(
            close > upper,
            close < lower,
            close < lower,
            close > upper,
        )
        states.append((f"donchian_persistent_{window}", state))
    for window in base.BAND_WINDOWS:
        zscore = frame[f"bb_z{window}"].to_numpy("float64")
        for entry_z in (1.0, 1.5, 2.0, 2.5, 3.0):
            for exit_z in (0.0, 0.5):
                state = state_machine(
                    zscore <= -entry_z,
                    zscore >= entry_z,
                    zscore >= -exit_z,
                    zscore <= exit_z,
                )
                states.append(
                    (f"bb_revert_state_{window}_e{entry_z:g}_x{exit_z:g}", state)
                )
    for window in base.RSI_WINDOWS:
        values = frame[f"rsi{window}"].to_numpy("float64")
        for low_threshold, high_threshold in ((20.0, 80.0), (25.0, 75.0), (30.0, 70.0), (35.0, 65.0), (40.0, 60.0)):
            state = state_machine(
                values <= low_threshold,
                values >= high_threshold,
                values >= 50.0,
                values <= 50.0,
            )
            states.append(
                (
                    f"rsi_revert_state_{window}_{low_threshold:g}_{high_threshold:g}",
                    state,
                )
            )
    for window in base.STOCH_WINDOWS:
        values = frame[f"stoch_k{window}"].to_numpy("float64")
        for low_threshold, high_threshold in ((10.0, 90.0), (20.0, 80.0), (30.0, 70.0), (40.0, 60.0)):
            state = state_machine(
                values <= low_threshold,
                values >= high_threshold,
                values >= 50.0,
                values <= 50.0,
            )
            states.append(
                (
                    f"stoch_revert_state_{window}_{low_threshold:g}_{high_threshold:g}",
                    state,
                )
            )
    for window in base.VWAP_WINDOWS:
        deviation = frame[f"vwap_dev_atr{window}"].to_numpy("float64")
        for entry_atr in (0.75, 1.0, 1.5, 2.0, 2.5):
            state = state_machine(
                deviation <= -entry_atr,
                deviation >= entry_atr,
                deviation >= 0.0,
                deviation <= 0.0,
            )
            states.append((f"vwap_revert_state_{window}_{entry_atr:g}", state))
    vote_score = (
        frame["h4_spread"].to_numpy("float64")
        + frame["h12_spread"].to_numpy("float64")
        + frame["d1_spread"].to_numpy("float64")
    )
    votes = np.where(np.isfinite(vote_score), np.sign(vote_score), 0).astype(np.int8)
    states.append(("htf_spread_vote", votes))
    return states


def apply_side(state: np.ndarray, side_mode: str) -> np.ndarray:
    result = state.copy()
    if side_mode == "long":
        result[result < 0] = 0
    elif side_mode == "short":
        result[result > 0] = 0
    return result


def state_trades(
    frame: pd.DataFrame,
    desired: np.ndarray,
    *,
    name: str,
    style: str,
    leverage: float,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
) -> list[Any]:
    held = np.zeros(len(desired), dtype=np.int8)
    held[1:] = desired[:-1]
    held[-1] = 0
    open_ = frame["open"].to_numpy("float64")
    ts_ns = frame["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    trades: list[Any] = []
    index = 1
    while index < len(held) - 1:
        side = int(held[index])
        if side == 0:
            index += 1
            continue
        entry_i = index
        exit_i = entry_i + 1
        while exit_i < len(held) and int(held[exit_i]) == side:
            exit_i += 1
        if exit_i >= len(held):
            exit_i = len(held) - 1
        raw_entry = float(open_[entry_i])
        raw_exit = float(open_[exit_i])
        entry_price = raw_entry * (1.0 + side * base.SLIPPAGE_PER_FILL)
        exit_price = raw_exit * (1.0 - side * base.SLIPPAGE_PER_FILL)
        price_ret = side * (exit_price / entry_price - 1.0)
        fee_ret = base.FEE_PER_FILL * (1.0 + exit_price / entry_price)
        funding_ret = base.trade_funding(
            int(ts_ns[entry_i]),
            int(ts_ns[exit_i]),
            side,
            funding_times,
            funding_cumulative,
        )
        net_ret = price_ret - fee_ret + funding_ret
        trades.append(
            base.Trade(
                config=name,
                style=style,
                signal_i=entry_i - 1,
                entry_i=entry_i,
                exit_i=exit_i,
                signal_ts=pd.Timestamp(ts_ns[entry_i - 1], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                exit_reason="next_open_state_change",
                bars_held=exit_i - entry_i,
                exposure=leverage,
                net_ret_1x=net_ret,
                equity_ret=leverage * net_ret,
                mae_1x=min(0.0, net_ret),
                equity_mae=leverage * min(0.0, net_ret),
                mfe_1x=max(0.0, net_ret),
                funding_ret_1x=funding_ret,
                signal_atr_bps=float(frame["atr_bps"].iloc[entry_i - 1]),
            )
        )
        index = max(exit_i, index + 1)
    return trades


def gate(metric: dict[str, float], min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= search.TARGET_ANNUAL_MULTIPLE
        and metric["win_rate"] >= search.TARGET_WIN_RATE
        and metric["max_dd"] > search.TARGET_MAX_DD
    )


def prefit_score(
    train: dict[str, float],
    validation: dict[str, float],
    prefit: dict[str, float],
) -> float:
    if prefit["trades"] < MIN_PREFIT_TRADES or validation["trades"] < MIN_VALIDATION_TRADES:
        return -1e9
    log_annual = math.log(max(min(prefit["annual_multiple"], 1e6), 1e-9))
    balance = min(
        math.log(max(min(train["annual_multiple"], 1e6), 1e-9)),
        math.log(max(min(validation["annual_multiple"], 1e6), 1e-9)),
    )
    penalty = 12.0 * sum(
        max(0.0, -0.20 - item["max_dd"]) for item in (train, validation, prefit)
    )
    penalty += 5.0 * sum(
        max(0.0, 0.50 - item["win_rate"]) for item in (train, validation, prefit)
    )
    penalty += 4.0 * sum(item["total_return"] <= 0.0 for item in (train, validation))
    return float(0.8 * log_annual + balance + 0.2 * min(prefit["profit_factor"], 5.0) - penalty)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = search.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=search.WARMUP_DAYS)
    oos_start = full_end - pd.DateOffset(months=search.LOCKED_OOS_MONTHS)
    train_end = train_start + (oos_start - train_start) * 0.65

    states = build_states(frame)
    rows: list[dict[str, Any]] = []
    trade_cache: dict[tuple[str, str, float], list[Any]] = {}
    for state_name, raw_state in states:
        style = state_name.split("_state", 1)[0]
        for side_mode in ("both", "long", "short"):
            desired = apply_side(raw_state, side_mode)
            for leverage in LEVERAGES:
                name = f"{state_name}__{side_mode}__x{leverage:g}"
                trades = state_trades(
                    frame,
                    desired,
                    name=name,
                    style=style,
                    leverage=leverage,
                    funding_times=funding_times,
                    funding_cumulative=funding_cumulative,
                )
                train = base.metrics(trades, train_start, train_end)
                validation = base.metrics(trades, train_end, oos_start)
                prefit = base.metrics(trades, train_start, oos_start)
                score = prefit_score(train, validation, prefit)
                if score <= -1e8:
                    continue
                key = (state_name, side_mode, leverage)
                trade_cache[key] = trades
                row: dict[str, Any] = {
                    "name": name,
                    "state": state_name,
                    "side_mode": side_mode,
                    "leverage": leverage,
                    "prefit_score": score,
                    "prefit_pass": bool(
                        gate(prefit, MIN_PREFIT_TRADES)
                        and validation["total_return"] > 0.0
                        and validation["win_rate"] >= 0.50
                        and validation["max_dd"] > -0.20
                    ),
                }
                for prefix, values in (("train", train), ("validation", validation), ("prefit", prefit)):
                    row.update({f"{prefix}_{key}": value for key, value in values.items()})
                rows.append(row)
    ranking = pd.DataFrame(rows).sort_values(
        ["prefit_pass", "prefit_score", "prefit_annual_multiple"],
        ascending=False,
    )
    finalists = ranking.head(300).copy()
    final_rows: list[dict[str, Any]] = []
    for row in finalists.to_dict(orient="records"):
        key = (str(row["state"]), str(row["side_mode"]), float(row["leverage"]))
        trades = trade_cache[key]
        holdout = base.metrics(trades, oos_start, full_end)
        full = base.metrics(trades, train_start, full_end)
        row.update({f"holdout_{key}": value for key, value in holdout.items()})
        row.update({f"full_{key}": value for key, value in full.items()})
        row["target_pass"] = bool(
            gate(holdout, MIN_OOS_TRADES) and gate(full, MIN_PREFIT_TRADES)
        )
        final_rows.append(row)
    final = pd.DataFrame(final_rows)
    final.to_csv(RANKING_CSV, index=False)
    best = final.iloc[0].to_dict()
    target_hits = int(final["target_pass"].sum())
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "phase": "persistent_regime_optimistic_boundary",
        "status": "no_go_not_promoted" if target_hits == 0 else "diagnostic_hit_requires_executable_retest",
        "warning": "No intrabar adverse excursion or protective stop is modeled; this is an optimistic boundary, never promotion evidence.",
        "quality": quality,
        "split": {
            "train_start": train_start,
            "train_end": train_end,
            "oos_start": oos_start,
            "full_end": full_end,
        },
        "search_counts": {
            "causal_states": len(states),
            "generated_variants": len(states) * 3 * len(LEVERAGES),
            "eligible_variants": len(ranking),
            "frozen_finalists": len(final),
            "prefit_pass": int(ranking["prefit_pass"].sum()),
            "locked_target_pass": target_hits,
        },
        "best_prefit_selected": best,
    }
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    lines = [
        "# TRX-1H 持续 regime 机制上界审计 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            "在故意偏乐观的持仓路径上仍没有冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛；持续持仓机制不能补救首轮差距。"
            if target_hits == 0
            else "偏乐观边界出现硬门槛命中，但该路径没有 intrabar 风险与保护单模型，只能进入严格可执行复测。"
        ),
        "",
        f"- causal states：`{len(states)}`；generated variants：`{len(states) * 3 * len(LEVERAGES)}`；eligible：`{len(ranking)}`。",
        f"- prefit pass：`{int(ranking['prefit_pass'].sum())}`；locked target pass：`{target_hits}/{len(final)}`。",
        f"- 最佳 prefit-selected：`{best['name']}`；prefit annual `{best['prefit_annual_multiple']:.3f}x`，DD `{best['prefit_max_dd']:.2%}`，win `{best['prefit_win_rate']:.2%}`。",
        f"- locked OOS：annual `{best['holdout_annual_multiple']:.3f}x`，DD `{best['holdout_max_dd']:.2%}`，win `{best['holdout_win_rate']:.2%}`，trades `{int(best['holdout_trades'])}`。",
        "",
        "## 覆盖",
        "",
        "EMA/price-EMA/MACD/Donchian 持续趋势状态，以及 Bollinger/RSI/Stochastic/rolling-VWAP 持续均值回归状态；每种覆盖 both/long/short 与 `0.5x-10x` 杠杆。",
        "",
        "## 审计边界",
        "",
        "所有状态都只使用闭合 K，并从下一根 open 改变仓位；计入 `0.001` fee/fill、`4 bps` slippage/fill 和历史资金费。为构造对持续 regime 的有利上界，本审计只在交易端点计算回撤，不读取 intrabar adverse excursion，也不模拟保护 stop。因此它不能产生 candidate；若这种偏乐观边界仍不达标，就没有理由继续把该机制包装成可实盘策略。",
        "",
        "## 产物",
        "",
        f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
        f"- `{RANKING_CSV.relative_to(ROOT)}`",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(search.json_safe(payload["search_counts"]), indent=2), flush=True)
    print(json.dumps(search.json_safe(best), indent=2), flush=True)


if __name__ == "__main__":
    main()
