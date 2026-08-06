# HYPE-1H-Multi-Mechanism-Trend-Following Core Ledger

## Family Identity

- Full name：`HYPE-1H-Multi-Mechanism-Trend-Following`
- Alias：`HYPE-1H-MMTF`
- Market：Binance USD-M Futures `HYPEUSDT` perpetual `1h`
- Boundary：独立纯趋势家族；不继承 `HYPE-1H-Adaptive-Regime` 或其他 HYPE 家族的版本、参数与结论。

## Current State

- 当前状态：V1-V3 `registered`；V3 `HARD-GATE-FAILED / not promoted / not live-ready`（尚未进入 runner，不使用 runner 后终态 `NO-GO`）。
- 当前版本：`HYPE-1H-Multi-Mechanism-Trend-Following-V3`（V2 为 V1 clean-equivalent）。
- 当前判断：冻结 V3 的 locked OOS 为 `1.7887x / 33.07% MDD / 84.62% / 13 trades`，完整样本为 `5.4102x / 33.07% / 87.67% / 73`；年化、回撤和 OOS 最低样本均失败。K+2、8bps 与 30m shifted phase 也失败。
- 下一决策门：不得围绕已揭示 OOS 追参。若继续研究，应换成对收线边界不敏感的多 bar hysteresis / trend-campaign 新机制，并从 `2026-07-22 10:00 UTC` 之后建立 prospective OOS。

## Version Rules

- `V1` 固定原始可执行基线身份，登记不等于 promotion。
- path-equal 清洁化版本可登记为 `V2 clean-equivalent`；成交路径发生变化时必须作为新的诊断版本并说明差异。
- `V3` 固定 clean-surface prefit/validation 调优结果；locked OOS 揭示后不得修改该版本参数或据其追参。
- 未完成 locked OOS、压力与 live-executable 门禁的版本保持 `not promoted / not live-ready`。

## Version Table

| Version | Status | Role | Evidence | Decision |
| --- | --- | --- | --- | --- |
| `HYPE-1H-Multi-Mechanism-Trend-Following-V1` | registered diagnostic baseline / not promoted / not live-ready | 双向 120h time-series momentum + EMA96/120 regime + ATR48 bracket，固定 `2x` | [V1 规格](specs/hype-1h-mmtf-v1-original-baseline-spec.md)；[广搜报告](diagnostics/hype-1h-mmtf-v1-broad-search-2026-07-22.md) | Prefit `4.8034x / 82.26% / 20.04% MDD / 62`；validation `10.3214x / 87.50% / 9.72% / 16`；未揭示 OOS，不 promotion |
| `HYPE-1H-Multi-Mechanism-Trend-Following-V2` | registered clean-equivalent / not promoted / not live-ready | 删除 8 个机制选择、fixed-disabled 或 path-equal 槽，保留 12 参数 clean interface | [V2 规格](specs/hype-1h-mmtf-v2-clean-equivalent-spec.md)；[消融](ablations/hype-1h-mmtf-v1-full-ablation-2026-07-22.md) | V1/V2 逐笔 SHA256 同为 `f70a8e...224b`；指标完全相同 |
| `HYPE-1H-Multi-Mechanism-Trend-Following-V3` | registered / HARD-GATE-FAILED / not promoted / not live-ready | V2 有效参数面调优：EMA96/168、TP1.25ATR、trail2ATR、cooldown18h、`2.5x` | [V3 规格](specs/hype-1h-mmtf-v3-tuned-spec.md)；[最终审计](diagnostics/hype-1h-mmtf-v3-final-audit-2026-07-22.md) | Prefit `7.3616x / 19.83% / 88.33% / 60`；OOS `1.7887x / 33.07% / 84.62% / 13`；full `5.4102x / 33.07% / 87.67% / 73`；promotion failed |

## Shared Assumptions

- 闭合 `1h` K 信号，最早下一根 open 成交；单净仓；总杠杆不超过 `3x`。
- fee `0.001/fill`、base slippage `4 bps/fill`、逐时段真实 funding；stop-first、gap-open 保守成交。
- 最终硬门槛：完整样本与 locked OOS 同时达到 annual equity factor `>=20x`、win rate `>=80%`、MDD `<20%`，且交易数分别至少 `60/15`。

## Evidence Map

- [数据冻结与质量报告](diagnostics/hype-1h-mmtf-data-freeze-2026-07-22.md)
- [V1 广搜报告](diagnostics/hype-1h-mmtf-v1-broad-search-2026-07-22.md)
- [V1 冻结规格](specs/hype-1h-mmtf-v1-original-baseline-spec.md)
- [V1 全消融](ablations/hype-1h-mmtf-v1-full-ablation-2026-07-22.md)
- [V2 clean-equivalent 规格](specs/hype-1h-mmtf-v2-clean-equivalent-spec.md)
- [V3 调优规格](specs/hype-1h-mmtf-v3-tuned-spec.md)
- [V3 最终审计](diagnostics/hype-1h-mmtf-v3-final-audit-2026-07-22.md)
- [决策记录](decision-log.md)
