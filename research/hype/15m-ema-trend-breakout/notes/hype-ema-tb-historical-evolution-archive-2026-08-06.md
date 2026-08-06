# HYPE-EMA-TB 历史演化归档

本文承接主账压缩前的 V1/V2 与 V29–V34 长叙事。当前登记版本、状态和关键指标以 core ledger 为准；具体参数以 specs/diagnostics/artifacts 为准。

## V1：趋势回踩

- V1A 在两日上涨趋势中买 12h 急跌，ATR672 动态仓位，6ATR TP/SL、最长约 48h；低回撤主线全样本 `+160.94%`、DD `-12.77%`。
- V1B 加入空头，收益略增但 DD 扩至约 `-24.33%`，说明空头扩展并非免费。
- V1 机制与后来的 EMA 突破主线不同，只保留历史家族演化，不作为 V35 回退候选。

## V2A–V2P：从高周期突破到 15m 双向

- V2A 用 1h Keltner/ADX/volume 与 4h DI 确认，收益低于 V1 但 DD 约 `-7.09%`，建立纯趋势突破方向。
- V2B SuperTrend 样本更多但收益/回撤弱于 V2A；V2C 严格空头未优于 long-only。
- V2D 提高 3x cap 只放大收益与回撤；V2E BTC 直接迁移失败，证明参数不能跨资产继承。
- V2F 放宽过滤提高频率与收益，但 DD 超过低回撤目标。
- V2G/H/I 把信号下沉到 15m 并扩双向；交易增多但噪音和 DD 上升。V2J 改 5m execution 后收益下降且 DD 扩大。
- V2K 是 V2I 周边均衡版；V2L 为高收益版；V2M 对称化空头 sizing 后收益提高但 DD 接近 20%。
- V2N 去 volume filter 后收益明显下降，确认成交量过滤有效。
- V2O 在回撤期降仓并提高 ADX exit，保留收益且 DD 约从 19.6% 降至 14.7%。
- V2P 参数重扫提高收益，但 train 弱于 V2O，只能作为候选。

## V2Q–V2Z：精简、利润奔跑与固定 bracket

- V2Q 精简空头参数，收益略升但 DD 扩大。
- V2R 去 Keltner、保留 EMA/ADX/DI/volume/1h confirm 后收益显著提高，但对 target ATR 与开关敏感。
- V2S 将指标退出延迟 3 根，收益提高但认错更慢；V2T 在 MFE≥2ATR 后关闭指标退出，让利润奔跑。
- V2U 删除 EMA exit 与 V2T 等价；V2V 把 ADX exit 提到 22 后收益提升；V2W 删除冗余 EMA96 slope，结果近似等价。
- V2X 固定 entry ATR `TP4.3/SL12` 更贴近实盘；V2Y 删除历史 0 次触发的 trailing，与 V2X 等价。
- V2Z 将 SL12 收紧到 SL9，收益 `+1436.46%`、DD `-15.28%`，成为当时高收益低回撤候选。

## V29–V34：可执行时序

- V29 去 DI 入场和回撤降仓，与 V2Z 收益近似但风险略差；V30 去 DI 反向退出，只保留 ADX22 delayed3，收益 `+2188.01%`。
- V31 改为 K0 signal、完整等待 K1、K2 open 入场并 TP5；Binance `+926.89%`、DD `-28.60%`，HL/OKX 同向为正。
- V32 去 cooldown 后 Binance `+4001.27%`，但依赖短间隔连续重入。
- V33 修正 live-realistic 顺序：K2 open、上一根 ATR sizing、指标/timeout 收盘确认后 next-open、禁止同 K 回到 open 重入；成为后续消融基准。
- V34 在 V33 上用 long/short target `0.020/0.018`、MFE1.5 关闭指标退出和 SL7；Binance `+5840.03%`、DD `-23.89%`，跨所方向不完全一致。

## V35 以后研究教训

- V35 放宽 timeout 至 384；样本内 timeout 0 次，身份仍有意义，因为 live 数据可能触发。
- V35A/B indicator-exit 反手提高样本内收益，但样本少且 ping-pong 风险高，不应自动覆盖主线。
- V36 跨所执行保留约 86% 同窗收益并降低 Binance 闪崩插针风险，但信号/成交双源增加 basis 与 operational risk。
- V37 early-long satellite 提高组合收益，但卫星只有约 38–40 笔；V38 近 TP floor 降低收益且不改善 DD，明确否决。
- V39–V41 的参数微调和风险撤回不改变 promotion 规则；等价重编号不提供新增验证。

## 证据入口

- [V35 spec](../specs/hype-trend-strategy-v35-spec.md)
- [V35.1 promotion review](../diagnostics/hype-ema-tb-v35-1-dry-run-promotion-review-2026-07-20.md)
- [V35.3 asymmetric stop](../diagnostics/hype-ema-tb-v35-3-asymmetric-stop-backtest-2026-07-20.md)
- [V39 full ablation](hype-ema-tb-v35-full-ablation-recent-tune-2026-07-08.md)
- [V35/V39 near-TP floor](hype-ema-tb-v35-v39-near-tp-floor-diagnostic-2026-07-14.md)
- [runner reconciliation](../runner-tracking/hype-ema-tb-v35-post-freeze-live-parity-2026-07-22.md)
