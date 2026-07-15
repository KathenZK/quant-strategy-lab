from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
INVENTORY = FAMILY_DIR / "artifacts/binance_as6s_v5_parameter_inventory_2026-07-15.json"
FRONTIER = FAMILY_DIR / "artifacts/binance_as6s_v5_frontier_full_ablation_2026-07-15.json"
CLEAN_RSI = FAMILY_DIR / "artifacts/binance_as6s_v5_clean_rsi_full_ablation_2026-07-15.json"
LEGACY = FAMILY_DIR / "artifacts/binance_as6s_v5_legacy_exact_full_ablation_2026-07-15.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_clean_surface_2026-07-15.json"
REPORT = FAMILY_DIR / "ablations/binance-as6s-v6-clean-surface-2026-07-15.md"


NON_REMOVABLE_RISK = {
    "sl_atr",
    "stop_pct",
    "max_hold_bars",
    "entry_delay_bars",
}
FRONTIER_COMPONENT_FIELDS = {
    "remove_min_atr": ["min_atr_pct"],
    "remove_max_atr": ["max_atr_pct"],
    "remove_atr_ratio": ["max_atr_ratio"],
    "remove_adx_min": ["adx_min"],
    "remove_rvol_min": ["rvol_min"],
    "remove_h1": ["require_h1"],
    "remove_body": ["require_body"],
    "remove_side_restriction": ["side_mode"],
    "remove_ema_order": ["ema_fast", "ema_slow", "ema_order_condition"],
    "remove_di_direction": ["di_direction_condition"],
    "remove_max_distance": ["max_dist_atr"],
    "remove_pullback": ["pullback_condition"],
    "remove_momentum": ["momentum_condition"],
    "remove_edge_trigger": ["edge_trigger_condition"],
    "remove_trend_break": ["trend_break_exit"],
    "remove_trail": ["trail_activate_atr", "trail_atr"],
    "remove_macd_direction": ["macd_direction_condition"],
    "remove_tp": ["tp_atr"],
}


def legacy_neutral(field: str, value: Any) -> bool:
    if field == "side_mode":
        return value == "both"
    if field == "min_adx" or field == "min_rvol" or field == "min_atr_bps":
        return float(value) == 0.0
    if field == "max_adx":
        return float(value) >= 100.0
    if field == "max_atr_bps" or field == "max_dist_ema_bps":
        return float(value) >= 10_000.0
    if field == "min_dir_roc_bps":
        return float(value) <= -10_000.0
    if field == "htf_mode":
        return value == "none"
    if field in {"require_macd_turn", "require_body_dir"}:
        return not bool(value)
    if field == "max_aligned_funding_bps":
        return float(value) >= 10_000.0
    if field == "cooldown_bars":
        return int(value) == 0
    return False


