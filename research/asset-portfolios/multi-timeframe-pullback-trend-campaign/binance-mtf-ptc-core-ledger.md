# Binance-MTF-Pullback-Trend-Campaign Core Ledger

## Family Identity

- Full family：`Binance-MTF-Pullback-Trend-Campaign`
- Alias：`BIN-MTF-PTC`
- Market：Binance USD-M perpetual；BTC/ETH/HYPE
- Mechanism：multi-horizon trend admission + causal continuation/survival meter + pullback/restart entry + independent-risk layers + structural campaign protection
- Boundary：独立新家族；PIC V2 只作即时追价 benchmark，不是 parent version

## Current State

- Current version：无；全部候选均为未登记研究机制。
- Current status：`explore / not promoted / not live-ready`；current decision `HARD-GATE-FAILED`。
- Goal：completed research / target not achieved。目标 `>=20×` 未实现；最高合规 BTC 2x frontier 在 revealed diagnostic validation 约 `1.134×` annual multiple，bar 内 MDD `-17.05%`。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：BTC frontier validation top-1/top-3 毛利润集中度 `72.6%/96.0%` 且收益远低于目标；ETH stress 失败；HYPE base/stress 失败且历史不足；无合格资产组合；current runner 无 lot-level same-direction resize parity。
- Locked historical evaluation：未运行。所有资产在进入 locked 前已因成本、稳定、集中度或收益门禁失败。
- Next gate：当前机制停止调参。若用户继续，必须创建 materially new mechanism/family；不得用 locked evaluation、删年份/方向或扩大风险救本家族。

## Version Rules

- Goal research completed 也不等于版本登记或 promotion。
- 只有用户明确要求登记，才把冻结候选加入 Version Table，默认 `registered`。
- 20×目标不得通过 OOS 调参、未来信息、不可成交 intrabar 顺序或风险超限达成。
- 资产可使用不同周期/参数，但必须独立冻结选择过程和证据；不能从最终 OOS 事后选择赢家资产。
- materially new label、状态机或退出机制必须新合同；已揭示锁定评估不得修复。

## Version Table

当前无 registered version。

## Evidence Map

- Goal Contract：[2026-08-03 Goal 合同](specs/binance-mtf-ptc-goal-contract-2026-08-03.md)
- Data Split：[2026-08-03 数据切分合同](specs/binance-mtf-ptc-data-split-contract-2026-08-03.md)
- Final Diagnostics：[Goal 最终研究报告](diagnostics/binance-mtf-ptc-goal-final-report-2026-08-03.md)
- Reproduction Spec：[BTC 历史前沿复现规格](specs/binance-mtf-ptc-btc-frontier-reproduction-spec-2026-08-03.md)
- Runner Gap：[2026-08-03 能力差距](runner-tracking/binance-mtf-ptc-runner-gap-2026-08-03.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
- Live spec：无；runner tracking 只有能力差距审计，不是 handoff。
