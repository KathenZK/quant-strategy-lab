# Binance-MTF-Dual-State-Trend-Campaign Core Ledger

## Family Identity

- Full family：`Binance-MTF-Dual-State-Trend-Campaign`
- Alias：`BIN-MTF-DSTC`
- Market：Binance USD-M perpetual；HYPEUSDT、BTCUSDT、ETHUSDT
- Mechanism：daily Campaign state + independent position/lot risk state + 4h/1h/15m pullback/restart + profit-confirmed pyramiding
- Boundary：materially new successor to closed `BIN-MTF-PTC`; independent of `HYPE-15M-MTPP` and diagnostic `BIN-1D-MA7DC`

## Current State

- Current version：无；Goal 搜索候选均为 unregistered diagnostic。
- Current status：`HARD-GATE-FAILED / explore / not promoted / not live-ready`；Goal complete，family closed。
- Target：最低候选净年化资本因子 `>=2x`、MDD `<=20%`、PF `>=1.3`、effective leverage `<=3x`；`5x` 为 Tier S、`20x` 为 Stretch。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Evidence boundary：BTC/ETH cutoff 固定在 `2026-08-03 11:45 UTC`；HYPE 查询层 cutoff 固定在 `2026-08-01 15:15 UTC`，不得读取 `HYPE-15M-MTPP` 已锁定的 `2026-08-02` 后 prospective；HYPE 2026-03 后可用历史只能作 exposed audit；本家族 fresh prospective 从 `2026-08-05 00:00 UTC` 起 outcome-blind。
- Result：432 个账户级回测完成；`BTC-BAL` 是最干净微弱优势，1% 风险 `1.028x annual / -12.2% MDD / PF1.65`，但所有风险档均远低于 `2x annual`；HYPE 无 E02 资格配置；historical final audit 未揭示。
- Blockers：收益强度不足；提高风险先突破 20% MDD；空头无独立优势；多个增长路径 remove-top-3 失败。无数据/时序/成本/延迟 blocker。
- Next gate：停止同机制调参。任何 successor 必须 materially new，并重新冻结 prospective/OOS；本家族不得创建版本、live spec 或 runner handoff。

## Version Rules

- 用户明确要求登记前不创建 `V1`；Goal active/complete 都不等于登记或 promotion。
- Campaign state、position stop、restart、layer、risk 或执行时序发生实质变化必须有预声明 contract 和 experiment id。
- HYPE/BTC/ETH 独立冻结参数与资格；不能在最终评估后只保留赢家资产并声称跨资产成立。
- 已揭示 historical audit 与 prospective 失败不得用于静默救参。

## Version Table

当前无 registered version。

## Shared Assumptions

- 完整闭合 `15m` 数据聚合 `1h/4h/1d`；高周期状态只在闭合后可见，动作最早下一根 `15m open`。
- Binance base cost 为 `0.1% fee/fill + 4bps adverse slippage/fill + actual funding`；8/12bps 做 stress。
- 初始计划风险 1%，通过机制门禁后才机械比较至 3%；fill 与持仓途中 effective leverage 均不得超过 3x。
- 账户级 MDD 使用逐 15m liquidation equity 与 bar 内不利极值，不只看平仓点。

## Evidence Map

- [Goal 合同](specs/binance-mtf-dstc-goal-contract-2026-08-04.md)
- [数据与评估合同](specs/binance-mtf-dstc-data-evaluation-contract-2026-08-04.md)
- [实验注册表](specs/binance-mtf-dstc-experiment-registry-2026-08-04.md)
- [E05 稳定性候选冻结](specs/binance-mtf-dstc-stability-candidate-freeze-2026-08-04.md)
- [Goal 最终报告](final/binance-mtf-dstc-goal-final-2026-08-04.md)
- [决策记录](decision-log.md)
- [脚本说明](scripts/README.md)
- [产物说明](artifacts/README.md)
