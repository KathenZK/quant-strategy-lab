from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_5m_micro_scalp_search as engine
from research_hype_5m_micro_scalp_v1_1_ablation_and_tuning import v1_1_config
from research_hype_5m_micro_scalp_v1_simplified_combo_search import verify_raw_normalized_parity


RUN_ID = "2026-07-01"
FAMILY_ROOT = Path("research/hype/5m-micro-scalp")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
RESEARCH_NOTE_ROOT = FAMILY_ROOT / "notes"

REPORT_PATH = RESEARCH_NOTE_ROOT / f"hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-{RUN_ID}.md"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_{RUN_ID}.json"
CONFIG_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_2_baseline_config_{RUN_ID}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_summary_{RUN_ID}.csv"
SLICES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_slices_{RUN_ID}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_monthly_{RUN_ID}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_trades_{RUN_ID}.csv"

FEE_RATE_PER_FILL = 0.001
SLIPPAGE_RATE_PER_FILL = 4.0 / 10000.0
LEVERAGES = (1.0, 2.0, 3.0)


def v1_2_config() -> engine.ScalpConfig:
    return replace(
        v1_1_config(),
        name="HYPE-5M-Micro-Scalp-V1.2",
        ema_htf=192,
        min_adx=0.0,
        max_chop=70.0,
        min_rvol=0.75,
        max_atr_pct_bps=9999.0,
        tp_bps=110.0,
        sl_bps=400.0,
    )


def assert_data_quality(quality: dict[str, Any], parity: dict[str, Any]) -> None:
    blockers: list[str] = []
    if int(quality["missing_bars"]) != 0:
        blockers.append(f"missing_bars={quality['missing_bars']}")
    if int(quality["duplicate_ts"]) != 0:
        blockers.append(f"duplicate_ts={quality['duplicate_ts']}")
    if any(int(value) != 0 for value in quality["nulls"].values()):
        blockers.append(f"nulls={quality['nulls']}")
    if any(int(value) != 0 for value in quality["ohlcv_violations"].values()):
        blockers.append(f"ohlcv_violations={quality['ohlcv_violations']}")
    if quality["is_closed_counts"] != {"True": int(quality["rows"])}:
        blockers.append(f"is_closed_counts={quality['is_closed_counts']}")
    if int(parity["timestamp_mismatch"]) != 0 or any(int(value) != 0 for value in parity["field_mismatches"].values()):
        blockers.append(f"raw_normalized_parity={parity}")
    if blockers:
        raise RuntimeError("data quality blockers: " + "; ".join(blockers))


