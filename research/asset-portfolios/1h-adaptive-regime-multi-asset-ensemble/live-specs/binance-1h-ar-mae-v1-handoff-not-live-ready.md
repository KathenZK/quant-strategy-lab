---
spec_role: lab_handoff
strategy_id: BIN-1H-AR-MAE-V1
family_id: BIN-1H-AR-MAE
runner_kind: six_asset_ensemble
spec_status: active
peer_spec: crates/quant-runner/src/runner/strategies/six_asset_ensemble/BIN-1H-AR-MAE-V1-SPEC.md
manifest_instance_ids:
  - six-asset-ensemble-dry-run
approval_level_max: dry_run
---

# BIN-1H-AR-MAE-V1 Runner Handoff

状态：`dry-run only / NO-GO / not live-ready`。

- Exchange / market：Binance USD-M Futures。
- Assets / timeframe：六资产组合 / `1h`。
- Runner kind：`six_asset_ensemble`。
- Runtime：组合级严格单仓，自管多资产 K 线和 funding；不得按占位
  `BTC/USDT:USDT` 进入普通单标的共享行情组。
- 完整参数、数据窗口、费用、funding、closed-bar 和 replay 口径以
  [`BIN-1H-AR-MAE-V1-SPEC.md`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/six_asset_ensemble/BIN-1H-AR-MAE-V1-SPEC.md)
  为准。
- 现有逐笔 parity 只支持保持 dry-run；任何 live 提案都必须新开决策并修改
  manifest approval，当前 Runner 仍有代码级 live 拒绝。

```toml
name = "six-asset-ensemble-dry-run"
kind = "six_asset_ensemble"
mode = "dry_run"
symbol = "BTC/USDT:USDT"
timeframe = "1h"
state_dir = "/home/admin/quant-runner/state/six-asset-ensemble-dry-run"
warmup_bars = 1500
dry_run_notional_usdt = 10.0
```
