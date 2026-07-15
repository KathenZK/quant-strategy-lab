from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from as6s_engine import FEE_PER_FILL, funding_arrays, funding_return, load_funding


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
TRADES = FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_trades_2026-07-15.csv"
MARK_ROOT = (
    ROOT
    / "data/normalized/mark_price_klines/exchange=binance/market_type=perp/timeframe=15m"
)
TRADE_ROOT = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_price_trigger_audit_2026-07-15.json"
DETAILS = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_price_trigger_details_2026-07-15.csv"
REPORT = FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-price-trigger-audit-2026-07-15.md"
SLUGS = {
    "BTCUSDT": "btc_usdt_usdt",
    "ETHUSDT": "eth_usdt_usdt",
    "SOLUSDT": "sol_usdt_usdt",
    "BNBUSDT": "bnb_usdt_usdt",
    "TRXUSDT": "trx_usdt_usdt",
    "HYPEUSDT": "hype_usdt_usdt",
}
STOP_REASONS = {"stop", "stop_loss", "stop_market"}
TARGET_REASONS = {"target", "take_profit"}
SLIPPAGE = 0.0004


def load_partitioned(root: Path, slug: str) -> pd.DataFrame:
    paths = sorted(root.glob(f"date=*/symbol={slug}.parquet"))
    if not paths:
        raise RuntimeError(f"missing partitions under {root} for {slug}")
    frame = pd.concat(
        [pd.read_parquet(path, columns=["ts", "open", "high", "low", "close"]) for path in paths],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)


def recover_exit_fill(
    row: Any,
    funding_ret: float,
) -> float:
    net_minus_funding = float(row.net_return_1x) - funding_ret
    side = int(row.side)
    if str(row.sleeve).startswith("frontier15m:") or row.exit_reason == "strong_breakout_preemption":
        price_return = net_minus_funding + 2.0 * FEE_PER_FILL
        ratio = 1.0 + side * price_return
    elif side > 0:
        ratio = (net_minus_funding + 1.0 + FEE_PER_FILL) / (1.0 - FEE_PER_FILL)
    else:
        ratio = (1.0 - FEE_PER_FILL - net_minus_funding) / (1.0 + FEE_PER_FILL)
    return float(row.entry_price) * ratio


def first_cross(
    frame: pd.DataFrame,
    *,
    side: int,
    kind: str,
    threshold: float,
) -> pd.Timestamp | None:
    if kind == "stop":
        mask = frame["low"] <= threshold if side > 0 else frame["high"] >= threshold
    else:
        mask = frame["high"] >= threshold if side > 0 else frame["low"] <= threshold
    matches = frame.loc[mask, "ts"]
    return None if matches.empty else pd.Timestamp(matches.iloc[0])


def metric(rows: pd.DataFrame) -> dict[str, Any]:
    counts = rows["classification"].value_counts().to_dict()
    total = len(rows)
    same = int(counts.get("same_bar", 0))
    earlier = int(counts.get("mark_earlier", 0))
    missing = int(counts.get("mark_not_triggered_by_trade_exit", 0))
    leads = rows.loc[rows["lead_minutes"].notna(), "lead_minutes"]
    return {
        "audited_fixed_protection_trades": total,
        "same_bar": same,
        "same_bar_rate": same / total if total else 0.0,
        "mark_earlier": earlier,
        "mark_earlier_rate": earlier / total if total else 0.0,
        "mark_not_triggered_by_trade_exit": missing,
        "mark_not_triggered_rate": missing / total if total else 0.0,
        "median_lead_minutes_when_earlier": (
            float(leads.median()) if not leads.empty else 0.0
        ),
        "max_lead_minutes": float(leads.max()) if not leads.empty else 0.0,
        "trade_exit_bar_threshold_sanity_rate": float(
            rows["trade_exit_bar_crossed"].mean()
        ) if total else 0.0,
        "by_reason": rows["exit_reason"].value_counts().to_dict(),
        "by_symbol": rows["symbol"].value_counts().to_dict(),
    }


