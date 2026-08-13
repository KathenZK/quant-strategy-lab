# HYPE-4H-MA7-RSI6-Asymmetric-Reversal

- Alias：`HYPE-4H-MA7-RSI6-AR`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `4h`
- 机制：SMA7 上方从空仓做多；多头跌破 SMA7 且最近三根 RSI6 曾 `>70` 时反手做空；空头在 RSI6 `<30` 后平仓等待。
- 防串线：不是始终持仓的 MA7 close reversal，也不是 4H MA7-ABT 的 slope / ATR reclaim 搜索。
- 当前状态：`explore / not promoted / not live-ready`；V1 原生相位盈利但相位失败；V2 Cross-Reentry 降至 `+12.16%` 且无超额，不采纳、不登记。

入口：

- [家族主账](hype-4h-ma7-rsi6-ar-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结合同](specs/hype-4h-ma7-rsi6-asymmetric-reversal-contract-2026-08-06.md)
- [基准诊断](diagnostics/hype-4h-ma7-rsi6-asymmetric-reversal-baseline-2026-08-06.md)
- [完整交易路径 HTML](artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_trade_path_2026-08-06.html)
- [V2 观察合同](specs/hype-4h-ma7-rsi6-cross-reentry-v2-observation-contract-2026-08-07.md)
- [V2 诊断](diagnostics/hype-4h-ma7-rsi6-cross-reentry-v2-observation-2026-08-07.md)
- [V2 完整交易路径 HTML](artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_trade_path_2026-08-07.html)
- [复现脚本](scripts/research_hype_4h_ma7_rsi6_asymmetric_reversal.py)
- [机器证据](artifacts/README.md)
