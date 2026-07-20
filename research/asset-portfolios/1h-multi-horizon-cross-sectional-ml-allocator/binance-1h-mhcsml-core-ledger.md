# Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator Core Ledger

## Family Identity

- Full family name：`Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator`
- Alias：`BIN-1H-MHCSML`
- Market / exchange / symbol / timeframe：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`1h`
- Mechanism summary：分离 long/short/tail-risk 标签与模型，比较多期限和多决策频率，由允许空仓的 utility/risk allocator 形成组合。
- Boundary / collision warnings：不是 `BIN-1H-CSLGBM` 的版本增量，不继承其 Top7/Bottom7、单模型目标或错误收益结论。

## Current State

- Current version(s)：`BIN-1H-MHCSML-V1`，最终开发冻结为 `freeze R4`。
- Current status：`registered / not promoted / not live-ready`。
- Runner / dry-run / live status：无 runner；未 dry-run；未 live。
- Live-readiness blockers：未来三个月 prospective OOS 已启动但未完成；首个 `00:00 UTC` 节点按契约记为 `MISSED`；历史胜率 `53.67%` 低于最终 `55%` 门槛；订单、保证金、强平、断线恢复和重启状态机未审计。当前登记不代表 promotion。
- Next decision gate：继续每 4 小时只按 R4 记录盲信号；主采集在入场小时后第 `3` 分钟运行，signal-only watchdog 在第 `18` 分钟核对，仍受 `entry+25min` 截止与逾期 `MISSED` 约束。信号窗口在 `2026-10-19 00:00 UTC` 结束，最后 48h 腿成熟后最早于 `2026-10-20 21:05 UTC` 一次性揭示并执行全部硬门槛，期间不得改参数。

## Version Rules

- `V1`：首个同时冻结数据 manifest、因子、三类标签/模型、多期限 allocator、成本、风险规则和 prospective OOS 契约的候选。
- `Vx.y`：同一标签、模型和 allocator 机制下的小型实现修订；不得复用已揭示 OOS 选参。
- Observation / diagnostic rows：数据审计、标签正确性、基线和失败模型不占版本号。
- New version trigger：标签目标、主数据频率、币池、模型职责、allocator 或执行/保证金状态机发生实质变化。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| BIN-1H-MHCSML-V1 freeze R4 | `registered / not promoted / not live-ready` | 四种子 short-return + MAE + squeeze + confirmation；横截面校准 utility allocator | 历史 OOF：年化 `59.30%`、DD `17.77%`、胜率 `53.67%`、Sharpe `4.49`、PF `1.546`、`7/7` folds 盈利；非 OOS | [历史 OOF 审计](diagnostics/binance-1h-mhcsml-oof-model-allocator-2026-07-18.md)、[R4 candidate lock](artifacts/freeze/bin-1h-mhcsml-v1-prefit-lock-r4.json)、[R4 model freeze](artifacts/freeze/bin-1h-mhcsml-v1-model-freeze-r4.json) | 仅登记研究候选；等待 prospective OOS；未 promotion |

## Shared Assumptions

- Data：Binance 官方 API + Binance Vision；历史上市/退市合约均进入 point-in-time universe，先通过数据质量门禁再训练。
- Cost：每次成交手续费 `0.001` + `4 bps` 不利滑点；双边基础成本 `0.0028`，另按方向计真实 funding；压力成本为基础的 `1.5x`。
- Execution timing：K0 `1h` 收盘后生成特征，最早 K1 open 成交；不得读取 K1 或未来横截面；标签退出为对应持有期后的 open。
- Position sizing：allocator 可空仓、可单边、可变 N；基础保守敞口先过门槛，禁止用 3 倍杠杆制造通过。
- Funding / carry：long 扣 funding，short 加 funding；缺失 funding 不得静默视为真实 0。

## Evidence Map

- Specs：[冻结研究契约](specs/binance-1h-mhcsml-research-contract-2026-07-18.md)、[V1 R4 外部独立复现规格](specs/binance-1h-mhcsml-v1-r4-external-reproduction-spec-2026-07-19.md)、[R4 master freeze](artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json)、[最终裁决合同](artifacts/freeze/bin-1h-mhcsml-v1-final-adjudication-contract-r4.json)、[条件式 3x 风险规格](specs/binance-1h-mhcsml-v1-r4-3x-tail-risk-audit-spec-2026-07-19.md)、[条件式 3x 风险合同](artifacts/freeze/bin-1h-mhcsml-v1-three-x-risk-contract-r4.json)
- Diagnostics / ablations：[数据质量与补洞报告](diagnostics/binance-1h-mhcsml-data-quality-2026-07-18.md)、[因子与标签面板审计](diagnostics/binance-1h-mhcsml-factor-panel-2026-07-18.md)、[历史开发矩阵隔离审计](diagnostics/binance-1h-mhcsml-development-matrix-2026-07-18.md)、[历史 OOF、模型与 allocator 审计](diagnostics/binance-1h-mhcsml-oof-model-allocator-2026-07-18.md)、[因子组消融与 tail IC 审计](ablations/binance-1h-mhcsml-factor-group-ablation-2026-07-19.md)、[目标完成度矩阵](diagnostics/binance-1h-mhcsml-goal-completion-matrix-2026-07-19.md)。
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：[脚本入口](scripts/README.md)；artifact 位于 `artifacts/`，仅作可复现证据。
