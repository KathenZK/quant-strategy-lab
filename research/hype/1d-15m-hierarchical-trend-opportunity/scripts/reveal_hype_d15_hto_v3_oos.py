from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import hto_engine as engine
import hto_v2


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-15m-hierarchical-trend-opportunity"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
V3_PATH = ARTIFACT_DIR / "hype_d15_hto_v3_tune_2026-07-29.json"
PREFIT_AUDIT_PATH = ARTIFACT_DIR / "hype_d15_hto_v3_prefit_audit_2026-07-29.json"
REVEAL_PATH = ARTIFACT_DIR / "hype_d15_hto_v3_locked_oos_reveal_2026-07-29.json"
RUN_DATE = "2026-07-29"


def scenario(name: str, result: engine.BacktestResult) -> dict[str, Any]:
    return {"scenario": name, **result.metrics}


def buy_hold(
    book: engine.FeatureBook, *, start: pd.Timestamp
) -> dict[str, Any]:
    start_index = int(np.searchsorted(book.ts.as_unit("ns").asi8, start.value, side="left"))
    entry = float(book.open[start_index]) * (1 + engine.BASE_SLIPPAGE)
    closes = book.close[start_index:]
    marked = closes * (1 - engine.BASE_SLIPPAGE) / entry
    equity = marked - 2 * engine.BASE_FEE
    ending = float(equity[-1])
    peaks = np.maximum.accumulate(np.r_[1.0, equity])[1:]
    drawdown = 1 - equity / peaks
    hours = (book.terminal_ts - start).total_seconds() / 3600
    annual_factor = (
        float(np.exp(np.log(ending) * engine.HOURS_PER_YEAR / hours))
        if ending > 0
        else 0.0
    )
    return {
        "start_ts": start.isoformat(),
        "end_ts": book.terminal_ts.isoformat(),
        "entry_price_with_slippage": entry,
        "ending_equity": ending,
        "total_return": ending - 1,
        "annual_factor": annual_factor,
        "max_drawdown": float(drawdown.max()),
        "fee_per_fill": engine.BASE_FEE,
        "slippage_per_fill": engine.BASE_SLIPPAGE,
    }


def recent_slices(
    book: engine.FeatureBook, config: engine.Config
) -> list[dict[str, Any]]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    output: list[dict[str, Any]] = []
    for label, width in windows.items():
        start = max(book.source_start, book.terminal_ts - width)
        result = engine.run_backtest(book, config, start_ts=start)
        output.append({"slice": label, **result.metrics})
    return output


def render_report(payload: dict[str, Any]) -> str:
    base = payload["oos_scenarios"][0]
    full = payload["full_continuous"]
    hold = payload["oos_buy_hold"]
    return "\n".join(
        [
            "# HYPE-D15-HTO-V3 最近三个月 locked OOS 一次性揭示",
            "",
            f"- OOS：`[{payload['oos_start']}, {payload['oos_end']})`。",
            "- 规则：冻结后首次且唯一一次读取；OOS 从空仓、权益 1.0 开始，不用于任何后续调参。",
            "- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际资金费。",
            "",
            "## OOS 结果",
            "",
            (
                f"净收益 `{base['total_return']:.2%}`，年化倍数 `{base['annual_factor']:.3f}x`，"
                f"胜率 `{base['win_rate']:.2%}`，MDD `{base['max_drawdown']:.2%}`，"
                f"`{base['trades']}` 笔。"
            ),
            (
                f"同期 1x 买入持有净收益 `{hold['total_return']:.2%}`，"
                f"策略超额 `{payload['oos_excess_return']:.2%}`。"
            ),
            "",
            "## 全冻结样本连续回放",
            "",
            (
                f"净收益 `{full['total_return']:.2%}`，年化倍数 `{full['annual_factor']:.3f}x`，"
                f"胜率 `{full['win_rate']:.2%}`，MDD `{full['max_drawdown']:.2%}`，"
                f"`{full['trades']}` 笔。"
            ),
            "",
            "## 决策",
            "",
            (
                "`HYPE-D15-HTO-V3` "
                + ("通过" if payload["oos_hard_target_pass"] else "未通过")
                + " OOS 三项硬门槛。"
            ),
            "prefit 已在年化、回撤、参数邻域和相位上失败，因此无论 OOS 单段表现如何，",
            "本家族均保持 `registered / not promoted / not live-ready`；不得依据已揭示 OOS 救参数。",
            "",
            "## 证据",
            "",
            "- [机器摘要](../artifacts/hype_d15_hto_v3_locked_oos_reveal_2026-07-29.json)",
            "- [OOS 逐笔成交](../artifacts/hype_d15_hto_v3_locked_oos_trades_2026-07-29.csv)",
            "- [OOS 权益路径](../artifacts/hype_d15_hto_v3_locked_oos_equity_2026-07-29.csv)",
            "- [最近切片](../artifacts/hype_d15_hto_v3_final_slices_2026-07-29.csv)",
            "",
        ]
    )


