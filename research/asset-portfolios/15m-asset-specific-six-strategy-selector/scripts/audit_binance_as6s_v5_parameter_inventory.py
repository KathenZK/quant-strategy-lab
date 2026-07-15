from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

import audit_legacy_asset_specific_1h_sleeves as legacy
from as6s_engine import REUSED_END, SYMBOLS, load_funding


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v5_parameter_inventory_2026-07-15.json"
REPORT = FAMILY_DIR / "ablations/binance-as6s-v5-parameter-inventory-2026-07-15.md"


LEGACY_SELECTED_NAMES = {
    "legacy1h:BNBUSDT:wick_reject": "BNB_1H_AR_V2_WICK_REJECT_T01080",
    "legacy1h:BTCUSDT:keltner_break": "BTC_1H_AR_V4_KELTNER",
    "legacy1h:ETHUSDT:rsi_reversal": "ETH_1H_AR_V1_RSI",
    "legacy1h:HYPEUSDT:di_cross": "HYPE_1H_AR_V4_DI",
    "legacy1h:SOLUSDT:donchian_break": "SOL_1H_AR_HW_R132002",
    "legacy1h:TRXUSDT:macd_flip": "TRX_1H_AR_V2_MACD",
}


LEGACY_EVIDENCE = {
    "legacy1h:BNBUSDT:wick_reject": [
        "research/bnb/1h-adaptive-regime/ablations/bnb-1h-ar-v2-full-parameter-ablation-2026-07-07.md",
        "research/bnb/1h-adaptive-regime/notes/bnb-1h-ar-v2-micro-tune-2026-07-07.md",
    ],
    "legacy1h:BTCUSDT:keltner_break": [
        "research/btc/1h-adaptive-regime/ablations/btc-1h-ar-v3-full-parameter-ablation-2026-07-06.md",
        "research/btc/1h-adaptive-regime/notes/btc-1h-ar-v3-minimal-micro-tune-2026-07-07.md",
    ],
    "legacy1h:ETHUSDT:rsi_reversal": [
        "research/eth/1h-adaptive-regime/ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md",
        "research/eth/1h-adaptive-regime/notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md",
    ],
    "legacy1h:HYPEUSDT:di_cross": [
        "research/hype/1h-adaptive-regime/ablations/hype-1h-ar-v3-full-parameter-ablation-2026-07-06.md",
        "research/hype/1h-adaptive-regime/notes/hype-1h-ar-v3-prune-and-tune-2026-07-07.md",
    ],
    "legacy1h:SOLUSDT:donchian_break": [
        "research/sol/1h-adaptive-regime/ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md",
        "research/sol/1h-adaptive-regime/diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md",
    ],
    "legacy1h:TRXUSDT:macd_flip": [
        "research/trx/1h-adaptive-regime/ablations/trx-1h-ar-v2-full-parameter-ablation-2026-07-06.md",
        "research/trx/1h-adaptive-regime/notes/trx-1h-ar-v2-ablation-guided-tune-2026-07-06.md",
    ],
}


