# Binance BTC/ETH 1D Log-Ratio Mean-Reversion

- 标准家族名：`Binance-1D-BTCETH-Log-Ratio-Mean-Reversion`
- 短 id：`BIN-1D-BE-LRMR`
- 状态：`explore / research line closed / HARD-GATE-FAILED / not promoted / not live-ready`
- 当前版本：无
- 机制：BTC/ETH log price ratio 的日频均值回归；两腿同时成交、初始各 `0.5x`、总毛杠杆 `1x`
- 数据：Binance USDⓈ-M BTCUSDT/ETHUSDT `1h` 与真实 funding，聚合闭合 UTC 日信号
- 目标：development 净值 `>=20x`、conservative ordered `1h` MDD `<=20%`，再进入唯一候选审计

阅读顺序：[P0 冻结合同](specs/binance-1d-be-lrmr-p0-contract-2026-08-12.md) → [主账](binance-1d-be-lrmr-core-ledger.md) → [决策日志](decision-log.md)。

本家族不是 MA7 V2，也不是 RCR 后续版本；它以双腿相对价值替代单腿方向预测。P0 `15,288` 配置最高仅 `1.5471x/-44.88% ordered MDD`，当前研究线已关闭。
