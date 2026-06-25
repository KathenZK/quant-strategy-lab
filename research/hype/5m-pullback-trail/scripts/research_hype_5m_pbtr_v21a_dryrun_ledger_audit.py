from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DB_PATH = Path("/Users/ZK/OpenCode/hype-pullback/state/hype_pullback.sqlite3")
REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_dryrun_ledger_audit.json")
TRADE_CSV_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_dryrun_ledger_audit_trades.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v21a-dryrun-ledger-audit-2026-06-24.md"
)
SYMBOL = "HYPEUSDT"
INTERVAL = "5m"
FEE_RATE_PER_FILL = 3.0578 / 7374.2110
EXIT_SLIPPAGE_RATE = -2.64 / 10000.0


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def usd(value: float, digits: int = 4) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def fetch_binance_klines(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    rows: list[list[Any]] = []
    while start_ms <= end_ms:
        query = urllib.parse.urlencode(
            {
                "symbol": SYMBOL,
                "interval": INTERVAL,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            }
        )
        with urllib.request.urlopen(f"https://fapi.binance.com/fapi/v1/klines?{query}", timeout=20) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not batch:
            break
        rows.extend(batch)
        start_ms = int(batch[-1][0]) + 5 * 60 * 1000
        if int(batch[-1][0]) >= end_ms:
            break
        time.sleep(0.1)

    frame = pd.DataFrame(
        rows,
        columns=[
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    frame = frame.loc[:, ["ts", "open", "high", "low", "close", "volume"]].copy()
    frame["ts"] = pd.to_datetime(frame["ts"], unit="ms", utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.drop_duplicates("ts").sort_values("ts").set_index("ts")


def load_trade_rows(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        select
            trade_id, side, signal_ts, entry_ts, exit_ts, entry_price, exit_price,
            quantity, initial_stop, current_stop, stop_order_id, exit_order_id,
            exit_reason, bars_held, net_pnl_usdt, net_ret_1x, payload_json
        from trade_ledger
        where status = 'closed'
        order by entry_ts
        """
    ).fetchall()
    return [dict(row) for row in rows]


def load_event_summary(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    event_counts = {
        str(row["event_type"]): int(row["count"])
        for row in conn.execute("select event_type, count(*) as count from event_log group by event_type")
    }
    payload_counts: dict[str, int] = {}
    for row in conn.execute("select payload_json from event_log"):
        payload = json.loads(row["payload_json"])
        event = str(payload.get("event") or "")
        if event:
            payload_counts[event] = payload_counts.get(event, 0) + 1
    range_row = conn.execute("select min(ts) as first_ts, max(ts) as last_ts from event_log").fetchone()
    return {
        "event_counts": event_counts,
        "payload_event_counts": payload_counts,
        "first_event_ts": range_row["first_ts"],
        "last_event_ts": range_row["last_ts"],
    }


def crossed(price: float, stop: float, side: str) -> bool:
    return bool(price <= stop if side == "long" else price >= stop)


def hit_bar(high: float, low: float, stop: float, side: str) -> bool:
    return bool(low <= stop if side == "long" else high >= stop)


def pnl_at_raw_exit(entry_price: float, quantity: float, side_sign: int, raw_exit_price: float) -> tuple[float, float, float]:
    exit_price = float(raw_exit_price * (1.0 - side_sign * EXIT_SLIPPAGE_RATE))
    gross_pnl = side_sign * (exit_price - entry_price) * quantity
    fee = FEE_RATE_PER_FILL * (entry_price * quantity + exit_price * quantity)
    net_pnl = gross_pnl - fee
    net_ret = net_pnl / (entry_price * quantity)
    return exit_price, float(net_pnl), float(net_ret)


def reconcile(trades: list[dict[str, Any]], candles: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        side_sign = 1 if trade["side"] == "long" else -1
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        stop_set_ts = pd.Timestamp(str(trade["stop_order_id"]).removeprefix("dry-stop-"))
        setup = candles.loc[stop_set_ts]
        exit_bar = candles.loc[exit_ts]
        entry_price = float(trade["entry_price"])
        quantity = float(trade["quantity"])
        stop = float(trade["current_stop"])
        stop_exit_price, stop_pnl, stop_ret = pnl_at_raw_exit(entry_price, quantity, side_sign, stop)
        open_exit_price, open_pnl, open_ret = pnl_at_raw_exit(entry_price, quantity, side_sign, float(exit_bar["open"]))
        close_exit_price, close_pnl, close_ret = pnl_at_raw_exit(entry_price, quantity, side_sign, float(exit_bar["close"]))
        rows.append(
            {
                "trade_id": trade["trade_id"],
                "side": trade["side"],
                "signal_ts": trade["signal_ts"],
                "entry_ts": trade["entry_ts"],
                "stop_set_ts": stop_set_ts.isoformat(),
                "exit_ts": trade["exit_ts"],
                "ledger_bars_held": int(trade["bars_held"]),
                "actual_closed_bars_inclusive": int((exit_ts - entry_ts) / pd.Timedelta(minutes=5)) + 1,
                "entry_price": entry_price,
                "stop": stop,
                "setup_open": float(setup["open"]),
                "setup_high": float(setup["high"]),
                "setup_low": float(setup["low"]),
                "setup_close": float(setup["close"]),
                "setup_close_crossed_stop": crossed(float(setup["close"]), stop, str(trade["side"])),
                "setup_bar_touched_stop": hit_bar(float(setup["high"]), float(setup["low"]), stop, str(trade["side"])),
                "exit_open": float(exit_bar["open"]),
                "exit_high": float(exit_bar["high"]),
                "exit_low": float(exit_bar["low"]),
                "exit_close": float(exit_bar["close"]),
                "exit_open_crossed_stop": crossed(float(exit_bar["open"]), stop, str(trade["side"])),
                "exit_bar_touched_stop": hit_bar(float(exit_bar["high"]), float(exit_bar["low"]), stop, str(trade["side"])),
                "ledger_exit_price": float(trade["exit_price"]),
                "stop_exit_price": stop_exit_price,
                "open_exit_price": open_exit_price,
                "close_exit_price": close_exit_price,
                "ledger_net_pnl_usdt": float(trade["net_pnl_usdt"]),
                "stop_net_pnl_usdt": stop_pnl,
                "open_net_pnl_usdt": open_pnl,
                "close_net_pnl_usdt": close_pnl,
                "stop_net_ret_1x": stop_ret,
                "open_net_ret_1x": open_ret,
                "close_net_ret_1x": close_ret,
            }
        )
    return pd.DataFrame(rows)


def aggregate(df: pd.DataFrame) -> dict[str, Any]:
    invalid = df["setup_close_crossed_stop"]
    return {
        "closed_trades": int(len(df)),
        "short_trades": int((df["side"] == "short").sum()),
        "long_trades": int((df["side"] == "long").sum()),
        "ledger_net_sum_usdt": float(df["ledger_net_pnl_usdt"].sum()),
        "open_net_sum_usdt": float(df["open_net_pnl_usdt"].sum()),
        "close_net_sum_usdt": float(df["close_net_pnl_usdt"].sum()),
        "ledger_wins": int((df["ledger_net_pnl_usdt"] > 0).sum()),
        "open_wins": int((df["open_net_pnl_usdt"] > 0).sum()),
        "close_wins": int((df["close_net_pnl_usdt"] > 0).sum()),
        "setup_close_crossed_count": int(invalid.sum()),
        "setup_bar_touched_count": int(df["setup_bar_touched_stop"].sum()),
        "exit_open_crossed_count": int(df["exit_open_crossed_stop"].sum()),
        "exit_bar_touched_count": int(df["exit_bar_touched_stop"].sum()),
        "invalid_stop_ledger_net_sum_usdt": float(df.loc[invalid, "ledger_net_pnl_usdt"].sum()),
        "invalid_stop_open_net_sum_usdt": float(df.loc[invalid, "open_net_pnl_usdt"].sum()),
        "invalid_stop_close_net_sum_usdt": float(df.loc[invalid, "close_net_pnl_usdt"].sum()),
        "valid_stop_count": int((~invalid).sum()),
        "valid_stop_ledger_net_sum_usdt": float(df.loc[~invalid, "ledger_net_pnl_usdt"].sum()),
        "valid_stop_open_net_sum_usdt": float(df.loc[~invalid, "open_net_pnl_usdt"].sum()),
        "valid_stop_close_net_sum_usdt": float(df.loc[~invalid, "close_net_pnl_usdt"].sum()),
    }


def render_markdown(df: pd.DataFrame, summary: dict[str, Any], events: dict[str, Any]) -> str:
    lines = [
        "# HYPE-5M-PBTR-V2.1A dry-run ledger 审计 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告复核 `/Users/ZK/OpenCode/hype-pullback` 中的 paper-live dry-run SQLite 数据，目标是解释一天 dry-run 看到第 7 根附近频繁止损退出且账面盈利的真实原因。",
        "",
        "## 数据范围",
        "",
        f"- SQLite：`{DB_PATH}`",
        f"- event_log 时间：`{events['first_event_ts']}` 到 `{events['last_event_ts']}`",
        f"- closed trades：`{summary['closed_trades']}` 笔；全部为 `short`。",
        f"- event payload 统计：`would_enter={events['payload_event_counts'].get('would_enter', 0)}`，`would_replace_stop={events['payload_event_counts'].get('would_replace_stop', 0)}`，`would_close={events['payload_event_counts'].get('would_close', 0)}`。",
        "",
        "注意：SQLite 中是 `13` 笔已关闭交易，不是 `14` 笔。`would_replace_stop=14` 是因为其中一笔交易更新过两次 stop，且第一笔交易由迁移记录承接，没有对应 `would_enter` payload。",
        "",
        "## 汇总",
        "",
        "| 口径 | 净 PnL USDT | 赢的笔数 | 说明 |",
        "| --- | ---: | ---: | --- |",
        f"| dry-run ledger / stop 价成交 | `{usd(summary['ledger_net_sum_usdt'])}` | `{summary['ledger_wins']}/{summary['closed_trades']}` | runner 用 `current_stop` 作为 `raw_exit_price`。 |",
        f"| 下一根 K 开盘价退出 | `{usd(summary['open_net_sum_usdt'])}` | `{summary['open_wins']}/{summary['closed_trades']}` | 用 Binance public K 线的 exit bar open 替代 stop 价。 |",
        f"| 下一根 K 收盘价退出 | `{usd(summary['close_net_sum_usdt'])}` | `{summary['close_wins']}/{summary['closed_trades']}` | 用 Binance public K 线的 exit bar close 替代 stop 价。 |",
        "",
        "## 关键发现",
        "",
        f"- `setup_close_crossed_stop={summary['setup_close_crossed_count']}/{summary['closed_trades']}`：多数交易在 runner 设置 stop 的那根闭合 K 线收盘时，价格已经处于 stop 触发侧。",
        f"- `setup_bar_touched_stop={summary['setup_bar_touched_count']}/{summary['closed_trades']}`：全部交易在设置 stop 的那根 K 线内部都已经触碰过 stop。",
        f"- `exit_open_crossed_stop={summary['exit_open_crossed_count']}/{summary['closed_trades']}`：下一根 K 开盘时，多数交易仍然已经越过 stop。",
        f"- 对这些设置时已经穿越的交易，dry-run ledger 记为 `{usd(summary['invalid_stop_ledger_net_sum_usdt'])}` USDT；若按下一根开盘价退出则为 `{usd(summary['invalid_stop_open_net_sum_usdt'])}` USDT，若按下一根收盘价退出则为 `{usd(summary['invalid_stop_close_net_sum_usdt'])}` USDT。",
        "",
        "这说明 dry-run 的盈利不是第 7 根退出本身产生的 edge，而是 runner 在锁仓结束后才计算 stop，并在 stop 已经不可按该价格挂出/成交的情况下，仍把 `current_stop` 当作成交价。",
        "",
        "## 状态机解释",
        "",
        "- `runner.py` 在持仓时用 `since_entry = frame[ts >= entry_ts]` 计算 `bars_held`。当 `bars_held < min_hold_bars` 时继续锁仓；等于 `6` 时才开始计算 trailing stop。",
        "- 第一次可设置 stop 的周期使用刚刚闭合的第 6 根 K 线的 high/low/ATR 来计算 `desired_stop`，但没有检查当前 close 是否已经越过 stop。",
        "- dry-run 只在下一轮 `_paper_stop_hit()` 里用下一根 K 的 high/low 判断触发，然后 `_close_position_local()` 直接把 `raw_exit_price=state.position.current_stop` 写入成交。",
        "- 因此 ledger 的 `bars_held=6` 不是实际退出时重新计算的持仓 K 数；多数交易实际是 entry 到 exit 共 `7` 根闭合 K，一笔为 `8` 根。",
        "",
        "## 逐笔摘要",
        "",
        "| entry_ts | stop_set_ts | exit_ts | ledger bars | actual bars | stop | setup close | setup close crossed | exit open | ledger PnL | open PnL | close PnL |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in df.to_dict(orient="records"):
        lines.append(
            "| "
            f"`{row['entry_ts']}` | `{row['stop_set_ts']}` | `{row['exit_ts']}` | "
            f"`{int(row['ledger_bars_held'])}` | `{int(row['actual_closed_bars_inclusive'])}` | "
            f"`{row['stop']:.6f}` | `{row['setup_close']:.6f}` | "
            f"`{bool(row['setup_close_crossed_stop'])}` | `{row['exit_open']:.6f}` | "
            f"`{usd(float(row['ledger_net_pnl_usdt']))}` | `{usd(float(row['open_net_pnl_usdt']))}` | `{usd(float(row['close_net_pnl_usdt']))}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "这份 dry-run 数据支持“V2.1A 多数交易在 `min_hold_bars=6` 后很快退出”的观察，但不支持“这个状态机已经证明赚钱”。真实情况是：dry-run runner 在第 6 根闭合后才计算并记录 trailing stop，随后即使 stop 在计算/设置时已经被价格穿越，也仍按 stop 价记账。",
            "",
            "因此，这批 dry-run 的 `+0.3672 USDT` 账面盈利应视为执行口径污染，不能作为扩大仓位或确认 V2.1A 可实盘的证据。后续 runner 必须在设置/替换 stop 前检查当前价格是否已经触发；若已经触发，只能按当前可成交价市价平仓或记录为不可挂 stop，而不能按旧 stop 价成交。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_dryrun_ledger_audit.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 逐笔 CSV：`{TRADE_CSV_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    trades = load_trade_rows(DB_PATH)
    if not trades:
        raise RuntimeError("no closed trades found")
    start = min(pd.Timestamp(row["entry_ts"]) for row in trades) - pd.Timedelta(hours=1)
    end = max(pd.Timestamp(row["exit_ts"]) for row in trades) + pd.Timedelta(hours=1)
    candles = fetch_binance_klines(start, end)
    df = reconcile(trades, candles)
    summary = aggregate(df)
    events = load_event_summary(DB_PATH)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(TRADE_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(df, summary, events), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V2.1A",
                "audit": "paper_live_dryrun_sqlite_ledger",
                "db_path": str(DB_PATH),
                "summary": summary,
                "events": events,
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "trade_csv": str(TRADE_CSV_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"markdown={MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
