# Decision Log — Binance-1D-Generic-MA7-Trend

## 2026-08-18 — 冻结 v0 后再看 market-cap universe 结果

决定：按 genericization audit 冻结对称 `SMA7/ATR7 reclaim + 0.02 ATR slope + 0.75 ATR hysteresis + 1.5 ATR hard/trailing`，删除 HYPE OAPP、short RSI、PEHC、forced reversal、max-hold、cooldown及多空不对称；本任务结果只裁决迁移，不允许回写参数。证据：[v0规格](specs/binance-1d-generic-ma7-trend-v0-spec.md) · [audit](diagnostics/binance-1d-generic-ma7-trend-v0-genericization-audit-2026-08-18.md) · [配置](configs/binance-1d-generic-ma7-trend-v0.json)。

## 2026-08-18 — current-top30 retrospective 完成；不 promotion

最终 22 币中 `12/22` 净 Sharpe > 0、横截面中位 Sharpe `0.239`；equal-risk 净 `+22.84% / Sharpe 0.582 / MDD -25.11%`。但 short 聚合 PF `0.966`、2025 与最近一年为负、1.2 ATR stop 扰动组合 Sharpe 仅 `0.112`。同一注册窗口 Generic v0 仅保留 V7.1 权威收益锚的 `13.18%`。决定：存在弱 generic core，但 `NO-GO for promotion / not live-ready`；v0 不改参数。证据：[最终报告](diagnostics/binance-1d-generic-ma7-trend-v0-top30-market-cap-backtest-2026-08-18.md) · [机器总结](artifacts/binance_1d_gma7t_v0_2026-08-18_summary.json)。
