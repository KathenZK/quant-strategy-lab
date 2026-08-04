# HYPE-1D-Price-Kinematics-Continuation Core Ledger

## Family Identity

- Full family：`HYPE-1D-Price-Kinematics-Continuation`
- Alias：`HYPE-1D-PKC`
- 市场：Binance USD-M perpetual；`HYPE/USDT:USDT`
- 周期：完整 UTC `1d` 轨迹；过去 `3d/7d/14d` 状态预测未来 `3d/7d/14d`
- 机制：只用对数价格的位移、速度、加速度、路径长度、一致性、脉冲集中度与粗糙度验证趋势延续
- 边界：独立于 `HYPE-1H-PKC`、`HYPE-15M-PKC`、`HYPE-1D-PT`、`HYPE-1D-MHEF` 与所有传统指标策略

## Current State

- 当前版本：无；只有未编号的统计诊断。
- 状态：`explore / diagnostic-only / not promoted / not live-ready`。
- 初始验证：Long/Short 均为 `daily-kinematic-evidence-supported = false`。Long Validation Full IC 为 `0.264/0.336/0.450`，但 Train OOF 只有 `1/3` 同号；Short 三个时期同号但 Full 不优于 Baseline，且 Validation 绝对延续率仅 `18.2%–43.8%`。
- 证据功效：427 根完整日 K；预声明 Q1/Q5 检验最少只有 Long `9`、Short `6` 个独立 14 日块，均低于 `20` 门槛；无方向拥有两个跨两个 horizon 的稳定结构特征。
- 下一门：不得用已揭示 Validation 挑 Long `14d` 或单一 `coherence_14`；只允许在冻结 prospective OOS 中观察，或在不混池的独立资产家族验证同一物理假设。

## Version Rules

- 统计观察、相图或失败假设不构成版本。
- 只有用户明确要求登记、且交易逻辑另行冻结后，才允许创建策略 `V1`；统计关系成立不等于 promotion。
- 改变过去窗口、方向定义、未来标签、模型或 Validation 属于新冻结研究轮次，不得覆盖本轮。

## Version Table

当前无 registered version。

## Shared Assumptions

- 只保留由连续 `96` 根已闭合 Binance `15m` K 聚合的完整 UTC 日 K；日 K 在下一 UTC 午夜才可用。
- 过去窗口为 `3/7/14` 日，过去 `7d` 位移定义 Long/Short；未来标签为 `3/7/14` 日方向收益和路径。
- Train：`[2025-06-15, 2026-02-01 UTC)`；Validation：`[2026-02-15, 2026-08-03 UTC)`；prospective OOS：`[2026-08-03, 2026-11-03 UTC)`，保持未揭示。
- 第一阶段无交易收益与成本口径；Ridge `alpha=10`、Logit `C=0.1` 固定，14 日 block bootstrap `2000` 次。

## Evidence Map

- Spec：[初始研究合同](specs/hype-1d-pkc-initial-research-contract-2026-08-03.md)
- Diagnostics：[初始验证](diagnostics/hype-1d-pkc-initial-research-2026-08-03.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