def frontier_parameter_roles(mechanism: str, config: dict[str, Any]) -> dict[str, dict[str, str]]:
    roles: dict[str, dict[str, str]] = {}

    def add(field: str, status: str, role: str, note: str) -> None:
        roles[field] = {"status": status, "role": role, "note": note}

    add("config_id", "identity", "metadata", "不参与信号或退出")
    add("symbol", "structural", "routing", "决定读取的市场数据")
    add("mechanism", "structural", "signal family", "决定机制分支")
    add("side_mode", "active", "entry gate", "限制多空方向")
    add(
        "adx_window",
        "active",
        "entry and ranking",
        "选择ADX/DI序列；所有机制均用于门禁或strength",
    )
    add("adx_min", "active", "entry gate", "common ADX下限")
    add(
        "rvol_window",
        "active",
        "entry and ranking",
        "选择RVOL序列；即使rvol_min为0仍进入strength",
    )
    add(
        "rvol_min",
        "active" if float(config["rvol_min"]) > 0.0 else "neutral_baseline",
        "entry gate",
        "0代表门禁关闭；RVOL本身仍参与strength",
    )
    add("min_atr_pct", "active", "entry gate", "ATR96百分比下限")
    add("max_atr_pct", "active", "entry gate", "ATR96百分比上限")
    add(
        "max_atr_ratio",
        "active" if float(config["max_atr_ratio"]) < 99.0 else "neutral_baseline",
        "entry gate",
        "99代表近似关闭",
    )
    add(
        "require_h1",
        "active" if bool(config["require_h1"]) else "neutral_baseline",
        "entry gate",
        "只读取已闭合1h状态",
    )
    add(
        "require_body",
        "active" if bool(config["require_body"]) else "neutral_baseline",
        "entry gate",
        "要求K线实体方向一致",
    )
    add("tp_atr", "active" if float(config["tp_atr"]) > 0.0 else "structural_off", "exit", "0代表无固定止盈")
    add("sl_atr", "active", "exit and risk", "固定灾难止损")
    add("max_hold_bars", "active", "exit", "最长持仓")

    if mechanism in {"trend_state", "breakout"}:
        add("ema_fast", "active", "entry", "趋势方向均线")
        add("ema_slow", "active", "entry and exit", "趋势方向；trend_state还用于趋势失效退出")
    else:
        add("ema_fast", "code_inert", "none", "reversal分支不读取")
        add("ema_slow", "code_inert", "none", "reversal分支不读取")

    if mechanism == "trend_state":
        add("indicator_window", "code_inert", "none", "trend_state分支不读取")
        add("threshold_long", "active", "entry", "同时控制多空回踩与动量确认层级")
        add("threshold_short", "code_inert", "none", "实现中多空都读取threshold_long")
        add("aux_fast", "code_inert", "none", "trend_state分支不读取MACD")
        add("aux_slow", "code_inert", "none", "trend_state分支不读取MACD")
        add("max_dist_atr", "active", "entry and ranking", "限制距快EMA距离并进入strength")
        add("trail_activate_atr", "active", "exit", "移动止损启动阈值")
        add("trail_atr", "active", "exit", "移动止损距离")
    elif mechanism == "breakout":
        add("indicator_window", "active", "entry and ranking", "Donchian窗口")
        add("threshold_long", "code_inert", "none", "breakout分支不读取")
        add("threshold_short", "code_inert", "none", "breakout分支不读取")
        add("aux_fast", "code_inert", "none", "breakout分支不读取")
        add("aux_slow", "code_inert", "none", "breakout分支不读取")
        add("max_dist_atr", "code_inert", "none", "breakout分支不读取")
        add("trail_activate_atr", "code_inert", "none", "仅trend_state执行移动止损")
        add("trail_atr", "code_inert", "none", "仅trend_state执行移动止损")
    else:
        add("indicator_window", "active", "entry and ranking", "RSI窗口")
        add("threshold_long", "active", "entry", "RSI向上穿越阈值")
        add("threshold_short", "active", "entry", "RSI向下穿越阈值")
        add("aux_fast", "active", "entry and ranking", "MACD方向过滤")
        add("aux_slow", "active", "entry and ranking", "MACD方向过滤")
        add("max_dist_atr", "code_inert", "none", "reversal分支不读取")
        add("trail_activate_atr", "code_inert", "none", "仅trend_state执行移动止损")
        add("trail_atr", "code_inert", "none", "仅trend_state执行移动止损")
    return roles


