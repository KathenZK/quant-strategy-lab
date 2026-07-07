# BNB Research Index

本目录存放 BNB 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。版本级指标与证据以各家族 core ledger 为唯一事实源。

## 当前研究线

- `BNB-1H-Adaptive-Regime`（`BNB-1H-AR`）：`1h-adaptive-regime/`。Binance USD-M Futures `BNBUSDT` perpetual `1h` 多指标自适应 regime 广搜；V1-V3 已登记；当前 `NO-GO / not promoted / not live-ready`。主账：`1h-adaptive-regime/bnb-1h-ar-core-ledger.md`。
- `BNB-15M-Adaptive-Regime`（`BNB-15M-AR`）：`15m-adaptive-regime/`。Binance USD-M Futures `BNBUSDT` perpetual `15m` BNB 专属趋势延续、波动压缩突破、结构修复与 regime 过滤研究；当前 `active diagnostic research / not promoted / not live-ready`。主账：`15m-adaptive-regime/bnb-15m-ar-core-ledger.md`。

## 数据与执行口径

BNB 合约研究默认遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成本/延迟压力、参数邻域、清算边界和生产状态机审计，不得标记为 candidate、dry-run、handoff 或 live。状态词定义见 `../strategy-status-glossary.md`。
