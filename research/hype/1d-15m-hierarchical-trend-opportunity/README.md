# HYPE-1D-15M-Hierarchical-Trend-Opportunity

- Alias：`HYPE-D15-HTO`
- 市场：Binance USD-M Futures `HYPEUSDT`
- 周期：完整 UTC 日线确定方向，`15m` 闭合 K 线寻找入场与管理仓位
- 机制：只读取前一完整 UTC 日的趋势状态；日线方向允许后，`15m` 通过突破、回踩恢复、动量扩张或均线延续寻找机会。
- 当前状态：V1-V3 `registered / not promoted / not live-ready`

这是独立家族，不继承 `HYPE-15M-MMTF`、`HYPE-1D-PT`、`HYPE-EMA-TB` 或其他 HYPE 家族的版本、参数、指标组合和研究结论；只复用标准数据湖、数据质量与实盘撮合口径。

## 入口

- [主账](hype-d15-hto-core-ledger.md)
- [决策记录](decision-log.md)
- [最终研究决策](diagnostics/hype-d15-hto-final-decision-2026-07-29.md)
- [V3 冻结规格](specs/hype-d15-hto-v3-spec.md)
- [脚本说明](scripts/README.md)
- [产物说明](artifacts/README.md)
