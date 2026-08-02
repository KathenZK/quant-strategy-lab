# HYPE-CC Runner Tracking

本目录保存 `HYPE-Candle-Count-Reversal` 各版本在 quant-runner dry-run / live 期间的 runner 观察报告。

- 命名：`hype-cc-runner-<YYYY-MM-DD>.md`。
- 每份报告必须写明：runner 配置（kind、mode、notional、杠杆/仓位上限）、观察窗口、成交笔数、实际费用/滑点 vs 回测假设、信号与指标对拍偏差、事件（重启、缺 K、拒单）以及 keep/stop/adjust 结论。
- core ledger 中 `forward-test required` 只能由本目录下的报告满足；口头描述不算证据。

## 当前跟踪对象

- `HYPE-CC-V35`：quant-runner `hype_candle_count` dry-run 配置，状态
  `dry-run / forward-test required`。首份治理报告见
  [`hype-cc-runner-2026-07-10.md`](hype-cc-runner-2026-07-10.md)。
  历史 live underperformance、full-window parity 和真实 runtime lifecycle
  仍是 blocker；当前 dry-run 不等于 live 批准。
- 2026-07-21 起共享 HYPE 15m 行情组 group halt，本实例停摆待复位；事件落档见
  [group halt 报告](../../15m-ema-crossover/runner-tracking/hype-ema-x-runner-2026-07-30-group-halt.md)。