def clean_rsi_parameter_roles(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for field, role in (
        ("rsi_window", "entry"),
        ("rsi_low", "entry"),
        ("rsi_high", "entry"),
        ("min_atr_pct96", "entry gate"),
        ("take_profit_pct", "exit"),
        ("stop_pct", "exit and risk"),
        ("max_hold_bars", "exit"),
    ):
        output[field] = {"status": "active", "role": role, "note": "运行路径直接读取"}
    for field in ("min_rvol96", "h1_confirm", "rsi14_band"):
        enabled = bool(config[field])
        output[field] = {
            "status": "active" if enabled else "neutral_baseline",
            "role": "entry gate",
            "note": "当前值关闭过滤；消融应验证等价，微调可重新开启",
        }
    output["implicit_macd_direction"] = {
        "status": "active_fixed_contract",
        "role": "entry gate",
        "note": "Config未暴露，但filter固定min_dir_macd=0；必须纳入条件消融",
    }
    output["implicit_max_atr_pct96"] = {
        "status": "active_fixed_contract",
        "role": "entry gate",
        "note": "Config未暴露，但filter固定max_atr_pct96=0.028；必须纳入条件消融",
    }
    return output


def capture_legacy_configs() -> dict[str, dict[str, Any]]:
    captured: dict[str, dict[str, Any]] = {}
    original = legacy.simulate_stateless

    def capture(
        engine: Any,
        frame: pd.DataFrame,
        cfg: Any,
        funding_times: Any,
        funding_cumulative: Any,
    ) -> list[Any]:
        del engine, frame, funding_times, funding_cumulative
        captured[cfg.name] = asdict(cfg) if is_dataclass(cfg) else dict(vars(cfg))
        return []

    legacy.simulate_stateless = capture
    try:
        first, contexts = legacy.prepare_legacy()
        frames = {symbol: legacy.aggregate_h1(symbol) for symbol in SYMBOLS}
        funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS}
        for symbol, frame in frames.items():
            if pd.Timestamp(frame["ts"].max()) >= REUSED_END:
                raise RuntimeError(f"{symbol} legacy inventory crossed frozen cutoff")
        for symbol, frame in funding.items():
            if pd.Timestamp(frame["ts"].max()) >= REUSED_END:
                raise RuntimeError(f"{symbol} funding inventory crossed frozen cutoff")
        legacy.simulate_components(
            first,
            contexts,
            frames,
            funding,
            slippage=0.0004,
            delay=1,
        )
    finally:
        legacy.simulate_stateless = original
    return captured


