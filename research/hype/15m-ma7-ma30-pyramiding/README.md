# HYPE-15M-MA7-MA30-Pyramiding

- Alias：`HYPE-15M-MA-PT`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，`15m`
- 机制：EMA7/EMA30 regime 内价格 reclaim EMA7 入场，浮盈后目标重置到 `3x`，比较反向交叉退出与收盘穿越 EMA7 退出。
- 当前状态：`explore / not promoted / not live-ready`

## 边界

这是独立的 `15m` 离散 campaign 家族，不是 `HYPE-1D-Pyramiding-Trend` 的版本，也不继承任何既有 HYPE 15m 家族的身份、参数结论或 promotion 状态。

## 入口

- 主账：[hype-15m-ma-pt-core-ledger.md](hype-15m-ma-pt-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结对照契约：[hype-15m-ma7-exit-comparison-contract-2026-07-30.md](specs/hype-15m-ma7-exit-comparison-contract-2026-07-30.md)
- 对照报告：[hype-15m-ma7-exit-comparison-2026-07-30.md](diagnostics/hype-15m-ma7-exit-comparison-2026-07-30.md)
- 研究脚本：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
