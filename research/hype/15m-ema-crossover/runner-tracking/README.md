# HYPE-EMA-X Runner Tracking

本目录保存 `HYPE-EMA-Crossover` 各版本在 quant-runner dry-run / live 期间的 runner 观察报告。

- 命名：`hype-ema-x-runner-<YYYY-MM-DD>.md`。
- 每份报告必须写明：runner 配置（kind、mode、notional、杠杆/仓位系数）、观察窗口、成交笔数、实际费用/滑点 vs 回测假设、信号与指标对拍偏差、事件（重启、缺 K、拒单）以及 keep/stop/adjust 结论。
- core ledger 中 `forward-test required` 只能由本目录下的报告满足；口头描述不算证据。

## 当前跟踪对象

- `HYPE-EMA-X-V18`：quant-runner `hype_ema_x` dry-run 配置（`configs/dryrun.toml`，`dry_run_notional_usdt = 10`），状态 `dry-run / forward-test required`。尚无 runner 观察报告；首份报告缺失前不得升级到 `live`，也不得据此给出 `NO-GO`。
