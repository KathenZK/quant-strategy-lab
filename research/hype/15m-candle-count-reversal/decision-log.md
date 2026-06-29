# HYPE-CC 决策日志

这是 HYPE candle-count reversal 研究的家族级阅读路径。

## 当前边界

- 本家族属于策略规格与归档材料。
- 它不是 active package code 的事实来源。
- 需要复现逻辑时，应使用 canonical specs 在一次性脚本或生产 runner 中重建。

## 版本记录

- `HYPE-CC-V10`：ATR dynamic stop 基线。
- `HYPE-CC-V13`：全 ATR288 双向限价规格。
- `HYPE-CC-V18`：ATR672 稳健基线。
- `HYPE-CC-V19`：仅多头 three-opposite-candle early exit。
- `HYPE-CC-V20`：inclusive opposite-three exit 变体。
- `HYPE-CC-V21`：双向 opposite-three exit 变体。
- `HYPE-CC-V35`：可复现性与过拟合诊断检查点。

## 决策记录

- `2026-06-29`：`diagnostics/hype-cc-v35-live-underperformance-review-2026-06-29.md` 在 Binance live 表现不佳和 6 月 OHLCV-proxy OOS replay 后，将 `HYPE-CC-V35` 下调为 live-underperformance / execution-risk diagnostic。当前归因优先级是策略 / 行情样本外亏损，其次是实盘成交摩擦放大；代码或状态机问题需要逐笔审计后才能确认。在补齐 2026-06-01 之后 mark-price replay 和逐笔交易执行审计前，不要把 `+8357.56%` 或 `58.53%` 胜率作为 live expectation 引用。

## 证据政策

优先使用家族文档，而不是 archived code。如果代码与文档不一致，先引用文档，再通过重新生成一次性回测进行验证。