def main() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
    clean_rsi = json.loads(CLEAN_RSI.read_text(encoding="utf-8"))
    legacy = json.loads(LEGACY.read_text(encoding="utf-8"))
    sleeves: dict[str, Any] = {}

    frontier_noops: dict[str, list[str]] = {}
    for row in frontier["exact_noop_variants"]:
        frontier_noops.setdefault(row["sleeve"], []).append(row["variant"])
    for sleeve, row in frontier["results"].items():
        roles = inventory["sleeves"][sleeve]["parameter_roles"]
        remove_fields = {
            field for field, role in roles.items() if role["status"] == "code_inert"
        }
        remove_components: list[str] = []
        for variant in frontier_noops.get(sleeve, []):
            if "diagnostic" in variant:
                continue
            fields = FRONTIER_COMPONENT_FIELDS.get(variant, [])
            if any(field in NON_REMOVABLE_RISK for field in fields):
                continue
            remove_components.append(variant)
            remove_fields.update(fields)
        config = row["baseline_config"]
        neutral_fields = {
            field
            for field, role in roles.items()
            if role["status"] in {"neutral_baseline", "structural_off"}
            and field not in NON_REMOVABLE_RISK
        }
        remove_fields.update(neutral_fields)
        retain = sorted(
            set(config)
            - {field for field in remove_fields if field in config}
            - {"config_id"}
        )
        sleeves[sleeve] = {
            "source": "frontier15m",
            "symbol": row["symbol"],
            "mechanism": row["mechanism"],
            "remove_fields": sorted(remove_fields),
            "remove_components": sorted(remove_components),
            "retain_fields": retain,
            "microtune_fields": [
                field
                for field in retain
                if field
                not in {
                    "symbol",
                    "mechanism",
                    "sl_atr",
                    "side_mode",
                }
            ],
            "risk_contract_fields": sorted(
                field for field in retain if field in NON_REMOVABLE_RISK
            ),
        }

    clean_sleeve = clean_rsi["sleeve"]
    clean_remove = set(clean_rsi["exact_noop_variants"])
    clean_field_map = {
        "remove_max_atr": "implicit_max_atr_pct96",
        "remove_rvol_min": "min_rvol96",
        "remove_h1": "h1_confirm",
        "remove_rsi14_band": "rsi14_band",
    }
    clean_fields = set(clean_rsi["baseline_config"])
    clean_removed_fields = {
        clean_field_map[name] for name in clean_remove if name in clean_field_map
    }
    sleeves[clean_sleeve] = {
        "source": "clean_rsi15m",
        "symbol": clean_rsi["symbol"],
        "mechanism": "clean_rsi_reversal",
        "remove_fields": sorted(clean_removed_fields),
        "retain_fields": sorted(clean_fields - clean_removed_fields),
        "microtune_fields": [
            "rsi_window",
            "rsi_low",
            "rsi_high",
            "min_atr_pct96",
            "take_profit_pct",
            "stop_pct",
            "max_hold_bars",
        ],
        "fixed_active_conditions": ["MACD direction >= 0"],
        "risk_contract_fields": ["stop_pct", "max_hold_bars"],
    }

    for sleeve, row in legacy["results"].items():
        config = row["baseline_config"]
        noops = {
            group
            for group, values in row["parameter_groups"].items()
            if values["classification"] == "remove_noop"
        }
        neutral = {
            field
            for field, value in config.items()
            if legacy_neutral(field, value)
        }
        externalized = {"sizing_kind", "fixed_leverage", "risk_fraction", "max_leverage"}
        remove = (noops | neutral | externalized) - NON_REMOVABLE_RISK
        retain = sorted(set(config) - remove - {"name"})
        sleeves[sleeve] = {
            "source": "legacy1h",
            "symbol": row["symbol"],
            "mechanism": row["mechanism"],
            "remove_fields": sorted(remove),
            "remove_noop_groups": sorted(noops),
            "neutral_fixed_removed": sorted(neutral),
            "externalized_account_risk_fields": sorted(externalized),
            "retain_fields": retain,
            "microtune_fields": [
                field
                for field in retain
                if field
                not in {
                    "style",
                    "entry_delay_bars",
                    "sl_atr",
                    "side_mode",
                }
            ],
            "risk_contract_fields": ["sl_atr", "max_hold_bars", "entry_delay_bars"],
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_clean_surface_before_microtune_not_candidate_not_registered",
        "research_cutoff_exclusive": inventory["research_cutoff_exclusive"],
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "decision_rules": {
            "code_inert": "remove",
            "three_scenario_exact_noop": "remove unless mandatory risk contract",
            "neutral_baseline": "remove from exposed interface and hardcode neutral behavior",
            "mandatory_stop_and_max_hold": "retain even when historical path did not touch it",
            "legacy_sizing": "remove from sleeve; joint account exposure <=3x is authoritative",
            "active_fields": "eligible for local microtune only",
        },
        "sleeves": sleeves,
        "summary": {
            "sleeves": len(sleeves),
            "remove_field_instances": sum(len(row["remove_fields"]) for row in sleeves.values()),
            "retained_field_instances": sum(len(row["retain_fields"]) for row in sleeves.values()),
            "microtune_field_instances": sum(len(row["microtune_fields"]) for row in sleeves.values()),
        },
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 clean参数表面（2026-07-15）",
        "",
        "这是V5之外的新研究线，只定义消融后的微调接口，不是候选、不是登记版本，也不修改V5未来OOS。",
        "",
        f"- 腿：`{payload['summary']['sleeves']}`",
        f"- 删除字段实例：`{payload['summary']['remove_field_instances']}`",
        f"- 保留字段实例：`{payload['summary']['retained_field_instances']}`",
        f"- 允许微调字段实例：`{payload['summary']['microtune_field_instances']}`",
        "- 灾难止损、最长持仓和K+1执行即便历史未触发也不会因消融而删除。",
        "- 旧1h腿内部杠杆/风险仓位字段全部外置，由联合账户不超过3x的暴露合同统一控制。",
        "",
        "## 逐腿clean表面",
        "",
        "| 腿 | 删除 | 保留 | 可微调 |",
        "|---|---:|---:|---:|",
    ]
    for sleeve, row in sleeves.items():
        lines.append(
            f"| `{sleeve}` | {len(row['remove_fields'])} | {len(row['retain_fields'])} | {len(row['microtune_fields'])} |"
        )
    lines.extend(
        [
            "",
            f"完整字段清单：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})。",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                **payload["summary"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
