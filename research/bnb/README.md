# BNB Research Index

本目录存放 BNB 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。

## 当前研究线

- `BNB-1H-Adaptive-Regime`（`BNB-1H-AR`）：Binance USD-M Futures `BNBUSDT` perpetual `1h` 多指标自适应 regime 广泛搜索；`BNB-1H-Adaptive-Regime-V1` 已登记为 `ema_pullback+wick_reject` diagnostic observation；`BNB-1H-Adaptive-Regime-V2` 已登记为 V1 clean-equivalent 版本并完成多窗口验证、V2 全参数消融和微调（tuned observation full `2.94x / -18.24% / 88.33%`，reused OOS 二次读取）；locked OOS 未通过，当前为 `NO-GO / not promoted / not live-ready`。
- `BNB-15M-Adaptive-Regime`（`BNB-15M-AR`）：Binance USD-M Futures `BNBUSDT` perpetual `15m` BNB 专属趋势延续、波动压缩突破、结构修复与 regime 过滤研究；当前为 `active diagnostic research / not promoted / not live-ready`。

## 数据与执行口径

BNB 合约研究默认遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成本/延迟压力、参数邻域、清算边界和生产状态机审计，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
