# Canvas 研究资产目录

Canvas 根目录：

`/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/`

不要移动 `.canvas.tsx` 文件本体；Cursor 只识别这个目录下的扁平 Canvas 文件。本页只做完整文件名对账；按主题拆分的入口见 `canvas-groups/README.md`。

## 核心台账

- [hype-trend-strategy-research.canvas.tsx](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-trend-strategy-research.canvas.tsx)：HYPE 趋势策略研究总台账。
- [hype-strategy-milestone-comparison.canvas.tsx](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-strategy-milestone-comparison.canvas.tsx)：HYPE 15m 里程碑对比总表。

## HYPE EMA 金叉死叉族

- [hype-ema-crossover-evolution.canvas.tsx](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-ema-crossover-evolution.canvas.tsx)：HYPE-EMA-X 主台账，当前 promoted versions 为 V15 高胜率/低回撤版与 V16 高收益版。

## HYPE 趋势突破族

- `hype-v2i-parameter-tuning.canvas.tsx`
- `hype-v2i-5m-execution-backtest.canvas.tsx`
- `hype-v2m-profit-source-analysis.canvas.tsx`
- `hype-v2m-time-slice-robustness.canvas.tsx`
- `hype-v2o-parameter-rescan.canvas.tsx`
- `hype-v2o-4h-confirmation-backtest.canvas.tsx`
- `hype-v2o-risk-adjusted-backtest.canvas.tsx`
- `hype-v2p-ablation-fitting-analysis.canvas.tsx`
- `hype-v2p-no-indicator-exit-analysis.canvas.tsx`
- `hype-v2p-long-only-backtest.canvas.tsx`
- `hype-v2p-short-mirror-backtest.canvas.tsx`
- `hype-v2p-robustness-risk.canvas.tsx`
- `hype-v2q-simplified-backtest.canvas.tsx`
- `hype-v2r-combined-trend-strategy.canvas.tsx`
- `hype-v2r-layered-take-profit-backtest.canvas.tsx`
- `hype-v2r-quality-boost-backtest.canvas.tsx`
- `hype-v2r-target-atr-scan.canvas.tsx`
- `hype-v2s-ablation-analysis.canvas.tsx`
- `hype-v2s-controlled-no-indicator-exit.canvas.tsx`
- `hype-v2w-fixed-entry-atr-backtest.canvas.tsx`
- `hype-v2w-take-atr-scan.canvas.tsx`
- `hype-v2y-hard-stop-atr-scan.canvas.tsx`
- `hype-v2z-ablation-analysis.canvas.tsx`
- `hype-v2z-hyperliquid-okx-backtest.canvas.tsx`
- `hype-v2z-remove-di-ddscale-backtest.canvas.tsx`
- `hype-v29-adx-exit-only-backtest.canvas.tsx`
- `hype-v30-aligned-exchange-backtest.canvas.tsx`
- `hype-v30-binance-signal-hl-execution.canvas.tsx`
- `hype-v30-delayed-execution-modes.canvas.tsx`
- `hype-v30-full-legacy-close-sensitivity.canvas.tsx`
- `hype-v30-hyperliquid-backtest.canvas.tsx`
- `hype-v30-k1-open-close-comparison.canvas.tsx`
- `hype-v30-k2-open-5-9-cross-exchange.canvas.tsx`
- `hype-v30-k2-open-wider-stop-take-scan.canvas.tsx`
- `hype-v30-lag-audit.canvas.tsx`
- `hype-v30-mfe-disable-scan.canvas.tsx`
- `hype-v30-next-open-wider-stop-take-scan.canvas.tsx`
- `hype-v30-okx-backtest.canvas.tsx`
- `hype-v30-wait-bars-scan-5-9.canvas.tsx`
- `hype-v31-full-parameter-ablation.canvas.tsx`
- `hype-v31-no-cooldown-validation.canvas.tsx`
- `hype-v32-k1-open-comparison.canvas.tsx`
- `hype-v32-live-realistic-backtest.canvas.tsx`
- `hype-v32-mfe1-stop8-ablation.canvas.tsx`
- `hype-v32-no-1h-confirm-ablation.canvas.tsx`
- `hype-v33-balanced-combo-backtest.canvas.tsx`
- `hype-v33-full-parameter-ablation.canvas.tsx`
- `hype-v34-let-profits-run-ablation.canvas.tsx`
- `hype-v35-cross-exchange-execution.canvas.tsx`
- `hype-v36-binance-signal-hl-execution.canvas.tsx`
- `hype-15m-signal-1h-confirm-backtest.canvas.tsx`
- `hype-15m-signal-1h-confirm-bidirectional.canvas.tsx`
- `hype-mtf-trend-search.canvas.tsx`
- `trend-confirmation-backtest.canvas.tsx`
- `hyperliquid-v2m-backtest.canvas.tsx`

## HYPE K 线计数反转族

- `hype-strategy-rationale.canvas.tsx`
- `hype-15m-optimization.canvas.tsx`
- `hype-adx-parameter-search.canvas.tsx`
- `hype-atr-trend-optimization.canvas.tsx`
- `hype-hyperliquid-fee-backtest.canvas.tsx`
- `hype-mark-dd20-risk.canvas.tsx`
- `hype-risk-control-analysis.canvas.tsx`
- `hype-v10-atr-window-comparison.canvas.tsx`
- `hype-v12-bidirectional-opposite-exit-backtest.canvas.tsx`
- `hype-v13-parameter-robustness.canvas.tsx`
- `hyperliquid-hype-v13-v15-v18.canvas.tsx`
- `hype-v18-param-review.canvas.tsx`
- `hype-v18-v21-updated-data-backtest.canvas.tsx`
- `hype-v21-misfire-reduction-variants.canvas.tsx`
- `hype-v21-robustness-validation.canvas.tsx`
- `hype-v21-time-sensitivity.canvas.tsx`
- `hype-v24-10ofn-sensitivity.canvas.tsx`
- `hype-v24-param-microsearch.canvas.tsx`
- `hype-recent-v18-v21-v24-v26-backtest.canvas.tsx`
- `hype-v26-v28-optimization.canvas.tsx`
- `v29-full-parameter-diagnosis.canvas.tsx`
- `v29-overfit-diagnosis.canvas.tsx`
- `v30-overfit-diagnosis.canvas.tsx`
- `v35-overfit-diagnosis.canvas.tsx`

## 跨品种与迁移验证

- `btc-hourly-trend-research.canvas.tsx`
- `btc-rsi-mean-reversion-validation.canvas.tsx`
- `btc-v2a-keltner-adx-backtest.canvas.tsx`
- `btc-v2r-migration-backtest.canvas.tsx`
- `btc-v2r-tweak-search.canvas.tsx`
- `btc-v4-atr-take-backtest.canvas.tsx`
- `btc-v13-parameter-research.canvas.tsx`
- `cmc-top50-v13-v18-comparison.canvas.tsx`
- `xmr-v13-3y-robustness.canvas.tsx`
- `xmr-v13-drawdown-mitigation.canvas.tsx`

## Minara / 外部策略研究

- `minara-21-approx-backtest-results.canvas.tsx`
- `minara-21-strategies-summary.canvas.tsx`
- `minara-five-adapted-strategies.canvas.tsx`
- `minara-rsi2065-btc-hype-backtest.canvas.tsx`
- `minara-tradingview-scripts-found.canvas.tsx`

## 平台策略与其他实验

- `cta-trend-grid-results.canvas.tsx`
- `spot-cta-diagnosis.canvas.tsx`
- `spot-trend-param-scan.canvas.tsx`