def main() -> None:
    if REVEAL_PATH.exists():
        raise RuntimeError(f"locked OOS was already revealed: {REVEAL_PATH}")
    v3 = json.loads(V3_PATH.read_text(encoding="utf-8"))
    prefit = json.loads(PREFIT_AUDIT_PATH.read_text(encoding="utf-8"))
    if v3["locked_oos_accessed"] or prefit["locked_oos_accessed"]:
        raise RuntimeError("prefit artifacts unexpectedly accessed locked OOS")
    clean = hto_v2.from_dict(v3["clean_config"])
    config = hto_v2.to_engine(clean)
    book = engine.build_book(include_locked_oos=True)
    manifest = engine.load_manifest()
    oos_start = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    )
    oos_end = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_end_exclusive"]
    )
    if book.terminal_ts != oos_end:
        raise RuntimeError("frozen terminal mismatch")
    base = engine.run_backtest(
        book, config, start_ts=oos_start, end_ts=oos_end, detailed=True
    )
    stress = engine.run_backtest(
        book,
        config,
        start_ts=oos_start,
        end_ts=oos_end,
        slippage_per_fill=engine.STRESS_SLIPPAGE,
    )
    delay = engine.run_backtest(
        book,
        config,
        start_ts=oos_start,
        end_ts=oos_end,
        entry_delay_bars=2,
    )
    original_fee = engine.BASE_FEE
    try:
        engine.BASE_FEE = 0.0
        zero_cost = engine.run_backtest(
            book,
            config,
            start_ts=oos_start,
            end_ts=oos_end,
            slippage_per_fill=0.0,
        )
    finally:
        engine.BASE_FEE = original_fee
    full = engine.run_backtest(book, config, detailed=True)
    hold = buy_hold(book, start=oos_start)
    slices = recent_slices(book, config)
    oos_pass = bool(
        base.metrics["annual_factor"] >= 10
        and base.metrics["win_rate"] >= 0.50
        and base.metrics["max_drawdown"] < 0.20
    )
    result = {
        "family": v3["family"],
        "version": v3["version"],
        "revealed_at_utc": datetime.now(UTC).isoformat(),
        "locked_oos_accessed": True,
        "parameters_changed_after_reveal": False,
        "config_sha256": v3["config_sha256"],
        "oos_start": oos_start.isoformat(),
        "oos_end": oos_end.isoformat(),
        "oos_reset_policy": "flat and equity=1.0 at locked boundary",
        "oos_scenarios": [
            scenario("base_4bps_k1", base),
            scenario("stress_8bps", stress),
            scenario("delay_k2", delay),
            scenario("zero_fee_zero_slippage", zero_cost),
        ],
        "oos_buy_hold": hold,
        "oos_excess_return": base.metrics["total_return"] - hold["total_return"],
        "oos_hard_target_pass": oos_pass,
        "full_continuous": full.metrics,
        "recent_slices": slices,
        "final_decision": {
            "status": "registered / not promoted / not live-ready",
            "promotion_review": "FAIL",
            "reasons": [
                "prefit annual_factor < 10x",
                "prefit max_drawdown >= 20%",
                "parameter-neighborhood target hit rate = 0",
                "15m phase gate failed",
            ],
        },
    }
    REVEAL_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pd.DataFrame(base.trades).to_csv(
        ARTIFACT_DIR / f"hype_d15_hto_v3_locked_oos_trades_{RUN_DATE}.csv",
        index=False,
    )
    pd.DataFrame(base.equity_path).to_csv(
        ARTIFACT_DIR / f"hype_d15_hto_v3_locked_oos_equity_{RUN_DATE}.csv",
        index=False,
    )
    pd.DataFrame(slices).to_csv(
        ARTIFACT_DIR / f"hype_d15_hto_v3_final_slices_{RUN_DATE}.csv",
        index=False,
    )
    (
        DIAGNOSTIC_DIR
        / f"hype-d15-hto-v3-locked-oos-final-{RUN_DATE}.md"
    ).write_text(render_report(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
