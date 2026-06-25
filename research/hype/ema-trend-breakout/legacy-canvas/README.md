# HYPE-EMA-TB Legacy Canvas Reports

本目录由 Cursor legacy Canvas 批量迁移生成。Markdown 是后续维护入口；原 `.canvas.tsx` 文件仅作为历史来源。
路径说明：迁移稿正文中的 `scripts/...` 等旧脚本路径保留原文语境；复现时优先检查 `archive/scripts/research/`、`src/strategy_lab/data/ingest/` 或当前家族文档索引。

冻结规则：本目录只保存从 Cursor Canvas 迁移来的历史证据，不作为新研究写入位置。新的结论应提升到对应 family 的 core ledger、`decision-log.md`、`canonical-specs/` 或 `diagnostics/`。


## 文件索引

- `hype-15m-signal-1h-confirm-backtest.md`：源 Canvas `hype-15m-signal-1h-confirm-backtest.canvas.tsx`。
- `hype-15m-signal-1h-confirm-bidirectional.md`：源 Canvas `hype-15m-signal-1h-confirm-bidirectional.canvas.tsx`。
- `hype-mtf-trend-search.md`：源 Canvas `hype-mtf-trend-search.canvas.tsx`；需人工抽查复杂组件。
- `hype-v29-adx-exit-only-backtest.md`：源 Canvas `hype-v29-adx-exit-only-backtest.canvas.tsx`。
- `hype-v2i-5m-execution-backtest.md`：源 Canvas `hype-v2i-5m-execution-backtest.canvas.tsx`。
- `hype-v2i-parameter-tuning.md`：源 Canvas `hype-v2i-parameter-tuning.canvas.tsx`。
- `hype-v2m-profit-source-analysis.md`：源 Canvas `hype-v2m-profit-source-analysis.canvas.tsx`。
- `hype-v2m-time-slice-robustness.md`：源 Canvas `hype-v2m-time-slice-robustness.canvas.tsx`。
- `hype-v2o-4h-confirmation-backtest.md`：源 Canvas `hype-v2o-4h-confirmation-backtest.canvas.tsx`。
- `hype-v2o-parameter-rescan.md`：源 Canvas `hype-v2o-parameter-rescan.canvas.tsx`。
- `hype-v2o-risk-adjusted-backtest.md`：源 Canvas `hype-v2o-risk-adjusted-backtest.canvas.tsx`。
- `hype-v2p-ablation-fitting-analysis.md`：源 Canvas `hype-v2p-ablation-fitting-analysis.canvas.tsx`。
- `hype-v2p-long-only-backtest.md`：源 Canvas `hype-v2p-long-only-backtest.canvas.tsx`。
- `hype-v2p-no-indicator-exit-analysis.md`：源 Canvas `hype-v2p-no-indicator-exit-analysis.canvas.tsx`。
- `hype-v2p-robustness-risk.md`：源 Canvas `hype-v2p-robustness-risk.canvas.tsx`。
- `hype-v2p-short-mirror-backtest.md`：源 Canvas `hype-v2p-short-mirror-backtest.canvas.tsx`。
- `hype-v2q-simplified-backtest.md`：源 Canvas `hype-v2q-simplified-backtest.canvas.tsx`。
- `hype-v2r-combined-trend-strategy.md`：源 Canvas `hype-v2r-combined-trend-strategy.canvas.tsx`。
- `hype-v2r-layered-take-profit-backtest.md`：源 Canvas `hype-v2r-layered-take-profit-backtest.canvas.tsx`。
- `hype-v2r-quality-boost-backtest.md`：源 Canvas `hype-v2r-quality-boost-backtest.canvas.tsx`。
- `hype-v2r-target-atr-scan.md`：源 Canvas `hype-v2r-target-atr-scan.canvas.tsx`。
- `hype-v2s-ablation-analysis.md`：源 Canvas `hype-v2s-ablation-analysis.canvas.tsx`。
- `hype-v2s-controlled-no-indicator-exit.md`：源 Canvas `hype-v2s-controlled-no-indicator-exit.canvas.tsx`。
- `hype-v2w-fixed-entry-atr-backtest.md`：源 Canvas `hype-v2w-fixed-entry-atr-backtest.canvas.tsx`。
- `hype-v2w-take-atr-scan.md`：源 Canvas `hype-v2w-take-atr-scan.canvas.tsx`。
- `hype-v2y-hard-stop-atr-scan.md`：源 Canvas `hype-v2y-hard-stop-atr-scan.canvas.tsx`。
- `hype-v2z-ablation-analysis.md`：源 Canvas `hype-v2z-ablation-analysis.canvas.tsx`。
- `hype-v2z-hyperliquid-okx-backtest.md`：源 Canvas `hype-v2z-hyperliquid-okx-backtest.canvas.tsx`。
- `hype-v2z-remove-di-ddscale-backtest.md`：源 Canvas `hype-v2z-remove-di-ddscale-backtest.canvas.tsx`。
- `hype-v30-aligned-exchange-backtest.md`：源 Canvas `hype-v30-aligned-exchange-backtest.canvas.tsx`。
- `hype-v30-binance-signal-hl-execution.md`：源 Canvas `hype-v30-binance-signal-hl-execution.canvas.tsx`。
- `hype-v30-delayed-execution-modes.md`：源 Canvas `hype-v30-delayed-execution-modes.canvas.tsx`。
- `hype-v30-full-legacy-close-sensitivity.md`：源 Canvas `hype-v30-full-legacy-close-sensitivity.canvas.tsx`。
- `hype-v30-hyperliquid-backtest.md`：源 Canvas `hype-v30-hyperliquid-backtest.canvas.tsx`。
- `hype-v30-k1-open-close-comparison.md`：源 Canvas `hype-v30-k1-open-close-comparison.canvas.tsx`。
- `hype-v30-k2-open-5-9-cross-exchange.md`：源 Canvas `hype-v30-k2-open-5-9-cross-exchange.canvas.tsx`。
- `hype-v30-k2-open-wider-stop-take-scan.md`：源 Canvas `hype-v30-k2-open-wider-stop-take-scan.canvas.tsx`。
- `hype-v30-lag-audit.md`：源 Canvas `hype-v30-lag-audit.canvas.tsx`。
- `hype-v30-mfe-disable-scan.md`：源 Canvas `hype-v30-mfe-disable-scan.canvas.tsx`。
- `hype-v30-next-open-wider-stop-take-scan.md`：源 Canvas `hype-v30-next-open-wider-stop-take-scan.canvas.tsx`。
- `hype-v30-okx-backtest.md`：源 Canvas `hype-v30-okx-backtest.canvas.tsx`。
- `hype-v30-wait-bars-scan-5-9.md`：源 Canvas `hype-v30-wait-bars-scan-5-9.canvas.tsx`。
- `hype-v31-full-parameter-ablation.md`：源 Canvas `hype-v31-full-parameter-ablation.canvas.tsx`。
- `hype-v31-no-cooldown-validation.md`：源 Canvas `hype-v31-no-cooldown-validation.canvas.tsx`。
- `hype-v32-k1-open-comparison.md`：源 Canvas `hype-v32-k1-open-comparison.canvas.tsx`。
- `hype-v32-live-realistic-backtest.md`：源 Canvas `hype-v32-live-realistic-backtest.canvas.tsx`。
- `hype-v32-mfe1-stop8-ablation.md`：源 Canvas `hype-v32-mfe1-stop8-ablation.canvas.tsx`。
- `hype-v32-no-1h-confirm-ablation.md`：源 Canvas `hype-v32-no-1h-confirm-ablation.canvas.tsx`。
- `hype-v33-balanced-combo-backtest.md`：源 Canvas `hype-v33-balanced-combo-backtest.canvas.tsx`。
- `hype-v33-full-parameter-ablation.md`：源 Canvas `hype-v33-full-parameter-ablation.canvas.tsx`。
- `hype-v34-let-profits-run-ablation.md`：源 Canvas `hype-v34-let-profits-run-ablation.canvas.tsx`。
- `hype-v35-early-long-satellite.md`：源 Canvas `hype-v35-early-long-satellite.canvas.tsx`；需人工抽查复杂组件。
- `hype-v35-early-short-satellite.md`：源 Canvas `hype-v35-early-short-satellite.canvas.tsx`；需人工抽查复杂组件。
- `hype-v35-final-parameter-ablation.md`：源 Canvas `hype-v35-final-parameter-ablation.canvas.tsx`；需人工抽查复杂组件。
- `hype-v35-indicator-exit-reverse-ablation.md`：源 Canvas `hype-v35-indicator-exit-reverse-ablation.canvas.tsx`。
- `hype-v35-live-execution-audit.md`：源 Canvas `hype-v35-live-execution-audit.canvas.tsx`；需人工抽查复杂组件。
- `hype-v35-nearmiss-relaxation-backtest.md`：源 Canvas `hype-v35-nearmiss-relaxation-backtest.canvas.tsx`；需人工抽查复杂组件。
- `hype-v35-no-mfe-disable-ablation.md`：源 Canvas `hype-v35-no-mfe-disable-ablation.canvas.tsx`。
- `hype-v35-original-long-short-drawdown.md`：源 Canvas `hype-v35-original-long-short-drawdown.canvas.tsx`；需人工抽查复杂组件。
- `hype-v35-retrace-exit-param-scan.md`：源 Canvas `hype-v35-retrace-exit-param-scan.canvas.tsx`。
- `hype-v35-stop-reverse-ablation.md`：源 Canvas `hype-v35-stop-reverse-ablation.canvas.tsx`。
- `hype-v35-take-profit-roll-backtest.md`：源 Canvas `hype-v35-take-profit-roll-backtest.canvas.tsx`；需人工抽查复杂组件。
- `hype-v35-tp-roll-reinvest-backtest.md`：源 Canvas `hype-v35-tp-roll-reinvest-backtest.canvas.tsx`。
- `hype-v35-winrate-loss-profile.md`：源 Canvas `hype-v35-winrate-loss-profile.canvas.tsx`；需人工抽查复杂组件。
- `hype-v36-binance-signal-hl-execution.md`：源 Canvas `hype-v36-binance-signal-hl-execution.canvas.tsx`。
- `hyperliquid-v2m-backtest.md`：源 Canvas `hyperliquid-v2m-backtest.canvas.tsx`。
- `trend-confirmation-backtest.md`：源 Canvas `trend-confirmation-backtest.canvas.tsx`。
