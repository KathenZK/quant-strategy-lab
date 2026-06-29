# HYPE-6H-RS4-Regime-Switch 决策日志

## 2026-06-26：启动同事 RS4 策略独立复现

- 输入材料：`/Users/ZK/Downloads/RS4-EXPLAINED-RS4策略详细图解.html`。
- 研究归属：新建 `HYPE-6H-RS4-Regime-Switch`，不并入既有 `15m`、`5m` 或 `1m` family。
- 初始状态：diagnostic only / not promoted。
- 原因：策略说明声称的核心证据包含 Bybit 2024-12 全史和 16 个 melt-leg 变体选择，但本仓库当前可直接复现的是 Binance HYPEUSDT perpetual `5m` normalized 数据湖聚合 `6h`。
- 硬性要求：任何收益结论都必须伴随数据质量、next-open 执行、成本、资金费和关键消融；若无法复核 raw-normalized equality 或 Bybit 全史，不能提升为 paper/live candidate。

## 2026-06-28：全参数消融与时间稳定性

- 复现实验：`scripts/research_hype_6h_rs4_parameter_ablation.py`。
- 保留报告：`diagnostics/hype-6h-rs4-parameter-ablation-stability-2026-06-28.md`。
- 实验范围：`68` 个配置，包含 `1` 个基线和 `67` 个 one-at-a-time 单参数变体，覆盖组合权重、range gate、MACD、long persist、MFEu、ATR、ER、Donchian、方向限制、成本和 funding 口径。
- 基线稳定性：全样本 `+624.06%`，最大回撤 `-29.77%`；正月份 `11/14`，最差月 `-12.61%`；正 21 天窗口 `15/19`，最差 21 天 `-7.86%`。
- 负面发现：`8` 个单参数变体触发失败条件；最脆弱区域集中在 v10 range gate、ER gate、MACD slow、long persist、ER threshold 和 melt 方向限制。
- 决策：维持 `diagnostic only / not promoted`。该策略能在 Binance 近期段赚钱，但不是宽参数平台；收益更高变体多来自放松过滤或提高 melt 暴露，不能作为调参采纳依据。

## 2026-06-28：简化版 RS4 回测

- 复现实验：`scripts/research_hype_6h_rs4_simplified_backtest.py`。
- 保留报告：`diagnostics/hype-6h-rs4-simplified-backtest-2026-06-28.md`。
- 简化内容：从正式参数面移除 `first_flat_exemption` 与 `breakeven_guard`；`donchian_entry`、`donchian_exit`、`atr_window` 固定为机制常量，不再作为搜索参数。
- 回测结果：简化版全样本 `+624.48%`，最大回撤 `-29.77%`，Sharpe `3.14`，交易 `128` 笔；相对原基线收益 `+0.42pp`，回撤无变化。
- 时间片：正月份 `11/14`，最差月 `-12.61%`；正 21 天窗口 `15/19`，最差 21 天 `-7.86%`，与基线几乎等价。
- 决策：接受简化版作为后续诊断口径，但状态仍为 `diagnostic only / not promoted`；该变更只是移除死参数，不解决 Bybit 全史、完整 funding、跨交易所和 live runner 状态机审计缺口。

## 2026-06-28：主账登记 V1

- 主账：`hype-6h-rs4-regime-switch-core-ledger.md`。
- 登记版本：`HYPE-6H-RS4-Regime-Switch-V1`。
- 版本定义：采用 2026-06-28 简化版 RS4 作为后续诊断基线。
- 状态：`diagnostic only / not promoted`。
- 决策：V1 是“可复现诊断规格”，不是 paper-live/live candidate；后续任何候选升级必须先补 Bybit 全史、完整 funding、跨交易所横测和 live runner 状态机审计。
