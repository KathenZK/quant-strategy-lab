from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from as6s_engine import (
    REUSED_END,
    StrategyConfig,
    load_funding,
    load_symbol_frame,
    simulate_opportunities,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
INVENTORY = FAMILY_DIR / "artifacts/binance_as6s_v5_parameter_inventory_2026-07-15.json"
OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_inert_parameter_equivalence_2026-07-15.json"
)
REPORT = (
    FAMILY_DIR
    / "ablations/binance-as6s-v5-inert-parameter-equivalence-2026-07-15.md"
)
SCENARIOS = {
    "base_4bps_k1": (0.0004, 1),
    "stress_8bps_k1": (0.0008, 1),
    "base_4bps_k2": (0.0004, 2),
}


def alternate(field: str, current: Any) -> Any:
    choices: dict[str, Any] = {
        "ema_fast": 21,
        "ema_slow": 96,
        "indicator_window": 24,
        "threshold_long": 123.456,
        "threshold_short": -123.456,
        "aux_fast": 8,
        "aux_slow": 21,
        "max_dist_atr": 0.125,
        "trail_activate_atr": 0.0,
        "trail_atr": 9.75,
    }
    value = choices[field]
    if value == current:
        if isinstance(value, int):
            return value + 1
        return float(value) + 0.125
    return value


def signature(rows: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    payload = [
        {
            "side": row.side,
            "signal_ts": row.signal_ts.isoformat(),
            "entry_ts": row.entry_ts.isoformat(),
            "exit_ts": row.exit_ts.isoformat(),
            "entry_fill": round(row.entry_fill, 12),
            "exit_fill": round(row.exit_fill, 12),
            "score": round(row.score, 12),
            "net_return_1x": round(row.net_return_1x, 12),
            "mae_return_1x": round(row.mae_return_1x, 12),
            "exit_reason": row.exit_reason,
        }
        for row in rows
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    frames: dict[str, Any] = {}
    funding: dict[str, Any] = {}
    baseline_cache: dict[tuple[str, str], tuple[str, list[dict[str, Any]]]] = {}

    for sleeve in manifest["selected_sleeves"]:
        audit = manifest["sleeve_configs"][sleeve]
        if audit["source"] != "prefit_frontier_asset_first":
            continue
        symbol = audit["symbol"]
        if symbol not in frames:
            frames[symbol] = load_symbol_frame(symbol, end=REUSED_END)
            funding[symbol] = load_funding(symbol, end=REUSED_END)
            if frames[symbol]["ts"].max() >= REUSED_END:
                raise RuntimeError(f"{symbol} frame crossed research cutoff")
            if funding[symbol]["ts"].max() >= REUSED_END:
                raise RuntimeError(f"{symbol} funding crossed research cutoff")
        config = StrategyConfig.from_dict(audit["config"])
        inert_fields = [
            field
            for field, role in inventory["sleeves"][sleeve][
                "parameter_roles"
            ].items()
            if role["status"] == "code_inert"
        ]
        for scenario, (slippage, delay) in SCENARIOS.items():
            key = (sleeve, scenario)
            baseline_rows = simulate_opportunities(
                frames[symbol],
                funding[symbol],
                config,
                end=REUSED_END,
                slippage=slippage,
                entry_delay_bars=delay,
            )
            baseline_cache[key] = signature(baseline_rows)
        for field in inert_fields:
            variant = replace(config, **{field: alternate(field, getattr(config, field))})
            scenario_results: dict[str, Any] = {}
            for scenario, (slippage, delay) in SCENARIOS.items():
                variant_rows = simulate_opportunities(
                    frames[symbol],
                    funding[symbol],
                    variant,
                    end=REUSED_END,
                    slippage=slippage,
                    entry_delay_bars=delay,
                )
                variant_hash, variant_payload = signature(variant_rows)
                baseline_hash, baseline_payload = baseline_cache[(sleeve, scenario)]
                scenario_results[scenario] = {
                    "baseline_trades": len(baseline_payload),
                    "variant_trades": len(variant_payload),
                    "baseline_sha256": baseline_hash,
                    "variant_sha256": variant_hash,
                    "exact_trade_path_equal": baseline_hash == variant_hash,
                }
            cases.append(
                {
                    "sleeve": sleeve,
                    "symbol": symbol,
                    "mechanism": config.mechanism,
                    "field": field,
                    "baseline_value": getattr(config, field),
                    "alternate_value": getattr(variant, field),
                    "scenarios": scenario_results,
                    "all_scenarios_exact": all(
                        result["exact_trade_path_equal"]
                        for result in scenario_results.values()
                    ),
                }
            )

    failures = [case for case in cases if not case["all_scenarios_exact"]]
    expected = int(inventory["code_inert_frontier_field_occurrences"])
    if len(cases) != expected:
        raise RuntimeError(f"inert case count drift: expected {expected}, got {len(cases)}")
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v5_frontier_code_inert_exact_trade_path_equivalence",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "scenarios": SCENARIOS,
        "expected_cases": expected,
        "tested_cases": len(cases),
        "passing_cases": len(cases) - len(failures),
        "failing_cases": len(failures),
        "result": "PASS" if not failures else "FAIL",
        "cases": cases,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V5 代码无效参数等价审计（2026-07-15）",
        "",
        "本审计逐字段改成明显不同的值，并在 `4 bps/K+1`、`8 bps/K+1`、`4 bps/K+2` 三个场景比较完整交易路径哈希。",
        "",
        f"- 预期实例：`{expected}`",
        f"- 已测试：`{len(cases)}`",
        f"- 精确等价：`{len(cases) - len(failures)}`",
        f"- 失败：`{len(failures)}`",
        f"- 结论：`{payload['result']}`",
        "- 数据严格为 `ts < 2026-07-14T09:00Z`；未读取未来OOS，未修改V5。",
        "",
        "只有三场景的信号时间、进出场、方向、成交价、strength原始分数、收益、MAE和退出原因全部一致，才判定可从clean接口移除。",
        "",
        f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})。",
    ]
    if failures:
        lines.extend(["", "## 失败项", ""])
        lines.extend(f"- `{row['sleeve']}` / `{row['field']}`" for row in failures)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "result": payload["result"],
                "tested_cases": len(cases),
                "failing_cases": len(failures),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
