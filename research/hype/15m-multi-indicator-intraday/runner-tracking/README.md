# HYPE-15M-MII Runner Tracking

本目录保存 `HYPE-15M-Multi-Indicator-Intraday` 各版本在 quant-runner dry-run / live 期间的 runner 观察报告。

- 命名：`hype-15m-mii-runner-<YYYY-MM-DD>.md`。
- 每份报告必须写明：runner 配置（kind、mode、notional、杠杆/暴露）、观察窗口、成交笔数、实际费用/滑点 vs 回测假设、信号与指标对拍偏差、事件（重启、缺 K、拒单）以及 keep/stop/adjust 结论。
- core ledger 中 `forward-test required` 只能由本目录下的报告满足；口头描述不算证据。

## 当前跟踪对象

- `HYPE-15M-MII-V1.3`：已于 `2026-07-10T07:13:16Z` 被同一实例上的 V1.4A dry-run 替代；历史事件仍按 V1.3 identity 保留。
- `HYPE-15M-MII-V1.4A`：quant-runner `hype_mii` 当前 dry-run（实例仍名为 `hype-mii-dry-run`，内部 ledger identity 为 `HYPE-15M-MII-V1.4A`，`dry_run_notional_usdt = 10`，固定 `2.5x` 暴露）；旧实例从未开仓，因此沿用既有 state 目录。状态 `dry-run validation running / not live-ready`。首个 cycle 健康且无信号，后续逐笔证据见 `hype-15m-mii-runner-2026-07-10.md`。
- 2026-07-21 起共享 HYPE 15m 行情组 group halt，本实例停摆待复位；事件落档见
  [group halt 报告](../../15m-ema-crossover/runner-tracking/hype-ema-x-runner-2026-07-30-group-halt.md)。