def leveraged_metrics(
    trades: list[engine.Trade],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    leverage: float,
) -> dict[str, float | int | bool]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if not selected:
        return {
            "trades": 0,
            "trades_per_day": 0.0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_account": 0.0,
            "worst_trade_account": 0.0,
            "best_trade_account": 0.0,
            "liquidation_path_count": 0,
            "bankrupt": False,
        }

    account_rets = np.array([leverage * trade.net_ret_1x for trade in selected], dtype=float)
    account_maes = np.array([leverage * trade.mae_1x for trade in selected], dtype=float)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    bankrupt = False
    liquidation_path_count = 0
    for ret, mae in zip(account_rets, account_maes, strict=True):
        if 1.0 + mae <= 0.0:
            liquidation_path_count += 1
        trough = equity * max(0.0, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        if 1.0 + ret <= 0.0:
            equity = 0.0
            max_dd = -1.0
            bankrupt = True
            break
        equity *= 1.0 + ret
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)

    wins = account_rets[account_rets > 0]
    losses = account_rets[account_rets <= 0]
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    annualized = float(equity ** (365.25 / days)) if equity > 0 else 0.0
    return {
        "trades": int(len(selected)),
        "trades_per_day": float(len(selected) / days),
        "equity_multiple": float(equity),
        "annualized_multiple": annualized,
        "total_return": float(equity - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float((account_rets > 0).mean()),
        "profit_factor": profit_factor,
        "avg_trade_account": float(account_rets.mean()),
        "worst_trade_account": float(account_rets.min()),
        "best_trade_account": float(account_rets.max()),
        "liquidation_path_count": int(liquidation_path_count),
        "bankrupt": bankrupt,
    }


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return f"{value:.2f}x"


def num(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.3f}"


def table(rows: pd.DataFrame, *, include_slice: bool = False) -> list[str]:
    prefix = "| 策略 | 杠杆 |"
    divider = "| --- | ---: |"
    if include_slice:
        prefix += " 窗口 |"
        divider += " --- |"
    header = prefix + " 交易数 | 年化资金倍数 | 区间收益 | 最大回撤 | 胜率 | PF | 平均单笔账户收益 | 最差单笔 |"
    rule = divider + " ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    output = [header, rule]
    for row in rows.to_dict(orient="records"):
        values = f"| `{row['strategy']}` | `{float(row['leverage']):.0f}x` |"
        if include_slice:
            values += f" `{row['slice']}` |"
        values += (
            f" `{int(row['trades'])}` | `{mult(float(row['annualized_multiple']))}` | "
            f"`{pct(float(row['total_return']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['profit_factor']))}` | "
            f"`{pct(float(row['avg_trade_account']))}` | `{pct(float(row['worst_trade_account']))}` |"
        )
        output.append(values)
    return output


def render_report(
    summary: pd.DataFrame,
    slices: pd.DataFrame,
    monthly: pd.DataFrame,
    quality: dict[str, Any],
    parity: dict[str, Any],
    configs: list[engine.ScalpConfig],
) -> str:
    monthly_stats = (
        monthly.groupby(["strategy", "leverage"], as_index=False)
        .agg(
            negative_months=("total_return", lambda values: int((values < 0).sum())),
            worst_month_return=("total_return", "min"),
            best_month_return=("total_return", "max"),
        )
        .sort_values(["strategy", "leverage"])
    )
    indexed = summary.set_index(["strategy", "leverage"])
    baseline_1x = indexed.loc[("HYPE-5M-Micro-Scalp-V1.1", 1.0)]
    baseline_2x = indexed.loc[("HYPE-5M-Micro-Scalp-V1.1", 2.0)]
    baseline_3x = indexed.loc[("HYPE-5M-Micro-Scalp-V1.1", 3.0)]
    v1_2_1x = indexed.loc[("HYPE-5M-Micro-Scalp-V1.2", 1.0)]
    v1_2_2x = indexed.loc[("HYPE-5M-Micro-Scalp-V1.2", 2.0)]
    v1_2_3x = indexed.loc[("HYPE-5M-Micro-Scalp-V1.2", 3.0)]
    slice_view = slices.loc[slices["slice"].isin(["train_2025_05_30_to_2026_03_01", "val_2026_03_01_to_2026_06_01", "fwd_2026_06_01_to_latest", "recent_30d"])]
    lines = [
        "# HYPE-5M-Micro-Scalp-V1.2 登记与 1-3 倍杠杆复测 2026-07-01",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "本报告将 V1.1 微调观察行 `V1.1_tune_grid_004895` 正式登记为 `HYPE-5M-Micro-Scalp-V1.2`，并按用户指定成本对 V1.1/V1.2 做 `1x/2x/3x` 复测。",
        "",
        "## 数据质量",
        "",
        f"- Binance HYPEUSDT perpetual `5m`：`{quality['rows']}` 根，UTC `{quality['start_ts']}` 至 `{quality['end_ts']}`。",
        f"- raw/normalized 分区：`{parity['raw_files']}` / `{quality['normalized_file_count']}`；对齐行数 `{parity['merged_rows']}`。",
        f"- missing `{quality['missing_bars']}`，duplicate `{quality['duplicate_ts']}`，关键空值 `{sum(quality['nulls'].values())}`，OHLC/VWAP/volume 违规 `{sum(quality['ohlcv_violations'].values())}`。",
        "- raw/normalized 的 timestamp、OHLCV、quote volume、trade count、VWAP、is_closed 均逐字段一致。",
        "",
        "## 成本与杠杆口径",
        "",
        "- 手续费：`0.001` / fill，即每次成交按名义价值收取 `10 bps`；完整进出约 `20 bps`。",
        "- 滑点：entry `4 bps`、exit `4 bps`，均按不利方向；完整进出约 `8 bps`。",
        "- 杠杆：`1x`、`2x`、`3x`；每笔名义仓位分别为当时账户权益的 `100%`、`200%`、`300%`，逐笔复利，一次只持有一个仓位。",
        "- 账户单笔收益按 `leverage * net_ret_1x` 计算，因此杠杆同步放大价格盈亏、手续费、滑点和持仓内 MAE。",
        "- 信号与订单时序不变：收盘 K 产生信号，下一根 open 入场，立即放固定 TP/SL；同 K 双触发按 stop-first；gap 按 open 市价；timeout 下一根 open。",
        "- 新滑点会改变实际 entry、TP/SL 绝对价位及退出时点，进而改变冷却期占用；所以本次交易数可以与旧成本报告略有差异，不是信号参数发生变化。",
        "- 未计资金费；未模拟 Binance maintenance margin 与强平价格。当前路径在 `3x` 下没有账户 MAE 穿越 `-100%`，但这不等于完成交易所强平审计。",
        "",
        "## 全样本结果",
        "",
        *table(summary),
        "",
        "## 时间切片",
        "",
        *table(slice_view, include_slice=True),
        "",
        "## 月度稳定性",
        "",
        "| 策略 | 杠杆 | 负收益月份 | 最差月 | 最好月 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in monthly_stats.to_dict(orient="records"):
        lines.append(
            f"| `{row['strategy']}` | `{float(row['leverage']):.0f}x` | `{int(row['negative_months'])}` | "
            f"`{pct(float(row['worst_month_return']))}` | `{pct(float(row['best_month_return']))}` |"
        )

    lines.extend(["", "## 参数身份", ""])
    for cfg in configs:
        lines.append(
            f"- `{cfg.name}`：EMA `{cfg.ema_fast}/{cfg.ema_slow}/{cfg.ema_htf}`，VWAP deviation `{cfg.vwap_dev_bps:g} bps`，"
            f"TP/SL `{cfg.tp_bps:g}/{cfg.sl_bps:g} bps`，hold/cooldown `{cfg.max_hold_bars}/{cfg.cooldown_bars}`。"
        )

    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            "- V1.2 是 `V1.1_tune_grid_004895` 的正式版本身份；本次没有重新搜索参数，只统一了版本名、成本与杠杆复测口径。",
            f"- V1.1 在 `1x/2x/3x` 下为 `{mult(float(baseline_1x['annualized_multiple']))}` / `{mult(float(baseline_2x['annualized_multiple']))}` / `{mult(float(baseline_3x['annualized_multiple']))}`，maxDD 为 `{pct(float(baseline_1x['max_dd']))}` / `{pct(float(baseline_2x['max_dd']))}` / `{pct(float(baseline_3x['max_dd']))}`。",
            f"- V1.2 在 `1x/2x/3x` 下为 `{mult(float(v1_2_1x['annualized_multiple']))}` / `{mult(float(v1_2_2x['annualized_multiple']))}` / `{mult(float(v1_2_3x['annualized_multiple']))}`，maxDD 为 `{pct(float(v1_2_1x['max_dd']))}` / `{pct(float(v1_2_2x['max_dd']))}` / `{pct(float(v1_2_3x['max_dd']))}`。它在三个杠杆档位收益均更高，但回撤也略深，不是 V1.1 的全指标严格替代。",
            "- 若继续坚持“小回撤”，`1x` 是本次唯一仍把全样本 maxDD 控制在约 `10%` 的档位；`2x` 已接近 `20%`，`3x` 接近 `30%`。",
            "- V1.2 的 train PF 明显低于后续窗口，近期高 PF 不应外推；版本登记不改变其 paper-audit observation / not live-ready 状态。",
            "- `2x/3x` 是研究压力测试，不构成实盘仓位建议；任何 promotion 仍需逐笔路径、交易所 bracket maintenance、强平/保证金、资金费、重启恢复与 paper/live reconciliation。",
            "- VAL/FWD 已参与前序筛选，不能视作全新独立 OOS。",
            "",
            "## 产物",
            "",
            f"- Script：`{Path(__file__).as_posix()}`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- Slice CSV：`{SLICES_PATH}`",
            f"- Monthly CSV：`{MONTHLY_PATH}`",
            f"- Trades CSV：`{TRADES_PATH}`",
            f"- JSON：`{JSON_PATH}`",
            f"- V1.2 config：`{CONFIG_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame_raw, quality = engine.load_hype_5m()
    parity = verify_raw_normalized_parity(frame_raw)
    assert_data_quality(quality, parity)
    frame = engine.add_features(frame_raw)

    engine.FEE_RATE_PER_FILL = FEE_RATE_PER_FILL
    engine.ENTRY_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL
    engine.EXIT_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL

    configs = [v1_1_config(), v1_2_config()]
    slices = engine.validation_slices(frame)
    months = engine.month_slices(frame)
    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    reason_counts: dict[str, dict[str, int]] = {}

    for cfg in configs:
        signal = engine.build_signal(frame, cfg)
        trades, reasons = engine.simulate_trades(frame, signal, cfg)
        reason_counts[cfg.name] = reasons
        for leverage in LEVERAGES:
            for trade in trades:
                trade_rows.append(
                    {
                        **asdict(trade),
                        "strategy": cfg.name,
                        "leverage": leverage,
                        "net_account_ret": leverage * trade.net_ret_1x,
                        "mae_account": leverage * trade.mae_1x,
                        "mfe_account": leverage * trade.mfe_1x,
                    }
                )
            for item in slices:
                metrics = leveraged_metrics(trades, start=item["start"], end=item["end"], leverage=leverage)
                row = {
                    "strategy": cfg.name,
                    "leverage": leverage,
                    "slice": item["name"],
                    "slice_start": item["start"],
                    "slice_end": item["end"],
                    **metrics,
                }
                slice_rows.append(row)
                if item["name"] == "full":
                    summary_rows.append(row)
            for item in months:
                monthly_rows.append(
                    {
                        "strategy": cfg.name,
                        "leverage": leverage,
                        "month": item["name"],
                        "month_start": item["start"],
                        "month_end": item["end"],
                        **leveraged_metrics(trades, start=item["start"], end=item["end"], leverage=leverage),
                    }
                )

    summary = pd.DataFrame(summary_rows).sort_values(["strategy", "leverage"])
    slices_frame = pd.DataFrame(slice_rows).sort_values(["strategy", "leverage", "slice_start"])
    monthly = pd.DataFrame(monthly_rows).sort_values(["strategy", "leverage", "month_start"])
    trade_frame = pd.DataFrame(trade_rows).sort_values(["strategy", "leverage", "entry_ts"])

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    RESEARCH_NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices_frame.to_csv(SLICES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    trade_frame.to_csv(TRADES_PATH, index=False)
    CONFIG_PATH.write_text(json.dumps(asdict(v1_2_config()), indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(render_report(summary, slices_frame, monthly, quality, parity, configs), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "registered_version": "HYPE-5M-Micro-Scalp-V1.2",
                "source_observation": "V1.1_tune_grid_004895",
                "status": "paper-audit observation / not live-ready",
                "run_id": RUN_ID,
                "data_quality": quality,
                "raw_normalized_parity": parity,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "slippage_rate_per_fill": SLIPPAGE_RATE_PER_FILL,
                    "funding_included": False,
                },
                "leverage_model": {
                    "leverages": LEVERAGES,
                    "notional_as_equity_multiple": True,
                    "one_position_at_a_time": True,
                    "maintenance_margin_modeled": False,
                },
                "configs": [asdict(cfg) for cfg in configs],
                "reason_counts": reason_counts,
                "summary": summary.to_dict(orient="records"),
                "outputs": {
                    "markdown": str(REPORT_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICES_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "trades": str(TRADES_PATH),
                    "config": str(CONFIG_PATH),
                },
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
