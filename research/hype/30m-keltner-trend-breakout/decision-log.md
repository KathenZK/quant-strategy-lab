# HYPE-30M-Keltner-Trend-Breakout Decision Log

## 2026-07-08：建线

结论：将同事外部规格 `K2-FQ-V2-ATRVT-OFF` 作为独立 `HYPE-30M-Keltner-Trend-Breakout` 研究线复现，不继承或提升任何既有 HYPE 家族状态。

证据：[README.md](README.md)，[scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)。

## 2026-07-08：回测复现

结论：独立回测与外部验收基本对账成功，但继续结算到 `2026-07-06 23:59 UTC` 后新增一笔亏损 time exit，单相位 6 bps/side 从外部验收等价的 `+7698.66% / 113 笔`降至 `+7516.88% / 114 笔`；策略保持 `explore / not promoted / not live-ready`。

证据：[research-notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](research-notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)。
