# HYPE-EMA-TB Runner Tracking

本目录保存 `HYPE-EMA-Trend-Breakout` 各版本在线上 runner（dry-run / live）期间的 runner 观察报告。

- 命名：`hype-ema-tb-runner-<YYYY-MM-DD>.md`。
- 每份报告必须写明：runner 配置（部署、mode、notional、杠杆/仓位上限）、观察窗口、成交笔数、实际费用/滑点 vs 回测假设、信号与指标对拍偏差、事件（重启、缺 K、拒单）以及 keep/stop/adjust 结论。
- 线上开平仓/成交统计与回测对齐检查也必须落成本目录报告，CSV/JSON 证据放 `../artifacts/` 并从报告链接。
- core ledger 中 `forward-test required` 只能由本目录下的报告满足；口头描述不算证据。

## 当前跟踪对象

- 独立 hype-trend runner 是部署早于 quant-runner 与当前 handoff 约定的 legacy 外部实例。生产历史依次观测到 V35、V35.1，并于 `2026-07-22 04:09 UTC` 观测到 `HYPE-EMA-TB-V35.3` live mode；该外部配置事实不改变 V35.3 的研究主状态 `registered / not promoted / not live-ready`，属于必须确认授权与修复状态冲突的 blocker。
- 最新全量对账：[hype-ema-tb-v35-post-freeze-live-parity-2026-07-22.md](hype-ema-tb-v35-post-freeze-live-parity-2026-07-22.md)；V35 冻结后 11 笔实盘 entry 全匹配研究，自动退出无方向/原因偏差，主要偏差来自两次人工平仓、账本漏记和最终 K 数据问题。单笔最新亏损复盘见 [hype-ema-tb-v35-1-runner-2026-07-22.md](hype-ema-tb-v35-1-runner-2026-07-22.md)，此前逐笔对账见 [hype-ema-tb-v35-runner-2026-07-15.md](hype-ema-tb-v35-runner-2026-07-15.md)。
