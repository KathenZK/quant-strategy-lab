# Binance-1D-Monthly-Cross-Sectional-Momentum-Long10 Core Ledger

## Family Identity

- Full name：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`
- Alias：`BIN-1D-MCSM-L10`
- 市场：Binance USD-M USDT 永续；UTC 日 K 由 `15m` Vision 全市场月档聚合
- 机制：上一完整日历月收益排序，月初开盘等权 long Top10，总 gross 100%，不做空
- 防串线：不是 [`BIN-1D-MCSM-LS3`](../1d-monthly-cs-momentum-ls3/README.md) 的 3+3 多空，也不是外部现货美股/加密混合横截面；Binance 原生股票/TradFi 永续属于 Binance 合约池

## Current State

- 当前主状态：`explore / diagnostic-only / not promoted / not live-ready`
- 当前观察：BTC SMA200 gate 与 MH136 均不是策略核心；赚钱效应诊断显示 breadth、市场收益中位数、leader spread 和 leader 3M strength 对稀疏右尾有条件解释力，`strong/strong` 月均超额 `+12.16%`，但只捕获约 `40%` 的完整价格右尾 PnL，月频状态候选失败
- 核心 blocker：15m 执行审计发现同 bar 成交、零成交占位 K 线入选、不可成交退出和持仓缺价静默置零；原 target12 有 41 个 blocker，按 `00:15 UTC` 可成交入选后仍有 15 个，所有旧引擎绩效标记 `PERFORMANCE_INVALIDATED`
- 下一门禁：执行修复与 alpha 研究分线；策略机制若继续，必须另行预注册“月度 Top10 + 日级 breadth/leader 相对强度状态机”，不允许把已揭示的 leader-strong 消融直接登记；四类执行 blocker 清零和新 prospective evidence 前不得 promotion

## Version Rules

- 当前没有注册版本；本轮只按用户字面规则做诊断。
- 改形成期、Top N、波动目标或市场范围均是新 observation 或独立家族，不继承本轮绩效。加入外部现货美股需另建跨市场家族；Binance 原生股票/TradFi 永续已经按同一合约资格规则纳入。

## Version Table

| Observation | Status | Role | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `2026-08-18 diagnostic` | `explore / diagnostic-only` | Binance 月频 1M Top10 long-only | 全上市 `+2402.97%` / CAGR `66.31%` / MDD `-93.79%`；ADV 版 `+2104.80%` / MDD `-92.99%` | [契约](specs/binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md) · [诊断](diagnostics/binance-1d-mcsm-long10-diagnostic-2026-08-18.md) | 不登记、不晋升 |
| `2026-08-19 breadth diagnostic` | `explore / diagnostic-only` | Binance 月频 1M Top10/20/30/40/50 long-only | 共同窗口中 Top10 仍最高；宽度增加时收益单调衰减，MDD 仍为 `-87%` 至 `-94%` | [契约](specs/binance-1d-mcsm-long-breadth-diagnostic-contract-2026-08-19.md) · [诊断](diagnostics/binance-1d-mcsm-long-breadth-diagnostic-2026-08-19.md) | 不登记、不晋升 |
| `2026-08-19 risk-buffer diagnostic` | `explore / diagnostic-only` | Top10 + 20% 组合目标波动、无杠杆；再加 10/20 缓冲 | 全上市 target20 `+217.36%` / CAGR `20.01%` / MDD `-42.33%`；缓冲后 `+199.18%` / MDD `-42.55%` | [契约](specs/binance-1d-mcsm-long10-risk-buffer-diagnostic-contract-2026-08-19.md) · [诊断](diagnostics/binance-1d-mcsm-long10-risk-buffer-diagnostic-2026-08-19.md) | 风险缩放有效；缓冲不改善；不登记、不晋升 |
| `2026-08-19 positive-cash diagnostic` | `explore / diagnostic-only` | Top10 仅买形成收益>0的名字，每槽10%，缺口现金 | 全上市 target20 `+245.39%` / MDD `-41.61%`；ADV target20 `+218.78%` / MDD `-40.56%` | [契约](specs/binance-1d-mcsm-long10-positive-cash-diagnostic-contract-2026-08-19.md) · [诊断](diagnostics/binance-1d-mcsm-long10-positive-cash-diagnostic-2026-08-19.md) | 单宇宙小幅改善、跨宇宙不稳健；不登记、不晋升 |
| `2026-08-20 liveability diagnostic` | `explore / diagnostic-only` | BTC SMA200 gate、MH136、target12 风险预算 | gate 与 MH136 失败；target12 旧引擎 `+94.82%` / Sharpe `0.906` / MDD `-25.073%`，但完整 12m cohort 仅 `2/5` 为正 | [冻结合同](specs/binance-1d-mcsm-long10-liveability-candidate-contract-2026-08-20.md) · [审计](diagnostics/binance-1d-mcsm-long10-liveability-audit-2026-08-20.md) | target12 仅保留假设；不登记、不晋升 |
| `2026-08-20 execution audit` | `HARD_BLOCKER / PERFORMANCE_INVALIDATED` | 真实 15m、`00:15 UTC` 入场/退出/估值审计 | 原路径 41 个 blocker；可成交重选后仍 15 个 | [修复合同](specs/binance-1d-mcsm-long10-execution-repair-contract-2026-08-20.md) · [blockers](artifacts/binance-1d-mcsm-long10-target12-execution-timing-2026-08-20-blockers.csv) | 旧绩效失效；停止 promotion |
| `2026-08-20 money-effect diagnostic` | `explore / diagnostic-only` | 月度赚钱效应 breadth × leader continuation 冻结 2×2 状态 | `strong/strong` 月均超额 `+12.16%`、胜率 `55.6%`，但完整价格正 PnL/右尾捕获仅 `42.0%/40.1%`，完整 12m cohort 仅 `1/4` 为正 | [合同](specs/binance-1d-mcsm-money-effect-continuation-diagnostic-contract-2026-08-20.md) · [诊断](diagnostics/binance-1d-mcsm-money-effect-continuation-diagnostic-2026-08-20.md) | 方向部分成立，月频 gate 失败；不登记、不晋升 |

## Shared Assumptions

- 信号只使用已闭合上月数据；原“月初 `00:00` 开盘成交”已被执行审计否决，修复口径最早为 `00:15 UTC` 可成交 bar；各腿未缩放目标 `1/10`。
- Binance 每边手续费 `0.001`、滑点 `4 bps`，逐日资金费；末日收盘平仓。
- 全市场月档 `2020-01`–`2026-06`，评估 `2020-03-01`–`2026-06-30`；线性 PnL，不模拟强平。

## Evidence Map

- [诊断契约](specs/binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md)
- [诊断报告](diagnostics/binance-1d-mcsm-long10-diagnostic-2026-08-18.md)
- [宽度诊断](diagnostics/binance-1d-mcsm-long-breadth-diagnostic-2026-08-19.md)
- [风险与缓冲诊断](diagnostics/binance-1d-mcsm-long10-risk-buffer-diagnostic-2026-08-19.md)
- [正收益与现金缺口诊断](diagnostics/binance-1d-mcsm-long10-positive-cash-diagnostic-2026-08-19.md)
- [可实盘化与执行审计](diagnostics/binance-1d-mcsm-long10-liveability-audit-2026-08-20.md)
- [赚钱效应与领涨延续诊断](diagnostics/binance-1d-mcsm-money-effect-continuation-diagnostic-2026-08-20.md)
- [执行语义修复合同](specs/binance-1d-mcsm-long10-execution-repair-contract-2026-08-20.md)
- [Artifacts](artifacts/README.md)
- [Scripts](scripts/README.md)