def legacy_parameter_roles(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    metadata = {"name", "style"}
    contract = {
        "side_mode",
        "exit_kind",
        "tp_atr",
        "sl_atr",
        "trail_activation_atr",
        "trail_atr",
        "max_hold_bars",
        "cooldown_bars",
        "entry_delay_bars",
        "sizing_kind",
        "fixed_leverage",
        "risk_fraction",
        "max_leverage",
    }
    output: dict[str, dict[str, str]] = {}
    for field in config:
        if field in metadata:
            status, role = "identity", "metadata"
        elif field in contract:
            status, role = "active_or_contract", "execution/risk"
        else:
            status, role = "requires_differential_ablation", "signal/filter candidate"
        output[field] = {
            "status": status,
            "role": role,
            "note": "旧家族通用配置含机制无关字段；以逐字段交易路径差分判定，不按字段名猜测",
        }
    return output


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    legacy_configs = capture_legacy_configs()
    sleeves: dict[str, Any] = {}
    for sleeve in manifest["selected_sleeves"]:
        frozen = manifest["sleeve_configs"][sleeve]
        source = frozen["source"]
        if source == "prefit_frontier_asset_first":
            config = frozen["config"]
            roles = frontier_parameter_roles(frozen["mechanism"], config)
            evidence: list[str] = []
            exact_source_ablation = False
        elif source == "asset_specific_clean_rsi_hf":
            config = frozen["config"]
            roles = clean_rsi_parameter_roles(config)
            evidence = [
                "research/hype/15m-multi-indicator-intraday/ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md"
            ]
            exact_source_ablation = False
        elif source == "legacy_asset_specific_1h":
            expected_name = LEGACY_SELECTED_NAMES[sleeve]
            config = legacy_configs[expected_name]
            roles = legacy_parameter_roles(config)
            evidence = LEGACY_EVIDENCE[sleeve]
            exact_source_ablation = any(
                expected_name in (ROOT / path).read_text(encoding="utf-8")
                for path in evidence
                if (ROOT / path).exists()
            )
        else:
            raise RuntimeError(f"unknown sleeve source {source}")
        counts: dict[str, int] = {}
        for row in roles.values():
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        sleeves[sleeve] = {
            "source": source,
            "symbol": frozen["symbol"],
            "mechanism": frozen["mechanism"],
            "exposure": frozen["exposure"],
            "config": config,
            "parameter_roles": roles,
            "status_counts": counts,
            "source_evidence": evidence,
            "exact_selected_identity_present_in_source_evidence": exact_source_ablation,
            "fresh_exact_ablation_required": True,
        }

    inert_occurrences = sum(
        row["status_counts"].get("code_inert", 0) for row in sleeves.values()
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v5_parameter_inventory_before_fresh_ablation",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "selected_sleeves": len(sleeves),
        "symbols": sorted({row["symbol"] for row in sleeves.values()}),
        "code_inert_frontier_field_occurrences": inert_occurrences,
        "sleeves": sleeves,
        "ablation_contract": {
            "selection_data": f"ts < {REUSED_END.isoformat()}",
            "windows": {
                "prefit": [None, "2026-04-14T09:00:00+00:00"],
                "reused_diagnostic": [
                    "2026-04-14T09:00:00+00:00",
                    REUSED_END.isoformat(),
                ],
                "through_cutoff": [None, REUSED_END.isoformat()],
            },
            "required_scenarios": ["base_4bps_k1", "stress_8bps_k1", "base_4bps_k2"],
            "decision_rule": (
                "先验证单字段移除的交易路径差分，再看单腿与账户边际；"
                "reused_diagnostic只能淘汰，不能单独选优"
            ),
            "future_candidate_rule": "任何微调结果另行冻结并启动独立未来三个月OOS",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# BIN-15M-AS6S V5 参数盘点（2026-07-15）",
        "",
        "本盘点只读取 `2026-07-14T09:00Z` 之前的数据与冻结配置；不读取未来OOS，也不修改V5。",
        "",
        "## 结论",
        "",
        f"- 共核对 `{len(sleeves)}` 条腿、`{len(payload['symbols'])}` 个币。",
        f"- 8条frontier 15m腿中发现 `{inert_occurrences}` 个按腿计数的代码无效字段实例；这些字段必须从后续clean配置表面移除。另1条15m腿是独立clean-RSI实现。",
        "- 6条旧1h腿已从原始运行模块重新构造精确配置；旧家族消融只作先验，15条腿仍全部需要在当前联合账户语义下重新做精确消融。",
        "- HYPE clean-RSI还包含两个未暴露在Config里的固定条件：MACD方向和ATR96上限，必须纳入消融。",
        "",
        "## 逐腿状态",
        "",
        "| 腿 | 币 | 周期来源 | 机制 | 代码无效字段数 | 是否需要当前账户精确消融 |",
        "|---|---|---|---|---:|---|",
    ]
    for sleeve, row in sleeves.items():
        lines.append(
            f"| `{sleeve}` | `{row['symbol']}` | `{row['source']}` | `{row['mechanism']}` | "
            f"{row['status_counts'].get('code_inert', 0)} | 是 |"
        )
    lines.extend(
        [
            "",
            "## 后续顺序",
            "",
            "1. 单腿逐字段移除，先做交易路径等价与生效性审计。",
            "2. 比较单腿 prefit、reused diagnostic、through-cutoff，并将每个变体替换回联合账户测边际。",
            "3. 删除代码无效和可安全移除字段，形成clean参数接口。",
            "4. 只在clean接口上做局部微调；随后复测8 bps、K+2、参数邻域与两种路由。",
            "5. 新结果独立冻结，不使用V5正在积累的未来OOS选优。",
            "",
            f"结构化清单：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})。",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "sleeves": len(sleeves),
                "code_inert_frontier_field_occurrences": inert_occurrences,
                "future_oos_read": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
