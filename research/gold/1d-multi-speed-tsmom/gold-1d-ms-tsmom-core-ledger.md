# GOLD-1D-Multi-Speed-TSMOM Core Ledger

## Family Identity

- Full name：`GOLD-1D-Multi-Speed-TSMOM`
- Alias：`GOLD-1D-MS-TSMOM`
- 市场：COMEX Gold continuous futures；Stooq `GC.F` 长期快照与 Yahoo `GC=F` 独立近期段
- 周期：日数据输入、月末调仓
- 机制：`1M/3M/12M` 时序收益符号信号与 10% 单资产波动率目标
- 防串线：不是 `BTC-1D-CCTA`、`BIN-1D-TSMOM-VT` 或 ETF 代理研究

## Current State

- 当前主状态：`explore / not promoted / not live-ready`
- 当前观察：`2026-08-18 literature baseline` + `recent extension`，均无版本号、未登记
- 数据状态：`raw_unaccepted`；连续合约 roll/adjustment、交易日历和闭合字段未核验；两供应商路径不拼接
- 下一门禁：获得当前 CME 官方连续序列或逐合约可复建数据并完成 trusted normalization

## Version Rules

- 当前没有注册版本；本次固定规则只构成 literature baseline observation。
- 未来只有用户明确要求登记时才创建 `V1`；更换数据执行面不静默覆盖本观察。

## Version Table

| Observation | Status | Role | Evidence | Decision |
| --- | --- | --- | --- | --- |
| `2026-08-18 baseline` | `explore` | 固定 1M/3M/12M 文献规则的单黄金诊断 | [规格](specs/gold-1d-ms-tsmom-baseline-2026-08-18.md) · [诊断](diagnostics/gold-1d-ms-tsmom-backtest-2026-08-18.md) | 不登记、不晋升 |
| `2026-08-18 recent extension` | `diagnostic-only` | Yahoo `GC=F` 2021-12–2026-07 独立近期段 | [诊断](diagnostics/gold-1d-ms-tsmom-recent-2026-08-18.md) | 不拼接、不登记、不晋升 |

## Shared Assumptions

- 月末收盘生成信号，下一交易日开始持有；月内方向不更新。
- `position = forecast × 10% / sigma_ann`；无仓位上限，不做组合协方差缩放。
- 60-day COM EWMA 使用滞后一天的日简单收益平方；年化因子 `252`。
- 主成本为单边每单位换手 `2 bps`，另保留 `0 bps` 对照；未单列换月成交成本。

## Evidence Map

- [基线规格](specs/gold-1d-ms-tsmom-baseline-2026-08-18.md)
- [诊断报告](diagnostics/gold-1d-ms-tsmom-backtest-2026-08-18.md)
- [2022–2026 近期扩展](diagnostics/gold-1d-ms-tsmom-recent-2026-08-18.md)
- [Artifacts index](artifacts/README.md)
- [Scripts index](scripts/README.md)