def main() -> None:
    trades = pd.read_csv(TRADES)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    markets: dict[str, dict[str, pd.DataFrame]] = {}
    funding: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    basis: dict[str, Any] = {}
    for symbol, slug in SLUGS.items():
        trade = load_partitioned(TRADE_ROOT, slug)
        mark = load_partitioned(MARK_ROOT, slug)
        merged = trade.merge(mark, on="ts", suffixes=("_trade", "_mark"), how="inner")
        expected_start = max(trade["ts"].min(), mark["ts"].min())
        expected_end = min(trade["ts"].max(), mark["ts"].max())
        expected = pd.date_range(expected_start, expected_end, freq="15min")
        if len(merged) != len(expected) or merged["ts"].duplicated().any():
            raise RuntimeError(f"{symbol} trade/mark alignment is incomplete")
        close_basis_bps = 10000.0 * (
            merged["close_mark"] / merged["close_trade"] - 1.0
        )
        basis[symbol] = {
            "rows": len(merged),
            "start": merged["ts"].iloc[0].isoformat(),
            "end": merged["ts"].iloc[-1].isoformat(),
            "mean_bps": float(close_basis_bps.mean()),
            "p01_bps": float(close_basis_bps.quantile(0.01)),
            "p50_bps": float(close_basis_bps.quantile(0.50)),
            "p99_bps": float(close_basis_bps.quantile(0.99)),
            "max_abs_bps": float(close_basis_bps.abs().max()),
        }
        markets[symbol] = {"trade": trade, "mark": mark}
        funding[symbol] = funding_arrays(load_funding(symbol, end=pd.Timestamp("2026-07-14T09:00:00Z")))

    detail_rows: list[dict[str, Any]] = []
    fixed = trades.loc[trades["exit_reason"].isin(STOP_REASONS | TARGET_REASONS)]
    for row in fixed.itertuples(index=False):
        times, prefix = funding[row.symbol]
        funding_ret = funding_return(
            int(row.side), row.entry_ts, row.exit_ts, times, prefix
        )
        exit_fill = recover_exit_fill(row, funding_ret)
        trigger_price = exit_fill / (1.0 - int(row.side) * SLIPPAGE)
        kind = "stop" if row.exit_reason in STOP_REASONS else "target"
        source_bar_end = row.exit_ts + (
            pd.Timedelta(minutes=45)
            if row.source_timeframe == "1h"
            else pd.Timedelta(0)
        )
        mark_path = markets[row.symbol]["mark"].loc[
            (markets[row.symbol]["mark"]["ts"] >= row.entry_ts)
            & (markets[row.symbol]["mark"]["ts"] <= source_bar_end)
        ]
        trade_exit_bar = markets[row.symbol]["trade"].loc[
            (markets[row.symbol]["trade"]["ts"] >= row.exit_ts)
            & (markets[row.symbol]["trade"]["ts"] <= source_bar_end)
        ]
        mark_cross = first_cross(
            mark_path,
            side=int(row.side),
            kind=kind,
            threshold=trigger_price,
        )
        trade_cross = first_cross(
            trade_exit_bar,
            side=int(row.side),
            kind=kind,
            threshold=trigger_price,
        )
        if mark_cross is None:
            classification = "mark_not_triggered_by_trade_exit"
            lead_minutes = np.nan
        elif mark_cross < row.exit_ts:
            classification = "mark_earlier"
            lead_minutes = (row.exit_ts - mark_cross).total_seconds() / 60.0
        else:
            classification = "same_bar"
            lead_minutes = 0.0
        detail_rows.append(
            {
                "mode": row.mode,
                "sleeve": row.sleeve,
                "symbol": row.symbol,
                "side": int(row.side),
                "entry_ts": row.entry_ts,
                "trade_exit_ts": row.exit_ts,
                "trade_source_bar_end_ts": source_bar_end,
                "exit_reason": row.exit_reason,
                "protection_kind": kind,
                "recovered_trigger_price": trigger_price,
                "mark_first_cross_ts": mark_cross,
                "classification": classification,
                "lead_minutes": lead_minutes,
                "trade_exit_bar_crossed": trade_cross is not None,
            }
        )
    details = pd.DataFrame(detail_rows)
    details.to_csv(DETAILS, index=False)
    results = {
        mode: metric(group.reset_index(drop=True))
        for mode, group in details.groupby("mode", sort=True)
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_price_trigger_diagnostic_not_registered",
        "research_cutoff_exclusive": "2026-07-14T09:00:00+00:00",
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "data_quality": {
            "trade_mark_alignment": "PASS",
            "basis": basis,
        },
        "method": (
            "Recover the static fixed stop/target trigger from each routed trade's "
            "entry, net return, funding and fee/slippage convention, then compare the "
            "first Binance mark-price OHLC crossing with the trade-OHLC exit bar."
        ),
        "limitations": [
            "Trailing stops are excluded because the threshold changes through the path.",
            "A mark-price trigger submits a market order; 15m OHLC cannot reconstruct its exact trade-price fill.",
            "Earlier mark exits can change later account arbitration; this diagnostic does not reroute the account after a changed exit.",
            "Continuous dry-run mark-trigger/fill parity remains mandatory before promotion.",
        ],
        "results": results,
        "details_csv": str(DETAILS.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 mark-price保护触发审计（2026-07-15）",
        "",
        "六币mark-price 15m数据与trade OHLC完整对齐。下表仅审计固定止损/止盈的触发时序；移动止损与真实市价成交仍需dry-run。",
        "",
        "| 路线 | 固定保护交易 | 同K触发 | mark更早 | 截至trade退出仍未触发 |",
        "|---|---:|---:|---:|---:|",
    ]
    for mode, result in results.items():
        lines.append(
            f"| `{mode}` | {result['audited_fixed_protection_trades']} | "
            f"{result['same_bar_rate']:.2%} | {result['mark_earlier_rate']:.2%} | "
            f"{result['mark_not_triggered_rate']:.2%} |"
        )
    lines.extend(
        [
            "",
            "此结果是离线触发诊断，不是mark-price完整收益回测；任何时序分歧都必须在连续dry-run中核对实际保护成交与后续账户仲裁。",
            "",
            f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})；逐笔明细：[`{DETAILS.name}`](../artifacts/{DETAILS.name})。",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "details": str(DETAILS.relative_to(ROOT)),
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
