# Asset Portfolios Research Index

本目录存放组合策略、跨资产策略、迁移研究和多 sleeve 资金结构研究。当前材料主要基于 Binance USD-M Futures 市场数据；若某个研究线后续变成单一资产策略家族，应迁入对应资产目录并保留这里的交叉引用。状态词定义见 [strategy-status-glossary.md](../../docs/research-governance/strategy-status-glossary.md)。

## 当前研究线

- `Binance-1H-Cross-Sectional-LightGBM-Selector`（`BIN-1H-CSLGBM`）：[1h-cross-sectional-lightgbm-selector/](1h-cross-sectional-lightgbm-selector/README.md)。Binance USD-M 历史动态币池、横截面因子与 LightGBM regression/classification/ranking selector；旧绩效因空头公式错误全部撤销，`HARD-GATE-FAILED / registered / not promoted / not live-ready`。
- `Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator`（`BIN-1H-MHCSML`）：[1h-multi-horizon-cross-sectional-ml-allocator/](1h-multi-horizon-cross-sectional-ml-allocator/README.md)。分离 long/short/tail-risk 模型、多期限预测与允许空仓的风险效用 allocator；`V1 registered / prospective OOS active / not promoted / not live-ready`。主账：[binance-1h-mhcsml-core-ledger.md](1h-multi-horizon-cross-sectional-ml-allocator/binance-1h-mhcsml-core-ledger.md)。
- `Binance-1D-Turtle-Breakout`：[1d-turtle-breakout/](1d-turtle-breakout/README.md)。BTC/ETH/HYPE 日线 20/10 turtle breakout 诊断；`explore`。
- `Binance-15M-Multi-Indicator-Intraday-Transfer`：[15m-multi-indicator-intraday/](15m-multi-indicator-intraday/README.md)。基于 `HYPE-15M-MII-V1.1` 机制的 BTC/ETH `15m` 受约束参数迁移诊断；`explore / not promoted`。
- `Binance-15M-Asset-Specific-Six-Strategy-Selector`（`BIN-15M-AS6S`）：[15m-asset-specific-six-strategy-selector/](15m-asset-specific-six-strategy-selector/README.md)。V1 为九腿历史基线；V6 NP/SBP 两条冻结路线已启用持续 `dry-run`，未来三个月 OOS 仍锁定，live disabled。主账：[binance-15m-as6s-core-ledger.md](15m-asset-specific-six-strategy-selector/binance-15m-as6s-core-ledger.md)。
- `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`（`BIN-1H-AR-MAE`）：[1h-adaptive-regime-multi-asset-ensemble/](1h-adaptive-regime-multi-asset-ensemble/README.md)。六个 `1h` adaptive-regime 家族登记版本的跨资产组合；V1 已登记并启用 `dry-run`，strict replay parity PASS，live disabled。主账：[binance-1h-ar-mae-core-ledger.md](1h-adaptive-regime-multi-asset-ensemble/binance-1h-ar-mae-core-ledger.md)。
- `Binance-1H-Multi-Leg-Six-Asset-Selector`（`BIN-1H-ML6AS`）：[1h-multi-leg-six-asset-selector/](1h-multi-leg-six-asset-selector/README.md)。BTC/ETH/SOL/BNB/TRX/HYPE 三交易臂、币内融合与抢占/非抢占全局单仓研究；`explore / not promoted / not live-ready`。主账：[binance-1h-ml6as-core-ledger.md](1h-multi-leg-six-asset-selector/binance-1h-ml6as-core-ledger.md)。
- `Binance-MK7-Multi-Strategy-Account`（外部别名 `mk7`）：[mk7-multi-strategy-account/](mk7-multi-strategy-account/README.md)。六币 `1h` + HYPE K2FQ + HYPE MII 双槽共享账户的外部规格复现审计；全窗 LSR 已补齐，回测接近但未逐笔对齐，回测终点后 10.875 天 forward 基本持平；状态 `explore / not promoted / not live-ready`。
- `HYPE-Cross-Strategy-Account`：[hype-cross-strategy-account/](hype-cross-strategy-account/README.md)。HYPE 单资产多策略共享子账户、全局单仓、跨策略优先级和账户级风控诊断；`explore`，不提升任何子策略状态。
