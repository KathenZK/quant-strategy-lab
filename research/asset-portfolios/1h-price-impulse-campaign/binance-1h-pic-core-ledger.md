# Binance-1H-Price-Impulse-Campaign Core Ledger

## Family Identity

- Full family：`Binance-1H-Price-Impulse-Campaign`
- Alias：`BIN-1H-PIC`
- Market：Binance USD-M perpetual，ETH candidate；BTC/HYPE/SOL controls；`1h`
- Mechanism：每日 `4h` 波动归一化价格冲量 admission + 25% probe + MFE 分层 add + 半回吐去新增层 + funding 后风险维护 + `1R` stop + 24h validation
- Boundary：独立策略家族；不把 FATHA 事后 habitat 或既有 HYPE NO-GO 当作本家族绩效证据

## Current State

- Current version：无；V0、V1、V2 均为运行前冻结但未登记的研究候选。V2 已完成，修复 V1 的 funding 风险漂移，但未过最近 6m 门禁。
- Current status：`explore / not promoted / not live-ready`。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：V2 最近 6m `-0.23%`；规则形成于已揭示历史；缺少新的 prospective OOS；runner 尚无同仓 partial resize、LIFO lot/stop parity 与 funding 后 risk trim。
- Next gate：不再用已揭示历史救参数。只有用户明确要求登记冻结身份后，才能建立新的 prospective OOS 合同；其通过后再做 promotion review。

## Version Rules

- V0 候选规则由 2026-08-03 合同冻结；运行后不得在同一历史改 threshold、stop 或 timeout 来救结果。
- V1/V2 各自在运行前冻结；V1 的 `2.06%` funding 风险漂移和 V2 的 6m 失败必须保留，禁止回写合同。
- 只有用户明确要求登记，或后续明确 promotion 流程需要固定身份时，才把候选写入 Version Table 为 `registered`。
- 改变资产、观察相位、impulse threshold、R、退出或 position sizing 属于新候选。
- 真实 pyramiding/resize 是后续机制版本，不能把 shadow add 当成已执行仓位。

## Version Table

当前无 registered version。

## Shared Assumptions

- Data：标准数据湖 Binance `15m` OHLCV/funding，四根完整 bar 聚合为 `1h`，raw/normalized parity fail-closed。
- Cost：fee `10bps/fill` + adverse slippage `4bps/fill` + 实际 funding。
- Timing：closed-bar signal，下一根 `1h open`；保护更新只使用上一根已闭合 bar。
- Sizing：计划风险 `1%`，真实 quantity，entry leverage cap `3x`。
- Live：研究脚本不执行订单；只有通过门禁的 sibling `quant-runner` 可运行。

## Evidence Map

- Spec：[V0 合同](specs/binance-1h-pic-v0-contract-2026-08-03.md)
- V1 Spec：[分层候选合同](specs/binance-1h-pic-v1-layered-contract-2026-08-03.md)
- V2 Spec：[风险不变量合同](specs/binance-1h-pic-v2-risk-invariant-contract-2026-08-03.md)
- Diagnostics：[V0–V2 初始研究结论](diagnostics/binance-1h-pic-v0-v2-initial-research-2026-08-03.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
- Live specs / runner tracking：无
