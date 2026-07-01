# Binance-15M-MII-Transfer 决策日志

这是 Binance USD-M Futures `BTCUSDT`、`ETHUSDT` `15m` multi-indicator intraday 迁移诊断的决策记录。

## 决策

- `2026-06-30`：创建独立跨资产迁移研究线 `Binance-15M-Multi-Indicator-Intraday-Transfer`，不把 BTC/ETH 参数写入 HYPE 家族版本号。原因是 BTC/ETH 不是 HYPE 专属策略家族，参数微调只能说明迁移诊断，不代表 `HYPE-15M-MII` 版本演进。
- `2026-06-30`：使用 `HYPE-15M-MII-V1.1` 同一机制做受约束微调搜索：保留 RSI 反转、MACD 方向过滤、ATR/RVOL、固定 TP/SL/hold、下一根 open 入场、K+2 延迟压力和 Binance 成本；只缩放 BTC/ETH 更小波动相关参数。固定 `1x` 暴露，避免靠杠杆制造收益。
- `2026-06-30`：搜索 `69,122` 个 asset-config 行。BTC 找到 K+1/K+2 同时为正的低收益诊断版，代表为 `btceth_mii_rsi9_35_60_long_atrmin35_rvol1_tp90_sl240_hold8_x1`：K+1 总收益 `2.99%`、回撤 `-3.46%`、`31` 笔；K+2 总收益 `2.24%`、回撤 `-4.03%`、`31` 笔。收益太薄，最近 30 天 K+2 为负，不提升。
- `2026-06-30`：ETH 未找到 K+1/K+2 同时为正的稳健迁移版本。K+1-only 代表为 `btceth_mii_rsi9_40_60_short_atrmin45_rvol1_tp75_sl240_hold24_x1`：K+1 总收益 `6.63%`、回撤 `-5.99%`、胜率 `82.81%`、`64` 笔；但 K+2 总收益 `-11.11%`、回撤 `-17.13%`。该配置只可作为延迟敏感性诊断，不提升。

## 状态

当前结论：`diagnostic only / not live-ready / not paper-live-ready`。后续若继续推进，必须补标准 raw/normalized 数据湖复验、资金费、参数邻域、更多窗口、真实订单滑点和 runner 可复现审计。
