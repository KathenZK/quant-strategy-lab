# HYPE-EMA-TB Runner Tracking

本目录保存 `HYPE-EMA-Trend-Breakout` 各版本在线上 runner（dry-run / live）期间的 runner 观察报告。

- 命名：`hype-ema-tb-runner-<YYYY-MM-DD>.md`。
- 每份报告必须写明：runner 配置（部署、mode、notional、杠杆/仓位上限）、观察窗口、成交笔数、实际费用/滑点 vs 回测假设、信号与指标对拍偏差、事件（重启、缺 K、拒单）以及 keep/stop/adjust 结论。
- 线上开平仓/成交统计与回测对齐检查也必须落成本目录报告，CSV/JSON 证据放 `../artifacts/` 并从报告链接。
- core ledger 中 `forward-test required` 只能由本目录下的报告满足；口头描述不算证据。

## 当前跟踪对象

- `HYPE-EMA-TB-V35`：在独立 hype-trend live runner 上真实资金运行（部署早于 quant-runner 与当前 handoff 约定，属于 legacy 例外）。此前线上观察只散落在 decision log 与诊断报告中；后续线上表现结论、开平仓对齐统计应回流到本目录。V36-V40 均为 `registered / not promoted / not live-ready`，未进入任何 runner。
- 最新对账：[hype-ema-tb-v35-runner-2026-07-15.md](hype-ema-tb-v35-runner-2026-07-15.md)；最新空单与研究 SL 结果基本一致，上一笔多单已确认是人工平仓，但 runner 将其错标为 TP。
