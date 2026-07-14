# SOL-4H-RS4-Regime-Switch Decision Log

## 2026-07-13：建立独立 SOL 4h RS4 family

- 按新机制优先级迁移 HYPE-RS4 的显式压缩/扩张 router，但建立独立 `SOL-4H-RS4-Regime-Switch` family，不继承任何旧版本。
- 使用 2026-07-13 刷新的 SOL 最近两年 `1h` 标准数据，聚合为 `4379` 根完整 `4h` K；missing、duplicate、row-count、OHLC violations 均为 `0`。
- 成本改为仓库 Binance 默认：fee `0.001`/fill、slippage `4 bps`/fill，并计真实 funding。
- 搜索限制为 `401` 个预定义/随机小矩阵规格，不再采用十万级同构广搜。

## 2026-07-13：首轮 NO-GO

- `401` 个规格中 base-gate pass `0`，`10x / 80% / <20% DD` hard pass `0`。
- 最好失败观察 `SOL_4H_RS4_R0343`：prefit annual `1.2045x`、DD `-26.58%`；reused holdout return `-23.04%`、DD `-34.13%`；current full annual `1.0312x`、DD `-47.97%`。
- fresh forward 约 10 天 `+2.24%`、3 笔，样本太短，不能覆盖 reused-holdout 与 full 失败。
- K+2 full DD `-48.99%`；成本翻倍 full annual `0.7013x`、DD `-59.21%`。
- 当前模型没有交易所驻留 intrabar protection stop；即使收益改善也不能 promotion。
- 决策：`NO-GO / explore / not promoted / not live-ready`；不登记 V1，不继续同结构参数搜索。

