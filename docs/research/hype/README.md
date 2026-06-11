# HYPE 研究索引

HYPE 研究以两个 Canvas 为最高优先级入口，Markdown 文档用于复现参数、实盘交付、诊断和历史规格留档。

## 核心 Canvas

- [HYPE 趋势策略研究](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-trend-strategy-research.canvas.tsx)：趋势突破族版本台账、胜率排名、参数矩阵和研究结论。
- [HYPE 15m Strategy Milestone Comparison](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-strategy-milestone-comparison.canvas.tsx)：K 线计数反转族里程碑对比、分窗口回测和版本结论。
- `canvases/README.md`：Canvas 研究资产分类入口。
- `canvas-catalog.md`：100 个 Canvas 文件名完整对账目录。

## 趋势突破族

目录：`trend-breakout/`

这条线是 15m EMA96/384 趋势突破 + ADX / 量能 / 1h 确认，后续演进到 live-realistic 与跨所执行。

- `trend-breakout/hype-v2p-strategy-spec.md`：V2P 早期趋势突破候选。
- `trend-breakout/hype-trend-strategy-v30-spec.md`：V30 趋势族基线。
- `trend-breakout/hype-trend-strategy-v34-spec.md`：V34 高收益低回撤组合。
- `trend-breakout/hype-trend-strategy-v35-spec.md`：V35 放宽 timeout。
- `trend-breakout/hype-trend-strategy-v36-spec.md`：V36 Binance 信号 + Hyperliquid 执行。

## K 线计数反转族

目录：`candle-count/`

这条线是 10 根 K 中 8 根同色反转 + ATR 风控 + 多层提前退出。注意它的 V 编号与趋势突破族会撞号，引用时必须带策略族。

- `candle-count/hype-v10-atr-dynamic-stop-strategy-spec.md`：V10 ATR 动态止损规格。
- `candle-count/hype-v10-v13-rust-backtest-baseline.md`：V10 / V13 Rust 对账基准。
- `candle-count/hype-v13-strategy-spec.md`：V13 全 ATR288 规格。
- `candle-count/hype-v18-atr672-strategy-spec.md`：V18 ATR672 稳健基线。
- `candle-count/hype-v19-long-opposite-three-exit-strategy-spec.md`：V19 多单三阴提前平仓。
- `candle-count/hype-v20-inclusive-opposite-three-exit-strategy-spec.md`：V20 含开仓 K 三反向提前平仓。
- `candle-count/hype-v21-bidirectional-opposite-three-exit-strategy-spec.md`：V21 双向三反向提前平仓。
- `candle-count/hype-v21-reproducible-params.md`：V21 复现参数。
- `candle-count/hype-v26-reproducible-params.md`：V26 复现参数。
- `candle-count/hype-v29-reproducible-params.md`：V29 复现参数。
- `candle-count/hype-v35-reproducible-params.md`：V35 复现参数。
- `candle-count/hype-v35-overfit-diagnosis.md`：V35 过拟合诊断。

## 编号注意

- 趋势突破族的 V30 / V35 / V36 与 K 线计数反转族的 V30 / V35 / V36 不是同一条策略线。
- 趋势突破族文档文件名包含 `hype-trend-strategy-*`。
- K 线计数反转族文档文件名多为 `hype-v*-*`。
