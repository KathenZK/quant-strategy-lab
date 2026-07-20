# BIN-1H-CSLGBM-V1 OOS 公式纠错审计（2026-07-18）

## 结论

- 正式状态：`registered / not promoted / not live-ready`。
- 研究门槛：`HARD-GATE-FAILED`。
- 2026-07-17 揭示报告中的 `+221.84%` OOS 收益、`6.09%` 回撤及“只失败月集中度”的结论全部作废；prefit 组合搜索及规则基线也使用了同一错误空头标签，其绩效同样作废。
- 错误公式为 `entry_open / exit_open - 1 - cost + funding`，它是现货价格倒数收益，不是 Binance USD-M 线性合约按入场名义金额归一化的空头 PnL。
- 正确公式为 `1 - exit_open / entry_open - cost + funding`。固定原模型分数、Top7/Bottom7、UTC 00:00、24h 持有和 `0.45x` gross 后重算，策略亏损 `37.04%`，不具备 promotion 条件。

## 影响范围

模型本身预测的是 `label_long_relative_24h`，因此已保存的模型分数可以用于定位错误影响；但是所有利用错误 `label_short_net_*` 计算的 portfolio search、前沿选择、prefit/OOS 绩效、规则基线、压力测试和近期分片均不得继续引用为有效收益证据。

本次纠错没有重新训练、重新选币或改变冻结组合，只替换空头 PnL 公式，因此它是对旧 V1 的损害评估，不是新候选，也不是可以继续在 `2026Q2` 调参的授权。

## 公式验证

以入场价 `100`、退出价 `50`、忽略成本和 funding 为例：

```text
long  = 50 / 100 - 1 = -50%
short = 1 - 50 / 100 = +50%
错误倒数公式 = 100 / 50 - 1 = +100%
```

纠错脚本逐行重构旧标签，旧 parquet 与错误倒数公式的最大绝对差为 `2.49e-14`，确认污染来自公式本身，而不是报告抄写。自动测试覆盖价格上涨/下跌、成本、funding 符号、缺失值和因子面板集成路径。

## 正确公式下的冻结 OOS

窗口仍为 `2026-04-01 <= ts < 2026-07-01 UTC`，只纳入 90 个能够完成 24h 退出的 UTC 00:00 决策，共 1,260 条腿。

| 指标 | 纠错值 | 硬门槛 | 结果 |
| --- | ---: | ---: | --- |
| 三个月累计收益 | `-37.04%` | `>=18.92%` | FAIL |
| 折算年化 | `-84.68%` | `>=100%` | FAIL |
| 最大回撤 | `37.04%` | `<=20%` | FAIL |
| 组合周期胜率 | `56.67%` | `>=55%` | PASS |
| Sharpe | `-3.26` | `>=1.50` | FAIL |
| 组合周期 PF | `0.60` | `>=1.30` | FAIL |
| 有效组合周期 | `90` | `>=45` | PASS |
| 完成长/短腿 | `1,260` | `>=300` | PASS |
| 正收益月份 | `0/3` | `>=2/3` | FAIL |
| 1.5x 成本收益 | `-40.53%` | `>0` | FAIL |
| 1.5x 成本回撤 | `40.53%` | `<=25%` | FAIL |

分方向看，账户敞口均为 `0.225x`：

| 方向 | 收益 | DD | 胜率 | PF | Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: |
| Long Top7 | `-10.51%` | `11.06%` | `41.11%` | `0.485` | `-5.14` |
| Short Bottom7 | `-29.83%` | `31.19%` | `56.67%` | `0.697` | `-2.35` |

空头腿虽然胜率超过一半，但最差单日空头侧账户收益为 `-14.09%`；选中腿中有 10 条持有期线性收益低于 `-100%`。这不是“缺失退出”，而是固定持有空头遭遇 squeeze 的真实尾部风险，旧组合没有逐时盯市、保证金或强平状态机。

## 模型排序为何仍会亏损

OOS 每小时平均 Spearman Rank IC 对 long relative label 约为正，但 score decile 的收益幅度不单调：最低分组被少数极端上涨币抬高，高分尾部并未形成稳定正净收益。Rank IC 主要描述排序方向，不保证极端 Top/Bottom 组合扣除成本和尾部损失后盈利。

旧 V1 还存在结构性错配：用预测做多相对收益的单一模型，把最低分直接当作空头；每天强制 Top7/Bottom7，不允许空仓；训练目标没有直接惩罚 squeeze、MAE 或组合尾部亏损。这些问题必须由独立的新家族重新定义标签、模型和 allocator，不能在已揭示 `2026Q2` 上继续挑参数。

## 可复现证据

- 纠错脚本：[audit_v1_short_return_correction.py](../scripts/audit_v1_short_return_correction.py)
- 标签构建脚本：[build_cross_sectional_factor_panel.py](../scripts/build_cross_sectional_factor_panel.py)
- 自动测试：[test_linear_contract_returns.py](../../../../tests/test_linear_contract_returns.py)
- 本地 artifact：`../artifacts/v1_oos_2026q2/linear_return_correction/correction_audit.json`、`corrected_completed_trades.csv`、`corrected_portfolio_decisions.csv`

原始揭盲 artifact 保留为错误证据，不覆盖、不删除；其指标不得再作为策略结论。`2026Q2` 已被查看，只能作为 reused holdout / 诊断窗口，不能承担后续版本的独立 OOS。
