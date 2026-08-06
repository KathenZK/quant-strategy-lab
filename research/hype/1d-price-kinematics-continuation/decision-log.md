# Decision Log

## 2026-08-03：冻结独立日线纯价格运动学诊断

将真正的完整 UTC 日 K 状态与既有 `HYPE-1H-PKC` 的小时观察/日级标签分开；结果揭示前固定过去 `3d/7d/14d`、未来 `3d/7d/14d`、Long/Short 分离、14 日 block bootstrap 和 prospective OOS。证据见[冻结合同](specs/hype-1d-pkc-initial-research-contract-2026-08-03.md)。

## 2026-08-03：日线呈现局部做多排序，但稳定规律与统计功效均未通过

Long Validation 的日级排序明显强于短周期，但 Train/Validation 阶段翻转、结构特征与独立 14 日块不足；Short 的绝对延续失败。因此不设计交易策略、不读取 prospective OOS。证据见[初始验证](diagnostics/hype-1d-pkc-initial-research-2026-08-03.md)。
