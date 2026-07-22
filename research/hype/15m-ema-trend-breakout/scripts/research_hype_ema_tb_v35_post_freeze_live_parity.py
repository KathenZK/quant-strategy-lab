"""审计 V35 参数冻结后的研究表现，并与生产实盘逐笔对账。

生产输入是 2026-07-22 只读提取的 SQLite trade_ledger 摘要，以及按相邻
entry 区间从 Binance USD-M income history 聚合的 REALIZED_PNL、COMMISSION
和 FUNDING_FEE。脚本不连接生产环境、不读取密钥，也不修改 runner。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_post_freeze_live_parity_2026-07-22"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"

# V35 规格使用数据的最后时间点；只统计此后新开仓，排除 2026-06-01
# 01:15 UTC 已经入场、23:15 UTC 才退出的跨界持仓。
FREEZE_DATA_END = pd.Timestamp("2026-06-01T03:00:00Z")
LIVE_SERVICE_FIRST_EVENT = pd.Timestamp("2026-06-12T09:42:11Z")
LIVE_FIRST_ENTRY = pd.Timestamp("2026-06-15T04:45:00Z")
SNAPSHOT_AT = pd.Timestamp("2026-07-22T05:53:14Z")


# binance_net_usdt 是每笔 entry 到下一笔 entry 之前的 HYPEUSDT income 聚合；
# 由于策略全局单仓，这一窗口完整覆盖本笔 entry/exit fee、realized PnL 与 funding。
LIVE_TRADES: tuple[dict[str, Any], ...] = (
    {
        "trade_id": "ht-e-1979443",
        "direction": 1,
        "entry_ts": "2026-06-15T04:45:00Z",
        "entry_price": 64.782,
        "entry_qty": 3.80,
        "allocation": 2.4689773262044223,
        "exit_ts": "2026-06-15T10:30:00Z",
        "exit_reason": "take_profit",
        "binance_realized_pnl_usdt": 9.975,
        "binance_commission_usdt": -0.17431511,
        "binance_funding_usdt": 0.01784884,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1979467",
        "direction": 1,
        "entry_ts": "2026-06-15T10:45:00Z",
        "entry_price": 67.176,
        "entry_qty": 4.23,
        "allocation": 2.590868462430135,
        "exit_ts": "2026-06-16T03:45:00Z",
        "exit_reason": "take_profit",
        "binance_realized_pnl_usdt": 10.96839,
        "binance_commission_usdt": -0.20110181,
        "binance_funding_usdt": 0.01387110,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1979556",
        "direction": 1,
        "entry_ts": "2026-06-16T09:00:00Z",
        "entry_price": 73.7885931,
        "entry_qty": 20.25,
        "allocation": 2.868171896672045,
        "exit_ts": "2026-06-16T10:45:00Z",
        "exit_reason": "take_profit",
        "binance_realized_pnl_usdt": 52.03049,
        "binance_commission_usdt": -1.05635939,
        "binance_funding_usdt": 0.0,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1979564",
        "direction": 1,
        "entry_ts": "2026-06-16T11:00:00Z",
        "entry_price": 75.468,
        "entry_qty": 22.07,
        "allocation": 2.9113896457765684,
        "exit_ts": "2026-06-17T11:00:00Z",
        "exit_reason": "stop_loss",
        "binance_realized_pnl_usdt": -79.0106,
        "binance_commission_usdt": -1.62607343,
        "binance_funding_usdt": -0.49061349,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1981191",
        "direction": 1,
        "entry_ts": "2026-07-03T09:45:00Z",
        "entry_price": 67.7169938,
        "entry_qty": 38.60,
        "allocation": 2.968387136765661,
        "exit_ts": "2026-07-03T14:45:00Z",
        "exit_reason": "take_profit",
        "binance_realized_pnl_usdt": 88.04684,
        "binance_commission_usdt": -1.84732252,
        "binance_funding_usdt": -0.13372818,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1981213",
        "direction": 1,
        "entry_ts": "2026-07-03T15:15:00Z",
        "entry_price": 70.5294647,
        "entry_qty": 466.98,
        "allocation": 3.0,
        "exit_ts": "2026-07-07T13:34:30.040Z",
        "exit_reason": "manual_exit",
        "binance_realized_pnl_usdt": 457.11625979,
        "binance_commission_usdt": -33.16440741,
        "binance_funding_usdt": -32.56097418,
        "manual_exit": True,
    },
    {
        "trade_id": "ht-e-1982171",
        "direction": -1,
        "entry_ts": "2026-07-13T14:45:00Z",
        "entry_price": 64.146,
        "entry_qty": 531.10,
        "allocation": 3.0,
        "exit_ts": "2026-07-15T02:57:34.125Z",
        "exit_reason": "stop_loss",
        "binance_realized_pnl_usdt": -1286.76139,
        "binance_commission_usdt": -34.71132125,
        "binance_funding_usdt": 8.03900295,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1982356",
        "direction": 1,
        "entry_ts": "2026-07-15T13:00:00Z",
        "entry_price": 68.9912188,
        "entry_qty": 437.05,
        "allocation": 3.0,
        "exit_ts": "2026-07-15T18:45:06.502Z",
        "exit_reason": "indicator_exit",
        "binance_realized_pnl_usdt": -393.22696973,
        "binance_commission_usdt": -29.95599855,
        "binance_funding_usdt": -1.48420863,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1982492",
        "direction": -1,
        "entry_ts": "2026-07-16T23:00:00Z",
        "entry_price": 61.8909443,
        "entry_qty": 466.06,
        "allocation": 3.0,
        "exit_ts": "2026-07-17T01:30:00Z",
        "exit_reason": "take_profit",
        "binance_realized_pnl_usdt": 735.8828,
        "binance_commission_usdt": -20.04424876,
        "binance_funding_usdt": -2.04017321,
        "manual_exit": False,
    },
    {
        "trade_id": "ht-e-1982504",
        "direction": -1,
        "entry_ts": "2026-07-17T02:00:00Z",
        "entry_price": 60.0265899,
        "entry_qty": 516.30,
        "allocation": 3.0,
        "exit_ts": "2026-07-17T16:02:42.328Z",
        "exit_reason": "manual_exit",
        "binance_realized_pnl_usdt": -392.17698973,
        "binance_commission_usdt": -31.18781661,
        "binance_funding_usdt": -3.05715181,
        "manual_exit": True,
    },
    {
        "trade_id": "ht-e-1982903",
        "direction": 1,
        "entry_ts": "2026-07-21T05:45:00Z",
        "entry_price": 63.0384048,
        "entry_qty": 471.63,
        "allocation": 3.0,
        "exit_ts": "2026-07-21T17:26:12Z",
        "exit_reason": "stop_loss",
        "binance_realized_pnl_usdt": -1043.22074992,
        "binance_commission_usdt": -29.20919231,
        "binance_funding_usdt": 0.01119474,
        "manual_exit": False,
    },
)


def research_trade_total_return(
    trades: pd.DataFrame,
    trade_cost_rate: float,
) -> pd.Series:
    """补回 entry cost，得到从开仓前权益到最终退出后的完整单笔收益。"""
    entry_multiplier = 1.0 - trade_cost_rate * trades["allocation"]
    return (1.0 + trades["trade_return"]) * entry_multiplier - 1.0


def compounded_metrics(returns: pd.Series) -> dict[str, Any]:
    if returns.empty:
        return {
            "return_pct": 0.0,
            "max_closed_trade_drawdown_pct": 0.0,
            "trades": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
        }
    curve = (1.0 + returns.astype(float)).cumprod()
    prior_peak = pd.concat(
        [pd.Series([1.0]), curve.reset_index(drop=True)],
        ignore_index=True,
    ).cummax().iloc[1:].to_numpy()
    drawdown = curve.to_numpy() / prior_peak - 1.0
    wins = int(returns.gt(0.0).sum())
    return {
        "return_pct": round(float(curve.iloc[-1] - 1.0) * 100.0, 4),
        "max_closed_trade_drawdown_pct": round(
            float(drawdown.min()) * 100.0,
            4,
        ),
        "trades": int(len(returns)),
        "wins": wins,
        "win_rate_pct": round(wins / len(returns) * 100.0, 2),
    }


def prepare_live_trades() -> pd.DataFrame:
    live = pd.DataFrame(LIVE_TRADES)
    live["entry_ts"] = pd.to_datetime(
        live["entry_ts"],
        utc=True,
        format="mixed",
    )
    live["exit_ts"] = pd.to_datetime(
        live["exit_ts"],
        utc=True,
        format="mixed",
    )
    live["binance_net_usdt"] = (
        live["binance_realized_pnl_usdt"]
        + live["binance_commission_usdt"]
        + live["binance_funding_usdt"]
    )
    live["implied_entry_equity_usdt"] = (
        live["entry_price"] * live["entry_qty"] / live["allocation"]
    )
    live["live_total_return"] = (
        live["binance_net_usdt"] / live["implied_entry_equity_usdt"]
    )
    return live


def prepare_research_trades(
    run: base.RunResult,
    config: base.V35Config,
) -> pd.DataFrame:
    trades = run.trades.copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades = trades.loc[trades["entry_ts"].gt(FREEZE_DATA_END)].copy()
    trades["research_total_return"] = research_trade_total_return(
        trades,
        config.trade_cost_rate,
    )
    return trades


def parity_table(
    research: pd.DataFrame,
    live: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    research_columns = [
        "entry_ts",
        "direction",
        "exit_ts",
        "entry_price",
        "exit_price",
        "entry_atr",
        "allocation",
        "exit_reason",
        "research_total_return",
    ]
    renamed = research[research_columns].rename(
        columns={
            "exit_ts": "research_exit_ts",
            "entry_price": "research_entry_price",
            "exit_price": "research_exit_price",
            "entry_atr": "research_entry_atr",
            "allocation": "research_allocation",
            "exit_reason": "research_exit_reason",
        }
    )
    matched = live.merge(
        renamed,
        on=["entry_ts", "direction"],
        how="inner",
        validate="one_to_one",
    )
    matched["entry_adverse_slippage_bps"] = (
        matched["direction"]
        * (
            matched["entry_price"] / matched["research_entry_price"]
            - 1.0
        )
        * 10_000.0
    )
    matched["return_delta_pp"] = (
        matched["live_total_return"]
        - matched["research_total_return"]
    ) * 100.0
    matched["exit_reason_match"] = (
        ~matched["manual_exit"]
        & matched["exit_reason"].eq(matched["research_exit_reason"])
    )

    keys = ["entry_ts", "direction"]
    research_only = research.merge(
        live[keys],
        on=keys,
        how="left",
        indicator=True,
    ).loc[lambda frame: frame["_merge"].eq("left_only")].drop(
        columns="_merge"
    )
    live_only = live.merge(
        research[keys],
        on=keys,
        how="left",
        indicator=True,
    ).loc[lambda frame: frame["_merge"].eq("left_only")].drop(
        columns="_merge"
    )
    return matched, research_only, live_only


def distribution(values: pd.Series) -> dict[str, float]:
    return {
        "mean": round(float(values.mean()), 4),
        "median": round(float(values.median()), 4),
        "p90": round(float(values.quantile(0.90)), 4),
        "max": round(float(values.max()), 4),
    }


def serializable_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    no_floor = base.ProfitFloorConfig(enabled=False)

    canonical_features = base.build_features(frame, config)
    v35 = base.run_backtest(
        "v35",
        frame,
        funding,
        canonical_features,
        config,
        no_floor,
    )
    v35_1_features = signal_engine.build_signals(
        canonical_features,
        config,
        signal_engine.SignalFlags(short_use_h1_ema=False),
    )
    v35_1 = base.run_backtest(
        "v35_1",
        frame,
        funding,
        v35_1_features,
        config,
        no_floor,
    )
    parity_diff = float(
        (v35.equity_curve - v35_1.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise RuntimeError(f"V35/V35.1 parity changed: {parity_diff}")

    research = prepare_research_trades(v35, config)
    live = prepare_live_trades()
    matched, research_only, live_only = parity_table(research, live)

    research_metrics = compounded_metrics(
        research["research_total_return"]
    )
    live_metrics = compounded_metrics(live["live_total_return"])
    matched_research_metrics = compounded_metrics(
        matched["research_total_return"]
    )
    matched_live_metrics = compounded_metrics(
        matched["live_total_return"]
    )
    automatic = matched.loc[~matched["manual_exit"]].copy()
    manual = matched.loc[matched["manual_exit"]].copy()

    if len(research) != 12 or len(live) != 11 or len(matched) != 11:
        raise RuntimeError(
            "Unexpected trade counts: "
            f"research={len(research)} live={len(live)} matched={len(matched)}"
        )
    if len(research_only) != 1 or not live_only.empty:
        raise RuntimeError(
            "Unexpected parity shape: "
            f"research_only={len(research_only)} live_only={len(live_only)}"
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_reference": "HYPE-EMA-TB-V35",
        "run_date": "2026-07-22",
        "status": "runner_tracking_diagnostic_only",
        "boundaries": {
            "parameter_freeze_data_end_utc": FREEZE_DATA_END.isoformat(),
            "spec_documented_in_git_date": "2026-06-08",
            "live_service_first_event_utc": (
                LIVE_SERVICE_FIRST_EVENT.isoformat()
            ),
            "live_first_entry_utc": LIVE_FIRST_ENTRY.isoformat(),
            "snapshot_at_utc": SNAPSHOT_AT.isoformat(),
        },
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "v35_vs_v35_1_max_equity_diff": parity_diff,
            "production_evidence": (
                "read-only SQLite trade_ledger/event_log plus Binance "
                "USD-M income history"
            ),
        },
        "assumptions": {
            "research_market": "Binance USD-M HYPEUSDT perpetual 15m",
            "research_execution": (
                "K0 close signal, K2 open entry, K1 ATR672, intrabar "
                "TP5/SL7 stop-first, indicator/timeout next open."
            ),
            "research_costs": (
                "0.00085 per filled allocation (0.00045 fee + 4bps "
                "adverse slippage) plus Binance funding."
            ),
            "post_freeze_rule": (
                "Only trades with entry_ts strictly later than the frozen "
                "dataset end are counted; the crossing position opened at "
                "2026-06-01 01:15 UTC is excluded."
            ),
            "live_return": (
                "Time-weighted trade return uses Binance income net divided "
                "by entry notional/allocation; deposits and withdrawals "
                "therefore do not contaminate the return."
            ),
            "drawdown": (
                "Reported comparison drawdown is closed-trade sequence "
                "drawdown, not intratrade mark-to-market drawdown."
            ),
        },
        "config": asdict(config),
        "research_post_freeze": {
            **research_metrics,
            "long_trades": int(research["direction"].eq(1).sum()),
            "short_trades": int(research["direction"].eq(-1).sum()),
            "exit_counts": {
                str(key): int(value)
                for key, value in research["exit_reason"]
                .value_counts()
                .items()
            },
        },
        "live": {
            **live_metrics,
            "cash_net_pnl_usdt_not_return_comparable": round(
                float(live["binance_net_usdt"].sum()),
                4,
            ),
            "long_trades": int(live["direction"].eq(1).sum()),
            "short_trades": int(live["direction"].eq(-1).sum()),
            "manual_exits": int(live["manual_exit"].sum()),
            "exit_counts": {
                str(key): int(value)
                for key, value in live["exit_reason"]
                .value_counts()
                .items()
            },
        },
        "parity": {
            "exact_entry_matches": int(len(matched)),
            "research_only_entries": int(len(research_only)),
            "live_only_entries": int(len(live_only)),
            "automatic_exit_reason_matches": int(
                automatic["exit_reason_match"].sum()
            ),
            "automatic_trades": int(len(automatic)),
            "entry_adverse_slippage_bps": distribution(
                matched["entry_adverse_slippage_bps"]
            ),
            "full_research_minus_live_return_pp": round(
                research_metrics["return_pct"]
                - live_metrics["return_pct"],
                4,
            ),
            "matched_research": matched_research_metrics,
            "matched_live": matched_live_metrics,
            "automatic_research": compounded_metrics(
                automatic["research_total_return"]
            ),
            "automatic_live": compounded_metrics(
                automatic["live_total_return"]
            ),
            "manual_research": compounded_metrics(
                manual["research_total_return"]
            ),
            "manual_live": compounded_metrics(
                manual["live_total_return"]
            ),
            "research_only": serializable_rows(
                research_only[
                    [
                        "entry_ts",
                        "exit_ts",
                        "direction",
                        "exit_reason",
                        "research_total_return",
                    ]
                ]
            ),
        },
        "runtime_observation": {
            "through_2026_07_20": (
                "Production ran V35; V35.1 was recorded from 2026-07-20 "
                "07:42 UTC. Their realized path is parity-equivalent here."
            ),
            "current_as_of_snapshot": (
                "run_metadata records HYPE-EMA-TB-V35.3 at 2026-07-22 "
                "04:09 UTC; no post-switch trade exists in this snapshot."
            ),
            "governance_note": (
                "Observed external production state does not itself promote "
                "V35.3 or clear its not-live-ready research blockers."
            ),
        },
        "matched_trades": serializable_rows(matched),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    export = matched.copy()
    export["parity_status"] = np.where(
        export["manual_exit"],
        "manual_path_divergence",
        np.where(
            export["exit_reason_match"],
            "automatic_match",
            "automatic_mismatch",
        ),
    )
    if not research_only.empty:
        missing = research_only.copy()
        missing["trade_id"] = ""
        missing["entry_price"] = np.nan
        missing["entry_qty"] = np.nan
        missing["live_total_return"] = np.nan
        missing["return_delta_pp"] = np.nan
        missing["entry_adverse_slippage_bps"] = np.nan
        missing["parity_status"] = "research_only_blocked_by_live_occupancy"
        export = pd.concat([export, missing], ignore_index=True, sort=False)
    export.to_csv(TRADES_PATH, index=False)

    print(
        f"data {quality['start']} ~ {quality['end']} "
        f"quality_gate={quality_gate['passed']} parity={parity_diff:.2e}"
    )
    print(
        "research post-freeze "
        f"{research_metrics['return_pct']:+.4f}% / "
        f"{research_metrics['win_rate_pct']:.2f}% / "
        f"{research_metrics['trades']} trades"
    )
    print(
        "live time-weighted "
        f"{live_metrics['return_pct']:+.4f}% / "
        f"{live_metrics['win_rate_pct']:.2f}% / "
        f"{live_metrics['trades']} trades"
    )
    print(
        f"matched={len(matched)} research_only={len(research_only)} "
        f"live_only={len(live_only)} manual={int(live['manual_exit'].sum())}"
    )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
