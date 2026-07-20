# BIN-1H-CSLGBM-V1 外部复现规格（已撤销）

## 撤销声明

本规格于 2026-07-18 撤销，不得用于复现或宣传有效策略绩效。原版本将 Binance USD-M 线性合约空头净收益错误写为：

```text
entry_open / exit_open - 1 - round_trip_cost + funding_sum
```

正确口径应为：

```text
1 - exit_open / entry_open - round_trip_cost + funding_sum
```

因此原 `+221.84%` OOS、`+315.43%` prefit 年化及其所有衍生基线、压力和近期分片结论均已作废。固定原模型分数和冻结选币重算后的 `2026Q2` OOS 为 `-37.04%`、最大回撤 `37.04%`、Sharpe `-3.26`、PF `0.60`。

原始模型、冻结 SHA、揭盲 marker 和错误结果 artifact 保留为研究事故证据，不应覆盖或删除。`2026Q2` 已经揭示，任何新策略必须使用独立 family、正确的 long/short/tail 标签，以及未来未见的 prospective OOS。

## 附录：仓库内校验（非复现依赖）

- [V1 OOS 公式纠错审计](../diagnostics/binance-1h-cslgbm-v1-oos-2026-07-17.md)
- [纠错脚本](../scripts/audit_v1_short_return_correction.py)
- [标签构建脚本](../scripts/build_cross_sectional_factor_panel.py)
- [自动测试](../../../../tests/test_linear_contract_returns.py)
