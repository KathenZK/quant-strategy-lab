# Binance-1D-Trend-Prebreakout-State-Atlas Core Ledger

## Family Identity

- Full name：`Binance-1D-Trend-Prebreakout-State-Atlas`
- Alias：`BIN-1D-TPSA`
- 市场/周期：Binance 全部历史 USDT-M 永续合约 / 完整 UTC 日 K
- 边界：均线只制造事件；研究对象是截至突破前一日已经形成的价格与波动路径。
- 防串线：不继承 `BIN-1D-MA7-RC` 的固定 ATR 格子、全市场 breadth、账户或 ML 交易筛选。

## Current State

- 当前观察：`P1`
- 状态：`exploratory signal / diagnostic-only / new OOS required / not promoted / not live-ready`
- 结论：P0R 的第20日最终收益没有跨 MA×年份稳定过滤器；P1 改用“先 +2 ATR、后 -1 ATR”的趋势发生标签后，做多在 MA7/MA30 均得到多数年份正确排序，指向下跌/回撤后的低波稳定区向上脱离。做空 MA30 不稳定；股票类仍无合格事件。
- 下一门禁：不写策略；冻结可解释的 long 状态分数，在真正未揭示区间验证趋势发生率、概率校准及可执行退出，且不得用 P1 历史挑阈值。

## Version Rules

- 本家族登记的是市场状态观察，不是交易策略版本。
- 改变事件定义、前置观察窗、状态阈值、形态库、标签或模型特征，必须新建观察编号并在读取结果前冻结。
- 从状态地图写成交易策略必须另立策略家族，不能把本家族的探索性事件收益当作策略年化。

## Version Table

| 观察 | 状态 | 角色 | 证据 | 决策 |
| --- | --- | --- | --- | --- |
| `P0` | data-scope-incomplete | 首次完整路径形态地图；误用严格自然日连续块 | [合同](specs/binance-1d-trend-prebreakout-state-atlas-p0-contract-2026-08-25.md) | 被 P0R 输入修复取代 |
| `P0R` | completed / insufficient evidence | 保持全部形态、阈值和模型不变，仅修复周末休市合约连续块 | [修复合同](specs/binance-1d-trend-prebreakout-state-atlas-p0r-input-repair-2026-08-25.md) · [报告](diagnostics/binance-1d-trend-prebreakout-state-atlas-p0r-results-2026-08-25.md) | 不写策略；无跨 MA×年份稳定结构 |
| `P1` | exploratory signal / new OOS required | 用预先定义的 first-hit 路径标签学习趋势是否发生，不再预测第20日盈亏 | [合同](specs/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md) · [报告](diagnostics/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md) | long 跨 MA 有排序信息；尚非策略 |

## Shared Assumptions

- 数据截止 `2026-07-01`，至少上市 120 个自然日，连续块内计算。
- 前置状态截止 `t-1`；突破日字段与前置状态严格隔离。
- 固定观察未来 `1/3/5/10/20/40` 日，不做账户、不计算策略年化。

## Evidence Map

- [P0 合同](specs/binance-1d-trend-prebreakout-state-atlas-p0-contract-2026-08-25.md)
- [P0 机器配置](configs/binance-1d-trend-prebreakout-state-atlas-p0.json)
- [P0R 输入修复配置](configs/binance-1d-trend-prebreakout-state-atlas-p0r.json)
- [P0R 结果](diagnostics/binance-1d-trend-prebreakout-state-atlas-p0r-results-2026-08-25.md)
- [P0R artifact manifest](artifacts/binance_1d_tpsa_p0r_artifact_manifest.json)
- [P1 路径标签合同](specs/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md)
- [P1 路径标签结果](diagnostics/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md)
- [P1 artifact manifest](artifacts/binance_1d_tpsa_p1_artifact_manifest.json)
