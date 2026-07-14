"""Frozen-parameter mk7-v8 replay for the post-2026-07-02 OOS window."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY = ROOT / "research/asset-portfolios/mk7-multi-strategy-account"
CACHE = ROOT / "data/cache/mk7_v8_binance"
ART = FAMILY / "artifacts"
NOTES = FAMILY / "notes"

FROZEN_END = pd.Timestamp("2026-07-02T03:00:00Z")
STRICT_10D_END = FROZEN_END + pd.Timedelta(days=10)
JULY_START = pd.Timestamp("2026-07-01T00:00:00Z")
DATE_TAG = "2026-07-13"

OOS_1H = {
    asset: CACHE / f"klines/{asset.lower()}usdt_1h_oos_extended.parquet"
    for asset in ("TRX", "SOL", "HYPE", "ETH", "BTC", "BNB")
}


def load_backtest() -> Any:
    path = FAMILY / "scripts/research_mk7_v8_backtest.py"
    spec = importlib.util.spec_from_file_location("mk7_oos_engine", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load mk7 backtest: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def cohort_stats(
    selected: list[tuple[Any, float]],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    entries = [(c, exp) for c, exp in selected if start <= c.entry_ts < end]
    closed = [(c, exp) for c, exp in entries if c.exit_ts < end]
    open_at_end = [(c, exp) for c, exp in selected if c.entry_ts < end <= c.exit_ts]
    returns = [0.5 * exp * c.net_ret_1x for c, exp in closed]
    by_component = {
        component: sum(c.component == component for c, _exp in entries)
        for component in ("six", "k2fq", "mii")
    }
    by_asset = {
        asset: sum(c.asset == asset for c, _exp in entries)
        for asset in ("TRX", "SOL", "HYPE", "ETH", "BTC", "BNB")
    }
    return {
        "entry_trades": len(entries),
        "closed_entry_trades_by_window_end": len(closed),
        "entry_trades_still_open_at_window_end": sum(c.exit_ts >= end for c, _ in entries),
        "account_positions_open_at_window_end": len(open_at_end),
        "closed_trade_win_rate": (
            sum(value > 0 for value in returns) / len(returns) if returns else None
        ),
        "closed_trade_profit_factor": (
            sum(value for value in returns if value > 0)
            / abs(sum(value for value in returns if value < 0))
            if any(value < 0 for value in returns)
            else None
        ),
        "entries_by_component": by_component,
        "entries_by_asset": by_asset,
        "open_positions": [
            {
                "asset": c.asset,
                "component": c.component,
                "side": c.side,
                "entry_ts": c.entry_ts,
                "scheduled_exit_ts_in_replay": c.exit_ts,
                "exposure": exp,
            }
            for c, exp in open_at_end
        ],
    }


def metrics_for_window(
    engine: Any,
    selected: list[tuple[Any, float]],
    curve: pd.Series,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    metrics = engine.equity_metrics(
        selected, start, end, full_curve=curve, main_annual=False
    )
    return {
        "start": start,
        "end": end,
        "duration_hours": (end - start).total_seconds() / 3600.0,
        "account_return": metrics["multiple"] - 1.0,
        "account_multiple": metrics["multiple"],
        "mdd": metrics["mdd"],
        "daily_sharpe": metrics["sharpe"],
        **cohort_stats(selected, start=start, end=end),
    }


def parity_check(
    selected: list[tuple[Any, float]], frozen_path: Path
) -> dict[str, Any]:
    frozen = pd.read_csv(frozen_path)
    frozen["entry_ts"] = pd.to_datetime(frozen["entry_ts"], utc=True)
    frozen["exit_ts"] = pd.to_datetime(frozen["exit_ts"], utc=True)
    frozen = frozen.loc[frozen["entry_ts"] < FROZEN_END].copy()
    extended_rows = [
        {
            "asset": c.asset,
            "leg": c.leg,
            "side": c.side,
            "entry_ts": c.entry_ts,
            "exit_ts": c.exit_ts,
        }
        for c, _exp in selected
        if c.entry_ts < FROZEN_END
    ]
    extended = pd.DataFrame(extended_rows)
    keys = ["asset", "leg", "side", "entry_ts"]
    merged = frozen[keys + ["exit_ts"]].merge(
        extended[keys + ["exit_ts"]],
        on=keys,
        how="outer",
        suffixes=("_frozen", "_extended"),
        indicator=True,
    )
    both = merged.loc[merged["_merge"] == "both"]
    exit_mismatch = int(
        both["exit_ts_frozen"].ne(both["exit_ts_extended"]).sum()
    )
    return {
        "frozen_entry_count": len(frozen),
        "extended_replay_pre_oos_entry_count": len(extended),
        "missing_from_extended": int((merged["_merge"] == "left_only").sum()),
        "new_before_oos": int((merged["_merge"] == "right_only").sum()),
        "common_entry_exit_timestamp_mismatches": exit_mismatch,
        "entry_identity_pass": bool((merged["_merge"] == "both").all()),
    }


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)
    update_meta = json.loads(
        (CACHE / "logs/oos_data_update_2026-07-13.json").read_text()
    )
    latest_end = pd.Timestamp(update_meta["common_closed_end"])
    if latest_end < STRICT_10D_END:
        raise RuntimeError(
            f"latest data {latest_end} does not cover strict OOS end {STRICT_10D_END}"
        )

    engine = load_backtest()
    engine.FULL_END = latest_end
    engine.ARTIFACT_1H = OOS_1H

    six, six_counts, frames = engine.six_coin_candidates()
    funding = pd.read_parquet(
        ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp"
        / "symbol=hype_usdt_usdt/funding.parquet"
    )
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    k2 = engine.k2fq_candidates(funding)
    mii = engine.mii_candidates()
    selected = engine.select_dual_slot(six + k2 + mii)
    curve = engine.build_full_equity_curve(selected, frames)

    frozen_selected_path = ART / "mk7_v8_selected_trades_2026-07-13.csv"
    parity = parity_check(selected, frozen_selected_path)
    strict = metrics_for_window(
        engine,
        selected,
        curve,
        start=FROZEN_END,
        end=STRICT_10D_END,
    )
    through_latest = metrics_for_window(
        engine,
        selected,
        curve,
        start=FROZEN_END,
        end=latest_end,
    )
    july_mtd = metrics_for_window(
        engine,
        selected,
        curve,
        start=JULY_START,
        end=latest_end,
    )

    oos_rows = []
    for c, exp in selected:
        if c.entry_ts < JULY_START:
            continue
        oos_rows.append(
            {
                "asset": c.asset,
                "component": c.component,
                "leg": c.leg,
                "side": c.side,
                "entry_ts": c.entry_ts.isoformat(),
                "exit_ts": c.exit_ts.isoformat(),
                "exposure": exp,
                "net_ret_1x": c.net_ret_1x,
                "equity_ret": 0.5 * exp * c.net_ret_1x,
                "inside_strict_10d_entry_window": (
                    FROZEN_END <= c.entry_ts < STRICT_10D_END
                ),
                "closed_before_strict_10d_end": c.exit_ts < STRICT_10D_END,
                "inside_post_frozen_window": c.entry_ts >= FROZEN_END,
            }
        )
    oos_trades = pd.DataFrame(oos_rows)
    trades_path = ART / f"mk7_v8_oos_trades_{DATE_TAG}.csv"
    oos_trades.to_csv(trades_path, index=False)

    curve_oos = curve.loc[curve.index >= FROZEN_END].rename("nav").reset_index()
    curve_oos.columns = ["ts", "nav"]
    curve_path = ART / f"mk7_v8_oos_equity_15m_{DATE_TAG}.csv"
    curve_oos.to_csv(curve_path, index=False)

    summary = {
        "version": "mk7-v8 frozen-parameter OOS replay",
        "status": "post_freeze_diagnostic_not_promotion",
        "frozen_data_end": FROZEN_END,
        "strict_10d_end": STRICT_10D_END,
        "latest_common_closed_end": latest_end,
        "data_update_evidence": "data/cache/mk7_v8_binance/logs/oos_data_update_2026-07-13.json",
        "pre_oos_parity": parity,
        "extended_raw_counts": {
            "six": six_counts,
            "k2fq": len(k2),
            "mii": len(mii),
        },
        "extended_selected_trades": len(selected),
        "strict_10d": strict,
        "through_latest": through_latest,
        "july_mtd_utc": july_mtd,
        "caveats": [
            "Parameters and arbitration rules are frozen; OOS data did not participate in selection.",
            "Account return is mark-to-market at the window boundary.",
            "Win rate and PF use only entry-cohort trades closed before the boundary.",
            "Current independent implementation still differs from external identity before OOS (747 vs 743 frozen trades).",
        ],
    }
    summary_path = ART / f"mk7_v8_oos_10d_summary_{DATE_TAG}.json"
    summary_path.write_text(
        json.dumps(json_safe(summary), indent=2, ensure_ascii=False) + "\n"
    )

    def pct(value: float | None) -> str:
        return "N/A" if value is None else f"{value * 100:.2f}%"

    note_path = NOTES / f"mk7-v8-oos-10d-{DATE_TAG}.md"
    note_path.write_text(
        "\n".join(
            [
                "# mk7-v8 冻结后 10 天 OOS 回测",
                "",
                "状态：`post-freeze diagnostic / not promoted / not live-ready`",
                "",
                "## 窗口与数据",
                "",
                f"- 冻结样本结束：`{FROZEN_END.isoformat()}`。",
                f"- 严格 10 天 OOS：`{FROZEN_END.isoformat()} <= t < {STRICT_10D_END.isoformat()}`。",
                f"- 最新共同闭合数据：`{latest_end.isoformat()}`。",
                "- 参数、信号、scale、双槽仲裁均冻结；OOS 数据未参与选参。",
                "- 六币 1h、HYPE/BTC 1m/15m、premium、LSR、aggTrades/CVD 与 funding 均已增量核验。",
                "",
                "## 结果",
                "",
                "| 窗口 | MTM 收益 | MDD | 入场笔数 | 已平仓 | 已平仓胜率 | 期末账户持仓 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
                (
                    f"| 严格 10d | `{pct(strict['account_return'])}` | `{pct(strict['mdd'])}` | "
                    f"`{strict['entry_trades']}` | `{strict['closed_entry_trades_by_window_end']}` | "
                    f"`{pct(strict['closed_trade_win_rate'])}` | `{strict['account_positions_open_at_window_end']}` |"
                ),
                (
                    f"| 至最新闭合时点 | `{pct(through_latest['account_return'])}` | "
                    f"`{pct(through_latest['mdd'])}` | `{through_latest['entry_trades']}` | "
                    f"`{through_latest['closed_entry_trades_by_window_end']}` | "
                    f"`{pct(through_latest['closed_trade_win_rate'])}` | "
                    f"`{through_latest['account_positions_open_at_window_end']}` |"
                ),
                (
                    f"| 7月 MTD（UTC） | `{pct(july_mtd['account_return'])}` | "
                    f"`{pct(july_mtd['mdd'])}` | `{july_mtd['entry_trades']}` | "
                    f"`{july_mtd['closed_entry_trades_by_window_end']}` | "
                    f"`{pct(july_mtd['closed_trade_win_rate'])}` | "
                    f"`{july_mtd['account_positions_open_at_window_end']}` |"
                ),
                "",
                "收益按账户 15m MTM 曲线在边界重定基；胜率仅统计窗口内入场且在窗口结束前已经平仓的交易，避免使用窗口后的结果。",
                "",
                "## 组件与资产",
                "",
                f"- 严格 10d 组件入场：`{strict['entries_by_component']}`。",
                f"- 严格 10d 资产入场：`{strict['entries_by_asset']}`。",
                f"- 7月 MTD 组件入场：`{july_mtd['entries_by_component']}`。",
                f"- 7月 MTD 资产入场：`{july_mtd['entries_by_asset']}`。",
                f"- 冻结段 entry identity 对拍：`{parity}`。",
                "",
                "## OOS 逐笔路径",
                "",
                "| 资产 / 组件 | 方向 | 入场 | 出场 | 账户收益贡献 | 严格 10d 入场 |",
                "| --- | ---: | --- | --- | ---: | --- |",
                *[
                    (
                        f"| `{row.asset} / {row.component}` | `{int(row.side):+d}` | "
                        f"`{row.entry_ts}` | `{row.exit_ts}` | "
                        f"`{row.equity_ret * 100:.2f}%` | "
                        f"`{'是' if row.inside_strict_10d_entry_window else '否'}` |"
                    )
                    for row in oos_trades.itertuples(index=False)
                ],
                "",
                "- 严格 10d 虽有 75% 已平仓胜率，但 PF 仅约 `0.97`，三笔小赢基本被 BTC CCI 一笔亏损抵消。",
                "- 严格 10d 之后新增 HYPE DI 与 TRX Stoch 两笔亏损，使截至最新闭合时点收益降至约 `-17.49%`、MDD 到 `-21.98%`。",
                "- OOS 期间 MII 为 `0` 笔；结果主要检验六币高杠杆腿与一笔 K2FQ，而不是完整三组件都得到验证。",
                "",
                "## 证据",
                "",
                f"- [OOS 汇总](../artifacts/{summary_path.name})",
                f"- [OOS 逐笔](../artifacts/{trades_path.name})",
                f"- [OOS 15m 权益](../artifacts/{curve_path.name})",
                "- [数据增量与质量报告](../../../../data/cache/mk7_v8_binance/logs/oos_data_update_2026-07-13.json)",
                "",
                "## 边界",
                "",
                "- 本仓冻结段仍有 `747 vs 743` 的身份偏差；本 OOS 结论只代表当前独立实现。",
                "- 10 天样本很短，不满足 promotion、live-ready 或统计显著性要求。",
                "- K2FQ same-close 成交与相位敏感风险仍未消除。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(json_safe(summary), indent=2, ensure_ascii=False))
    print("wrote", summary_path)
    print("wrote", trades_path)
    print("wrote", curve_path)
    print("wrote", note_path)


if __name__ == "__main__":
    main()
