# Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator

- 别名：`BIN-1H-MHCSML`
- 市场：Binance USD-M USDT 永续合约，point-in-time 动态全市场币池，`1h` 输入。
- 机制：分别预测 long 净收益、short 净收益和尾部风险，在 `4/8/12/24/48h` 多期限上由允许空仓的风险效用 allocator 分配组合。
- 当前状态：`archived`；`BIN-1H-MHCSML-V1` freeze R4 的本地产物、模型和盲链
  数据已删除，prospective OOS 已终止且不再揭盲。这里只保留 Markdown 研究记录与
  历史脚本，未授权 dry-run 或 live。

## 边界

- 本家族不是固定 Top7/Bottom7 的 `BIN-1H-CSLGBM` 修订版，不继承其版本号、错误绩效、单模型标签或强制持仓规则。
- 已揭示的 `2026Q2` 只能作 reused holdout / 诊断；`2026-07-19 00:00 <= ts < 2026-10-19 00:00 UTC` 为锁定 prospective OOS 信号窗口，最后 48h 腿成熟后最早于 `2026-10-20 21:05 UTC` 一次性揭盲。
- 本家族已封存，不创建 live spec，不修改 `quant-runner`。

## 入口

- [Core ledger](binance-1h-mhcsml-core-ledger.md)
- [Decision log](decision-log.md)
- [冻结研究契约](specs/binance-1h-mhcsml-research-contract-2026-07-18.md)
- [V1 R4 外部独立复现规格](specs/binance-1h-mhcsml-v1-r4-external-reproduction-spec-2026-07-19.md)
- [条件式 3x 尾部风险审计规格](specs/binance-1h-mhcsml-v1-r4-3x-tail-risk-audit-spec-2026-07-19.md)
- [数据质量与补洞报告](diagnostics/binance-1h-mhcsml-data-quality-2026-07-18.md)
- [因子与标签面板审计](diagnostics/binance-1h-mhcsml-factor-panel-2026-07-18.md)
- [历史 OOF、模型与 allocator 审计](diagnostics/binance-1h-mhcsml-oof-model-allocator-2026-07-18.md)
- [因子组消融与 tail IC 审计](ablations/binance-1h-mhcsml-factor-group-ablation-2026-07-19.md)
- [目标完成度矩阵](diagnostics/binance-1h-mhcsml-goal-completion-matrix-2026-07-19.md)
- `scripts/`：数据审计、标签/因子、nested walk-forward、allocator、冻结和 OOS 门禁脚本。
- `artifacts/`：本地数据 manifest、OOF 预测、模型、逐腿证据和冻结 SHA；不替代 Markdown 结论。
