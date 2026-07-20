# BIN-1H-CSLGBM-V1 artifact 撤销声明

本目录中的原始模型、预测、逐腿、组合、基线、压力和近期分片产物均保留为研究事故证据，但其绩效结论已经撤销，不得再用于选参、宣传、复现有效策略或 promotion。

原始空头公式错误使用：

```text
entry_open / exit_open - 1 - round_trip_cost + funding_sum
```

线性 USD-M 正确公式为：

```text
1 - exit_open / entry_open - round_trip_cost + funding_sum
```

因此旧 `+221.84%` OOS、`+315.43%` prefit 年化和“只失败月集中度”全部无效。固定原模型分数与选币、只修正收益公式后，`2026Q2` OOS 为 `-37.04%`、最大回撤 `37.04%`、Sharpe `-3.26`、PF `0.60`，结论为 `HARD-GATE-FAILED / not promoted / not live-ready`。

机器读取时必须先检查同目录 [REVOCATION.json](REVOCATION.json)。权威纠错证据为 [correction_audit.json](linear_return_correction/correction_audit.json)，长期结论见 [公式纠错审计](../../diagnostics/binance-1h-cslgbm-v1-oos-2026-07-17.md)。
