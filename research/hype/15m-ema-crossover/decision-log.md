# HYPE-EMA-X 决策日志

这是 HYPE EMA golden/death cross 研究的家族级阅读路径。

## 当前边界

- 这是本仓库四个核心研究方向之一。
- 它通过仓库 Markdown ledgers 和 archived scripts 保留，而不是通过打磨后的 canonical specs 保留。
- 不应把它视为已经失败的浅层尝试。
- 不应将它合并进 `HYPE-EMA-TB`。

## 版本记录

- `HYPE-EMA-X-V2/V4`：早期 EMA cross comparisons。
- `HYPE-EMA-X-V5`：regime-hold variant。
- `HYPE-EMA-X-V7`：volume exhaustion。
- `HYPE-EMA-X-V8`：volume overlay。
- `HYPE-EMA-X-V9`：higher-timeframe RSI exit。
- `HYPE-EMA-X-V10`：oscillator top exit。
- `HYPE-EMA-X-V11`：trade-path diagnostics。
- `HYPE-EMA-X-V12`：state-machine variants。
- `HYPE-EMA-X-V13`：late re-entry and missed-trend diagnostics。
- `HYPE-EMA-X-V14`：main late-entry/backfill/ablation checkpoint。
- `HYPE-EMA-X-V15`：已提升的 high-win-rate / low-drawdown candidate。Source search row：`V17_atr18_trend7_base_age384_d075_pnlm03_either2_stop8`。Metrics：`+2303.65% / -17.79% / 90.32% / 31 trades`。
- `HYPE-EMA-X-V16`：已提升的 high-return candidate。Source search row：`V17_atr18_base_age384_pnlm03_either2_stop8`。Metrics：`+3202.92% / -28.19% / 86.84% / 38 trades`。
- `HYPE-EMA-X-V17`：已提升的 V15/V16 hybrid candidate。Source row：`HYBRID_score5_dist04_atr11` / `HYPE_EMA_X_V17`。Metrics：`+2910.74% / -17.79% / 90.91% / 33 trades`。
- `HYPE-EMA-X-V17.1`：已提升的 V17 sizing-enhanced candidate。Source row：`HYPE_EMA_X_V17__hq_scale=1p1`。Metrics：`+3861.48% / -19.44% / 90.91% / 33 trades`。

这些已提升版本的 canonical main ledger 是 `hype-ema-x-core-ledger.md`。旧 Cursor canvas 仅作为 legacy source 保留。

## 研究批次记录

- `research_hype_v15_effective_cross.py`：effective-cross quality probe；仅作为证据，不是已提升的 `HYPE-EMA-X-V15`。
- `research_hype_v16_indicator_expansion.py`：indicator-expansion probe。Early indicator entries 增加了交易数，但稀释了 V14 quality；OKX 没有确认足够稳定性。
- `research_hype_v17_trend_state_search.py`：覆盖 common indicator families 的 broad trend-state search。没有 candidate 同时满足 `50x return`、`<20% max drawdown` 和 `>80% win rate`。其中最佳低回撤行和高收益行现在已提升为 `HYPE-EMA-X-V15` 和 `HYPE-EMA-X-V16`。
- `research_hype_v17_hybrid_ablation.py`：围绕 `HYPE-EMA-X-V17` 的完整 single-parameter/single-module ablation。Baseline V17 仍是 signal-layer official version；最佳消融行为 `hq_scale=1.1`，指标为 `+3861.48% / -19.44% / 90.91% / 33 trades`，现记录为 `HYPE-EMA-X-V17.1`。

## 证据政策

使用 `hype-ema-x-core-ledger.md`、`legacy-canvas/` 和 archived script names 重建谱系。如果后续需要 polished spec，应基于这些证据文件在 `canonical-specs/` 下创建。
